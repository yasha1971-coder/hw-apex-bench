#!/usr/bin/env python3
"""HWAB-NBD-1 gates (before any comparison with the prediction): the xz rows g = 1 MiB and 16 MiB of
`./run.sh --pick --g 1M,16M --region-size 4K` on silesia_tar and enwik8 against HWAB-ZEEK-1 r4K
(evidence/hwab-zeek-1-20261107/r4K): ratio equal, archive SHA-256 equal, p50 within max(10 %, 2 x spread)
(gate-c-tolerance.json of ZEEK-1: 10 % on every row). Usage: gates_nbd.py <run dir> <zeek-1 r4K dir> -> gates.json"""
import json, sys
from pathlib import Path

run, ref = Path(sys.argv[1]), Path(sys.argv[2]); TOL = 0.10; out = {"rows": [], "pass": True}
for corpus in ("silesia.tar", "enwik8"):
    new = {(r["codec"], r["g"]): r for r in json.load(open(run / corpus / "pick.json"))["rows"]}
    old = {(r["codec"], r["g"]): r for r in json.load(open(ref / corpus / "pick.json"))["rows"]}
    for g in (1 << 20, 16 << 20):
        n, o = new.get(("xz", g)), old.get(("xz", g))
        if not n or not o or n.get("status") != "measured":
            out["rows"].append({"corpus": corpus, "g": g, "pass": False, "why": "row missing or not measured"}); out["pass"] = False; continue
        sha = lambda r: sorted(a["sha256"] for a in r["evidence"]["ratio"]["archive_artifacts"].values())
        d = n["p50_ms"] / o["p50_ms"] - 1
        row = {"corpus": corpus, "g": g, "ratio_new": n["ratio"], "ratio_ref": o["ratio"], "sha_equal": sha(n) == sha(o),
               "p50_new_ms": n["p50_ms"], "p50_ref_ms": o["p50_ms"], "p50_delta": d}
        row["pass"] = n["ratio"] == o["ratio"] and row["sha_equal"] and abs(d) <= TOL
        out["rows"].append(row); out["pass"] &= row["pass"]
json.dump(out, open(run / "gates.json", "w"), indent=1)
for r in out["rows"]: print(r)
print("GATES", "PASS" if out["pass"] else "FAIL"); sys.exit(0 if out["pass"] else 1)
