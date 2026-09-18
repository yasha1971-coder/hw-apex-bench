#!/usr/bin/env python3
import argparse, json, math, statistics
from pathlib import Path

def rows(p):
    return [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]
def nearest(xs,q):
    y=sorted(xs); return y[max(0,math.ceil(q*len(y))-1)]
def perf_value(p,event):
    for line in Path(p).read_text().splitlines():
        parts=[x.strip() for x in line.split(';')]
        name=next((x for x in parts if x.startswith(event)),None)
        if not name: continue
        raw=parts[0].replace(',','')
        if raw.startswith('<'): return None
        return float(raw)
    return None
def med_perf(files,event):
    vals=[perf_value(x,event) for x in files]
    if not vals or any(v is None for v in vals): return None
    return statistics.median(vals)

ap=argparse.ArgumentParser()
ap.add_argument("--latency",required=True)
ap.add_argument("--alloc",required=True)
ap.add_argument("--micro",required=True)
ap.add_argument("--perf-dir",type=Path,required=True)
ap.add_argument("--queries",type=int,default=20000)
ap.add_argument("--receipt",required=True)
ap.add_argument("--out",type=Path,required=True)
a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)

lat=rows(a.latency); assert len(lat)==200 and all(x["verified"] for x in lat)
ms=[float(x["latency_ms"]) for x in lat]
al=rows(a.alloc); assert len(al)==200
micro=json.loads(Path(a.micro).read_text())
receipt=json.loads(Path(a.receipt).read_text())

def files(kind,n): return sorted(a.perf_dir.glob(f'{kind}-{n}-*.csv'))
events=("cycles","instructions")
perf={}
available=True
for event in events:
    real0=med_perf(files("real",0),event)
    realn=med_perf(files("real",a.queries),event)
    stub0=med_perf(files("stub",0),event)
    stubn=med_perf(files("stub",a.queries),event)
    if None in (real0,realn,stub0,stubn):
        available=False
        perf[event]=None
        continue
    real_delta=(realn-real0)/a.queries
    stub_delta=(stubn-stub0)/a.queries
    perf[event]={"real_query_loop_per_query":real_delta,
                 "stub_loop_per_query":stub_delta,
                 "hc_region_adjusted_per_query":real_delta-stub_delta}

calls=[x["malloc"]+x["calloc"]+x["realloc"] for x in al]
frees=[x["free"] for x in al]
bytes_alloc=[x["malloc_bytes"]+x["calloc_bytes"]+x["realloc_bytes"] for x in al]
alloc_time=[(x.get("alloc_ns",0)+x.get("free_ns",0))/1000.0 for x in al]
clock_overheads=[x.get("clock_pair_overhead_ns",0) for x in al]

result={
 "schema":"chr1-region-cost-baseline-v1",
 "configuration":receipt,
 "full_hc_region":{
   "samples":200,"request_bytes":16384,
   "p50_us":nearest(ms,.50)*1000,
   "p99_us":nearest(ms,.99)*1000,
   "min_us":min(ms)*1000,"max_us":max(ms)*1000
 },
 "isolated_components":{
   "header_and_range_locate_us":micro["header_locate_us"],
   "linear_stream_index_scan_us":micro["linear_index_scan_us"],
   "allocator_calls_raw_us_p50":nearest(alloc_time,.50),
   "allocator_calls_raw_us_p99":nearest(alloc_time,.99),
   "note":"separate instrumented or isolated measurements; overlapping components, not additive decomposition"
 },
 "archive_geometry":{
   k:micro[k] for k in ("block_count","lit_chunks","off_chunks","len_chunks","cmd_chunks","fse_chunk_bytes")
 },
 "allocation_calls_inside_hc_region":{
   "p50_alloc_like_calls":nearest(calls,.50),
   "p99_alloc_like_calls":nearest(calls,.99),
   "p50_free_calls":nearest(frees,.50),
   "p99_free_calls":nearest(frees,.99),
   "p50_requested_alloc_bytes":nearest(bytes_alloc,.50),
   "p99_requested_alloc_bytes":nearest(bytes_alloc,.99),
   "clock_pair_overhead_ns":statistics.median(clock_overheads),
   "note":"LD_PRELOAD counter/timer enabled only around hc_region; separate from uninstrumented latency run"
 },
 "perf_stat":{
   "available":available,
   "events":perf,
   "reason":None if available else "hardware cycles/instructions not exposed by this hosted runner PMU"
 },
 "derived":{
   "ipc_adjusted":(perf["instructions"]["hc_region_adjusted_per_query"]/perf["cycles"]["hc_region_adjusted_per_query"])
      if available and perf["cycles"]["hc_region_adjusted_per_query"]>0 else None
 }
}
(a.out/"baseline.json").write_text(json.dumps(result,indent=2)+"\n")

def fmt(v,spec=".3f"):
    return format(v,spec) if v is not None else "n/a"
pc=perf["cycles"]["hc_region_adjusted_per_query"] if available else None
pi=perf["instructions"]["hc_region_adjusted_per_query"] if available else None
lines=[
"# chr1 current ACE region-cost baseline","",
"Current API, before resident-context optimization. g=16 KiB, R=16 KiB, full hg38 chr1 archive.","",
"| Layer / diagnostic | Measured baseline |",
"|---|---:|",
f'| full current hc_region p50 | {result["full_hc_region"]["p50_us"]:.3f} us |',
f'| full current hc_region p99 | {result["full_hc_region"]["p99_us"]:.3f} us |',
f'| isolated header + range locate | {micro["header_locate_us"]:.3f} us |',
f'| isolated linear stream-index scan | {micro["linear_index_scan_us"]:.3f} us |',
f'| allocator calls, instrumented p50 | {result["isolated_components"]["allocator_calls_raw_us_p50"]:.3f} us |',
f'| allocations-like calls / request, p50 | {result["allocation_calls_inside_hc_region"]["p50_alloc_like_calls"]:.0f} |',
f'| free calls / request, p50 | {result["allocation_calls_inside_hc_region"]["p50_free_calls"]:.0f} |',
f'| requested allocation bytes / request, p50 | {result["allocation_calls_inside_hc_region"]["p50_requested_alloc_bytes"]:.0f} B |',
f'| perf instructions / hc_region (loop-adjusted) | {fmt(pi,".0f")} |',
f'| perf cycles / hc_region (loop-adjusted) | {fmt(pc,".0f")} |',
f'| adjusted IPC | {fmt(result["derived"]["ipc_adjusted"],".3f")} |',"",
"Isolated rows are directly measured but overlap work inside full hc_region; do not sum or subtract them to manufacture an unmeasured remainder.","",
f'Archive geometry: {micro["block_count"]} blocks; literal chunks {micro["lit_chunks"]}; FSE chunks off/len/cmd = {micro["off_chunks"]}/{micro["len_chunks"]}/{micro["cmd_chunks"]}; FSE chunk = {micro["fse_chunk_bytes"]} B.',
]
if not available:
    lines += ["","perf hardware events were requested and executed, but this hosted runner returned <not supported> for cycles and instructions. They remain n/a rather than being replaced by a surrogate counter."]
(a.out/"baseline.md").write_text("\n".join(lines)+"\n")
print((a.out/"baseline.md").read_text())
