"""Render only complete same-run batch and break-even measurements."""
import math
from configurations import CODECS
from access_profiles import PROFILES, SIZES

def render_stage2(rows):
    def one(codec, metric, profile=None, n=None, method=None):
        rr = [r for r in rows if r["codec"] == codec and r["metric"] == metric and
              (profile is None or r.get("access_profile") == profile) and (n is None or r.get("n") == n) and
              (method is None or r.get("method") == method)]
        if len(rr) != 1: raise ValueError("Missing/duplicate stage2 point: " + str((codec,metric,profile,n,method)))
        r = rr[0]
        if not math.isfinite(r["value"]) or r["value"] <= 0 or r.get("correctness") != "pass" or not r.get("commands"):
            raise ValueError("Invalid stage2 point")
        return r
    text = ["## Break-even", "", "Model: independent 16 KiB reads at their measured p50 versus one full library decode.",
            "Smallest integer N with N × p50 > full decode time; full time is the median of five verified decodes after one warmup.",
            "This is a derived intersection, not an observed batch crossover or a plateau-throughput measurement.", "",
            "| Codec/profile | block bytes | Full decode ms | Region p50 ms | Break-even N | Full decoder threads |",
            "|---|---:|---:|---:|---:|---|"]
    for c in CODECS:
        f = one(c, "full_decode_ms"); b = one(c, "break_even_n"); p = one(c, "region_p50")
        if b["value"] != math.floor(f["value"] / p["value"]) + 1: raise ValueError("Break-even mismatch")
        text.append(f"| {c} | {f['configuration']['block']} | {f['value']:.6f} | {p['value']:.6f} | {b['value']} | {f['thread_policy']} |")
    text += ["", "## Batch", "", "Identical raw-byte requests across codecs; every native batch answer matches the single-call result and original bytes.",
             "Three repetitions, median duration; loop/native order alternates. Native batch threads are requested explicitly.",
             "H_alpha counts request-start blocks (actual GZI boundaries for BGZF, declared frame/block boundaries otherwise). H_alpha_16k is also recorded.",
             "bgzip and zstd-seekable native batch: n/a (no native batch API in these adapters); their measured method is loop.",
             "All N=100/600/2000/5000 points are in [BATCH_RESULTS.md](BATCH_RESULTS.md). The fixed N=5000 view follows.", ""]
    header = ["| Codec/profile | block bytes | Access profile | method | N | H_alpha bits | Threads requested | ranges/s | / bgzip loop |",
              "|---|---:|---|---|---:|---:|---:|---:|---|"]
    full = ["# Batch results", "", "Generated from results.jsonl. All repetitions and trace hashes are retained in evidence.", "", *header]
    summary = [*header]
    for profile in PROFILES:
        for n in SIZES:
            for c in CODECS:
                for method in (("loop", "batch") if c.startswith("aceapex") else ("loop",)):
                    r = one(c, "batch_throughput", profile, n, method)
                    rel = one(c, "batch_throughput_relative_to_bgzip", profile, n, method)
                    base = one("bgzip+htslib", "batch_throughput", profile, n, "loop")
                    if rel["value"] != r["value"] / base["value"]: raise ValueError("Batch relation mismatch")
                    if rel["status"] != ("pass" if rel["value"] >= 1 else "fail"): raise ValueError("Batch verdict mismatch")
                    if not 0 <= r["H_alpha"] <= math.log2(n) + 1e-9: raise ValueError("Invalid entropy")
                    line = f"| {c} | {r['configuration']['block']} | {profile} | {method} | {n} | {r['H_alpha']:.6f} | {r['threads_requested']} | {r['value']:.3f} | {rel['value']:.3f} {rel['status'].upper()} |"
                    full.append(line)
                    if n == 5000: summary.append(line)
                if c.startswith("aceapex"):
                    r = one(c, "batch_speedup_over_loop", profile, n, "batch/loop")
                    if r["status"] != ("pass" if r["value"] >= 1 else "fail"): raise ValueError("Paired speedup verdict mismatch")
    text += summary
    text += ["", "The full matrix keeps native batch and loop visible separately; a failed speed relation remains FAIL.",
             "The prior EPYC 9V74 4.78× result remains unchanged in [historical evidence](evidence/audit-20260909/FAILS.md).",
             "", "| Historical machine | Reported batch/loop | Evidence status |",
             "|---|---:|---|", "| EPYC 9V74 | 4.78× | measured, preserved original log; below its upstream 5× predicate |",
             "| EPYC 4344P | 13.3× | declared by user; matching command/configuration/receipt unavailable here |",
             "", "These historical points use another protocol and are not inputs to current pass/fail.",
             "The old parse checks without numpy are interpreted as skipped (missing dependency); the original FAIL text is preserved.",
             "", "Stop for review here. c(g), plateau throughput and the subsequent three-machine run remain deferred.",
             "See [batch protocol and upstream attribution](BATCH_METHOD.md).", ""]
    return "\n".join(text), "\n".join(full) + "\n"
