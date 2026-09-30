#!/usr/bin/env python3
import argparse,hashlib,json,math,os,platform,random,shutil,struct,subprocess,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/"evidence/t2t-regions-20260916/manifest.json"
LEGAL=(4096,8192,16384,32768,65280)
CODECS=("ace-interactive","ace-open","bgzip","zstd-seekable")
LABELS={
 "ace-interactive":"ACEAPEX v2.2.0 interactive (l1 default)",
 "ace-open":"ACEAPEX v2.2.0 open (l1 default)",
 "bgzip":"BGZF + htslib",
 "zstd-seekable":"zstd-seekable 1.5.7",
}
ACE_SHA="0a143cd64b35a802835f18c361f981968edf25a1"
ZSTD_SHA="f8745da6ff1ad1e7bab384bd1f9d742439278e99"
HTS_SHA="8f7231035d0409d525767c66d9f49f1f967ee1df"
LIBDEFLATE_SHA="dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f"

def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def md5(p):
    h=hashlib.md5()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def nr(xs,q):
    ys=sorted(xs); return ys[math.ceil(q*len(ys))-1]

def run(cmd,**kw):
    subprocess.run([str(x) for x in cmd],check=True,**kw)

def clean_env():
    bad={"ACEAPEX_BS","LIT_CHUNK","FSE_CHUNK","MIN_MATCH","AX_PROFILE","AX_TOK","AX_LIT","AX_ENC"}
    return {k:v for k,v in os.environ.items() if k not in bad}

def ace_env(g,profile="interactive",encoder="l1"):
    e=clean_env()
    e.update(ACEAPEX_BS=str(g),LIT_CHUNK="65536",FSE_CHUNK="4096")
    if profile=="open": e["AX_PROFILE"]="open"
    if encoder=="chain": e["AX_ENC"]="chain"
    return e

def ctx(native,codec,counter=False):
    if codec.startswith("ace-"): return native/("ace-counter-context.so" if counter else "ace-context.so")
    if codec=="zstd-seekable": return native/("zstd-counter-context.so" if counter else "zstd-context.so")
    if codec=="bgzip": return native/("bgzf-counter-context.so" if counter else "bgzf-context.so")
    raise KeyError(codec)

def bgzf_isizes(data):
    out=[];p=0
    while p<len(data):
        if len(data)-p<26 or data[p:p+4]!=b"\x1f\x8b\x08\x04": raise AssertionError("invalid BGZF")
        b=(data[p+16]|(data[p+17]<<8))+1
        if b<26 or p+b>len(data): raise AssertionError("invalid BGZF BSIZE")
        out.append(int.from_bytes(data[p+b-4:p+b],"little"));p+=b
    if p!=len(data) or not out or out[-1]!=0: raise AssertionError("missing BGZF EOF")
    return out

def encode(native,codec,inp,arc,g,tmp,encoder="l1"):
    if codec=="ace-interactive":
        env=ace_env(g,"interactive",encoder)
        cmd=[native/"aceapex-v220","c","--in",inp,"--out",arc,"--threads","8","--level","2"]
        run(cmd,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=900)
        return cmd,env,""
    if codec=="ace-open":
        env=ace_env(g,"open",encoder)
        cmd=[native/"aceapex-v220","c","--in",inp,"--out",arc,"--threads","8","--level","2"]
        run(cmd,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=900)
        return cmd,env,""
    if codec=="bgzip":
        env=clean_env();cmd=[native/"bgzf-encode-g",inp,arc,str(g)]
        run(cmd,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=900)
        return cmd,env,str(Path(str(arc)+".gzi").resolve())
    if codec=="zstd-seekable":
        env=clean_env()
        td=tmp/f"zstd-{hashlib.sha256(str(arc).encode()).hexdigest()[:16]}";td.mkdir(parents=True)
        cp=td/"input";shutil.copyfile(inp,cp)
        cmd=[native/"seekable_compression",cp,str(g),"3"]
        run(cmd,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=900)
        shutil.move(str(cp)+".zst",arc)
        shutil.rmtree(td)
        return [native/"seekable_compression",inp,str(g),"3"],env,""
    raise KeyError(codec)

