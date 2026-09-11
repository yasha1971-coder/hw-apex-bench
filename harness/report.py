"""Generate the review table only from one complete, verified three-codec run."""
import json,pathlib,sys
from table_cells import unavailable, validate_tables
from configurations import CODECS, configuration, ACE_SHA
METRICS=("ratio","region_p50","region_p99","amplification")
ROOT=pathlib.Path(__file__).resolve().parents[1]
def validate(rows):
    index={}
    if not rows: raise ValueError("No measurements")
    core=[r for r in rows if r["codec"] in CODECS]
    if len({r["run_id"] for r in core})!=1 or len({r["benchmark_commit"] for r in core})!=1:
        raise ValueError("Mixed runs or benchmark commits")
    for r in core:
        if r["metric"] not in (*METRICS,"ratio_relative_to_bgzip","region_p50_relative_to_bgzip","region_p99_relative_to_bgzip"): continue
        k=(r["codec"],r["metric"])
        if k in index: raise ValueError("Duplicate metric")
        index[k]=r
    for c in CODECS:
        for m in METRICS:
            r=index[(c,m)]
            if not isinstance(r["value"],(int,float)) or not __import__("math").isfinite(r["value"]) or r["value"]<=0:
                raise ValueError("Invalid measurement")
            if not r.get("commands"): raise ValueError("Missing command")
            if r["corpus"]["md5"]!="9465e0f0df6e2c6eb39729c39cee5465": raise ValueError("Wrong corpus")
            if m=="ratio":
                if r.get("full_restore")!="pass": raise ValueError("Restore not verified")
            elif r.get("correctness")!="pass": raise ValueError("Region not verified")
        for m in ("ratio","region_p50","region_p99"):
            r=index[(c,m+"_relative_to_bgzip")]
            if r["status"] not in ("pass","fail"): raise ValueError("Missing comparison verdict")
    if set(index)!={(c,m) for c in CODECS for m in (*METRICS,"ratio_relative_to_bgzip","region_p50_relative_to_bgzip","region_p99_relative_to_bgzip")}:
        raise ValueError("Unexpected or missing row")
    for r in rows:
        # Separate strict c(g) claims may intentionally use another pinned
        # revision/configuration. Their validator lives in independence.py.
        if r["codec"] not in CODECS:
            if r["metric"] == "independence_cost_strict_percent" or r.get("evidence_group") in ("zstd-frame-frontier","gpu-declared","cg-five-point-v1"):
                continue
            raise ValueError("Unexpected external codec row")
        if r["configuration"]!=configuration(r["codec"]): raise ValueError("Configuration mismatch")
        if r["versions"]["aceapex_sha"]!=ACE_SHA: raise ValueError("Wrong ACEAPEX revision")
        if r["metric"].startswith("region_") and r["protocol"]["protocol_version"]!="api-bytes-v3": raise ValueError("Wrong timer protocol")
    return index
