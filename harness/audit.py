"""Matched-archive, matched-API audit. Runs after the existing stage-1 build."""
import os,sys,json,pathlib,subprocess,hashlib,shlex,re,statistics,filecmp
R=pathlib.Path(__file__).resolve().parents[1]; D=R/".work"; A=D/"audit"; A.mkdir(exist_ok=True)
OLD="b1bee4df9c1c0a18d979df2a43947ef1b7adeb57"
REF="1b13df34ac8e839dd3232b59bc59560d689a435a"
Z=D/"zstd"; FA=D/"chr1.fa"; commands=[]; rows=[]
base_env=os.environ.copy()
for k in ("LD_PRELOAD","ACEAPEX_BS","LIT_CHUNK","FSE_CHUNK","MIN_MATCH","ACEAPEX_DUMP"):
    base_env.pop(k,None)
env=dict(base_env,ACEAPEX_BS="16384",LIT_CHUNK="65536",MIN_MATCH="0")
def run(args,**kw):
    args=list(map(str,args)); commands.append(shlex.join(args))
    print("+ "+commands[-1],file=sys.stderr,flush=True)
    return subprocess.run(args,check=True,**kw)
def output(args): return subprocess.check_output(list(map(str,args)),text=True).strip()
def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()
assert hashlib.md5(FA.read_bytes()).hexdigest()=="9465e0f0df6e2c6eb39729c39cee5465"
source=D/"aceapex"; current=A/"aceapex-reference"
run(["git","clone","--no-checkout","https://github.com/yasha1971-coder/aceapex.git",current])
run(["git","-C",current,"fetch","--depth=1","origin",REF])
run(["git","-C",current,"checkout","--detach","FETCH_HEAD"])
assert output(["git","-C",source,"rev-parse","HEAD"])==OLD
assert output(["git","-C",current,"rev-parse","HEAD"])==REF
# Audit copies change ONLY this repository's harness; upstream sources stay unchanged.
original=(R/"harness/region_latency.c").read_text()
def replace_once(s,old,new):
    assert s.count(old)==1, old
    return s.replace(old,new)
paper=replace_once(original,"uint64_t seed=20260909;","uint64_t seed=20260812;")
paper=replace_once(paper,"for(int q=-12;q<QUERIES;q++) {","for(int q=-1;q<QUERIES;q++) {")
paper=replace_once(paper,
    "uint64_t pos=q==-12 ? 0 : q==-11 ? BASES-LENGTH : rng(&seed)%(BASES-LENGTH+1);",
    "uint64_t pos=(rng(&seed)>>33)%(BASES-LENGTH);")
def raw_timer(s):
    s=replace_once(s,"double t0=now();","double t0=now(), api_end=0;")
    s=replace_once(s,"            size_t k=0;","            api_end=now();\n            size_t k=0;")
    return replace_once(s,"double elapsed=(now()-t0)*1000;","double elapsed=(api_end-t0)*1000;")
warmone=replace_once(original,"        uint64_t decoded=0;","        if(q < -1) continue; /* consume RNG; preserve measured trace */\n        uint64_t decoded=0;")
sources={"bench_seq":original,"bench_raw":raw_timer(original),"paper_seq":paper,
         "paper_raw":raw_timer(paper),"bench_seq_warm1":warmone}
ht=shlex.split(output(["pkg-config","--cflags","--libs","htslib"]))
inc=["-I"+str(source/"src"),"-I"+str(Z/"lib"),"-I"+str(Z/"lib/common"),
     "-I"+str(Z/"contrib/seekable_format"),"-DXXH_NAMESPACE=ZSTD_"]
for name,text in sources.items():
    p=A/(name+".c"); p.write_text(text)
    run(["gcc","-O3",*inc,*ht,"-c",p,"-o",A/(name+".o")])
