"""Grow repeated chr1 input until encode and API full-decode rates plateau."""
import hashlib, json, math, os, pathlib, shlex, statistics, subprocess, time
from configurations import CODECS, configuration, clean_environment

COPIES=(1,2,4,8)
ENCODE_REPEATS=3
DECODE_REPEATS=5
PLATEAU_POINTS=3
PLATEAU_SPREAD=0.05
SAMPLE_CV_LIMIT=0.05

def _sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""): h.update(chunk)
    return h.hexdigest()

def _cv(values):
    mean=statistics.fmean(values)
    return statistics.pstdev(values)/mean if len(values)>1 else 0.0

def _plateau(points):
    if len(points)<PLATEAU_POINTS:return False
    tail=points[-PLATEAU_POINTS:]
    rates=[p["value"] for p in tail]
    return max(rates)/min(rates)-1<=PLATEAU_SPREAD and all(p["sample_cv"]<=SAMPLE_CV_LIMIT for p in tail)

def add_throughput(rows,meta,archives,D,inc,htflags,compile,run):
    root=D.parent; z=D/"zstd"; source=D/"chr1.fa"; work=D/"plateau"
    work.mkdir(exist_ok=True)
    compile(["gcc","-O3","-Wall","-Wextra",*inc,*htflags,"-c",root/"harness/throughput.c","-o",D/"throughput.o"])
    compile(["g++",D/"throughput.o",D/"aceapex_api.o",D/"seek.o",z/"lib/libzstd.a","-pthread",*htflags,"-o",D/"throughput"])
    protocol={"input_growth_copies":list(COPIES),"corpus_concatenation":"byte concatenation of verified chr1.fa with itself",
      "plateau_rule":f"latest {PLATEAU_POINTS} scale medians have max/min spread <= {PLATEAU_SPREAD:.0%}; every scale sample CV <= {SAMPLE_CV_LIMIT:.0%}",
      "encode":"median of 3 process wall-clock runs; output creation only; corpus construction and hashing excluded",
      "full_decode":"one warmup plus median of 5 library calls; archive and expected output resident; output preallocated/prefaulted; verification outside timer",
      "units":"decimal MB/s (input bytes / wall seconds / 1e6)","max_copies":max(COPIES),
      "edge_rule":"if either curve does not satisfy plateau rule by max_copies, summary is data_edge with null value",
      "edge_reason":"declared CI resource edge: 8 copies = 2031484456 input bytes; growth beyond this is outside the run budget"}
    meta=dict(meta,throughput_protocol=protocol)
    raw=[]; curve={c:{"encode":[],"decode":[]} for c in CODECS}
    for copies in COPIES:
        inp=work/f"chr1-x{copies}.fa"
        with inp.open("wb") as out:
            for _ in range(copies):
                with source.open("rb") as src:
                    for chunk in iter(lambda:src.read(1<<20),b""):out.write(chunk)
        input_bytes=inp.stat().st_size
        md5=hashlib.md5()
        with inp.open("rb") as f:
            for chunk in iter(lambda:f.read(1<<20),b""):md5.update(chunk)
        expected_md5=md5.hexdigest()
        for codec in CODECS:
            cfg=configuration(codec); env=clean_environment(os.environ); commands=[]; times=[]
            arc=work/(codec.replace("+","-")+f"-x{copies}.archive")
            gzi=pathlib.Path(str(arc)+".gzi")
            api=cfg["implementation"]
            denv=clean_environment(os.environ);denv.update(cfg.get("reader_environment",{}))
            prefix=("env "+shlex.join(k+"="+v for k,v in cfg["reader_environment"].items())+" ") if cfg.get("reader_environment") else ""
            verification_commands=[]
            for rep in range(ENCODE_REPEATS):
                arc.unlink(missing_ok=True);gzi.unlink(missing_ok=True)
                if codec=="bgzip+htslib":
                    args=["bgzip","-l","6","-@","1","-i","-I",gzi,"-c",inp]
                    command=shlex.join(map(str,args))+" > "+shlex.quote(str(arc))
                    start=time.monotonic()
                    with arc.open("wb") as f:subprocess.run(list(map(str,args)),stdout=f,env=env,check=True,timeout=1800)
                elif codec=="zstd-seekable":
                    args=[z/"contrib/seekable_format/examples/seekable_compression",inp,"16384","3"]
                    command=shlex.join(map(str,args))
                    generated=pathlib.Path(str(inp)+".zst");generated.unlink(missing_ok=True)
                    start=time.monotonic();subprocess.run(list(map(str,args)),env=env,check=True,timeout=1800);stop=time.monotonic()
                    generated.replace(arc)
                else:
                    profile=cfg["profile"]
                    args=[D/"aceapex-cli","c","--in",inp,"--out",arc,"--threads","1","--level","2","--profile",profile]
                    command=shlex.join(map(str,args))
                    start=time.monotonic();subprocess.run(list(map(str,args)),env=env,check=True,timeout=1800);stop=time.monotonic()
                if codec=="bgzip+htslib":stop=time.monotonic()
                elapsed=(stop-start)*1000
                if not arc.is_file() or arc.stat().st_size==0:raise RuntimeError(codec+" encode produced no archive")
                verify=[D/"throughput",api,arc,inp,"0"]
                subprocess.run(list(map(str,verify)),stdout=subprocess.DEVNULL,env=denv,check=True,timeout=1800)
                verification_commands.append(prefix+shlex.join(map(str,verify)))
                times.append(elapsed);commands.append(command)
            median=statistics.median(times); rates=[input_bytes/t/1000 for t in times]
            common=dict(meta,codec=codec,configuration=cfg,input_copies=copies,input_bytes=input_bytes,
              input_md5=expected_md5,archive_bytes=arc.stat().st_size,index_bytes=gzi.stat().st_size if gzi.exists() else 0,
              archive_sha256=_sha(arc),correctness="pass",threads_requested=1)
            erow=dict(common,metric="encode_throughput_curve",value=input_bytes/median/1000,unit="MB/s",status="declared",
              wall_ms=median,sample_wall_ms=times,sample_rates_mb_s=rates,sample_cv=_cv(rates),commands=commands,
              timing_boundary="subprocess wall clock around encoder only",full_restore="pass for every timed archive",
              verification_commands=verification_commands)
            rows.append(erow);curve[codec]["encode"].append(erow);raw.append(erow)
            args=[D/"throughput",api,arc,inp,str(DECODE_REPEATS)]
            target=work/("decode-"+codec.replace("+","-")+f"-x{copies}.jsonl")
            with target.open("w") as f:run(args,stdout=f,env=denv)
            samples=[json.loads(s) for s in target.read_text().splitlines()]
            if len(samples)!=DECODE_REPEATS or not all(s["verified"] and s["verified_bytes"]==input_bytes for s in samples):
                raise RuntimeError(codec+" throughput decode verification failed")
            dt=[s["wall_ms"] for s in samples];dr=[input_bytes/t/1000 for t in dt];dmed=statistics.median(dt)
            drow=dict(common,metric="full_decode_throughput_curve",value=input_bytes/dmed/1000,unit="MB/s",status="declared",
              wall_ms=dmed,sample_wall_ms=dt,sample_rates_mb_s=dr,sample_cv=_cv(dr),commands=[prefix+shlex.join(map(str,args))],
              timing_boundary="library API only; resident archive and prefaulted output",decoder_thread_policy=("8 reconstruction workers; API has no thread argument" if api=="aceapex" else "single decoder thread"))
            rows.append(drow);curve[codec]["decode"].append(drow);raw.append(drow)
            arc.unlink(missing_ok=True);gzi.unlink(missing_ok=True)
        inp.unlink()
        if all(_plateau(curve[c][phase]) for c in CODECS for phase in ("encode","decode")):break
    for codec in CODECS:
        for phase,metric in (("encode","encode_throughput_mb_s"),("decode","full_decode_throughput_mb_s")):
            points=curve[codec][phase]; reached=_plateau(points);last=points[-1]
            rows.append(dict(last,metric=metric,value=last["value"] if reached else None,
              status="declared" if reached else "data_edge",plateau_reached=reached,
              plateau_evidence=[{"input_copies":p["input_copies"],"value":p["value"],"sample_cv":p["sample_cv"]} for p in points[-PLATEAU_POINTS:]],
              reason=None if reached else f"curve not flat by data edge: {points[-1]['input_copies']} corpus copies"))
    for phase,metric in (("encode","encode_throughput_mb_s"),("decode","full_decode_throughput_mb_s")):
        summaries={r["codec"]:r for r in rows if r["metric"]==metric}
        base=summaries["bgzip+htslib"]
        for codec,r in summaries.items():
            relmetric=metric.replace("_mb_s","_relative_to_bgzip")
            if r["value"] is None or base["value"] is None:
                rows.append(dict(r,metric=relmetric,value=None,unit="dimensionless",status="n/a",predicate=">=1",
                  reason="relation unavailable until both codec and bgzip reach plateau"))
            else:
                value=r["value"]/base["value"]
                rows.append(dict(r,metric=relmetric,value=value,unit="dimensionless",status="pass" if value>=1 else "fail",
                  predicate=">=1",baseline_codec="bgzip+htslib",baseline_value=base["value"],baseline_commands=base["commands"]))
    (D/"throughput-raw.json").write_text(json.dumps({"protocol":protocol,"points":raw},indent=2)+"\n")
    return rows

