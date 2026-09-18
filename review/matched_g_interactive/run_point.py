#!/usr/bin/env python3
import argparse, hashlib, json, math, os, platform, random, struct, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "evidence/t2t-regions-20260916/manifest.json"
LEGAL = {65280, 32768, 16384, 8192, 4096}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(cmd, **kw): subprocess.run([str(x) for x in cmd], check=True, **kw)
def p50(xs):
    ys=sorted(xs); return ys[math.ceil(0.50*len(ys))-1]

def bgzf_isizes(data):
    out=[]; p=0
    while p < len(data):
        if len(data)-p < 26 or data[p:p+4] != b"\x1f\x8b\x08\x04":
            raise AssertionError("invalid BGZF member")
        b = data[p+16] | (data[p+17] << 8); b += 1
        if b < 26 or p+b > len(data): raise AssertionError("invalid BSIZE")
        u = int.from_bytes(data[p+b-4:p+b], "little")
        out.append(u); p += b
    if p != len(data) or not out or out[-1] != 0: raise AssertionError("missing EOF block")
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--g", type=int, required=True)
    ap.add_argument("--inputs", type=Path, required=True)
    ap.add_argument("--build", type=Path, required=True)
    ap.add_argument("--native", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a=ap.parse_args()
    if a.g not in LEGAL: raise SystemExit("g outside frozen legal corridor")
    a.out.mkdir(parents=True, exist_ok=False)
    (a.out/"raw").mkdir()
    (a.out/"archives").mkdir()

    allowed=sorted(os.sched_getaffinity(0)); cpu=allowed[0]; os.sched_setaffinity(0,{cpu})
    manifest=json.loads(MANIFEST.read_text())
    windows=manifest["windows"]
    for w in windows:
        p=a.inputs/w["file"]
        if len(p.read_bytes()) != 2097152 or sha(p) != w["input_sha256"]:
            raise AssertionError("frozen input mismatch: "+w["file"])

    ace=a.build/"aceapex"
    encoder=a.native/"bgzf_encode_g"
    measure=a.native/"native_measure"
    ace_so=a.native/"ace_context.so"
    bgzf_so=a.native/"bgzf_context.so"
    env={k:v for k,v in os.environ.items() if not k.startswith(("ACEAPEX_","LIT_","FSE_")) and k!="MIN_MATCH"}
    env["ACEAPEX_BS"]=str(a.g)
    env["LIT_CHUNK"]="65536"
    env["FSE_CHUNK"]="4096"

    configs=[]
    for wi,w in enumerate(windows):
        inp=(a.inputs/w["file"]).resolve()
        for codec in ("aceapex","bgzip"):
            stem=f'{wi:02d}-{codec}-g{a.g}'
            arc=(a.out/"archives"/(stem+".archive")).resolve()
            side=""
            if codec=="aceapex":
                cmd=[ace,"c","--in",inp,"--out",arc,"--threads","8"]
                run(cmd,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=600)
                stored=arc.stat().st_size
                geometry={"granularity":a.g}
                lib=ace_so
            else:
                gzi=Path(str(arc)+".gzi").resolve(); side=str(gzi)
                cmd=[encoder,inp,arc,str(a.g)]
                run(cmd,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=600)
                z=bgzf_isizes(arc.read_bytes()); data=z[:-1]
                if any(x > a.g for x in data) or any(x != a.g for x in data[:-1]):
                    raise AssertionError("BGZF geometry mismatch")
                rem=2097152 % a.g
                if data[-1] != (rem or a.g): raise AssertionError("BGZF tail mismatch")
                stored=arc.stat().st_size+gzi.stat().st_size
                geometry={"isizes":data,"eof_isize":z[-1],"granularity":a.g,
                          "archive_bytes":arc.stat().st_size,"index_bytes":gzi.stat().st_size}
                lib=bgzf_so

            decode=[measure,lib,arc,inp,"decode",side,"1"]
            q=subprocess.run([str(x) for x in decode],env=env,text=True,capture_output=True,check=True,timeout=180)
            if '"verified":true' not in q.stdout: raise AssertionError("full decode not verified")
            configs.append({"id":len(configs),"window":w["file"],"group":w["group"],"codec":codec,
                            "g":a.g,"input_bytes":2097152,"stored_bytes":stored,
                            "archive":arc.name,"archive_sha256":sha(arc),
                            "sidecar":Path(side).name if side else None,
                            "sidecar_sha256":sha(side) if side else None,
                            "geometry":geometry,"encode_command":[str(x) for x in cmd],
                            "decode_command":[str(x) for x in decode],"bit_perfect":True})

    with (a.out/"configurations.jsonl").open("w") as f:
        for c in configs: f.write(json.dumps(c,sort_keys=True)+"\n")

    samples={(c["codec"],c["group"]):[] for c in configs}
    all_samples={"aceapex":[],"bgzip":[]}
    with (a.out/"samples.jsonl").open("w") as out:
        for pass_id in range(3):
            order=list(range(len(configs))); random.Random(20260918+pass_id).shuffle(order)
            for idx in order:
                c=configs[idx]
                arc=(a.out/"archives"/c["archive"]).resolve()
                side=str((a.out/"archives"/c["sidecar"]).resolve()) if c["sidecar"] else ""
                lib=ace_so if c["codec"]=="aceapex" else bgzf_so
                inp=(a.inputs/c["window"]).resolve()
                cp=subprocess.run([str(measure),str(lib),str(arc),str(inp),"region",side],
                                  env=env,text=True,capture_output=True,check=True,timeout=180)
                rows=[json.loads(x) for x in cp.stdout.splitlines() if x.strip()]
                if len(rows)!=200 or not all(r.get("verified") and r["requested_bytes"]==16384 for r in rows):
                    raise AssertionError("invalid region sample")
                for r in rows:
                    v=float(r["latency_ms"]); all_samples[c["codec"]].append(v); samples[c["codec"],c["group"]].append(v)
                    out.write(json.dumps({"config":idx,"pass":pass_id,**r},sort_keys=True)+"\n")
                out.flush()

    totals={}
    for codec in ("aceapex","bgzip"):
        cs=[c for c in configs if c["codec"]==codec]
        total_in=sum(c["input_bytes"] for c in cs); total_stored=sum(c["stored_bytes"] for c in cs)
        totals[codec]={"input_bytes":total_in,"stored_bytes":total_stored,"ratio":total_in/total_stored,
                       "p50_ms":p50(all_samples[codec]),"samples":len(all_samples[codec])}
    groups={}
    for group in sorted({w["group"] for w in windows}):
        groups[group]={}
        for codec in ("aceapex","bgzip"):
            cs=[c for c in configs if c["codec"]==codec and c["group"]==group]
            groups[group][codec]={"ratio":sum(c["input_bytes"] for c in cs)/sum(c["stored_bytes"] for c in cs),
                                  "p50_ms":p50(samples[codec,group])}
    result={"schema":"matched-g-interactive-point-v1","g":a.g,"corpus":"30 frozen T2T 2MiB windows","ace_profile":"interactive","lit_chunk":65536,"fse_chunk":4096,
            "queries_per_config_per_pass":200,"passes":3,"warmups":12,"request_bytes":16384,
            "configs":len(configs),"bit_perfect_archives":len(configs),
            "totals":totals,"groups":groups,
            "density_gain_pct":(totals["aceapex"]["ratio"]/totals["bgzip"]["ratio"]-1)*100,
            "latency_penalty_pct":(totals["aceapex"]["p50_ms"]/totals["bgzip"]["p50_ms"]-1)*100}
    (a.out/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    prov={"platform":platform.platform(),"lscpu":subprocess.check_output(["lscpu"],text=True),
          "affinity_available":allowed,"timed_cpu":cpu,"g":a.g,"ace_profile":"interactive","lit_chunk":65536,"fse_chunk":4096,
          "benchmark_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
          "manifest_sha256":sha(MANIFEST),
          "native_measure_sha256":sha(measure),"ace_context_sha256":sha(ace_so),
          "bgzf_context_sha256":sha(bgzf_so),"bgzf_encoder_sha256":sha(encoder),
          "completed_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}
    (a.out/"provenance.json").write_text(json.dumps(prov,indent=2)+"\n")
    print(json.dumps(result,sort_keys=True))

if __name__=="__main__": main()
