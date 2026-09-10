"""Validate and import owner-supplied GPU evidence without upgrading it to measured."""
import json, math, pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1]
GPU_SHA="606f6fc7600c803116ac1a73346e72b5c2162a80"
CHR1_MD5="9465e0f0df6e2c6eb39729c39cee5465"

def _prepare(block):
    return [
      f"env ACEAPEX_BS={block} ./aceapex_depth c --in chr1.fa --out /tmp/chr1-{block}.aet --threads 8",
      f"env ACEAPEX_BS={block} ./aceapex_depth d --in /tmp/chr1-{block}.aet --out /tmp/chr1-{block}.restore"
    ]

def add_gpu_declarations(rows,meta):
    src=json.loads((ROOT/"gpu-results.declared.json").read_text())
    if src["status"]!="declared" or src["aceapex_sha"]!=GPU_SHA or src["corpus"]["md5"]!=CHR1_MD5:
        raise ValueError("GPU declaration provenance mismatch")
    common={"evidence_group":"gpu-declared","codec":"aceapex-gpu","status":"declared",
      "run_id":"owner-declared-2026-09-10","benchmark_commit":meta["benchmark_commit"],
      "aceapex_sha":GPU_SHA,"g":src["g"],"corpus":src["corpus"],"software":src["software"],
      "correctness":"pass","correctness_text":"MATCHES OK",
      "source":src["source"],"timing_boundary":"device-resident GPU decoder as declared by source; raw pod receipt unavailable"}
    for p in src["full_decode"]:
        if p["block_bytes"] not in (4096,8192,16384) or p["gb_s"]<=0: raise ValueError("invalid GPU full-decode point")
        d=src["devices"][p["device"]]
        command=f"./e2e_pipe streams.bin chr1.fa {src['g']} 0 {p['blocks']}"
        row=dict(common,metric="gpu_full_decode_gb_s",value=p["gb_s"],unit="GB/s",
          device=d,block_bytes=p["block_bytes"],blocks=p["blocks"],commands=_prepare(p["block_bytes"])+[command],
          stream_md5=src["stream_md5_16k"] if p["block_bytes"]==16384 else None,
          stream_md5_status="supplied" if p["block_bytes"]==16384 else "n/a: per-point stream hash not supplied")
        if "wall_ms" in p: row["wall_ms"]=p["wall_ms"]
        rows.append(row)
    for p in src["seek"]:
        d=src["devices"][p["device"]]
        cmd=f"./e2e_seek streams.bin chr1.fa {src['g']} {p['start_block']} {p['count']}"
        row=dict(common,metric="gpu_region_seek_observation",value=p.get("observed_us"),unit="us",device=d,
          block_bytes=p["block_bytes"],start_block=p["start_block"],count=p["count"],commands=_prepare(p["block_bytes"])+[cmd],
          stream_md5=src["stream_md5_16k"],stream_md5_status="supplied",statistic="single supplied observation; not p50/p99")
        if "min_us" in p: row.update(min_us=p["min_us"],max_us=p["max_us"],spread_percent=p["spread_percent"])
        rows.append(row)
    for p in src["composition_scan"]:
        d=src["devices"][p["device"]]
        rows.append(dict(common,metric="gpu_composition_scan_speedup",value=p["speedup"],unit="scan/sequential",
          status="pass" if p["speedup"]>=1 else "fail",predicate=">=1",device=d,block_bytes=p["block_bytes"],blocks=p["blocks"],
          commands=_prepare(p["block_bytes"])+[f"./scan_bench streams.bin 0 {p['blocks']}"],
          stream_md5=src["stream_md5_16k"],stream_md5_status="supplied"))
    for codec in ("bgzip+htslib","zstd-seekable"):
        rows.append(dict(common,evidence_group="gpu-declared",codec=codec+"-gpu",metric="gpu_full_decode_gb_s",
          value=None,unit="GB/s",status="n/a",reason="no GPU decoder in benchmark adapter",block_bytes=None,
          commands=["n/a: no GPU decoder in benchmark adapter"],correctness="n/a"))
    return rows

