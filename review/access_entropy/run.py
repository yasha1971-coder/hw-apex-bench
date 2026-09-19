#!/usr/bin/env python3
import argparse,collections,ctypes as C,hashlib,json,math,os,platform,statistics,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"harness"))
from qualification import clean_environment,require_current,work_directory,digest
from reader_environment import parameters
from resident_probe import Context

N=5000
R=16384
CORPUS_BYTES=253935557
CORPUS_MD5="9465e0f0df6e2c6eb39729c39cee5465"
ADAPTERS=(
    ("bgzip+htslib",ROOT/"codecs/bgzip.sh"),
    ("zstd-seekable",ROOT/"codecs/zstd_seekable.sh"),
    ("aceapex-interactive",ROOT/"codecs/aceapex.sh"),
    ("aceapex-dense",ROOT/"codecs/aceapex_dense.sh"),
)

def file_hash(path,algorithm="sha256"):
    h=hashlib.new(algorithm)
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def run(argv,env=None,timeout=3600,stdout=None,stderr=None):
    return subprocess.run([str(x) for x in argv],env=env,check=True,text=True,
                          timeout=timeout,stdout=stdout,stderr=stderr)

def output(argv,env=None,timeout=120):
    return subprocess.check_output([str(x) for x in argv],env=env,text=True,timeout=timeout).strip()

def call(adapter,work,op,*args):
    return output(["bash",adapter,"_call",op,*args],clean_environment(work),3600)

def same_file(a,b):
    with Path(a).open("rb") as x,Path(b).open("rb") as y:
        while True:
            xb=x.read(1024*1024);yb=y.read(1024*1024)
            if xb!=yb:return False
            if not xb:return True

def load_trace(path):
    rows=[]
    for line in Path(path).read_text().splitlines():
        o,n=map(int,line.split())
        if n!=R:raise ValueError("trace request size")
        rows.append(o)
    if len(rows)!=N:raise ValueError("trace count")
    return rows

def mapped_entropy(library,archive,sidecar,offsets,expected_size):
    ctx=Context(library,Path(archive).read_bytes(),expected_size=expected_size,
                sidecar=sidecar or None)
    try:
        fn=ctx.lib.hc_block_id
        fn.argtypes=[C.c_void_p,C.c_uint64]
        fn.restype=C.c_uint64
        ids=[int(fn(ctx.ptr,o)) for o in offsets]
        if any(x==(1<<64)-1 for x in ids):raise ValueError("block-id mapping failed")
        counts=collections.Counter(ids)
        h=-math.fsum((v/len(ids))*math.log2(v/len(ids)) for v in counts.values())
        return h,len(counts),hashlib.sha256(json.dumps(ids,separators=(",",":")).encode()).hexdigest()
    finally:
        ctx.close()

def parse_worker(text,native):
    points=[json.loads(x) for x in text.splitlines() if x.strip()]
    methods=("loop","batch") if native else ("loop",)
    expected={(rep,m) for rep in range(3) for m in methods}
    got={(p.get("repeat"),p.get("method")) for p in points}
    if got!=expected or len(points)!=len(expected):
        raise ValueError("incomplete batch samples")
    for p in points:
        if p.get("verified") is not True or p.get("n")!=N:
            raise ValueError("unverified batch point")
        if type(p.get("wall_ms")) not in (int,float) or not math.isfinite(p["wall_ms"]) or p["wall_ms"]<=0:
            raise ValueError("invalid batch duration")
    by={m:sorted((p for p in points if p["method"]==m),key=lambda p:p["repeat"]) for m in methods}
    lm=statistics.median(p["wall_ms"] for p in by["loop"])
    result={
        "loop_median_ms":lm,
        "loop_ranges_s":N*1000/lm,
        "loop_repeats":[p["wall_ms"] for p in by["loop"]],
        "verified_loop_ranges":N*3,
    }
    if native:
        bm=statistics.median(p["wall_ms"] for p in by["batch"])
        paired=[by["loop"][i]["wall_ms"]/by["batch"][i]["wall_ms"] for i in range(3)]
        result.update(
            batch_median_ms=bm,
            batch_ranges_s=N*1000/bm,
            batch_repeats=[p["wall_ms"] for p in by["batch"]],
            batch_speedup=statistics.median(paired),
            paired_speedups=paired,
            verified_batch_ranges=N*3,
        )
    return result,points

