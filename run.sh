#!/usr/bin/env bash
# First commit is deliberately self-contained and implements all three codecs.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export ACEAPEX_BS=16384 LIT_CHUNK=65536 FSE_CHUNK=32768 MIN_MATCH=0
export LC_ALL=C
python3 - "$@" <<'PY'
import gzip, hashlib, json, os, pathlib, platform, shlex, shutil, subprocess, sys, tempfile, urllib.request
ROOT=pathlib.Path.cwd()
D=ROOT/".work"
D.mkdir(exist_ok=True)
ACE_SHA="b1bee4df9c1c0a18d979df2a43947ef1b7adeb57"
ZSTD_REF="v1.5.7"
CORPUS={"id":"chr1-hg38-fasta","url":"https://hgdownload.soe.ucsc.edu/goldenPath/hg38/chromosomes/chr1.fa.gz","md5":"9465e0f0df6e2c6eb39729c39cee5465","md5_scope":"uncompressed FASTA"}
commands=[]
def run(argv, **kw):
    argv=list(map(str,argv))
    print("+ "+shlex.join(argv),file=sys.stderr,flush=True)
    commands.append(shlex.join(argv))
    return subprocess.run(argv,check=True,**kw)
def output(argv):
    return subprocess.check_output(list(map(str,argv)),text=True).strip()
def digest(p, algorithm="md5"):
    h=hashlib.new(algorithm)
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()
def checkout(url, ref, target):
    if not target.exists(): run(["git","clone","--no-checkout",url,target])
    run(["git","-C",target,"fetch","--depth=1","origin",ref])
    run(["git","-C",target,"checkout","--detach","FETCH_HEAD"])
    sha=output(["git","-C",target,"rev-parse","HEAD"])
    if len(ref)==40 and sha!=ref: raise RuntimeError("dependency SHA mismatch")
    if output(["git","-C",target,"status","--porcelain","--untracked-files=no"]):
        raise RuntimeError("dependency has modified tracked sources")
    return sha
if sys.argv[1:]==["--help"]:
    print("bash run.sh : build three codecs, verify chr1 MD5 and full restore, then run stage-1 region harness when present. No batch stage.")
    sys.exit(0)
for tool in ("git","make","gcc","g++","pkg-config","bgzip"):
    if not shutil.which(tool): raise SystemExit("Missing dependency: "+tool+"; see README prerequisites")
run(["pkg-config","--exists","htslib"])
fa=D/"chr1.fa"
if not fa.exists():
    tmp=fa.with_suffix(".download")
    with urllib.request.urlopen(CORPUS["url"],timeout=120) as response:
        with gzip.GzipFile(fileobj=response) as source,open(tmp,"wb") as dest:
            shutil.copyfileobj(source,dest,1024*1024)
    if digest(tmp)!=CORPUS["md5"]: raise RuntimeError("STOP: downloaded corpus MD5 mismatch")
    tmp.rename(fa)
if digest(fa)!=CORPUS["md5"]: raise RuntimeError("STOP: corpus MD5 mismatch")
z=D/"zstd"; a=D/"aceapex"
zsha=checkout("https://github.com/facebook/zstd.git",ZSTD_REF,z)
asha=checkout("https://github.com/yasha1971-coder/aceapex.git",ACE_SHA,a)
jobs=str(min(os.cpu_count() or 1,4))
run(["make","-C",z,"-j"+jobs])
run(["make","-C",z/"contrib/seekable_format/examples","seekable_compression"])
run(["g++","-O3","-std=c++17","-pthread","-I"+str(a/"src"),"-I"+str(z/"lib"),
     a/"src/aceapex_main.cpp",z/"lib/libzstd.a","-o",D/"aceapex-cli"])
# Index construction is setup, never a latency sample.
idx=D/"index.c"
idx.write_text('#include <htslib/faidx.h>\nint main(int n,char**v){return n==2 ? fai_build(v[1]) : 2;}\n')
htflags=shlex.split(output(["pkg-config","--cflags","--libs","htslib"]))
run(["gcc","-O2",idx,"-o",D/"index"]+htflags)
versions={"aceapex_sha":asha,"zstd_sha":zsha,"zstd_ref":ZSTD_REF,
          "libzstd":output([z/"programs/zstd","--version"]),
          "htslib":output(["pkg-config","--modversion","htslib"]),
          "bgzip":output(["bgzip","--version"]).splitlines()[0],
          "compiler_c":output(["gcc","--version"]).splitlines()[0],
          "compiler_cxx":output(["g++","--version"]).splitlines()[0]}
hardware={"platform":platform.platform(),"machine":platform.machine(),"logical_cpus":os.cpu_count()}
if shutil.which("lscpu"): hardware["lscpu"]=output(["lscpu"])
env={k:os.environ[k] for k in ("ACEAPEX_BS","LIT_CHUNK","FSE_CHUNK","MIN_MATCH")}
meta={"corpus":CORPUS,"versions":versions,"hardware":hardware,"environment":env,
      "benchmark_commit":output(["git","rev-parse","HEAD"]),"ratio_tolerance":0.01}
archives={}
rows=[]
for codec in ("bgzip+htslib","zstd-seekable","aceapex"):
    start=len(commands)
    if codec=="bgzip+htslib":
        arc=D/"chr1.fa.gz"
        with open(arc,"wb") as f: run(["bgzip","-l","6","-@", "1","-c",fa],stdout=f)
        run([D/"index",arc])
        dec=["bgzip","-d","-c",arc]
        sidecars=[pathlib.Path(str(arc)+s) for s in (".fai",".gzi")]
    elif codec=="zstd-seekable":
        run([z/"contrib/seekable_format/examples/seekable_compression",fa,"16384","3"])
        arc=pathlib.Path(str(fa)+".zst")
        dec=[z/"programs/zstd","-d","-c",arc]
        sidecars=[]
    else:
        arc=D/"chr1.aet"
        run([D/"aceapex-cli","c","--in",fa,"--out",arc,"--threads","1"])
        dec=[D/"aceapex-cli","d","--in",arc,"--out",D/"restore.fa"]
        sidecars=[]
    restored=D/"restore.fa"
    if codec=="aceapex": run(dec)
    else:
        with open(restored,"wb") as f: run(dec,stdout=f)
    if digest(restored)!=CORPUS["md5"]: raise RuntimeError(codec+" full restore mismatch")
    restored.unlink()
    # Total storage includes every required on-disk sidecar.
    total=arc.stat().st_size+sum(p.stat().st_size for p in sidecars)
    archives[codec]=str(arc)
    rows.append(dict(meta,codec=codec,metric="ratio",value=fa.stat().st_size/total,unit="input_bytes/archive_bytes",
        status="declared",archive_bytes=arc.stat().st_size,index_bytes=total-arc.stat().st_size,
        archive_sha256=digest(arc,"sha256"),input_bytes=fa.stat().st_size,
        full_restore_md5=CORPUS["md5"],full_restore="pass",commands=commands[start:]))
meta["build_commands"]=commands.copy()
(D/"metadata.json").write_text(json.dumps(meta,indent=2)+"\n")
(D/"archives.json").write_text(json.dumps(archives,indent=2)+"\n")
# Stage-1 only: throughput, independence sweeps and batch are not claimed here.
pending=D/"results.pending.jsonl"
pending.write_text("".join(json.dumps(r)+"\n" for r in rows))
if (ROOT/"harness/driver.py").exists():
    run([sys.executable,ROOT/"harness/driver.py"])
else:
    os.replace(pending,ROOT/"results.jsonl")
    print("Three-codec ratio and full-restore stage complete; region harness not yet installed.")
PY