def render(rows):
    ix=validate(rows)
    meta=rows[0]; v=meta["versions"]
    text=["# hw-apex-bench — Compressed Access Benchmark","",
          "Three codecs, four configurations. API-only byte regions; implemented axes and review boundary are below.",
          "",f"Run: {meta['run_id']}. Benchmark commit: {meta['benchmark_commit']}.",
          "",f"Corpus: chr1 hg38 FASTA, MD5 {meta['corpus']['md5']}.",
          "",f"libzstd: {v['libzstd']}; htslib: {v['htslib']}; bgzip: {v['bgzip']}.",
          f"C: {v['compiler_c']}; C++: {v['compiler_cxx']}.",
          f"ACEAPEX: {v['aceapex_sha']}; zstd reference implementation: {v['zstd_sha']}.",
          "",f"Machine: {meta['hardware']['platform']}; logical CPUs: {meta['hardware']['logical_cpus']}.",
          next((line.strip() for line in meta["hardware"].get("lscpu", "").splitlines() if line.startswith("Model name:")), "CPU model unavailable"),
          "Hardware details, parameters and commands accompany every measurement in results.jsonl.",
          "",
          __import__('axes').definitions(),
          "",
          "Coverage audit: [AXES_RESULTS.md](AXES_RESULTS.md). Recheck without measurements: `./run.sh --audit-axes`.",
          "",
          "| Configuration | Level | Encoder threads | Block/frame bytes | LIT bytes | FSE bytes |",
          "|---|---:|---:|---:|---:|---:|",
          "| bgzip+htslib | 6 | 1 | BGZF variable (<=65536 uncompressed) | n/a — no separate literal stream | n/a — no FSE stream |",
          "| zstd-seekable | 3 | 1 | 16384 | n/a — frame-owned literals | n/a — frame-owned entropy coding |",
          "| aceapex-interactive | 2 | 1 | 16384 | 65536 | 4096 |",
          "| aceapex-dense | 2 | 1 | 262144 | 1048576 | 32768 |",
          "",
          "| Codec / profile | block (bytes) | Ratio incl. indexes | Region p50 ms | Region p99 ms | Output amplification | GPU |",
          "|---|---:|---:|---:|---:|---:|---|"]
    for c in CODECS:
        text.append("| "+c+" | "+str(ix[c,"ratio"]["configuration"]["block"])+" | "+" | ".join(f"{ix[c,m]['value']:.6f}" for m in METRICS)+" | n/a — CPU run |")
    text+=["","Every timed operation reads the same 16,384 original-file bytes. No FASTA parsing is timed.",
           "Amplification A = sum_q(sum of bytes actually expanded by the decoder for query q) / sum_q(requested bytes) = decoded bytes / (200 × 16384).",
           "BGZF counts decompressed blocks, zstd counts reconstructed blocks within frames (including buffered output), and ACEAPEX counts only touched chunks in the literal, offset, length and command streams, not the complete streams. Repeated expansions count each time.",
           "BGZF block=65536 is its size ceiling; actual blocks may be shorter. An unaligned request can cross block and entropy-chunk boundaries. (64 + 3 × 4) / 16 = 4.75 describes exactly one chunk of each kind, not a constant for arbitrary offsets. See [the trace explanation](AMPLIFICATION.md).",
           "", "| Codec | block (bytes) | Ratio / bgzip >= 0.99 | p50 / bgzip <= 1 | p99 / bgzip <= 1 |",
           "|---|---:|---|---|---|"]
    for c in CODECS:
        cols=[]
        for m in ("ratio","region_p50","region_p99"):
            r=ix[c,m+"_relative_to_bgzip"]; cols.append(f"{r['value']:.4f} — {r['status'].upper()}")
        text.append("| "+c+" | "+str(ix[c,"ratio"]["configuration"]["block"])+" | "+" | ".join(cols)+" |")
    text += ["", "| Codec | Decoded bytes (numerator) | Requested bytes (denominator) | LIT / offset / length / command decoded bytes |", "|---|---:|---:|---|"]
    for c in CODECS:
        r=ix[c,"amplification"]
        if r["value"] != r["decoded_bytes_total"] / r["requested_bytes_total"]: raise ValueError("Amplification totals mismatch")
        streams=r.get("stream_decoded_bytes_total")
        if streams is not None and sum(streams)!=r["decoded_bytes_total"]: raise ValueError("Stream totals mismatch")
        text.append(f"| {c} | {r['decoded_bytes_total']} | {r['requested_bytes_total']} | {str(streams) if streams is not None else unavailable('no four-stream decomposition')} |")
    if meta.get("stage",1)>=2:
        from stage2_report import render_stage2
        extra, matrix=render_stage2(rows)
        text += ["",extra]
    if meta.get("stage",1)>=3:
        from independence import render_independence
        text += ["",render_independence(rows)]
    if meta.get("stage",1)>=4:
        from throughput import render_throughput
        text += ["",render_throughput(rows)]
    if meta.get("stage",1)>=5:
        from zstd_frontier import render_zstd_frontier
        from gpu import render_gpu
        text += ["",render_zstd_frontier(rows),"",render_gpu(rows)]
    if any(r.get("evidence_group") == "cg-five-point-v1" for r in rows):
        from cg_curve import render as render_cg
        text += ["", render_cg([r for r in rows if r.get("evidence_group") == "cg-five-point-v1"]).replace("# Density", "## Density", 1)]
    text+=["","These are descriptive comparisons against the same-machine baseline, not promises that any codec must win.",
           "A slower codec remains FAIL in this table; correctness failures abort report generation.",
           "",(ROOT/"METHOD.md").read_text()]
    rendered = "\n".join(text)+"\n"
    validate_tables(rendered)
    return rendered
if __name__=="__main__":
    rows=[json.loads(s) for s in (ROOT/"results.jsonl").read_text().splitlines() if s.strip()]
    result=render(rows)
    from axes import render_coverage as render_axes
    (ROOT/"AXES_RESULTS.md").write_text(render_axes(rows), encoding="utf-8")
    if rows[0].get("stage",1)>=2:
        from stage2_report import render_stage2
        _,matrix=render_stage2(rows)
        (ROOT/"BATCH_RESULTS.md").write_text(matrix)
    temp=ROOT/".work/README.pending.md"; temp.parent.mkdir(exist_ok=True); temp.write_text(result); temp.replace(ROOT/"README.md")
    print(f"Regenerated reports from {len(rows)} retained measurement rows.")