def verify_full(measure,lib,arc,inp,side,env,repeats=1):
    cp=subprocess.run([str(measure),str(lib),str(arc),str(inp),"decode",side,str(repeats)],
                      env=env,text=True,capture_output=True,check=True,timeout=300)
    pts=[json.loads(x) for x in cp.stdout.splitlines() if x.strip()]
    if len(pts)!=repeats or not all(x.get("verified") is True for x in pts):
        raise AssertionError("full decode judge failed")
    return [float(x["wall_ms"]) for x in pts]

def amplification(measure,lib,arc,inp,side,env):
    cp=subprocess.run([str(measure),str(lib),str(arc),str(inp),"amplification",side],
                      env=env,text=True,capture_output=True,check=True,timeout=300)
    pts=[json.loads(x) for x in cp.stdout.splitlines() if x.strip()]
    if len(pts)!=200 or not all(x.get("verified") is True and x["requested_bytes"]==16384 for x in pts):
        raise AssertionError("amplification judge failed")
    return pts

def versions(native):
    z=(native/"zstd-version.txt").read_text().strip()
    pin=(native/"PINS").read_text()
    return {"libzstd":z,"pins_text":pin}

def prov_base(native,host,run_id):
    return {
      "actions_run_id":run_id,
      "host":host,
      "aceapex_tag":"v2.2.0",
      "aceapex_sha":ACE_SHA,
      "ace_binary_sha256":sha(native/"aceapex-v220"),
      "ace_build":"upstream make with benchmark-pinned static libzstd",
      "libzstd_version":(native/"zstd-version.txt").read_text().strip(),
      "zstd_sha":ZSTD_SHA,
      "htslib_sha":HTS_SHA,
      "libdeflate_sha":LIBDEFLATE_SHA,
      "native_measure_sha256":sha(native/"native_measure"),
      "ace_context_sha256":sha(native/"ace-context.so"),
      "ace_counter_context_sha256":sha(native/"ace-counter-context.so"),
      "zstd_context_sha256":sha(native/"zstd-context.so"),
      "zstd_counter_context_sha256":sha(native/"zstd-counter-context.so"),
      "bgzf_context_sha256":sha(native/"bgzf-context.so"),
      "bgzf_counter_context_sha256":sha(native/"bgzf-counter-context.so"),
    }

