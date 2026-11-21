#!/usr/bin/env python3
"""HWAB-NBD-1: table and predictions from the probe output (summary.json of harness/nbd_xz_probe.py).
Per g the median over the 5 repeats of each per-repeat statistic (p50 / p99 over the 1 000 requests of a series).
Prediction 1: series A, p50 cold / g in [5, 9] ms/MiB for every g. Prediction 2: p50(64M) / p50(1M) in [40, 80].
Usage: summarize.py <probe dir> <recompress_sizes.txt> <raw bytes> -> table.md, predictions.json (in the probe dir)"""
import json, statistics as st, sys
from pathlib import Path

d = Path(sys.argv[1]); s = json.load(open(d / "summary.json")); raw = int(sys.argv[3])
sizes = {int(l.split()[0]): int(l.split()[1]) for l in open(sys.argv[2]) if l.strip()}
med = lambda rows, k: st.median(r[k] for r in rows if r.get(k) is not None)
lines = ["| g | archive B | ratio | A p50 cold ms | A p99 ms | A p50/g ms/MiB | B p50 ms | C p50 warm ms | peak RSS MiB |", "|---|---|---|---|---|---|---|---|---|"]
p1 = {}; rows_out = {}
for key, rows in sorted(s["rows"].items(), key=lambda kv: (kv[0] == "file", int(kv[0][1:-1]) if kv[0] != "file" else 0)):
    a50, a99, b50, c50, rss = (med(rows, k) for k in ("A_p50_ms", "A_p99_ms", "B_p50_ms", "C_p50_ms", "peak_rss_kib"))
    if key == "file":
        lines.append(f"| nbdkit file (raw) | {raw} | 1 | {a50:.4f} | {a99:.4f} | — | {b50:.4f} | {c50:.4f} | {rss/1024:.1f} |"); rows_out[key] = dict(A_p50=a50, B_p50=b50, C_p50=c50, rss_kib=rss); continue
    g = int(key[1:-1]); per = a50 / g; p1[g] = per
    lines.append(f"| {g}M | {sizes[g]} | {raw/sizes[g]:.3f} | {a50:.3f} | {a99:.3f} | {per:.2f} | {b50:.3f} | {c50:.4f} | {rss/1024:.1f} |")
    rows_out[key] = dict(g=g, archive_bytes=sizes[g], ratio=raw / sizes[g], A_p50=a50, A_p99=a99, A_p50_per_mib=per, B_p50=b50, C_p50=c50, rss_kib=rss)
r2 = st.median(r["A_p50_ms"] for r in s["rows"]["g64M"]) / st.median(r["A_p50_ms"] for r in s["rows"]["g1M"])
pred = {"prediction_1": {"range_ms_per_mib": [5, 9], "values": p1, "hit": all(5 <= v <= 9 for v in p1.values()),
                         "in_range": [g for g, v in p1.items() if 5 <= v <= 9], "out_of_range": [g for g, v in p1.items() if not 5 <= v <= 9]},
        "prediction_2": {"range": [40, 80], "value": r2, "hit": 40 <= r2 <= 80}, "mismatches": s["mismatches"], "rows": rows_out}
pred["killer"] = not (pred["prediction_1"]["hit"] and pred["prediction_2"]["hit"])
(d / "table.md").write_text("\n".join(lines) + "\n"); json.dump(pred, open(d / "predictions.json", "w"), indent=1)
print("\n".join(lines)); print(json.dumps({k: v for k, v in pred.items() if k != "rows"}, indent=1))
