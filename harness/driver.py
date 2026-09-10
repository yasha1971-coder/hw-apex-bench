"""Stage-1 region benchmark. All performance comparisons are declared in protocol.json."""
import hashlib,json,math,os,pathlib,shlex,subprocess,sys
from configurations import CODECS, configuration, clean_environment
ROOT=pathlib.Path(__file__).resolve().parents[1]
D=ROOT/".work"
meta=json.loads((D/"metadata.json").read_text())
archives=json.loads((D/"archives.json").read_text())
assert tuple(archives)==CODECS
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
from build_counters import build_counters
meta["counter_source_sha256"]=build_counters(D,compile,inc)
for phase in ("latency","amplification"):
    extra=["-DCOUNT_DECODER"] if phase=="amplification" else []
    compile(["gcc","-O3","-Wall","-Wextra",*inc,*extra,*htflags,"-c",ROOT/"harness/region_latency.c","-o",D/(phase+".o")])
    extra=[]
    api=D/("aceapex_count.o" if phase=="amplification" else "aceapex_api.o")
    lib=(D/"counter-zstd/lib/libzstd.a") if phase=="amplification" else z/"lib/libzstd.a"
    compile(["g++",D/(phase+".o"),api,D/"seek.o",lib,
             "-pthread","-ldl",*htflags,*extra,"-o",D/("region_"+phase)])
meta["region_build_commands"]=build
meta["protocol"]=protocol
rows=[json.loads(s) for s in (D/"results.pending.jsonl").read_text().splitlines()]
for codec,archive in archives.items():
    config=configuration(codec)
    api_codec=config["implementation"]
    samples={}
    source=[]
    sample_hashes={}
    for phase in ("latency","amplification"):
        args=[D/("region_"+phase),api_codec,archive,D/"chr1.fa",phase]
        env=clean_environment(os.environ)
        env.update(config.get("reader_environment",{}))
        # Only the separate counter pass preloads instrumentation.
        env.pop("LD_PRELOAD",None)
        prefix=("env "+shlex.join(k+"="+v for k,v in config["reader_environment"].items())+" ") if config.get("reader_environment") else ""
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
    if api_codec=="aceapex":
        from check_counts import check_ace_counts
        check_ace_counts(pathlib.Path(archive),samples["amplification"],config)
    assert [s["byte_offset"] for s in samples["latency"]]==[s["byte_offset"] for s in samples["amplification"]]
    times=sorted(s["latency_ms"] for s in samples["latency"])
    assert times[0]>0
    reconstructed=sum(s["decoded_bytes"] for s in samples["amplification"])
    assert reconstructed>0, "No decoder output counted: instrumentation is not working"
    archive_record=next(r for r in rows if r["codec"]==codec and r["metric"]=="ratio")
    common=dict(meta,codec=codec,configuration=config,commands=source,sample_sha256=sample_hashes,
                archive_sha256=archive_record["archive_sha256"],correctness="pass")
    for metric,value,unit,status in (
        ("region_p50",times[math.ceil(.50*len(times))-1],"ms","declared"),
        ("region_p99",times[math.ceil(.99*len(times))-1],"ms","declared"),
        ("amplification",reconstructed/(200*16384),"decoded_bytes/requested_bytes", "measured")):
        record=dict(common,metric=metric,value=value,unit=unit,status=status)
        if metric=="amplification":
            import collections
            ss=samples["amplification"]
            record.update(decoded_bytes_total=reconstructed, requested_bytes_total=sum(x["requested_bytes"] for x in ss),
                formula="sum(actual decoded unit bytes across queries) / sum(requested bytes across queries)",
                decoded_bytes_histogram=dict(sorted(collections.Counter(x["decoded_bytes"] for x in ss).items())))
            if api_codec=="aceapex":
                record["stream_decoded_bytes_total"]=[sum(x["stream_decoded_bytes"][i] for x in ss) for i in range(4)]
                record["stream_order"]=["literal","offset","length","command"]
                block=config["block"]
                record["output_blocks_touched_histogram"]=dict(sorted(collections.Counter((x["byte_offset"]+x["requested_bytes"]-1)//block-x["byte_offset"]//block+1 for x in ss).items()))
        rows.append(record)
# Relative predicates are the same for every codec; FAIL does not become SKIP.
for metric in ("ratio","region_p50","region_p99"):
    base=next(r["value"] for r in rows if r["codec"]=="bgzip+htslib" and r["metric"]==metric)
    for codec in archives:
        value=next(r["value"] for r in rows if r["codec"]==codec and r["metric"]==metric)
        relative=value/base
        passed=relative>=0.99 if metric=="ratio" else relative<=1.0
        rows.append(dict(meta,codec=codec,configuration=configuration(codec),metric=metric+"_relative_to_bgzip",
                    value=relative,unit="dimensionless",status="pass" if passed else "fail",
                    predicate=">=0.99" if metric=="ratio" else "<=1.0",
                    commands=["python3 harness/driver.py"],baseline_codec="bgzip+htslib"))
if meta.get("stage",1)==2:
    from stage2 import add_stage2
    rows=add_stage2(rows,meta,archives,D,inc,htflags,compile,run)
# Publish only after all four configurations have passed the exactness checks.
final=ROOT/"results.jsonl"
temp=D/"results.complete.jsonl"
temp.write_text("".join(json.dumps(r,sort_keys=True)+"\n" for r in rows))
os.replace(temp,final)
run([sys.executable,ROOT/"harness/report.py"])
print("STOP: requested stage complete; review before c(g), plateau throughput and three-machine runs.")