# Original libseek is used unchanged, including its quantile indices and one warmup.
run(["gcc","-O2","-I"+str(source/"src"),"-c",current/"scripts/libseek.c","-o",A/"libseek.o"])
objects={}
for label,src,opt in (("old_O3",source,"-O3"),("old_O2",source,"-O2"),("current_O2",current,"-O2")):
    obj=A/(label+".o")
    run(["g++",opt,"-std=c++17","-pthread","-I"+str(src/"src"),"-I"+str(Z/"lib"),
         "-DXXH_NAMESPACE=ZSTD_","-c",src/"src/aceapex_api.cpp","-o",obj])
    objects[label]=obj
    for harness in ("libseek",*sources):
        run(["g++",A/(harness+".o"),obj,*([] if harness=="libseek" else [D/"seek.o"]),
             Z/"lib/libzstd.a","-pthread","-ldl",*ht,"-o",A/(label+"-"+harness)])
# Two encoder entry points and their actual flags, as used by the two scripts.
encoders={"old_src":D/"aceapex-cli"}
for label,src in (("old_depth",source),("current_depth",current)):
    exe=A/(label+"-encoder")
    run(["g++","-O3","-march=native","-funroll-loops","-std=c++17","-I"+str(src/"src"),
         "-I"+str(Z/"lib"),src/"aceapex_depth.cpp",Z/"lib/libzstd.a","-pthread","-o",exe])
    encoders[label]=exe
archives={}
for label,encoder,fse,threads in (
    ("old_src_fse32","old_src",32768,1),("old_src_fse4","old_src",4096,1),
    ("old_depth_fse4","old_depth",4096,8),("current_depth_fse4","current_depth",4096,8)):
    p=A/(label+".aet"); e=dict(env,FSE_CHUNK=str(fse))
    cmd=[encoders[encoder],"c","--in",FA,"--out",p,"--threads",str(threads)]
    run(cmd,env=e)
    restored=A/"restore.fa"
    run([encoders[encoder],"d","--in",p,"--out",restored],env=e)
    assert filecmp.cmp(FA,restored,shallow=False),label
    restored.unlink()
    archives[label]={"path":str(p),"archive_sha256":sha(p),"archive_bytes":p.stat().st_size,
      "ratio":FA.stat().st_size/p.stat().st_size,"fse_chunk":fse,"encode_threads":threads,
      "encoder":encoder,"encode_command":shlex.join(map(str,cmd)),
      "aceapex_sha":REF if label.startswith("current") else OLD,"full_restore_byte_equal":True}
# Pin only measurement processes; every variant gets the same allowed CPU.
cpu=min(os.sched_getaffinity(0))
def pin(): os.sched_setaffinity(0,{cpu})
assert archives["old_src_fse32"]["archive_sha256"]==sha(D/"chr1.aet"), "Re-encoding the baseline changed its bytes"
provenance={"corpus_md5":"9465e0f0df6e2c6eb39729c39cee5465","benchmark_commit":output(["git","rev-parse","HEAD"]),
 "zstd_sha":output(["git","-C",Z,"rev-parse","HEAD"]),
 "compiler_c":output(["gcc","--version"]).splitlines()[0],
 "compiler_cxx":output(["g++","--version"]).splitlines()[0],"hardware":output(["lscpu"])}
jobs=[]
for arcname in archives:
    apis=["current_O2"] if arcname.startswith("current") else ["old_O3","old_O2"]
    for api in apis:
        harnesses=("libseek","paper_raw","bench_seq") if arcname.startswith("current") else ("libseek",*sources)
        for harness in harnesses: jobs.append((arcname,api,harness))
for repeat in range(3):
    # Rotate and reverse order; do not select the best timing run.
    ordered=jobs[repeat*7:]+jobs[:repeat*7]
    if repeat%2: ordered=list(reversed(ordered))
    for arcname,api,harness in ordered:
        arc=archives[arcname]; e=dict(env,FSE_CHUNK=str(arc["fse_chunk"]))
        args=[A/(api+"-"+harness),arc["path"]] if harness=="libseek" else [
            A/(api+"-"+harness),"aceapex",arc["path"],FA,"latency"]
        p=run(args,env=e,preexec_fn=pin,stdout=subprocess.PIPE,text=True)
        result={**provenance,"archive":arcname,"api":api,"harness":harness,"repeat":repeat,
                "command":shlex.join(map(str,args)),"cpu_affinity":[cpu],
                "environment":{k:e[k] for k in ("ACEAPEX_BS","LIT_CHUNK","FSE_CHUNK","MIN_MATCH")},
                **arc}
        if harness=="libseek":
            nums=re.findall(r"([0-9]+\.[0-9]+)ms",p.stdout)
            assert len(nums)==2,p.stdout
            result.update(p50_ms=float(nums[0]),p99_ms=float(nums[1]),
                          sample_verification="upstream harness only checks negative API return",
                          percentile_indices=[100,198],stdout=p.stdout)
        else:
            samples=[json.loads(s) for s in p.stdout.splitlines()]
            assert len(samples)==200 and all(s["verified"] for s in samples)
            times=sorted(s["latency_ms"] for s in samples)
            result.update(p50_ms=times[100],p99_ms=times[198],
                p50_nearest_rank_ms=times[99],p99_nearest_rank_ms=times[197],
                sample_verification="byte-exact against original FASTA",
                percentile_indices=[100,198],samples=samples)
        rows.append(result)
