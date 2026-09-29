#!/usr/bin/env python3
import argparse,hashlib,json,math,os,platform,random,struct,subprocess,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/"evidence/t2t-regions-20260916/manifest.json"
LEGAL=(4096,8192,16384,32768,65280)
CODECS=("ace-legacy","ace-v210","ace-open","bgzip")
LABELS={
  "ace-legacy":"ACEAPEX 1b13df3 interactive (legacy one-shot)",
  "ace-v210":"ACEAPEX v2.1.0 interactive (persistent C handle)",
  "ace-open":"ACEAPEX main open (persistent C handle)",
  "bgzip":"BGZF + htslib",
}
PINS={
  "ace-legacy":"1b13df34ac8e839dd3232b59bc59560d689a435a",
  "ace-v210":"50723533be48a8d9ed42e4b0f9e1f9106ef169b7",
  "ace-open":"ec3477877e7ed3f9792885a1a8beb26e48f4b717",
}

def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def run(cmd,**kw):
    subprocess.run([str(x) for x in cmd],check=True,**kw)

def percentile(xs,q):
    ys=sorted(xs)
    return ys[math.ceil(q*len(ys))-1]

def bgzf_isizes(data):
    out=[];p=0
    while p<len(data):
        if len(data)-p<26 or data[p:p+4]!=b"\x1f\x8b\x08\x04": raise AssertionError("bad BGZF")
        b=data[p+16]|(data[p+17]<<8);b+=1
        if b<26 or p+b>len(data): raise AssertionError("bad BGZF BSIZE")
        out.append(int.from_bytes(data[p+b-4:p+b],"little"));p+=b
    if p!=len(data) or not out or out[-1]!=0: raise AssertionError("missing BGZF EOF")
    return out

def env_for(codec,g):
    env={k:v for k,v in os.environ.items()
         if k not in {"ACEAPEX_BS","LIT_CHUNK","FSE_CHUNK","MIN_MATCH","AX_PROFILE","AX_TOK","AX_LIT"}}
    if codec!="bgzip":
        env.update(ACEAPEX_BS=str(g),LIT_CHUNK="65536",FSE_CHUNK="4096")
        if codec=="ace-open": env["AX_PROFILE"]="open"
    return env

def context_for(native,codec):
    return native/(codec+"-context.so") if codec!="bgzip" else native/"bgzf-context.so"

def encode(native,codec,inp,arc,g):
    env=env_for(codec,g)
    if codec=="bgzip":
        cmd=[native/"bgzf-encode-g",inp,arc,str(g)]
    else:
        cmd=[native/codec,"c","--in",inp,"--out",arc,"--threads","8","--level","2"]
    run(cmd,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=900)
    return cmd,env

def verify_archive(measure,lib,arc,inp,side,env):
    cp=subprocess.run([str(measure),str(lib),str(arc),str(inp),"decode",side,"1"],
                      env=env,text=True,capture_output=True,check=True,timeout=300)
    rows=[json.loads(x) for x in cp.stdout.splitlines() if x.strip()]
    if len(rows)!=1 or rows[0].get("verified") is not True:
        raise AssertionError("full restore gate failed")

