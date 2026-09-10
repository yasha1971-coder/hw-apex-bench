"""Measure the zstd-seekable addressability/full-decode frontier by frame size."""
import hashlib, json, math, os, pathlib, shlex, statistics
from configurations import clean_environment
from throughput import COPIES, DECODE_REPEATS, PLATEAU_POINTS, _cv, _plateau

FRAMES=(16384,65536,262144,2097152)
QUERIES=200
REQUEST_BYTES=16384

def _sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""): h.update(chunk)
    return h.hexdigest()

def _samples(path): return [json.loads(s) for s in path.read_text().splitlines() if s]

def add_zstd_frontier(rows,meta,D,run):
    z=D/"zstd"; source=D/"chr1.fa"; work=D/"zstd-frontier"; work.mkdir(exist_ok=True)
    compressor=z/"contrib/seekable_format/examples/seekable_compression"
    env=clean_environment(os.environ)
    raw=[]
    for frame in FRAMES:
        cfg={"implementation":"zstd-seekable","level":3,"frame_bytes":frame,"block":frame,
             "encoder_requested_threads":1,"api":"ZSTD_seekable_decompress"}
        common=dict(meta,evidence_group="zstd-frame-frontier",codec="zstd-seekable-frontier",
                    configuration=cfg,frame_bytes=frame,threads_requested=1)
        archive=work/f"chr1-frame-{frame}.zst"
        generated=pathlib.Path(str(source)+".zst"); generated.unlink(missing_ok=True)
        compress=[compressor,source,str(frame),"3"]
        run(compress,env=env); generated.replace(archive)
        ratio=source.stat().st_size/archive.stat().st_size
        verify=[D/"throughput","zstd-seekable",archive,source,"1"]
        run(verify,env=env,stdout=__import__("subprocess").DEVNULL)
        rows.append(dict(common,metric="zstd_frame_ratio",value=ratio,unit="input_bytes/archive_bytes",status="declared",
          input_bytes=source.stat().st_size,archive_bytes=archive.stat().st_size,archive_sha256=_sha(archive),correctness="pass",
          commands=[shlex.join(map(str,compress)),shlex.join(map(str,verify))],full_restore="pass"))
        phase_data={}
        for phase,binary in (("latency",D/"region_latency"),("amplification",D/"region_amplification")):
            target=work/f"frame-{frame}-{phase}.jsonl"
            cmd=[binary,"zstd-seekable",archive,source,phase]
            with target.open("w") as out: run(cmd,env=env,stdout=out)
            ss=_samples(target)
            if len(ss)!=QUERIES or not all(x["verified"] for x in ss): raise RuntimeError("zstd frontier query verification failed")
            phase_data[phase]=(ss,shlex.join(map(str,cmd)),_sha(target))
        times=sorted(x["latency_ms"] for x in phase_data["latency"][0])
        decoded=sum(x["decoded_bytes"] for x in phase_data["amplification"][0])
        for metric,value,unit,cmd,extra in (
          ("zstd_frame_region_p50_ms",times[math.ceil(.50*QUERIES)-1],"ms",phase_data["latency"][1],{}),
          ("zstd_frame_region_p99_ms",times[math.ceil(.99*QUERIES)-1],"ms",phase_data["latency"][1],{}),
          ("zstd_frame_amplification",decoded/(QUERIES*REQUEST_BYTES),"decoded_bytes/requested_bytes",phase_data["amplification"][1],
           {"decoded_bytes_total":decoded,"requested_bytes_total":QUERIES*REQUEST_BYTES})):
            rows.append(dict(common,metric=metric,value=value,unit=unit,status="declared",correctness="pass",commands=[cmd],
              sample_sha256={"latency":phase_data["latency"][2],"amplification":phase_data["amplification"][2]},
              timing_boundary="API only; resident archive; 10 random warmups plus two boundary checks; 200 timed byte-verified queries",**extra))
        curve=[]
        for copies in COPIES:
            inp=source if copies==1 else work/f"chr1-x{copies}.fa"
            if copies!=1:
                with inp.open("wb") as out:
                    for _ in range(copies):
                        with source.open("rb") as src:
                            for chunk in iter(lambda:src.read(1<<20),b""): out.write(chunk)
            arc=work/f"frame-{frame}-x{copies}.zst"; generated=pathlib.Path(str(inp)+".zst"); generated.unlink(missing_ok=True)
            ccmd=[compressor,inp,str(frame),"3"]
            run(ccmd,env=env); generated.replace(arc)
            target=work/f"frame-{frame}-decode-x{copies}.jsonl"
            dcmd=[D/"throughput","zstd-seekable",arc,inp,str(DECODE_REPEATS)]
            with target.open("w") as out: run(dcmd,env=env,stdout=out)
            ss=_samples(target); size=inp.stat().st_size
            if len(ss)!=DECODE_REPEATS or not all(x["verified"] and x["verified_bytes"]==size for x in ss):
                raise RuntimeError("zstd frontier full decode verification failed")
            wall=[x["wall_ms"] for x in ss]; rates=[size/x/1000 for x in wall]
            point=dict(common,metric="zstd_frame_full_decode_curve",value=size/statistics.median(wall)/1000,unit="MB/s",status="declared",
              input_copies=copies,input_bytes=size,wall_ms=statistics.median(wall),sample_wall_ms=wall,sample_rates_mb_s=rates,
              sample_cv=_cv(rates),archive_bytes=arc.stat().st_size,archive_sha256=_sha(arc),correctness="pass",
              commands=[shlex.join(map(str,ccmd)),shlex.join(map(str,dcmd))],
              timing_boundary="ZSTD_seekable_decompress API only; resident archive and prefaulted output")
            rows.append(point);curve.append(point);raw.append(point);arc.unlink()
            if copies!=1: inp.unlink()
        reached=_plateau(curve); last=curve[-1]
        rows.append(dict(last,metric="zstd_frame_full_decode_mb_s",value=last["value"] if reached else None,
          status="declared" if reached else "data_edge",plateau_reached=reached,
          plateau_evidence=[{"input_copies":p["input_copies"],"value":p["value"],"sample_cv":p["sample_cv"]} for p in curve[-PLATEAU_POINTS:]],
          reason=None if reached else "curve not flat by eight-copy data edge"))
        raw.extend([r for r in rows if r.get("evidence_group")=="zstd-frame-frontier" and r.get("frame_bytes")==frame and r["metric"]!="zstd_frame_full_decode_curve"])
        archive.unlink()
    (D/"zstd-frontier-raw.json").write_text(json.dumps({"frames":FRAMES,"points":raw},indent=2)+"\n")
    return rows