def matched_g(a,host):
    manifest=json.loads(MANIFEST.read_text());windows=manifest["windows"]
    for w in windows:
        p=a.inputs/w["file"]
        if p.stat().st_size!=2097152 or sha(p)!=w["input_sha256"]: raise AssertionError("window mismatch")
    out=a.out/"matched-g";out.mkdir()
    tmp=out/"tmp";tmp.mkdir()
    sample_file=out/"region-samples.jsonl"
    amp_file=out/"amplification-samples.jsonl"
    full_file=out/"full-decode-samples.jsonl"
    rows=[];base=prov_base(a.native,host,a.actions_run_id)
    with sample_file.open("w") as sf, amp_file.open("w") as af, full_file.open("w") as ff:
      for g in LEGAL:
        point=out/f"g{g}";(point/"archives").mkdir(parents=True)
        configs=[]
        for wi,w in enumerate(windows):
          inp=(a.inputs/w["file"]).resolve()
          for codec in CODECS:
            arc=(point/"archives"/f"{wi:02d}-{codec}.archive").resolve()
            cmd,env,side=encode(a.native,codec,inp,arc,g,tmp)
            sidecar_bytes=0
            if codec=="bgzip":
                gzi=Path(side);sidecar_bytes=gzi.stat().st_size
                z=bgzf_isizes(arc.read_bytes());data=z[:-1]
                if any(x>g for x in data) or any(x!=g for x in data[:-1]): raise AssertionError("BGZF g mismatch")
                rem=2097152%g
                if data[-1]!=(rem or g): raise AssertionError("BGZF tail")
            if codec.startswith("ace-"):
                with arc.open("rb") as f: block=struct.unpack_from("<I",f.read(28),20)[0]
                if block!=g: raise AssertionError("ACE block mismatch")
            dec=verify_full(a.native/"native_measure",ctx(a.native,codec),arc,inp,side,env,3)
            for rep,ms in enumerate(dec): ff.write(json.dumps({"g":g,"window":w["file"],"codec":codec,"repeat":rep,"wall_ms":ms})+"\n")
            amps=amplification(a.native/"native_measure",ctx(a.native,codec,True),arc,inp,side,env)
            for p in amps: af.write(json.dumps({"g":g,"window":w["file"],"codec":codec,**p},sort_keys=True)+"\n")
            configs.append({
              "id":len(configs),"window":w["file"],"codec":codec,"g":g,
              "input_bytes":2097152,"archive_bytes":arc.stat().st_size,
              "sidecar_bytes":sidecar_bytes,"ratio_file":2097152/arc.stat().st_size,
              "archive_sha256":sha(arc),"sidecar_sha256":sha(side) if side else None,
              "encode_command":[str(x) for x in cmd],
              "encoder_environment":{k:env[k] for k in ("ACEAPEX_BS","LIT_CHUNK","FSE_CHUNK","AX_PROFILE","AX_ENC") if k in env},
              "full_restore":"byte-exact"
            })
        lat={c:[] for c in CODECS}
        for pass_id in range(3):
          order=list(range(len(configs)));random.Random(20260930+g+pass_id).shuffle(order)
          for idx in order:
            c=configs[idx];codec=c["codec"];inp=(a.inputs/c["window"]).resolve()
            arc=point/"archives"/f"{windows.index(next(w for w in windows if w['file']==c['window'])):02d}-{codec}.archive"
            # use recorded archive path instead of reconstructed window index if available
            arc=(point/"archives"/Path(configs[idx]["archive_sha256"])).resolve() if False else arc.resolve()
            side=str(Path(str(arc)+".gzi").resolve()) if codec=="bgzip" else ""
            env=ace_env(g,"open" if codec=="ace-open" else "interactive") if codec.startswith("ace-") else clean_env()
            cp=subprocess.run([str(a.native/"native_measure"),str(ctx(a.native,codec)),str(arc),str(inp),"region",side],
                              env=env,text=True,capture_output=True,check=True,timeout=300)
            pts=[json.loads(x) for x in cp.stdout.splitlines() if x.strip()]
            if len(pts)!=200 or not all(x.get("verified") is True for x in pts): raise AssertionError("region judge")
            for p in pts:
              lat[codec].append(float(p["latency_ms"]))
              sf.write(json.dumps({"g":g,"config":idx,"pass":pass_id,"codec":codec,**p},sort_keys=True)+"\n")
        # aggregate separately from raw files using configs and just-written structures
        for codec in CODECS:
          cc=[x for x in configs if x["codec"]==codec]
          total_in=sum(x["input_bytes"] for x in cc); total_arc=sum(x["archive_bytes"] for x in cc)
          amp_pts=[]
          # re-read only current g/codec from retained file buffer after flush
          af.flush();ff.flush()
          amp_pts=[json.loads(x) for x in amp_file.read_text().splitlines() if json.loads(x)["g"]==g and json.loads(x)["codec"]==codec]
          full_pts=[json.loads(x) for x in full_file.read_text().splitlines() if json.loads(x)["g"]==g and json.loads(x)["codec"]==codec]
          decoded=sum(x["decoded_bytes"] for x in amp_pts);requested=sum(x["requested_bytes"] for x in amp_pts)
          full_ms=nr([x["wall_ms"] for x in full_pts],.5)
          p50=nr(lat[codec],.5);p99=nr(lat[codec],.99)
          be=math.floor(full_ms/p50)+1
          rows.append({
            "scope":"matched-g-t2t-30x2MiB","g":g,"codec":codec,"label":LABELS[codec],
            "ratio_file":total_in/total_arc,"input_bytes":total_in,"archive_bytes":total_arc,
            "required_sidecar_bytes":sum(x["sidecar_bytes"] for x in cc),
            "region_p50_ms":p50,"region_p99_ms":p99,"region_samples":len(lat[codec]),
            "amplification":decoded/requested,"amplification_decoded_bytes":decoded,
            "amplification_requested_bytes":requested,"amplification_samples":len(amp_pts),
            "full_decode_p50_ms":full_ms,"full_decode_samples":len(full_pts),
            "break_even_n":be,
            "provenance":{
              **base,
              "codec_version":("v2.2.0@"+ACE_SHA if codec.startswith("ace-") else ("1.5.7@"+ZSTD_SHA if codec=="zstd-seekable" else "htslib@"+HTS_SHA)),
              "profile":("open" if codec=="ace-open" else ("interactive" if codec=="ace-interactive" else None)),
              "encoder":"l1 default" if codec.startswith("ace-") else None,
              "ratio_definition":"sum input bytes / sum archive file bytes; BGZF .gzi sidecar recorded but excluded per assignment",
              "timer":"only resident library API call; setup/warmups/verification outside timer",
              "requests":"30 windows × 3 passes × 200 for region; 30 × 200 for amplification",
            }
          })
        (point/"configurations.json").write_text(json.dumps(configs,indent=2)+"\n")
    result={"schema":"aceapex-v220-matched-g-v1","date":"2026-09-30","rows":rows,
            "region_samples_sha256":sha(sample_file),"amplification_samples_sha256":sha(amp_file),
            "full_decode_samples_sha256":sha(full_file)}
    (out/"results.json").write_text(json.dumps(result,indent=2)+"\n")
    return result

