#!/usr/bin/env python3
import argparse,json,math,statistics,struct
from pathlib import Path
def rows(p): return [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]
def nearest(xs,q): y=sorted(xs); return y[max(0,math.ceil(q*len(y))-1)]
def perfv(p,event):
    for line in Path(p).read_text().splitlines():
        parts=[x.strip() for x in line.split(';')]
        if not any(x.startswith(event) for x in parts): continue
        raw=parts[0].replace(',','')
        return None if raw.startswith('<') else float(raw)
    return None
def med(files,event):
    v=[perfv(x,event) for x in files]
    assert v and all(x is not None for x in v),event
    return statistics.median(v)
def geom(p):
    d=Path(p).read_bytes()
    magic,ver,orig,bs,nb,xx,zl,zo,zn,zc=struct.unpack_from('<8sIQII8s4Q',d,0)
    assert magic==b'ACEPX2\0\0' and ver==2 and bs==16384
    off=68+nb*64; zlit=d[off:off+zl]
    h=struct.unpack_from('<Q',zlit,0)[0]
    assert h&(1<<62) and h&(1<<61)
    raw=h&~((1<<62)|(1<<61)|(1<<60))
    chunk=struct.unpack_from('<Q',zlit,8)[0]
    return {"archive_bytes":len(d),"blocks":nb,"literal_raw_bytes":raw,
            "literal_chunk_bytes":chunk,"literal_chunks":(raw+chunk-1)//chunk}
def one(name,root,arc,receipt,queries):
    root=Path(root); lat=rows(root/"latency.jsonl"); al=rows(root/"alloc.jsonl")
    ms=[float(x["latency_ms"]) for x in lat]
    calls=[x["malloc"]+x["calloc"]+x["realloc"] for x in al]
    frees=[x["free"] for x in al]
    b=[x["malloc_bytes"]+x["calloc_bytes"]+x["realloc_bytes"] for x in al]
    at=[(x.get("alloc_ns",0)+x.get("free_ns",0))/1000 for x in al]
    pd=root/"perf"
    def files(kind,n): return sorted(pd.glob(f'{kind}-{n}-*.csv'))
    perf={}
    for event in ("cycles","instructions"):
        r0,rn,s0,sn=med(files("real",0),event),med(files("real",queries),event),med(files("stub",0),event),med(files("stub",queries),event)
        perf[event]=((rn-r0)-(sn-s0))/queries
    rec=json.loads(Path(receipt).read_text())
    return {"name":name,"ratio":rec["ratio"],"archive_sha256":rec["archive_sha256"],
            "p50_us":nearest(ms,.5)*1000,"p99_us":nearest(ms,.99)*1000,
            "temp_bytes_p50":nearest(b,.5),"alloc_calls_p50":nearest(calls,.5),
            "free_calls_p50":nearest(frees,.5),"allocator_us_p50":nearest(at,.5),
            "instructions":perf["instructions"],"cycles":perf["cycles"],
            "ipc":perf["instructions"]/perf["cycles"],"geometry":geom(arc)}
ap=argparse.ArgumentParser()
for x in ("root64","root16","archive64","archive16","receipt64","receipt16"): ap.add_argument("--"+x,required=True)
ap.add_argument("--queries",type=int,default=20000);ap.add_argument("--out",type=Path,required=True)
a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
x=one("lit64",a.root64,a.archive64,a.receipt64,a.queries)
y=one("lit16",a.root16,a.archive16,a.receipt16,a.queries)
r={"schema":"chr1-literal-layer-v1","lit64":x,"lit16":y,
   "delta":{"instructions":y["instructions"]-x["instructions"],
            "instruction_reduction_pct":(x["instructions"]-y["instructions"])/x["instructions"]*100,
            "cycles":y["cycles"]-x["cycles"],
            "cycle_reduction_pct":(x["cycles"]-y["cycles"])/x["cycles"]*100,
            "p50_us":y["p50_us"]-x["p50_us"],
            "p50_reduction_pct":(x["p50_us"]-y["p50_us"])/x["p50_us"]*100,
            "temp_bytes":y["temp_bytes_p50"]-x["temp_bytes_p50"],
            "archive_bytes":y["geometry"]["archive_bytes"]-x["geometry"]["archive_bytes"],
            "ratio_pct":(y["ratio"]/x["ratio"]-1)*100}}
(a.out/"literal-layer.json").write_text(json.dumps(r,indent=2)+"\n")
lines=["# chr1 literal chunk 64 KiB → 16 KiB","",
"| diagnostic | 64 KiB | 16 KiB | delta |","|---|---:|---:|---:|",
f'| ratio | {x["ratio"]:.6f} | {y["ratio"]:.6f} | {r["delta"]["ratio_pct"]:+.3f}% |',
f'| archive bytes | {x["geometry"]["archive_bytes"]} | {y["geometry"]["archive_bytes"]} | {r["delta"]["archive_bytes"]:+d} |',
f'| p50 | {x["p50_us"]:.3f} us | {y["p50_us"]:.3f} us | {r["delta"]["p50_us"]:+.3f} us ({-r["delta"]["p50_reduction_pct"]:+.2f}%) |',
f'| temp requested p50 | {x["temp_bytes_p50"]} B | {y["temp_bytes_p50"]} B | {r["delta"]["temp_bytes"]:+d} B |',
f'| instructions/request | {x["instructions"]:.0f} | {y["instructions"]:.0f} | {r["delta"]["instructions"]:+.0f} ({-r["delta"]["instruction_reduction_pct"]:+.2f}%) |',
f'| cycles/request | {x["cycles"]:.0f} | {y["cycles"]:.0f} | {r["delta"]["cycles"]:+.0f} ({-r["delta"]["cycle_reduction_pct"]:+.2f}%) |',
f'| literal chunks | {x["geometry"]["literal_chunks"]} | {y["geometry"]["literal_chunks"]} | - |',
"",
"Only literal chunk size changes; g=R=16 KiB and FSE_CHUNK=4 KiB are fixed.",
"Production ACE source is unchanged; the 16 KiB archive uses a private encoder copy whose env gate permits 16 KiB."
]
(a.out/"literal-layer.md").write_text("\n".join(lines)+"\n")
print((a.out/"literal-layer.md").read_text())