(A/"audit-results.json").write_text(json.dumps(rows,indent=2)+"\n")
# The actual script is executed as a separate reproduction, not replaced by a guessed profile.
# We use the same zstd version through explicit library paths; all inherited codec tuning is cleared.
re=dict(base_env,CHR1=str(FA),NO_DOWNLOAD="1",BIN=str(A/"reproduce-cli"),
        OUT=str(A/"reproduce-results.json"),ZSTD_INC=str(Z/"lib"),
        LIBRARY_PATH=str(Z/"lib"),LD_LIBRARY_PATH=str(Z/"lib"))
with (A/"reproduce.log").open("w") as f:
    proc=subprocess.run(["bash","./reproduce_paper5.sh"],cwd=current,env=re,stdout=f,stderr=subprocess.STDOUT,timeout=1000)
log=(A/"reproduce.log").read_text()
claim_lines=[s for s in log.splitlines() if "lowlat_region_p50_ms" in s]
record=pathlib.Path("/tmp/_p5_records")
if record.exists(): (A/"reproduce-claims.jsonl").write_bytes(record.read_bytes())
meta={"benchmark_commit":output(["git","rev-parse","HEAD"]),"original_sha":OLD,"reference_sha":REF,
      "zstd_sha":output(["git","-C",Z,"rev-parse","HEAD"]),"libseek_source_sha256":sha(current/"scripts/libseek.c"),"commands":commands,
      "hardware":output(["lscpu"]),"cpu_affinity":[cpu],
      "reproduction_command":"bash ./reproduce_paper5.sh","reproduction_cwd":str(current),
      "reproduction_environment":{k:re[k] for k in ("CHR1","NO_DOWNLOAD","BIN","OUT","ZSTD_INC","LIBRARY_PATH","LD_LIBRARY_PATH")},
      "reproduction_exit_code":proc.returncode,"lowlat_claim_lines":claim_lines,
      "reproduction_log_sha256":sha(A/"reproduce.log")}
assert claim_lines,"Reference script did not reach lowlat claim"
(A/"audit-metadata.json").write_text(json.dumps(meta,indent=2)+"\n")
text=["# Matched-archive ACEAPEX latency audit","",
      "Values below are the median of three per-run p50 values (200 queries per run).",
      "Both quantile indices match the upstream libseek definition. No best-run selection.",
      "All measurement subprocesses use the same CPU affinity. All archives passed full byte equality.",
      "", "| Archive | API build | Harness | Median p50 ms | Min–max p50 ms |",
      "|---|---|---|---:|---:|"]
for arc,api,h in jobs:
    vals=[r["p50_ms"] for r in rows if (r["archive"],r["api"],r["harness"])==(arc,api,h)]
    text.append(f"| {arc} | {api} | {h} | {statistics.median(vals):.6f} | {min(vals):.6f}–{max(vals):.6f} |")
text+=["","## Original reproduction script","",f"Exit code: {proc.returncode}. A nonzero exit can include unrelated historical claims; inspect the complete log.",
       "",*claim_lines,"","Archive SHA-256 digests, commands, raw verified samples and versions are in audit-results.json and audit-metadata.json.",
       "No unqualified cross-codec performance conclusion is restored by this audit automatically."]
(A/"AUDIT_RESULTS.md").write_text("\n".join(text)+"\n")
print("\n".join(text))