def report(result):
    rows=result["rows"]
    lines=[
        "# Access-entropy sweep — N=5000, R=16 KiB, workers=1",
        "",
        "Same hg38 chr1 corpus, one runner, and the repository's existing resident adapters.",
        "The common H_alpha column is measured Shannon entropy of request starts on the shared 16 KiB grid; Zipf exponents are retained only in provenance.",
        "",
        "| workload | measured H_alpha bits | codec | codec-block H_alpha bits | loop ranges/s | native batch ranges/s | batch / loop |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    profile_order={p["profile"]:i for i,p in enumerate(result["profiles"])}
    codec_order={name:i for i,(name,_) in enumerate(ADAPTERS)}
    for r in sorted(rows,key=lambda x:(profile_order[x["profile"]],codec_order[x["codec"]])):
        batch="n/a — current adapter has no native batch API" if r["batch_ranges_s"] is None else f'{r["batch_ranges_s"]:,.1f}'
        speed="n/a" if r["batch_speedup"] is None else f'{r["batch_speedup"]:.2f}×'
        lines.append(
            f'| {r["profile"]} | {r["H_alpha_bits"]:.3f} | {r["codec"]} | '
            f'{r["codec_H_alpha_bits"]:.3f} | {r["loop_ranges_s"]:,.1f} | {batch} | {speed} |'
        )
    lines+=["","## Answer",""]
    lines.append(result["answer"]["batch_concentration"])
    lines.append("")
    lines.append(result["answer"]["dense_vs_interactive"])
    lines+=["",
        "All loop responses and every available native-batch response were compared byte-for-byte with the original by harness/native_batch.c outside the timed interval.",
        "Absolute rates belong to this host; the concentration trend is a same-run comparison.",
        "",
        "## Provenance",
        "",
        f'Actions run: {result["actions_run_id"]}.',
        f'Host: {result["host"]["cpu"]}; {result["host"]["platform"]}; timed affinity CPU {result["host"]["timed_cpu"]}.',
        "Trace hashes, adapter qualification receipts, archive hashes, raw three-repeat timings and exact Zipf parameters are retained in evidence/access-entropy-20260919/results.json and the run artifact.",
    ]
    return "\n".join(lines)+"\n"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",type=Path,required=True)
    ap.add_argument("--check-root",type=Path,required=True)
    ap.add_argument("--traces",type=Path,required=True)
    ap.add_argument("--worker",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--actions-run-id",type=int,default=0)
    a=ap.parse_args()
    if a.input.stat().st_size!=CORPUS_BYTES or file_hash(a.input,"md5")!=CORPUS_MD5:
        raise SystemExit("wrong chr1 corpus")
    profiles=json.loads((a.traces/"profiles.json").read_text())["profiles"]
    if [p["profile"] for p in profiles]!=["uniform","zipf-h8","zipf-h4","zipf-h2"]:
        raise ValueError("unexpected profiles")
    a.out.mkdir(parents=True,exist_ok=False)
    (a.out/"raw").mkdir()
    (a.out/"archives").mkdir()
    allowed=sorted(os.sched_getaffinity(0))
    cpu=allowed[0]
    os.sched_setaffinity(0,{cpu})

    prepared={}
    provenance=[]
    for label,adapter in ADAPTERS:
        work=work_directory(adapter,a.check_root)
        receipt,state=require_current(adapter,work)
        if state["codec"]!=label:raise ValueError(f"adapter label mismatch: {label}")
        env=clean_environment(work)
        archive=(a.out/"archives"/(label+".archive")).resolve()
        g=int(state["constraints"]["granularity"])
        run(["bash",adapter,"_call","codec_compress",a.input.resolve(),archive,g],env=env)
        artifacts=[Path(x).resolve() for x in json.loads(call(adapter,work,"codec_artifacts",archive))]
        sidecar=call(adapter,work,"codec_sidecar",archive)
        sidecar=str(Path(sidecar).resolve()) if sidecar else ""
        library=Path(call(adapter,work,"codec_library")).resolve()
        restored=a.out/"archives"/(label+".restore")
        run(["bash",adapter,"_call","codec_decompress",archive,restored],env=env)
        if not same_file(a.input,restored):raise ValueError(label+" full restore differs")
        restored.unlink()
        hashes={str(p):{"bytes":p.stat().st_size,"sha256":file_hash(p)} for p in artifacts}
        prepared[label]={
            "adapter":str(adapter),"work":str(work),"state":state,"archive":str(archive),
            "artifacts":hashes,"sidecar":sidecar,"library":str(library),
            "reader_env":{**env,**parameters(state["configuration"])},
        }
        provenance.append({
            "codec":label,
            "adapter":str(adapter.relative_to(ROOT)),
            "version":state["version"],
            "configuration":state["configuration"],
            "qualification_sha256":receipt["qualification_sha256"],
            "check_receipt_sha256":digest(work/"check.json"),
            "archive_artifacts":hashes,
            "full_restore":"byte-exact",
        })

    rows=[]
    raw_index=[]
    base_order=[x[0] for x in ADAPTERS]
    for pi,p in enumerate(profiles):
        offsets=load_trace(a.traces/p["trace"])
        order=base_order[pi:]+base_order[:pi]
        for label in order:
            st=prepared[label]
            h,distinct,ids_sha=mapped_entropy(st["library"],st["archive"],st["sidecar"],offsets,CORPUS_BYTES)
            native=st["state"]["capabilities"]["batch"]=="available"
            mode="batch" if native else "loop"
            cmd=[a.worker,st["library"],st["archive"],a.input.resolve(),st["sidecar"],
                 (a.traces/p["trace"]).resolve(),N,mode]
            cp=subprocess.run([str(x) for x in cmd],env=st["reader_env"],text=True,
                              capture_output=True,check=True,timeout=1800)
            stats,points=parse_worker(cp.stdout,native)
            raw=a.out/"raw"/f'{p["profile"]}-{label}.jsonl'
            raw.write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in points))
            for path,v in st["artifacts"].items():
                if file_hash(path)!=v["sha256"]:raise ValueError("reader modified archive")
            row={
                "profile":p["profile"],
                "H_alpha_bits":p["H_alpha_bits"],
                "target_bits":p["target_bits"],
                "codec":label,
                "codec_H_alpha_bits":h,
                "distinct_codec_start_blocks":distinct,
                "block_ids_sha256":ids_sha,
                "trace_sha256":p["trace_sha256"],
                "requests":N,"request_bytes":R,"workers":1,
                "loop_ranges_s":stats["loop_ranges_s"],
                "batch_ranges_s":stats.get("batch_ranges_s"),
                "batch_speedup":stats.get("batch_speedup"),
                "native_batch_available":native,
                "native_batch_reason":None if native else st["state"]["capabilities"]["batch"].removeprefix("n/a — "),
                "raw_samples":str(raw.relative_to(a.out)),
                "raw_sha256":file_hash(raw),
                "command":" ".join(map(str,cmd)),
                **stats,
            }
            rows.append(row)
            raw_index.append({"profile":p["profile"],"codec":label,"sha256":row["raw_sha256"]})

    ace={}
    for p in profiles:
        ace[p["profile"]]={r["codec"]:r for r in rows if r["profile"]==p["profile"] and r["codec"].startswith("aceapex-")}
    def speeds(codec):
        return [(p["H_alpha_bits"],ace[p["profile"]][codec]["batch_speedup"]) for p in profiles]
    clauses=[]
    for codec in ("aceapex-interactive","aceapex-dense"):
        vals=speeds(codec)
        monotonic=all(vals[i+1][1]>=vals[i][1] for i in range(len(vals)-1))
        endpoint=vals[-1][1]>vals[0][1]
        clauses.append(
            f'{codec}: batch/loop is '+
            ("monotonic nondecreasing" if monotonic else "not monotonic")+
            f' as H_alpha falls ({vals[0][1]:.2f}× at H={vals[0][0]:.3f} to {vals[-1][1]:.2f}× at H={vals[-1][0]:.3f}); '+
            ("the endpoint advantage grows." if endpoint else "the endpoint advantage does not grow.")
        )
    batch_answer=" ".join(clauses)

    comparisons=[]
    for p in profiles:
        d=ace[p["profile"]]["aceapex-dense"]["batch_ranges_s"]
        i=ace[p["profile"]]["aceapex-interactive"]["batch_ranges_s"]
        comparisons.append((p["H_alpha_bits"],d,i,p["profile"]))
    winners=[x for x in comparisons if x[1]>x[2]]
    if not winners:
        cross="Dense does not exceed interactive batch throughput at any measured entropy point."
    elif winners[0] is comparisons[0]:
        h,d,i,name=winners[0]
        cross=f'Dense already exceeds interactive at the highest measured entropy point, H_alpha={h:.3f} bits ({d:,.1f} vs {i:,.1f} ranges/s); no lower-entropy crossover is required by these measurements.'
    else:
        idx=comparisons.index(winners[0]);lo=comparisons[idx-1];hi=comparisons[idx]
        cross=(f'Dense first exceeds interactive at measured H_alpha={hi[0]:.3f} bits '
               f'({hi[1]:,.1f} vs {hi[2]:,.1f} ranges/s); the observed crossover is bracketed between '
               f'H_alpha={lo[0]:.3f} and {hi[0]:.3f} bits.')
    result={
        "schema":"access-entropy-sweep-v1",
        "actions_run_id":a.actions_run_id,
        "corpus":{"id":"chr1-hg38-fasta","bytes":CORPUS_BYTES,"md5":CORPUS_MD5,"sha256":file_hash(a.input)},
        "host":{
            "platform":platform.platform(),
            "machine":platform.machine(),
            "cpu":next((line.split(":",1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")),"unknown"),
            "timed_cpu":cpu,
            "available_affinity":allowed,
        },
        "workload":{"requests":N,"request_bytes":R,"workers":1,"repetitions":3},
        "entropy_axis":"measured Shannon entropy of request starts on common 16 KiB grid",
        "profiles":profiles,
        "adapters":provenance,
        "rows":rows,
        "answer":{"batch_concentration":batch_answer,"dense_vs_interactive":cross},
        "judge":"harness/native_batch.c compares every loop result byte-for-byte with original and every native-batch result with the same verified loop/original, outside timing",
        "raw_index":raw_index,
        "completed_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
        "benchmark_commit":output(["git","rev-parse","HEAD"]),
        "worker_sha256":file_hash(a.worker),
        "protocol_sha256":file_hash(ROOT/"review/access_entropy/PROTOCOL.md"),
    }
    (a.out/"results.json").write_text(json.dumps(result,indent=2)+"\n")
    (a.out/"REPORT.md").write_text(report(result))
    print((a.out/"REPORT.md").read_text())

if __name__=="__main__":
    main()