def render_throughput(rows):
    out=["## Encode and full decode on the plateau","",
      "Input is byte-concatenated chr1. A plateau requires the latest three scale medians to remain within 5%, with sample CV at every scale no greater than 5%. If this is not reached by the available data edge, no headline rate is printed.","",
      "| Codec/profile | block bytes | Encoder threads | Encode MB/s | vs bgzip | Full decoder threads | Full decode MB/s | vs bgzip | Largest input |","|---|---:|---:|---|---|---|---|---|---:|"]
    for codec in CODECS:
        enc=[r for r in rows if r["codec"]==codec and r["metric"]=="encode_throughput_curve"]
        dec=[r for r in rows if r["codec"]==codec and r["metric"]=="full_decode_throughput_curve"]
        if len(enc)!=len(dec) or len(enc)<PLATEAU_POINTS or [r["input_copies"] for r in enc]!=list(COPIES[:len(enc)]) or [r["input_copies"] for r in dec]!=list(COPIES[:len(dec)]):
            raise ValueError("Incomplete throughput curve: "+codec)
        for r,repeats in [(x,ENCODE_REPEATS) for x in enc]+[(x,DECODE_REPEATS) for x in dec]:
            if r.get("correctness")!="pass" or not r.get("commands") or len(r["sample_wall_ms"])!=repeats or any(x<=0 for x in r["sample_wall_ms"]):
                raise ValueError("Invalid throughput evidence: "+codec)
            expected=r["input_bytes"]/statistics.median(r["sample_wall_ms"])/1000
            if not math.isclose(expected,r["value"],rel_tol=1e-12):raise ValueError("Throughput formula mismatch")
        e=next(r for r in rows if r["codec"]==codec and r["metric"]=="encode_throughput_mb_s")
        d=next(r for r in rows if r["codec"]==codec and r["metric"]=="full_decode_throughput_mb_s")
        er=next(r for r in rows if r["codec"]==codec and r["metric"]=="encode_throughput_relative_to_bgzip")
        dr=next(r for r in rows if r["codec"]==codec and r["metric"]=="full_decode_throughput_relative_to_bgzip")
        for summary,points in ((e,enc),(d,dec)):
            reached=_plateau(points)
            if summary["plateau_reached"]!=reached or (summary["value"] is None)==reached:
                raise ValueError("Plateau decision mismatch: "+codec)
        for summary,rel in ((e,er),(d,dr)):
            base=next(r for r in rows if r["codec"]=="bgzip+htslib" and r["metric"]==summary["metric"])
            if summary["value"] is None or base["value"] is None:
                if rel["value"] is not None or rel["status"]!="n/a":raise ValueError("Invalid n/a relation")
            else:
                expected=summary["value"]/base["value"]
                if not math.isclose(expected,rel["value"],rel_tol=1e-12) or rel["status"]!=("pass" if expected>=1 else "fail"):
                    raise ValueError("Invalid throughput relation")
        def value(r):return f"{r['value']:.3f}" if r["value"] is not None else "data edge"
        def relation(r):return f"{r['value']:.3f} {r['status'].upper()}" if r["value"] is not None else "n/a"
        out.append(f"| {codec} | {e['configuration']['block']} | {e['threads_requested']} | {value(e)} | {relation(er)} | {d['decoder_thread_policy']} | {value(d)} | {relation(dr)} | {e['input_bytes']} |")
    out += ["","Encode is process wall clock around the encoder. Full decode is timed only around the library call, with archive resident and output allocated and prefaulted. All decoded bytes are compared with the concatenated input outside the timer.",
      "The declared resource edge is eight copies (2,031,484,456 input bytes). Every curve point, repetition, command, archive hash, machine and library version is retained in `results.jsonl` and `.work/throughput-raw.json`.","",
      "GPU remains a separate path and is not inferred from these CPU measurements.","",
      "Stop for review before the three-machine experiment and GPU publication."]
    return "\n".join(out)
