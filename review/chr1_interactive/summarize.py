#!/usr/bin/env python3
import argparse, json, math, statistics, struct
from pathlib import Path

def rows(p):
    return [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]
def nearest(xs,q):
    y=sorted(xs); return y[max(0,math.ceil(q*len(y))-1)]
def perf_value(p,event):
    for line in Path(p).read_text().splitlines():
        parts=[x.strip() for x in line.split(';')]
        if not any(x.startswith(event) for x in parts): continue
        raw=parts[0].replace(',','')
        if raw.startswith('<'): return None
        return float(raw)
    return None
def med_perf(files,event):
    vals=[perf_value(x,event) for x in files]
    if not vals or any(v is None for v in vals): return None
    return statistics.median(vals)

def archive_geometry(path,fse_chunk):
    data=Path(path).read_bytes()
    h=struct.unpack_from('<8sIQII8s4Q',data,0)
    magic,version,orig,block,count,xx,*zs=h
    assert magic==b'ACEPX2\0\0' and version==2 and block==16384
    off=68+count*64
    streams=[]
    for z in zs:
        streams.append(data[off:off+z]); off+=z
    assert off==len(data)
    zlit,zoff,zlen,zcmd=streams
    lh=struct.unpack_from('<Q',zlit,0)[0]
    assert lh&(1<<62), "literal entropy stream expected"
    literal_chunked=bool(lh&(1<<61))
    lit_orig=lh&~((1<<62)|(1<<61)|(1<<60))
    lit_chunk=struct.unpack_from('<Q',zlit,8)[0] if literal_chunked else (lit_orig+3)//4
    lit_chunks=(lit_orig+lit_chunk-1)//lit_chunk if lit_chunk else 0

    def fse(stream):
        raw=struct.unpack_from('<Q',stream,0)[0] & ~(1<<63)
        nc=(raw+fse_chunk-1)//fse_chunk
        assert len(stream)>=8+nc*8
        pos=8+nc*8
        cs=struct.unpack_from('<'+'Q'*nc,stream,8) if nc else ()
        for i,c in enumerate(cs):
            chunk_raw=min(fse_chunk,raw-i*fse_chunk)
            pos += chunk_raw if c>>63 else (c & ~(1<<63))
        assert pos==len(stream),(raw,nc,pos,len(stream))
        return {"raw_bytes":raw,"chunks":nc,"chunk_bytes":fse_chunk}
    return {
        "original_bytes":orig,"block_bytes":block,"blocks":count,
        "archive_bytes":len(data),
        "literal":{"raw_bytes":lit_orig,"chunks":lit_chunks,"chunk_bytes":lit_chunk},
        "offsets":fse(zoff),"lengths":fse(zlen),"commands":fse(zcmd)
    }

ap=argparse.ArgumentParser()
ap.add_argument("--latency",required=True)
ap.add_argument("--alloc",required=True)
ap.add_argument("--amplification",required=True)
ap.add_argument("--perf-dir",type=Path,required=True)
ap.add_argument("--archive",required=True)
ap.add_argument("--receipt",required=True)
ap.add_argument("--default-baseline",required=True)
ap.add_argument("--queries",type=int,default=20000)
ap.add_argument("--out",type=Path,required=True)
a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)

lat=rows(a.latency); assert len(lat)==200 and all(x["verified"] for x in lat)
amp=rows(a.amplification); assert len(amp)==200 and all(x["verified"] for x in amp)
al=rows(a.alloc); assert len(al)==200
default=json.loads(Path(a.default_baseline).read_text())
receipt=json.loads(Path(a.receipt).read_text())
geom=archive_geometry(a.archive,4096)

ms=[float(x["latency_ms"]) for x in lat]
decoded=sum(int(x["decoded_bytes"]) for x in amp)
requested=sum(int(x["requested_bytes"]) for x in amp)
calls=[x["malloc"]+x["calloc"]+x["realloc"] for x in al]
frees=[x["free"] for x in al]
bytes_alloc=[x["malloc_bytes"]+x["calloc_bytes"]+x["realloc_bytes"] for x in al]
alloc_time=[(x.get("alloc_ns",0)+x.get("free_ns",0))/1000 for x in al]

def files(kind,n): return sorted(a.perf_dir.glob(f'{kind}-{n}-*.csv'))
perf={}
for event in ("cycles","instructions"):
    r0=med_perf(files("real",0),event); rn=med_perf(files("real",a.queries),event)
    s0=med_perf(files("stub",0),event); sn=med_perf(files("stub",a.queries),event)
    assert None not in (r0,rn,s0,sn), event
    perf[event]={
        "real_query_loop_per_query":(rn-r0)/a.queries,
        "stub_loop_per_query":(sn-s0)/a.queries,
        "hc_region_adjusted_per_query":((rn-r0)-(sn-s0))/a.queries
    }

