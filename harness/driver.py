"""Stage-1 region benchmark. All performance comparisons are declared in protocol.json."""
import hashlib,json,math,os,pathlib,shlex,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
D=ROOT/".work"
meta=json.loads((D/"metadata.json").read_text())
archives=json.loads((D/"archives.json").read_text())
protocol=json.loads((ROOT/"protocol.json").read_text())
z=D/"zstd"; a=D/"aceapex"
def run(args,**kw):
    print("+ "+shlex.join(map(str,args)),file=sys.stderr,flush=True)
    return subprocess.run(list(map(str,args)),check=True,**kw)
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def flags(args): return shlex.split(subprocess.check_output(args,text=True))
htflags=flags(["pkg-config","--cflags","--libs","htslib"])
inc=["-I"+str(a/"src"),"-I"+str(z/"lib"),"-I"+str(z/"lib/common"),
     "-I"+str(z/"contrib/seekable_format"),"-DXXH_NAMESPACE=ZSTD_"]
build=[]
def compile(args):
    build.append(shlex.join(map(str,args))); run(args)
compile(["g++","-O3","-std=c++17","-pthread",*inc,"-c",a/"src/aceapex_api.cpp","-o",D/"aceapex_api.o"])
compile(["gcc","-O3",*inc,"-c",z/"contrib/seekable_format/zstdseek_decompress.c","-o",D/"seek.o"])
compile(["gcc","-O2","-shared","-fPIC",ROOT/"harness/bgzip_counters.c","-ldl","-o",D/"bgzip_counters.so"])
for phase in ("latency","amplification"):
    extra=["-DCOUNT_ZSTD"] if phase=="amplification" else []
    compile(["gcc","-O3","-Wall","-Wextra",*inc,*extra,*htflags,"-c",ROOT/"harness/region_latency.c","-o",D/(phase+".o")])
    extra=["-Wl,--wrap=ZSTD_decompressStream"] if phase=="amplification" else []
    compile(["g++",D/(phase+".o"),D/"aceapex_api.o",D/"seek.o",z/"lib/libzstd.a",
             "-pthread","-ldl",*htflags,*extra,"-o",D/("region_"+phase)])
meta["region_build_commands"]=build
meta["protocol"]=protocol
rows=[json.loads(s) for s in (D/"results.pending.jsonl").read_text().splitlines()]
for codec,archive in archives.items():
    samples={}
    source=[]
    sample_hashes={}
    for phase in ("latency","amplification"):
        args=[D/("region_"+phase),codec,archive,D/"chr1.fa",phase]
        env=os.environ.copy()
        # Only the separate counter pass preloads instrumentation.
        env.pop("LD_PRELOAD",None)
        prefix=""
        if phase=="amplification" and codec=="bgzip+htslib":
            env["LD_PRELOAD"]=str(D/"bgzip_counters.so")
            prefix="LD_PRELOAD="+shlex.quote(env["LD_PRELOAD"])+" "
        target=D/("samples-"+codec.replace("+","-")+"-"+phase+".jsonl")
        with target.open("w") as f: run(args,stdout=f,env=env)
        sample=[json.loads(s) for s in target.read_text().splitlines()]
        assert len(sample)==200 and all(s["verified"] for s in sample)
        assert [s["query"] for s in sample]==list(range(200))
        samples[phase]=sample
        source.append(prefix+shlex.join(map(str,args)))
        sample_hashes[target.name]=sha(target)
    assert [s["base_offset"] for s in samples["latency"]]==[s["base_offset"] for s in samples["amplification"]]
    times=sorted(s["latency_ms"] for s in samples["latency"])
    assert times[0]>0
    reconstructed=sum(s["decoded_output_bytes"] for s in samples["amplification"])
    assert reconstructed>0, "No decoder output counted: instrumentation is not working"
    archive_record=next(r for r in rows if r["codec"]==codec and r["metric"]=="ratio")
    common=dict(meta,codec=codec,commands=source,sample_sha256=sample_hashes,
                archive_sha256=archive_record["archive_sha256"],correctness="pass")
    for metric,value,unit,status in (
        ("region_p50",times[math.ceil(.50*len(times))-1],"ms","declared"),
        ("region_p99",times[math.ceil(.99*len(times))-1],"ms","declared"),
        ("amplification",reconstructed/(200*16384),"decoded_output_bytes/requested_sequence_bytes",
         "derived" if codec=="aceapex" else "measured")):
        rows.append(dict(common,metric=metric,value=value,unit=unit,status=status))
# Relative predicates are the same for every codec; FAIL does not become SKIP.
for metric in ("ratio","region_p50","region_p99"):
    base=next(r["value"] for r in rows if r["codec"]=="bgzip+htslib" and r["metric"]==metric)
    for codec in archives:
        value=next(r["value"] for r in rows if r["codec"]==codec and r["metric"]==metric)
        relative=value/base
        passed=relative>=0.99 if metric=="ratio" else relative<=1.0
        rows.append(dict(meta,codec=codec,metric=metric+"_relative_to_bgzip",
                    value=relative,unit="dimensionless",status="pass" if passed else "fail",
                    predicate=">=0.99" if metric=="ratio" else "<=1.0",
                    commands=["python3 harness/driver.py"],baseline_codec="bgzip+htslib"))
# Publish only after all three codecs have passed the exactness checks.
final=ROOT/"results.jsonl"
temp=D/"results.complete.jsonl"
temp.write_text("".join(json.dumps(r,sort_keys=True)+"\n" for r in rows))
os.replace(temp,final)
run([sys.executable,ROOT/"harness/report.py"])
print("STOP: stage-1 table ready for review. Batch, H_alpha and break-even are not run.")