def matched_g(a):
    manifest=json.loads(MANIFEST.read_text())
    windows=manifest["windows"]
    for w in windows:
        p=a.inputs/w["file"]
        if p.stat().st_size!=2097152 or sha(p)!=w["input_sha256"]:
            raise AssertionError("frozen T2T window mismatch "+w["file"])

    measure=a.native/"native_measure"
    out=a.out/"matched-g";out.mkdir(parents=True,exist_ok=False)
    rows=[]
    all_raw=out/"samples.jsonl"
    with all_raw.open("w") as sample_out:
      for g in LEGAL:
        point=out/f"g{g}";(point/"archives").mkdir(parents=True)
        configs=[]
        for wi,w in enumerate(windows):
            inp=(a.inputs/w["file"]).resolve()
            for codec in CODECS:
                arc=(point/"archives"/f"{wi:02d}-{codec}.archive").resolve()
                cmd,env=encode(a.native,codec,inp,arc,g)
                side=""
                stored=arc.stat().st_size
                geometry={"granularity":g}
                if codec=="bgzip":
                    gzi=Path(str(arc)+".gzi");side=str(gzi.resolve())
                    z=bgzf_isizes(arc.read_bytes());data=z[:-1]
                    if any(x>g for x in data) or any(x!=g for x in data[:-1]): raise AssertionError("BGZF g mismatch")
                    rem=2097152%g
                    if data[-1]!=(rem or g): raise AssertionError("BGZF tail mismatch")
                    stored+=gzi.stat().st_size
                    geometry.update(archive_bytes=arc.stat().st_size,index_bytes=gzi.stat().st_size,isizes=data)
                else:
                    with arc.open("rb") as f: hdr=f.read(28)
                    block=struct.unpack_from("<I",hdr,20)[0]
                    if block!=g: raise AssertionError(f"{codec}: encoded block {block} != {g}")
                lib=context_for(a.native,codec)
                verify_archive(measure,lib,arc,inp,side,env)
                configs.append({
                    "window":w["file"],"group":w["group"],"codec":codec,"g":g,
                    "input_bytes":2097152,"stored_bytes":stored,"archive":str(arc.relative_to(out)),
                    "archive_sha256":sha(arc),"sidecar":str(Path(side).relative_to(out)) if side else None,
                    "sidecar_sha256":sha(side) if side else None,"geometry":geometry,
                    "encode_command":[str(x) for x in cmd],"bit_perfect":True
                })
        lat={c:[] for c in CODECS}
        for pass_id in range(3):
            order=list(range(len(configs)));random.Random(20260930+g+pass_id).shuffle(order)
            for idx in order:
                c=configs[idx];codec=c["codec"]
                arc=out/c["archive"];side=str((out/c["sidecar"]).resolve()) if c["sidecar"] else ""
                inp=(a.inputs/c["window"]).resolve();env=env_for(codec,g)
                cp=subprocess.run([str(measure),str(context_for(a.native,codec)),str(arc.resolve()),str(inp),
                                   "region",side],env=env,text=True,capture_output=True,check=True,timeout=300)
                pts=[json.loads(x) for x in cp.stdout.splitlines() if x.strip()]
                if len(pts)!=200 or not all(p.get("verified") is True and p.get("requested_bytes")==16384 for p in pts):
                    raise AssertionError("region judge failed")
                for p in pts:
                    v=float(p["latency_ms"]);lat[codec].append(v)
                    sample_out.write(json.dumps({"g":g,"config":idx,"pass":pass_id,"codec":codec,**p},sort_keys=True)+"\n")
                sample_out.flush()
        totals={}
        for codec in CODECS:
            cc=[x for x in configs if x["codec"]==codec]
            tin=sum(x["input_bytes"] for x in cc); tst=sum(x["stored_bytes"] for x in cc)
            totals[codec]={
                "label":LABELS[codec],"input_bytes":tin,"stored_bytes":tst,
                "ratio":tin/tst,"p50_ms":percentile(lat[codec],.50),"p99_ms":percentile(lat[codec],.99),
                "samples":len(lat[codec]),"bit_perfect_archives":len(cc)
            }
        bg=totals["bgzip"]
        for codec in ("ace-legacy","ace-v210","ace-open"):
            totals[codec]["p50_over_bgzip"]=totals[codec]["p50_ms"]/bg["p50_ms"]
            totals[codec]["p99_over_bgzip"]=totals[codec]["p99_ms"]/bg["p99_ms"]
            totals[codec]["density_gain_pct"]=(totals[codec]["ratio"]/bg["ratio"]-1)*100
        rows.append({"g":g,"totals":totals,"configs":len(configs)})
        (point/"configurations.json").write_text(json.dumps(configs,indent=2)+"\n")
        (point/"result.json").write_text(json.dumps(rows[-1],indent=2)+"\n")

    deltas=[]
    for r in rows:
        v=r["totals"]["ace-v210"]["p50_ms"];o=r["totals"]["ace-open"]["p50_ms"]
        deltas.append({"g":r["g"],"v210_p50_us":v*1000,"open_p50_us":o*1000,
                       "open_minus_v210_us":(o-v)*1000,"reduction_pct":(v-o)/v*100})
    result={
      "schema":"aceapex-upgrade-matched-g-v1","date":"2026-09-30",
      "corpus":"30 frozen T2T-CHM13v2.0 windows x 2 MiB","request_bytes":16384,
      "passes":3,"queries_per_window_per_pass":200,"rows":rows,"open_vs_v210":deltas,
      "pins":PINS,"bgzip_boundary":65280,
      "timing":"resident library contexts; open outside timer; 12 warmups; nearest-rank p50/p99; byte judge outside timer",
      "samples_sha256":sha(all_raw)
    }
    (out/"results.json").write_text(json.dumps(result,indent=2)+"\n")
    return result

