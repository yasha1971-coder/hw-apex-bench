#!/usr/bin/env python3
import argparse,bisect,collections,hashlib,json,math,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"harness"))
from access_profiles import RNG,LENGTH,SEED,traces as historical_traces,entropy

N=5000
POINTS=(
    ("uniform",None,12.0),
    ("zipf-h8",1.089,8.0),
    ("zipf-h4",1.555,4.0),
    ("zipf-h2",2.163,2.0),
)

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def zipf_offsets(size,alpha):
    end=size-LENGTH
    blocks=end//LENGTH+1
    weights=[(i+1)**(-alpha) for i in range(blocks)]
    total=math.fsum(weights)
    cumulative=[];c=0.0
    for w in weights:
        c+=w/total
        cumulative.append(c)
    cumulative[-1]=1.0
    r=RNG(SEED+3)
    out=[]
    for _ in range(N):
        b=bisect.bisect_right(cumulative,r.uniform())
        off=b*LENGTH
        out.append(off+r.below(min(LENGTH,end-off+1)))
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--size",type=int,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    if a.size < 1024*1024+LENGTH:
        raise SystemExit("corpus too small")
    a.out.mkdir(parents=True,exist_ok=False)
    old,_=historical_traces(a.size)
    rows=[]
    for name,alpha,target in POINTS:
        offsets=old["uniform",N] if name=="uniform" else zipf_offsets(a.size,alpha)
        h=entropy(offsets,LENGTH)
        if abs(h-target)>0.15:
            raise RuntimeError(f"{name}: measured H={h:.6f} outside target band around {target}")
        counts=collections.Counter(x//LENGTH for x in offsets)
        path=a.out/(name+".ranges")
        path.write_text("".join(f"{x} {LENGTH}\n" for x in offsets))
        rows.append({
            "profile":name,
            "target_bits":target,
            "zipf_alpha":alpha,
            "H_alpha_bits":h,
            "distinct_16k_start_blocks":len(counts),
            "trace":path.name,
            "trace_sha256":sha(path),
            "requests":N,
            "request_bytes":LENGTH,
            "seed":SEED if name=="uniform" else SEED+3,
        })
    (a.out/"profiles.json").write_text(json.dumps({
        "schema":"access-entropy-traces-v1",
        "entropy_definition":"Shannon entropy of request-start counts on the common 16 KiB grid",
        "profiles":rows,
    },indent=2)+"\n")
    for row in rows:
        print(json.dumps(row,sort_keys=True))

if __name__=="__main__":
    main()