def c_g(a,host):
    inp=a.chr1.resolve()
    if inp.stat().st_size!=253935557 or md5(inp)!="9465e0f0df6e2c6eb39729c39cee5465": raise AssertionError("chr1 identity")
    out=a.out/"c-g";out.mkdir();tmp=out/"tmp";tmp.mkdir()
    base=prov_base(a.native,host,a.actions_run_id);rows=[]
    for enc in ("l1","chain"):
      points={}
      for name,g in (("g16k",16384),("whole",inp.stat().st_size)):
        arc=(out/f"{enc}-{name}.aet").resolve()
        cmd,env,_=encode(a.native,"ace-interactive",inp,arc,g,tmp,encoder=enc)
        verify_full(a.native/"native_measure",ctx(a.native,"ace-interactive"),arc,inp,"",env,1)
        points[name]={"g":g,"archive_bytes":arc.stat().st_size,"ratio":inp.stat().st_size/arc.stat().st_size,
                      "archive_sha256":sha(arc),"command":[str(x) for x in cmd],
                      "environment":{k:env[k] for k in ("ACEAPEX_BS","LIT_CHUNK","FSE_CHUNK","AX_ENC") if k in env}}
      cg=100*(1-points["g16k"]["ratio"]/points["whole"]["ratio"])
      rows.append({
        "scope":"full-chr1-c_file","encoder":enc,"profile":"interactive","g":16384,
        "c_g_percent":cg,"g16k":points["g16k"],"whole":points["whole"],
        "provenance":{**base,"codec_version":"v2.2.0@"+ACE_SHA,
                      "encoder":("l1 default" if enc=="l1" else "AX_ENC=chain"),
                      "fixed":"LIT_CHUNK=65536; FSE_CHUNK=4096; level=2; threads=8",
                      "judge":"both archives full byte-exact restore"}
      })
    if rows[0]["g16k"]["archive_sha256"]==rows[1]["g16k"]["archive_sha256"]:
        raise AssertionError("l1 and chain did not produce different chr1 16KiB archives")
    result={"schema":"aceapex-v220-cg-v1","date":"2026-09-30","rows":rows}
    (out/"results.json").write_text(json.dumps(result,indent=2)+"\n")
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--inputs",type=Path,required=True)
    ap.add_argument("--chr1",type=Path,required=True)
    ap.add_argument("--native",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--actions-run-id",type=int,required=True)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    allowed=sorted(os.sched_getaffinity(0));cpu=allowed[0];os.sched_setaffinity(0,{cpu})
    lscpu=subprocess.check_output(["lscpu"],text=True)
    cpu_name=next((x.split(":",1)[1].strip() for x in lscpu.splitlines() if x.startswith("Model name:")),"unknown")
    host={"platform":platform.platform(),"cpu":cpu_name,"timed_cpu":cpu,"affinity_available":allowed}
    mg=matched_g(a,host);cg=c_g(a,host)
    result={"schema":"aceapex-v220-refresh-v1","date":"2026-09-30","host":host,
            "matched_g":mg,"c_g":cg,
            "pins":(a.native/"PINS").read_text(),
            "completed_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
            "benchmark_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()}
    (a.out/"results.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"status":"pass","matched_rows":len(mg["rows"]),"cg_rows":len(cg["rows"])},sort_keys=True))

if __name__=="__main__": main()