def c_g_open(a):
    inp=a.chr1.resolve()
    if inp.stat().st_size!=253935557: raise AssertionError("chr1 size")
    import hashlib as _h
    md5=_h.md5()
    with inp.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): md5.update(b)
    if md5.hexdigest()!="9465e0f0df6e2c6eb39729c39cee5465": raise AssertionError("chr1 md5")
    out=a.out/"open-cg";out.mkdir(parents=True,exist_ok=False)
    vals={}
    for name,g in (("g16k",16384),("whole",inp.stat().st_size)):
        arc=(out/(name+".aet")).resolve()
        cmd,env=encode(a.native,"ace-open",inp,arc,g)
        with arc.open("rb") as f: block=struct.unpack_from("<I",f.read(28),20)[0]
        if block!=g: raise AssertionError("open c(g) block mismatch")
        verify_archive(a.native/"native_measure",context_for(a.native,"ace-open"),arc,inp,"",env)
        vals[name]={"g":g,"archive_bytes":arc.stat().st_size,"ratio":inp.stat().st_size/arc.stat().st_size,
                    "sha256":sha(arc),"command":[str(x) for x in cmd],"full_restore":"byte-exact"}
    cg=100*(1-vals["g16k"]["ratio"]/vals["whole"]["ratio"])
    result={"schema":"aceapex-open-cg-v1","date":"2026-09-30","corpus":"hg38 chr1 FASTA",
            "input_bytes":inp.stat().st_size,"input_md5":"9465e0f0df6e2c6eb39729c39cee5465",
            "profile":"main open","aceapex_sha":PINS["ace-open"],
            "fixed":{"LIT_CHUNK":65536,"FSE_CHUNK":4096,"AX_PROFILE":"open","level":2,"threads":8},
            "points":vals,"c_g_percent":cg,
            "historical_default_reference":{"value_percent":1.632267,"revision":"ee5a37e","scope":"separate strict historical experiment; not rewritten"}}
    (out/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    return result

def report(m,cg,a):
    lines=["# ACEAPEX v2.1.0 / open-profile refresh — 2026-09-30","",
      "CPU matched-g is one same-run comparison on the frozen 30-window T2T corpus. The legacy 1b13df3 configuration is rerun as a control; the previously published historical rows remain unchanged.",
      "Modern v2.1.0 and main-open region reads use the persistent C99 decoder handle, matching BGZF's persistent-context lifecycle. main open is pinned to ec347787 and encoded with AX_PROFILE=open.",
      "",
      "| g | codec | ratio | p50 ms | p99 ms | p50 / BGZF | density vs BGZF |",
      "|---:|---|---:|---:|---:|---:|---:|"]
    for row in m["rows"]:
      g=row["g"]
      for codec in CODECS:
        x=row["totals"][codec]
        if codec=="bgzip":
          lines.append(f'| {g:,} | {x["label"]} | {x["ratio"]:.6f} | {x["p50_ms"]:.6f} | {x["p99_ms"]:.6f} | 1.00× | — |')
        else:
          lines.append(f'| {g:,} | {x["label"]} | {x["ratio"]:.6f} | {x["p50_ms"]:.6f} | {x["p99_ms"]:.6f} | {x["p50_over_bgzip"]:.2f}× | {x["density_gain_pct"]:+.2f}% |')
    lines+=["","## Open versus v2.1.0 interactive","",
      "| g | v2.1 interactive p50 µs | main open p50 µs | open − v2.1 µs | reduction |",
      "|---:|---:|---:|---:|---:|"]
    for d in m["open_vs_v210"]:
      lines.append(f'| {d["g"]:,} | {d["v210_p50_us"]:.3f} | {d["open_p50_us"]:.3f} | {d["open_minus_v210_us"]:+.3f} | {d["reduction_pct"]:+.2f}% |')
    reductions=[d["reduction_pct"] for d in m["open_vs_v210"]]
    removed=[-d["open_minus_v210_us"] for d in m["open_vs_v210"]]
    lines+=["",
      f'Across the five matched-g points, open changes p50 by {min(reductions):+.2f}% to {max(reductions):+.2f}% relative to v2.1.0 interactive; the removed wall-time component is {min(removed):.3f}–{max(removed):.3f} µs. This is a measured same-run difference, not an attribution of every microsecond to one internal call.',
      "",
      "The mechanism is consistent with the source boundary: v2.1.0 interactive uses zstd-coded entropy chunks while the open profile replaces token/literal entropy with rANS/open coding. No extra timing axis or internal timer was added.",
      "",
      "## c(g) at 16 KiB — main open, separate chr1 scope","",
      f'Main-open c_file(16 KiB) = **{cg["c_g_percent"]:.6f}%** on full hg38 chr1: ratio {cg["points"]["g16k"]["ratio"]:.6f} at 16 KiB versus {cg["points"]["whole"]["ratio"]:.6f} with one whole-input block.',
      "Historical strict default reference remains **1.632267%** at ee5a37e; it is shown for context only and its old evidence is not rewritten.",
      "",
      "## GPU — imported measured external evidence","",
      "See GPU_OPEN_20260929.md. These rows are imported from ACEAPEX's retained Colab logs, not rerun by hw-apex-bench.",
      "",
      "## Provenance","",
      f'Workflow run: **{a.actions_run_id}**. Host: {platform.platform()}; CPU affinity {a.cpu}.',
      "All 600 matched-g archives (4 codecs × 30 windows × 5 g) passed full byte-exact restore before timing. Each codec/g has 18,000 verified region samples.",
      "Exact pins: legacy 1b13df34..., v2.1.0 50723533..., main-open ec347787.... libzstd/htslib/libdeflate remain the benchmark's pinned dependencies.",
    ]
    return "\n".join(lines)+"\n"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--inputs",type=Path,required=True)
    ap.add_argument("--chr1",type=Path,required=True)
    ap.add_argument("--native",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--actions-run-id",type=int,default=0)
    ns=ap.parse_args()
    ns.out.mkdir(parents=True,exist_ok=False)
    allowed=sorted(os.sched_getaffinity(0));ns.cpu=allowed[0];os.sched_setaffinity(0,{ns.cpu})
    m=matched_g(ns);cg=c_g_open(ns)
    summary={"schema":"aceapex-upgrade-cpu-v1","actions_run_id":ns.actions_run_id,
             "host":{"platform":platform.platform(),"lscpu":subprocess.check_output(["lscpu"],text=True),
                     "timed_cpu":ns.cpu,"affinity_available":allowed},
             "matched_g":m,"open_cg":cg,
             "benchmark_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
             "completed_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}
    (ns.out/"results.json").write_text(json.dumps(summary,indent=2)+"\n")
    (ns.out/"REPORT.md").write_text(report(m,cg,ns))
    print((ns.out/"REPORT.md").read_text())

if __name__=="__main__": main()
