#!/usr/bin/env python3
"""B: hash-bound window-law job for refrel3 and foreign formats.

Usage (only the explicit run command measures):
  python3 -m tools.verdict_refrel3 prepare --root INPUT --manifest cohort.json --out prepared
  python3 -m tools.verdict_refrel3 run --root INPUT --plan plan.json --out EVIDENCE
  python3 -m tools.verdict_refrel3 verify --root EVIDENCE

Preparation generates shared requests before opening any compressed archive.
Run is ace-core-only and refuses existing output. Unit tests inject readers and
artificial clocks into evaluate_variant; their output is labelled synthetic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time

from tools.axis3_window_engine import Window, SEED, sample_coordinates, freeze_windows, run_windows
from tools.window_law import diagnose, VERDICT_WINDOWS
from review.axis3.verdict_data import (
    DOMAIN, HASH, FastaTruth, capture_silence, checked_file, file_ref, load_json,
    normalize_full, resolve, sha256_file, verify_protocol, write_json, write_jsonl,
)
from review.axis3.verdict_readers import FOREIGN_FAMILIES, FAMILIES, open_reader

REPO = Path(__file__).resolve().parents[1]
REQUESTS = 10000
DEFAULT_SWEEP = [1 << k for k in range(17)]
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}")


def checked_windows(windows):
    if (not isinstance(windows, list) or not windows or
            any(type(w) is not int or not 1 <= w <= 65536 for w in windows) or
            windows != sorted(set(windows)) or not {1, *VERDICT_WINDOWS}.issubset(windows)):
        raise ValueError("freeze a sorted unique W list including 1,1024,8192,65536 in 1..65536")
    return windows


def prepare(root, manifest_name, out_name, windows=None, *, repo=REPO):
    """No clock and no codec use: only source truth, coordinates and hashes."""
    root = Path(root).resolve(strict=True)
    protocol = verify_protocol(repo)
    manifest_path = resolve(root, manifest_name)
    manifest = load_json(manifest_path)
    rows = manifest["assemblies"]
    if manifest.get("schema") != "window-law-corpus-v1" or not rows:
        raise ValueError("ordered window-law-corpus-v1 manifest required")
    sources = []
    for row in rows:
        if not isinstance(row.get("source_url"), str) or not row["source_url"]:
            raise ValueError("retain the real source URL in the cohort manifest")
        if not HASH.fullmatch(row.get("source_sha256", "")):
            raise ValueError("retain the compressed/source-object SHA in the cohort manifest")
        sources.append((row["assembly_id"], checked_file(root, row["fasta"])))
    out_path = Path(out_name)
    if out_path.is_absolute() or ".." in out_path.parts:
        raise ValueError("prepared directory must be root-relative")
    out = root / out_path
    if not out.parent.resolve().is_relative_to(root):
        raise ValueError("prepared directory escapes root")
    out.mkdir(parents=True, exist_ok=False)
    ws = checked_windows(windows if windows is not None else DEFAULT_SWEEP)
    truth = FastaTruth(sources)
    try:
        corpus = {"schema": "window-law-prepared-corpus-v1", "assemblies": []}
        for source in rows:
            aid = source["assembly_id"]
            contigs = [{"contig_id": c, "length": n} for a, c, n in truth.contigs() if a == aid]
            corpus["assemblies"].append({**source, "contigs": contigs, **truth.full_identity(aid)})
        write_json(out / "corpus.json", corpus)
        refs = []
        for w in ws:
            requests = freeze_windows(sample_coordinates(truth.contigs(), w, count=REQUESTS, seed=SEED), truth)
            path = out / f"w{w}.jsonl"
            write_jsonl(path, ({"id": r.id, "assembly_id": r.assembly, "contig_id": r.contig,
                               "start0": r.start0, "end0": r.end0, "sha256": r.sha256} for r in requests))
            refs.append({"W_bytes": w, "file": file_ref(root, path)})
        result = {"schema": "window-law-prepared-v1", "protocol_sha256": protocol["sha256"],
                  "manifest": file_ref(root, manifest_path), "corpus": file_ref(root, out / "corpus.json"),
                  "windows_bytes": ws, "samples_per_window": REQUESTS, "seed": SEED,
                  "prng": "python.random.Random/MT19937/randrange", "requests": refs,
                  "prepared_by": "tools.verdict_refrel3.prepare", "domain": DOMAIN}
        write_json(out / "prepared.json", result)
        return file_ref(root, out / "prepared.json")
    finally:
        truth.close()


def read_requests(root, prepared, corpus):
    ws = checked_windows(prepared["windows_bytes"])
    if (prepared.get("samples_per_window") != REQUESTS or prepared.get("seed") != SEED
            or prepared.get("domain") != DOMAIN or prepared.get("prng") != "python.random.Random/MT19937/randrange"
            or [x["W_bytes"] for x in prepared["requests"]] != ws):
        raise ValueError("prepared request/seed/domain contract mismatch")
    contigs = [(a["assembly_id"], c["contig_id"], c["length"])
               for a in corpus["assemblies"] for c in a["contigs"]]
    result = {}
    for item in prepared["requests"]:
        rows = []
        with checked_file(root, item["file"]).open(encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                rows.append(Window(d["id"], d["assembly_id"], d["contig_id"], d["start0"], d["end0"], d["sha256"]))
        expected = sample_coordinates(contigs, item["W_bytes"], count=REQUESTS, seed=SEED)
        if [(r.id, r.assembly, r.contig, r.start0, r.end0) for r in rows] != expected:
            raise ValueError("request list differs from frozen PRNG/seed/corpus/W")
        if any(not HASH.fullmatch(r.sha256) for r in rows):
            raise ValueError("invalid per-window truth SHA")
        result[item["W_bytes"]] = rows
    return result


class FullDecodeMismatch(ValueError):
    def __init__(self, message, checks):
        super().__init__(message)
        self.checks = checks


def full_check(outputs, corpus):
    """Outside timer. No length-only or codec-success-only acceptance."""
    if not isinstance(outputs, list) or [x[0] for x in outputs] != [a["assembly_id"] for a in corpus["assemblies"]]:
        raise ValueError("full decode must cover every assembly in frozen order")
    checks = []
    for (aid, domain, data), assembly in zip(outputs, corpus["assemblies"]):
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise ValueError("native full output must be bytes, not a decoded-file path")
        h = hashlib.sha256()
        count = 0
        for chunk in normalize_full(domain, data, assembly["contigs"]):
            count += len(chunk)
            h.update(chunk)
        got = h.hexdigest()
        row = {"assembly_id": aid, "native_domain": domain, "native_bytes": len(data),
               "canonical_bytes": count, "observed_sha256": got,
               "expected_sha256": assembly["canonical_sha256"]}
        if count != assembly["canonical_bytes"] or got != assembly["canonical_sha256"]:
            raise FullDecodeMismatch("full decode differs from canonical source SHA: " + aid, checks + [row])
        checks.append(row)
    return checks


def run_dq_series(reader, corpus, *, clock=time.perf_counter_ns, warmups=3, repeats=9, sink=None):
    if reader.scope != "cpu-in-process" or reader.decoder_threads != 1:
        raise ValueError("D_Q requires one-thread persistent CPU library scope")
    if type(warmups) is not int or type(repeats) is not int or warmups < 0 or repeats <= 0:
        raise ValueError("invalid full-decode repetitions")
    times = []
    total = sum(a["canonical_bytes"] for a in corpus["assemblies"])
    if total <= 0:
        raise ValueError("empty canonical corpus")
    for i in range(warmups + repeats):
        row = {"iteration": i, "kind": "warmup" if i < warmups else "measured", "status": "FAILED"}
        try:
            start = clock()
            outputs = reader.decode_native()
            stop = clock()
            if type(start) is not int or type(stop) is not int or stop <= start:
                raise ValueError("invalid D_Q clock interval")
            row.update(elapsed_ns=stop - start, checks=full_check(outputs, corpus), status="PASS")
            # Verify each decode, including all warmups, before reusing buffers.
            del outputs
            if i >= warmups:
                times.append(stop - start)
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
            if isinstance(exc, FullDecodeMismatch):
                row["checks"] = exc.checks
            if sink is not None:
                sink(row)
            raise
        if sink is not None:
            sink(row)
    median_ns = statistics.median(times)
    rate = Fraction(total * 1000000000, 1) / median_ns
    return {"canonical_bytes": total, "warmups": warmups, "repeats": repeats,
            "raw_ns": times, "median_ns": median_ns, "min_ns": min(times), "max_ns": max(times),
            "D_Q_Bps": float(rate), "D_Q_exact": str(rate),
            "timed_boundary": reader.full_timing_boundary,
            "normalization_and_sha_outside_timer": True}


def evaluate_variant(spec, reader, corpus, requests, out, *, clock=time.perf_counter_ns,
                     expected_count=REQUESTS, kind="measured", warmups=3, repeats=9):
    """The same orchestration is tested with artificial clocks; no synthetic codec rates are imported."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    result = {"id": spec["id"], "family": spec["family"], "variant": spec["variant"],
              "kind": kind, "data_status": "FAILED", "verdict": "FAIL", "error": None,
              "Q_bytes": None, "Q_exact": None, "geometry": [], "dq": None, "observations": [], "raw_logs": [],
              "build": reader.build}
    ws = checked_windows(sorted(requests))
    try:
        if kind not in ("measured", "synthetic") or (kind == "measured" and expected_count != REQUESTS):
            raise ValueError("official runs require exactly 10,000 requests")
        q = Fraction(reader.q)
        if q <= 0:
            raise ValueError("canonical Q must be positive")
        result["Q_bytes"] = float(q)
        result["Q_exact"] = str(q)
        result["geometry"] = reader.geometry
        dq_path = out / "dq.jsonl"
        with dq_path.open("x", encoding="utf-8") as log:
            def record(row):
                row["evidence_kind"] = kind
                log.write(json.dumps(row, sort_keys=True, allow_nan=False) + chr(10))
                log.flush()
            dq = run_dq_series(reader, corpus, clock=clock, warmups=warmups, repeats=repeats, sink=record)
        dq["raw_log"] = file_ref(out, dq_path)
        result["dq"] = dq
        rate = Fraction(dq["D_Q_exact"])
        probe_p50 = None
        observations = []
        for w in ws:
            rs = requests[w]
            if any(r.length != w for r in rs):
                raise ValueError("request bucket W differs from coordinates")
            summary, raw = run_windows(reader, rs, expected_count=expected_count, calibration=w == 1,
                                       diagnostic=w != 1 and w not in VERDICT_WINDOWS, clock=clock)
            raw_path = out / f"w{w}.jsonl"
            for record in raw:
                record["evidence_kind"] = kind
            write_jsonl(raw_path, raw)
            ref = file_ref(out, raw_path)
            result["raw_logs"].append(ref)
            if summary["status"] != "PASS":
                raise ValueError("canonical window judge failed at W=" + str(w))
            # The frozen protocol uses nearest-rank p50, not a second median convention.
            p50_ns = sorted(r["elapsed_ns"] for r in raw)[(50 * len(raw) + 99) // 100 - 1]
            p50 = Fraction(p50_ns, 1000)
            if w == 1:
                probe_p50 = p50
            row = diagnose(rate, w, q, p50, probe_p50)
            row.update(samples=len(raw), verified=len(raw), measured_p50_us=float(p50),
                       p95_us=summary["p95_us"], p99_us=summary["p99_us"], raw_log=ref)
            observations.append(row)
        eligible = [r for r in observations if r["verdict_eligible"]]
        if {r["W_bytes"] for r in eligible} != VERDICT_WINDOWS:
            raise ValueError("all verdict windows must be present exactly once")
        result.update(data_status="PASS", observations=observations,
                      verdict="PASS" if all(r["verdict"] == "PASS" for r in eligible) else "FAIL")
    except Exception as exc:
        # Timing diagnostics stay in raw logs, never in a valid failed row.
        result.update(data_status="FAILED", verdict="FAIL", error=f"{type(exc).__name__}: {exc}",
                      dq=None, observations=[], Q_bytes=None, Q_exact=None, geometry=[])
    result["raw_logs"] = [file_ref(out, p) for p in sorted(out.glob("*.jsonl"))]
    return result


def aggregate(entries):
    foreign = sorted({e["family"] for e in entries
                      if e["family"] in FOREIGN_FAMILIES and e["data_status"] == "PASS"})
    refrel_entries = [e for e in entries if e["family"] == "refrel3"]
    refrel = {e["variant"]: e for e in refrel_entries}
    both = {"q4k", "q16k"}.issubset(refrel)
    coverage = len(foreign) >= 4 and both
    valid = all(e["data_status"] == "PASS" for e in entries)
    refrel_verdict = "PASS" if both and all(e["verdict"] == "PASS" and e["data_status"] == "PASS"
                                           for e in refrel_entries) else "FAIL"
    return {"data_status": "PASS" if valid else "FAILED", "coverage_complete": coverage,
            "foreign_families": foreign, "foreign_format_count": len(foreign),
            "refrel3_verdict": refrel_verdict,
            "comparison_verdict": "PASS" if coverage and valid and all(e["verdict"] == "PASS" for e in entries) else "FAIL"}


def collect_file_refs(value):
    if isinstance(value, dict):
        if set(value) == {"path", "bytes", "sha256"}:
            yield value
        else:
            for v in value.values():
                yield from collect_file_refs(v)
    elif isinstance(value, list):
        for v in value:
            yield from collect_file_refs(v)


def load_plan(root, plan_name, repo=REPO):
    path = resolve(root, plan_name)
    plan = load_json(path)
    if (plan.get("schema") != "window-law-plan-v1" or plan.get("scope") != "cpu-in-process"
            or plan.get("threads") != 1 or plan.get("seed") != SEED
            or plan.get("dq_warmups") != 3 or plan.get("dq_repeats") != 9
            or not ID.fullmatch(plan.get("run_id", ""))):
        raise ValueError("wrong plan schema/scope/thread/seed/3+9 repetition contract")
    checked_file(root, plan["runbook"])
    prepared = load_json(checked_file(root, plan["prepared"]))
    protocol = verify_protocol(repo)
    if prepared.get("protocol_sha256") != protocol["sha256"]:
        raise ValueError("prepared requests belong to another protocol SHA")
    checked_file(root, prepared["manifest"])
    corpus = load_json(checked_file(root, prepared["corpus"]))
    ids = [a["assembly_id"] for a in corpus["assemblies"]]
    if len(ids) != len(set(ids)) or len(ids) != 4:
        raise ValueError("initial official cohort must contain four distinct assemblies")
    for a in corpus["assemblies"]:
        checked_file(root, a["fasta"])
        if type(a["canonical_bytes"]) is not int or a["canonical_bytes"] <= 0 or not HASH.fullmatch(a["canonical_sha256"]):
            raise ValueError("invalid canonical corpus identity")
        if sum(c["length"] for c in a["contigs"]) != a["canonical_bytes"]:
            raise ValueError("contig lengths differ from canonical assembly size")
    variants = plan["variants"]
    names = [v["id"] for v in variants]
    if not variants or len(names) != len(set(names)) or any(not ID.fullmatch(x) for x in names):
        raise ValueError("variant IDs must be distinct safe filenames")
    if any(v["family"] not in FAMILIES for v in variants):
        raise ValueError("unknown codec family")
    if not {"q4k", "q16k"}.issubset({v["variant"] for v in variants if v["family"] == "refrel3"}):
        raise ValueError("plan must include both refrel3 Q variants")
    if len({v["family"] for v in variants} & FOREIGN_FAMILIES) < 4:
        raise ValueError("plan needs at least four distinct foreign codec families")
    # BGZF default/matched-g are two configurations, not two independent formats.
    if {v["variant"] for v in variants if v["family"] == "bgzf"} != {"default", "matched-g"}:
        raise ValueError("BGZF comparison must retain both default and matched-g")
    return plan, prepared, corpus, read_requests(root, prepared, corpus), protocol


def verify_result(root):
    """Validate schema, all output hashes, exact row arithmetic, and aggregate scope."""
    import jsonschema
    root = Path(root)
    result = load_json(root / "results.json")
    frozen = verify_protocol(root / "contract")
    if frozen["sha256"] != result["protocol_sha256"]:
        raise ValueError("retained protocol differs from result digest")
    schema = load_json(REPO / "schemas/window-law-verdict-v1.schema.json")
    jsonschema.Draft202012Validator(schema).validate(result)
    checked_windows(result["windows_bytes"])
    if len({e["id"] for e in result["entries"]}) != len(result["entries"]):
        raise ValueError("duplicate variant result ID")
    for ref in result["silence_logs"]:
        snapshot = load_json(checked_file(root, ref))
        if result["kind"] == "measured" and snapshot["status"] != "PASS":
            # Failed preflight is permitted only when no valid row relies on it.
            name = ref["path"].removeprefix("silence-").removesuffix(".json")
            if name == "initial" or any(e["id"] == name and e["data_status"] == "PASS" for e in result["entries"]):
                raise ValueError("valid result despite failed preflight")
    for entry in result["entries"]:
        if entry["kind"] != result["kind"]:
            raise ValueError("mixed synthetic/measured evidence")
        directory = root / entry["id"]
        for ref in entry["raw_logs"]:
            checked_file(directory, ref)
        if entry["data_status"] != "PASS":
            continue
        if entry["Q_bytes"] != float(Fraction(entry["Q_exact"])):
            raise ValueError("displayed Q differs from exact geometry Q")
        dq = entry["dq"]
        checked_file(directory, dq["raw_log"])
        dq_rows = [json.loads(x) for x in (directory / dq["raw_log"]["path"]).read_text().splitlines()]
        if (len(dq_rows) != dq["warmups"] + dq["repeats"] or
                any(r["status"] != "PASS" or r.get("evidence_kind") != result["kind"] for r in dq_rows)):
            raise ValueError("invalid D_Q raw run records")
        times = [r["elapsed_ns"] for r in dq_rows if r["kind"] == "measured"]
        if times != dq["raw_ns"] or len(times) != dq["repeats"]:
            raise ValueError("D_Q raw samples differ from summary")
        for r in dq_rows:
            if any(c["observed_sha256"] != c["expected_sha256"] for c in r["checks"]):
                raise ValueError("full-decode SHA failure in raw record")
            if sum(c["canonical_bytes"] for c in r["checks"]) != dq["canonical_bytes"]:
                raise ValueError("D_Q canonical byte count changed")
        med = statistics.median(times)
        rate = Fraction(dq["canonical_bytes"] * 1000000000, 1) / med
        if (med != dq["median_ns"] or min(times) != dq["min_ns"] or max(times) != dq["max_ns"]
                or Fraction(dq["D_Q_exact"]) != rate or dq["D_Q_Bps"] != float(rate)):
            raise ValueError("D_Q summary was not generated from raw samples")
        observations = entry["observations"]
        if [o["W_bytes"] for o in observations] != result["windows_bytes"]:
            raise ValueError("missing, duplicate or reordered W observations")
        probe_rows = [json.loads(x) for x in (directory / observations[0]["raw_log"]["path"]).read_text().splitlines()]
        probe_times = sorted(r["elapsed_ns"] for r in probe_rows)
        probe = Fraction(probe_times[(50 * len(probe_times) + 99) // 100 - 1], 1000)
        for row in observations:
            checked_file(directory, row["raw_log"])
            raw = [json.loads(x) for x in (directory / row["raw_log"]["path"]).read_text().splitlines()]
            if len(raw) != result["samples_per_window"] or len(raw) != row["samples"] or row["verified"] != len(raw):
                raise ValueError("sample count mismatch")
            seen = set()
            for r in raw:
                c = r["canonical"]
                if (r["status"] != "PASS" or r.get("evidence_kind") != result["kind"] or r["observed_sha256"] != r["expected_sha256"]
                        or r["returned_bytes"] != row["W_bytes"] or c["end0"] - c["start0"] != row["W_bytes"]
                        or c.get("convention") != "0-based-half-open" or c["start0"] < 0
                        or r["elapsed_ns"] <= 0 or r["request_id"] in seen or not r.get("translated")):
                    raise ValueError("invalid window judge record")
                seen.add(r["request_id"])
            if seen != set(range(len(raw))):
                raise ValueError("window request IDs are not the frozen complete set")
            times_w = sorted(r["elapsed_ns"] for r in raw)
            p50 = Fraction(times_w[(50 * len(raw) + 99) // 100 - 1], 1000)
            for p, key in ((95, "p95_us"), (99, "p99_us")):
                if row[key] != times_w[(p * len(raw) + 99) // 100 - 1] / 1000:
                    raise ValueError("quantile not from raw timings")
            if float(p50) != row["measured_p50_us"]:
                raise ValueError("p50 not from raw timings")
            calc = diagnose(rate, row["W_bytes"], entry["Q_exact"], p50, probe)
            for key, value in calc.items():
                if row[key] != value:
                    raise ValueError("model value differs from independent raw calculation: " + key)
        valid = all(o["verdict"] == "PASS" for o in observations if o["verdict_eligible"])
        if entry["verdict"] != ("PASS" if valid else "FAIL"):
            raise ValueError("format verdict contradicts verdict-window set")
    if aggregate(result["entries"]) != result["summary"]:
        raise ValueError("aggregate verdict/coverage differs from entries")
    return result


def render_table(result):
    lines = ["# Window-law verdict", "", "Evidence kind: " + result["kind"],
             "Primary B; secondary A never controls verdict. W=1 is calibration only.", "",
             "| Format | Variant | W (B) | Role | Q (B) | D_Q (B/s) | c0 (us) | A (us) | B (us) | p50 (us) | Error B (%) | Verdict |",
             "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for e in result["entries"]:
        if e["data_status"] != "PASS":
            error = str(e["error"]).replace("|", "/").replace(chr(10), " ")
            lines.append(f"| {e['family']} | {e['variant']} | — | FAILED: {error} | — | — | — | — | — | — | — | FAIL |")
            continue
        for r in e["observations"]:
            lines.append("| " + " | ".join(map(str, (e["family"], e["variant"], r["W_bytes"], r["window_role"],
                         e["Q_bytes"], r["D_Q_Bps"], r["c0_us"], r["secondary_predicted_p50_us"],
                         r["primary_predicted_p50_us"], r["measured_p50_us"], r["primary_signed_error_percent"], r["verdict"]))) + " |")
    lines += ["", "## Where the model fails", ""]
    failed = [e["id"] for e in result["entries"] if e["verdict"] != "PASS"]
    lines.append(", ".join(failed) if failed else "No failing model row in this run; this is not a compression/performance ranking.")
    lines += ["", "## Provenance", "", "Protocol SHA-256: `" + result["protocol_sha256"] + "`."]
    for e in result["entries"]:
        for f in e["raw_logs"]:
            lines.append(f"- `{e['id']}/{f['path']}` SHA-256 `{f['sha256']}`")
    lines += ["", "Coverage and verdict: `" + json.dumps(result["summary"], sort_keys=True) + "`", ""]
    return chr(10).join(lines)


def harness_identity(repo):
    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True,
                              text=True, capture_output=True).stdout.strip()
    if git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("official run requires a clean tracked harness tree")
    return {"commit": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}")}


def run(root, plan_name, out, *, repo=REPO):
    """Only this explicit entry point uses the machine clock/native libraries."""
    root = Path(root).resolve(strict=True)
    harness = harness_identity(repo)
    plan, prepared, corpus, requests, protocol = load_plan(root, plan_name, repo)
    if plan.get("harness_commit") != harness["commit"]:
        raise ValueError("plan must freeze the actual applied harness commit")
    plan_ref = file_ref(root, resolve(root, plan_name))
    immutable_refs = [plan_ref, *list(collect_file_refs([plan, prepared, corpus]))]
    output = Path(out).resolve()
    output.mkdir(parents=True, exist_ok=False)
    contract = output / "contract/review/axis3"
    contract.mkdir(parents=True)
    for name in ("PROTOCOL_AXIS3.md", "PROTOCOL_FREEZE.json"):
        (contract / name).write_bytes((Path(repo) / "review/axis3" / name).read_bytes())
    initial = capture_silence(output)
    write_json(output / "silence-initial.json", initial)
    if initial["status"] != "PASS":
        raise ValueError("ace-core silence gate refused; retain silence-initial.json")
    entries = []
    for spec in plan["variants"]:
        reader = None
        try:
            # One preflight authorizes this bounded sequential job. Rechecking
            # load after our own CPU work would mistake our run for foreign load.
            # No claim of continuous host quiescence is made by a one-second gate.
            reader = open_reader(root, spec, corpus)
            entry = evaluate_variant(spec, reader, corpus, requests, output / spec["id"],
                                     warmups=plan["dq_warmups"], repeats=plan["dq_repeats"])
            entry["Q_exact"] = str(reader.q) if entry["data_status"] == "PASS" else None
        except Exception as exc:
            entry = {"id": spec["id"], "family": spec["family"], "variant": spec["variant"], "kind": "measured",
                     "data_status": "FAILED", "verdict": "FAIL", "error": f"{type(exc).__name__}: {exc}",
                     "Q_bytes": None, "Q_exact": None, "geometry": [], "dq": None, "observations": [],
                     "raw_logs": [], "build": {}}
        finally:
            if reader is not None:
                reader.close()
        entries.append(entry)
    immutable_error = None
    try:
        for ref in immutable_refs:
            checked_file(root, ref)
    except Exception as exc:
        immutable_error = str(exc)
        # Do not silently publish numbers after detecting an input mutation.
        for e in entries:
            e.update(data_status="FAILED", verdict="FAIL", error="input changed: " + immutable_error,
                     Q_bytes=None, Q_exact=None, geometry=[], dq=None, observations=[])
    result = {"schema": "window-law-verdict-v1", "run_id": plan["run_id"], "kind": "measured",
              "protocol_sha256": protocol["sha256"], "protocol_version": "1.1", "domain": DOMAIN,
              "scope": "cpu-in-process", "threads": 1, "seed": SEED, "harness": harness,
              "plan": plan_ref, "prepared": plan["prepared"],
              "input_references": immutable_refs,
              "windows_bytes": prepared["windows_bytes"], "samples_per_window": REQUESTS,
              "entries": entries, "summary": aggregate(entries), "immutable_input_error": immutable_error,
              "silence_logs": [file_ref(output, p) for p in sorted(output.glob("silence-*.json"))]}
    write_json(output / "results.json", result)
    verified = verify_result(output)
    (output / "table.md").write_text(render_table(verified), encoding="utf-8")
    refs = [file_ref(output, p) for p in sorted(output.rglob("*")) if p.is_file()]
    (output / "SHA256SUMS").write_text("".join(f"{r['sha256']}  {r['path']}" + chr(10) for r in refs))
    return verified


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--windows", default=",".join(map(str, DEFAULT_SWEEP)))
    p = sub.add_parser("run")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--plan", required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("verify")
    p.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.operation == "prepare":
            ref = prepare(args.root, args.manifest, args.out, [int(x) for x in args.windows.split(",")])
            print(json.dumps({"prepared": ref}, sort_keys=True))
            return 0
        if args.operation == "run":
            result = run(args.root, args.plan, args.out)
            print(json.dumps(result["summary"], sort_keys=True))
            return 0 if result["summary"]["comparison_verdict"] == "PASS" else 1
        verify_result(args.root)
        print("VERDICT_EVIDENCE_PASS")
        return 0
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, f"VERDICT_JOB_ERROR: {type(exc).__name__}: {exc}" + chr(10))


if __name__ == "__main__":
    sys.exit(main())