def _gpu_rows(rows): return [r for r in rows if r.get("evidence_group")=="gpu-declared"]

def render_gpu(rows):
    rr=_gpu_rows(rows)
    if not rr: raise ValueError("missing GPU evidence")
    full=[r for r in rr if r["metric"]=="gpu_full_decode_gb_s"]
    for r in rr:
        if not r.get("commands") or r.get("status") not in ("declared","pass","fail","n/a"):
            raise ValueError("invalid GPU row")
        if r["codec"]=="aceapex-gpu":
            if not r.get("block_bytes") or r["aceapex_sha"]!=GPU_SHA or r["corpus"]["md5"]!=CHR1_MD5:
                raise ValueError("GPU row lacks block/provenance")
            if r["correctness"]!="pass": raise ValueError("GPU correctness missing")
    out=["## GPU — separately declared device-resident path","",
      "These points are owner-supplied declarations, not measurements made by this runner. They use ACEAPEX `606f6fc`, G=16, chr1 MD5 `9465e0f0df6e2c6eb39729c39cee5465`, driver 580.178.04 and CUDA 12.4.131; every published point names its block size and reports `MATCHES OK`. Exact raw pod logs were not supplied, so no row is promoted to `measured`.","",
      "| Codec | GPU | VRAM | block bytes | blocks | Full decode GB/s | wall ms | streams.bin MD5 | status |",
      "|---|---|---:|---:|---:|---:|---:|---|---|"]
    for r in full:
        if r["value"] is None:
            out.append(f"| {r['codec'].removesuffix('-gpu')} | n/a | n/a | n/a | n/a | n/a | n/a | n/a | {r['reason']} |")
        else:
            out.append(f"| ACEAPEX | {r['device']['name']} | {r['device']['vram_gb']} GB | {r['block_bytes']} | {r['blocks']} | {r['value']:.1f} | {r.get('wall_ms','n/a')} | {r.get('stream_md5') or r['stream_md5_status']} | declared |")
    out += ["","The same GPU and corpus change materially with block size: H100 reports 179.8 GB/s at 4 KiB and 128.0 GB/s at 16 KiB; RTX reports 112.8 GB/s at 8 KiB and 99.2 GB/s at 16 KiB. These are supplied observations, not a universal optimum claim.","",
      "| GPU | block bytes | start block | count | seek observation | statistic |",
      "|---|---:|---:|---:|---|---|"]
    for r in rr:
        if r["metric"]!="gpu_region_seek_observation": continue
        obs=f"{r['min_us']}–{r['max_us']} us (spread {r['spread_percent']}%)" if "min_us" in r else f"{r['value']:.0f} us"
        out.append(f"| {r['device']['name']} | {r['block_bytes']} | {r['start_block']} | {r['count']} | {obs} | {r['statistic']} |")
    out += ["","No p50/p99 is inferred from the supplied seek range.","",
      "| GPU | block bytes | blocks | composition scan / sequential | verdict |",
      "|---|---:|---:|---:|---|"]
    for r in rr:
        if r["metric"]=="gpu_composition_scan_speedup":
            out.append(f"| {r['device']['name']} | {r['block_bytes']} | {r['blocks']} | {r['value']:.2f}× | {r['status'].upper()} |")
    out += ["","The RTX 0.87× result is retained as FAIL: composition scan lost. H100 won at the matched 15,499-block point.","",
      "The CPU table now supports a precise statement: ACEAPEX dense is the densest configuration, while ACEAPEX interactive has the fastest plateau-qualified full decode. Both ACEAPEX profiles lose encode throughput to zstd-seekable and lose the single-region p50 comparison. GPU rows are separate and do not establish a cross-codec GPU ranking.","",
      "Not published as headline rows: the old 172 GB/s and 0.36 ms values; the FASTQ result without corpus URL/MD5; plateau samples without their concatenation commands; composition/capacity points without an unambiguous block/input mapping.","",
      "Stop for review before merge."]
    return "\n".join(out)
