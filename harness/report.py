"""Generate the review table only from one complete, verified three-codec run."""
import json,pathlib,sys
CODECS=("bgzip+htslib","zstd-seekable","aceapex")
METRICS=("ratio","region_p50","region_p99","amplification")
ROOT=pathlib.Path(__file__).resolve().parents[1]
def validate(rows):
    index={}
    if not rows: raise ValueError("No measurements")
    if len({r["run_id"] for r in rows})!=1 or len({r["benchmark_commit"] for r in rows})!=1:
        raise ValueError("Mixed runs or benchmark commits")
    for r in rows:
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
    return index
def render(rows):
    ix=validate(rows)
    meta=rows[0]; v=meta["versions"]
    text=["# hw-apex-bench — Compressed Access Benchmark","",
          "Stage 1: first three-codec table, ready for review. Later axes remain deferred.",
          "",f"Run: {meta['run_id']}. Benchmark commit: {meta['benchmark_commit']}.",
          "",f"Corpus: chr1 hg38 FASTA, MD5 {meta['corpus']['md5']}.",
          "",f"libzstd: {v['libzstd']}; htslib: {v['htslib']}; bgzip: {v['bgzip']}.",
          f"C: {v['compiler_c']}; C++: {v['compiler_cxx']}.",
          f"ACEAPEX: {v['aceapex_sha']}; zstd reference implementation: {v['zstd_sha']}.",
          "",f"Machine: {meta['hardware']['platform']}; logical CPUs: {meta['hardware']['logical_cpus']}.",
          "Hardware details, parameters and commands accompany every measurement in results.jsonl.",
          "",
          "| Codec | Ratio incl. indexes | Region p50 ms | Region p99 ms | Output amplification | GPU |",
          "|---|---:|---:|---:|---:|---|"]
    for c in CODECS:
        text.append("| "+c+" | "+" | ".join(f"{ix[c,m]['value']:.6f}" for m in METRICS)+" | n/a |")
    text+=["","Amplification is reconstructed **FASTA output bytes / requested sequence bytes**.",
           "It excludes intermediate entropy buffers and is not total memory traffic.",
           "BGZF and zstd use decoder-output counters in a separate pass; ACEAPEX uses the exact block span derived from its pinned source and archive header.",
           "", "| Codec | Ratio / bgzip >= 0.99 | p50 / bgzip <= 1 | p99 / bgzip <= 1 |",
           "|---|---|---|---|"]
    for c in CODECS:
        cols=[]
        for m in ("ratio","region_p50","region_p99"):
            r=ix[c,m+"_relative_to_bgzip"]; cols.append(f"{r['value']:.4f} — {r['status'].upper()}")
        text.append("| "+c+" | "+" | ".join(cols)+" |")
    text+=["","These are descriptive comparisons against the same-machine baseline, not promises that any codec must win.",
           "A slower codec remains FAIL in this table; correctness failures abort report generation.",
           "",(ROOT/"METHOD.md").read_text()]
    return "\n".join(text)+"\n"
if __name__=="__main__":
    rows=[json.loads(s) for s in (ROOT/"results.jsonl").read_text().splitlines() if s.strip()]
    result=render(rows)
    temp=ROOT/".work/README.pending.md"; temp.write_text(result); temp.replace(ROOT/"README.md")
    print(result)