def render_zstd_frontier(rows):
    rr=[r for r in rows if r.get("evidence_group")=="zstd-frame-frontier"]
    if not rr: raise ValueError("missing zstd frame frontier")
    out=["## zstd-seekable frame-size frontier","",
      "Only frame size changes: zstd 1.5.7, level 3, one encoder thread, the same chr1 bytes and the same 16 KiB API requests. Region timers reuse one resident `ZSTD_seekable` handle. Full-decode speed is published only if the standard plateau rule is reached.","",
      "| frame bytes | Ratio incl. seek table | Region p50 ms | Region p99 ms | Amplification | Plateau full decode MB/s |",
      "|---:|---:|---:|---:|---:|---|"]
    def one(frame,metric):
        found=[r for r in rr if r["frame_bytes"]==frame and r["metric"]==metric]
        if len(found)!=1: raise ValueError(f"missing/duplicate zstd frontier {frame} {metric}")
        r=found[0]
        if not r.get("commands") or r.get("correctness")!="pass": raise ValueError("invalid zstd frontier evidence")
        return r
    for frame in FRAMES:
        ratio=one(frame,"zstd_frame_ratio");p50=one(frame,"zstd_frame_region_p50_ms");p99=one(frame,"zstd_frame_region_p99_ms")
        amp=one(frame,"zstd_frame_amplification");full=one(frame,"zstd_frame_full_decode_mb_s")
        speed=f"{full['value']:.3f}" if full["value"] is not None else "data edge"
        out.append(f"| {frame} | {ratio['value']:.6f} | {p50['value']:.6f} | {p99['value']:.6f} | {amp['value']:.6f} | {speed} |")
    out += ["","This is a measured tradeoff curve, not a single ‘zstd versus ACEAPEX’ point: larger frames may improve density or sequential decode while increasing the amount of work touched by a 16 KiB request. The table prints the observed result even when that expectation does not hold."]
    return "\n".join(out)