instr=perf["instructions"]["hc_region_adjusted_per_query"]
cycles=perf["cycles"]["hc_region_adjusted_per_query"]
dinstr=instr-default["perf_stat"]["instructions_per_hc_region"]
result={
  "schema":"chr1-interactive-profile-baseline-v1",
  "configuration":receipt,
  "full_hc_region":{
    "samples":200,"warmups":12,"request_bytes":16384,
    "p50_us":nearest(ms,.5)*1000,"p99_us":nearest(ms,.99)*1000,
    "min_us":min(ms)*1000,"max_us":max(ms)*1000
  },
  "temporary_allocations":{
    "p50_requested_bytes":nearest(bytes_alloc,.5),
    "p99_requested_bytes":nearest(bytes_alloc,.99),
    "p50_alloc_like_calls":nearest(calls,.5),
    "p50_free_calls":nearest(frees,.5),
    "allocator_libc_time_p50_us":nearest(alloc_time,.5)
  },
  "chunk_geometry":geom,
  "random_access_amplification":{
    "decoded_bytes":decoded,"requested_bytes":requested,
    "ra":decoded/requested,
    "definition":"entropy decoder output bytes / requested bytes, same 200-query trace"
  },
  "perf_stat":{
    "queries":a.queries,"repeats":5,
    "instructions_per_hc_region":instr,
    "cycles_per_hc_region":cycles,
    "ipc":instr/cycles
  },
  "default_control":{
    "default_archive_bytes":default["configuration"]["archive_bytes"],
    "default_ratio":default["configuration"]["ratio"],
    "default_p50_us":default["current_hc_region"]["p50_us"],
    "default_temp_bytes_p50":default["isolated_components"]["allocator_calls_instrumented"]["p50_requested_alloc_bytes"],
    "default_fse_chunk_bytes":default["archive_geometry"]["fse_chunk_bytes"],
    "default_instructions_per_hc_region":default["perf_stat"]["instructions_per_hc_region"],
    "instruction_delta":dinstr,
    "instruction_reduction_pct":-dinstr/default["perf_stat"]["instructions_per_hc_region"]*100,
    "p50_reduction_pct":(default["current_hc_region"]["p50_us"]-nearest(ms,.5)*1000)/default["current_hc_region"]["p50_us"]*100
  }
}
(a.out/"interactive-baseline.json").write_text(json.dumps(result,indent=2)+"\n")

lines=[
"# chr1 ACE interactive-profile baseline",
"",
"Same full hg38 chr1, same current public region API, g=R=16 KiB. Only entropy granularity changes to the documented interactive profile: LIT_CHUNK=64 KiB, FSE_CHUNK=4 KiB.",
"",
"| Diagnostic | Default | Interactive | Delta |",
"|---|---:|---:|---:|",
f'| archive bytes | {default["configuration"]["archive_bytes"]} | {geom["archive_bytes"]} | {geom["archive_bytes"]-default["configuration"]["archive_bytes"]:+d} |',
f'| complete ratio | {default["configuration"]["ratio"]:.6f} | {receipt["ratio"]:.6f} | {(receipt["ratio"]/default["configuration"]["ratio"]-1)*100:+.3f}% |',
f'| p50 | {default["current_hc_region"]["p50_us"]:.3f} us | {result["full_hc_region"]["p50_us"]:.3f} us | {-result["default_control"]["p50_reduction_pct"]:+.2f}% latency |',
f'| temp requested bytes p50 | {result["default_control"]["default_temp_bytes_p50"]} | {result["temporary_allocations"]["p50_requested_bytes"]} | {result["temporary_allocations"]["p50_requested_bytes"]-result["default_control"]["default_temp_bytes_p50"]:+d} B |',
f'| instructions / request | {result["default_control"]["default_instructions_per_hc_region"]:.0f} | {instr:.0f} | {dinstr:+.0f} ({-result["default_control"]["instruction_reduction_pct"]:+.2f}%) |',
f'| cycles / request | {default["perf_stat"]["cycles_per_hc_region"]:.0f} | {cycles:.0f} | {cycles-default["perf_stat"]["cycles_per_hc_region"]:+.0f} |',
f'| FSE chunk | {default["archive_geometry"]["fse_chunk_bytes"]} B | 4096 B | - |',
f'| literal chunk | 65536 B | {geom["literal"]["chunk_bytes"]} B | - |',
f'| RA amplification | n/a in default baseline | {result["random_access_amplification"]["ra"]:.6f}x | - |',
"",
f'Instruction reduction: **{result["default_control"]["instruction_reduction_pct"]:.2f}%**.',
f'Wall p50 reduction on this ARM runner class: **{result["default_control"]["p50_reduction_pct"]:.2f}%**.',
f'Interactive RA: **{result["random_access_amplification"]["ra"]:.6f}x**.',
"",
"Stop: no decoder or format optimization is part of this control."
]
(a.out/"interactive-baseline.md").write_text("\n".join(lines)+"\n")
print((a.out/"interactive-baseline.md").read_text())
