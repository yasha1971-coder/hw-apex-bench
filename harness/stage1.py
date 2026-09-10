import gzip, hashlib, json, os, pathlib, platform, shlex, shutil, subprocess, sys, tempfile, urllib.request
ROOT=pathlib.Path.cwd()
D=ROOT/".work"
D.mkdir(exist_ok=True)
from configurations import ACE_SHA, CODECS, PROFILES, configuration, clean_environment
clean_env=clean_environment(os.environ)
os.environ.clear(); os.environ.update(clean_env)
ZSTD_REF="v1.5.7"
CORPUS=json.loads((ROOT/"corpora.json").read_text())["chr1_hg38"]
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
    print("bash run.sh : build three codecs (four configurations), verify chr1 MD5/full restore, API regions, batch/H_alpha/break-even, c(g), plateau throughput, zstd frame frontier, and declared GPU evidence. --stage N stops after stage N; N=1..5.")
    sys.exit(0)
args=sys.argv[1:]
if args not in ([], ["--stage","1"], ["--stage","2"], ["--stage","3"], ["--stage","4"], ["--stage","5"]): raise SystemExit("Usage: ./run.sh [--stage 1|2|3|4|5]")
stage=int(args[1]) if args else 5
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
compile_trace=D/"compile-trace.jsonl"
compile_trace.unlink(missing_ok=True)
tracer=shlex.join([sys.executable,str(ROOT/"harness/compiler_trace.py"),"--real"])
build_env=os.environ.copy()
build_env.update(CABENCH_COMPILE_TRACE=str(compile_trace),CC=tracer+" gcc",CXX=tracer+" g++")
run(["bash","codecs/zstd_seekable.sh","build",D,jobs],env=build_env)
run(["bash","codecs/aceapex.sh","build",D],env=build_env)
source_spec=D/"source-spec.json"
source_spec.write_text(json.dumps({"codecs":[
    {"codec":"zstd-seekable","repository_root":str(z),"expected_commit":zsha,
     "required_translation_units":["programs/zstdcli.c","contrib/seekable_format/examples/seekable_compression.c"]},
    {"codec":"aceapex","repository_root":str(a),"expected_commit":asha,
     "required_translation_units":["aceapex_depth.cpp"]},
    {"codec":"bgzip+htslib","status":"n/a",
     "reason":"system htslib/bgzip package is not compiled by this benchmark",
     "binary":shutil.which("bgzip"),"binary_sha256":digest(shutil.which("bgzip"),"sha256")}
]},indent=2)+"\n")
source_provenance=D/"source-provenance.json"
run([sys.executable,ROOT/"harness/source_provenance.py","--trace",compile_trace,
     "--spec",source_spec,"--out",source_provenance])
# Profiles are CLI-owned, and environment overrides must be absent at encode time.
import re
cli_source=(a/"aceapex_depth.cpp").read_text()
for name, values in PROFILES.items():
    match=re.search(r'\{"'+name+r'",\s*"(\d+)",\s*"(\d+)",\s*"(\d+)"', cli_source)
    if not match or match.groups()!=tuple(values[k] for k in ("ACEAPEX_BS","LIT_CHUNK","FSE_CHUNK")):
        raise RuntimeError("Pinned CLI profile differs from configuration: "+name)
versions={"aceapex_sha":asha,"zstd_sha":zsha,"zstd_ref":ZSTD_REF,
          "libzstd":output([z/"programs/zstd","--version"]),
          "htslib":output(["pkg-config","--modversion","htslib"]),
          "bgzip":output(["bgzip","--version"]).splitlines()[0],
          "compiler_c":output(["gcc","--version"]).splitlines()[0],
          "compiler_cxx":output(["g++","--version"]).splitlines()[0]}
hardware={"platform":platform.platform(),"machine":platform.machine(),"logical_cpus":os.cpu_count()}
if shutil.which("lscpu"): hardware["lscpu"]=output(["lscpu"])
env={"codec_overrides": "cleared; CLI --profile selects encode settings; per-row reader_environment selects API settings"}
meta={"stage":stage,"run_id":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),"corpus":CORPUS,"versions":versions,"hardware":hardware,"environment":env,
      "benchmark_commit":output(["git","rev-parse","HEAD"]),"ratio_tolerance":0.01,"encode_requested_threads":1,
      "source_provenance":json.loads(source_provenance.read_text()),
      "note":"ACEAPEX may internally use additional entropy/decode workers; every throughput row declares its encoder and decoder thread policy"}
archives={}
rows=[]
for codec in CODECS:
    config=configuration(codec)
    start=len(commands)
    if codec=="bgzip+htslib":
        arc=D/"chr1.fa.gz"
        run(["bash","codecs/bgzip.sh","compress",fa,arc])
        dec=["bash","codecs/bgzip.sh","restore",arc]
        sidecars=[pathlib.Path(str(arc)+s) for s in (".gzi",)]
    elif codec=="zstd-seekable":
        run(["bash","codecs/zstd_seekable.sh","compress",D,fa])
        arc=pathlib.Path(str(fa)+".zst")
        dec=["bash","codecs/zstd_seekable.sh","restore",D,arc]
        sidecars=[]
    else:
        profile=config["profile"]
        arc=D/("chr1-"+profile+".aet")
        run(["bash","codecs/aceapex.sh","compress",D,fa,arc,profile])
        dec=["bash","codecs/aceapex.sh","restore",D,arc,D/"restore.fa",profile]
        sidecars=[]
    restored=D/"restore.fa"
    if codec.startswith("aceapex-"): run(dec)
    else:
        with open(restored,"wb") as f: run(dec,stdout=f)
    if digest(restored)!=CORPUS["md5"]: raise RuntimeError(codec+" full restore MD5 mismatch")
    if not __import__("filecmp").cmp(fa,restored,shallow=False): raise RuntimeError(codec+" full restore byte mismatch")
    restored.unlink()
    if codec.startswith("aceapex-"):
        import struct
        with arc.open("rb") as f: header=f.read(24)
        if struct.unpack_from("<I",header,20)[0]!=int(config["effective_environment"]["ACEAPEX_BS"]):
            raise RuntimeError("Encoded block size differs from profile")
    # Total storage includes every required on-disk sidecar.
    total=arc.stat().st_size+sum(p.stat().st_size for p in sidecars)
    archives[codec]=str(arc)
    rows.append(dict(meta,codec=codec,configuration=config,metric="ratio",value=fa.stat().st_size/total,unit="input_bytes/archive_bytes",
        status="declared",archive_bytes=arc.stat().st_size,index_bytes=total-arc.stat().st_size,
        archive_sha256=digest(arc,"sha256"),input_bytes=fa.stat().st_size,
        full_restore_md5=CORPUS["md5"],full_restore_byte_equal=True,full_restore="pass",commands=commands[start:]))
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
