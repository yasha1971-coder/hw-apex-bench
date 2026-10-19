#!/usr/bin/env python3
import argparse,csv,hashlib,json,os,random,resource,signal,subprocess,tempfile,time
from collections import Counter
from pathlib import Path

SEED=20261002
N=10000
KINDS=("bit_flip","random_bytes","zeroed_run","truncation","header","payload")

def mutation_plan(i,n):
    kind=KINDS[i % len(KINDS)]
    r=random.Random((SEED << 32) ^ i)
    if n < 2: raise ValueError("archive too small")
    def pos(lo,hi):
        if hi <= lo: return lo
        return lo + int(r.random() * (hi-lo))
    if kind=="bit_flip":
        p=pos(0,n); return kind,p,1,r.randrange(8)
    if kind=="random_bytes":
        ln=r.randint(1,16); p=pos(0,max(1,n-ln+1)); return kind,p,min(ln,n-p),None
    if kind=="zeroed_run":
        ln=r.randint(16,4096); p=pos(0,max(1,n-min(ln,n)+1)); return kind,p,min(ln,n-p),None
    if kind=="truncation":
        p=pos(0,n); return kind,p,n-p,None
    if kind=="header":
        hi=min(1024,n); p=pos(0,hi); return kind,p,1,r.randrange(8)
    p=pos(min(1024,n-1),n); return kind,p,1,r.randrange(8)

def mutate(src,i):
    b=bytearray(src); kind,p,ln,bit=mutation_plan(i,len(b)); r=random.Random((SEED << 32) ^ i ^ 0xA5A5A5A5)
    if kind in ("bit_flip","header","payload"): b[p] ^= 1 << bit
    elif kind=="random_bytes": b[p:p+ln]=bytes(r.randrange(256) for _ in range(ln))
    elif kind=="zeroed_run": b[p:p+ln]=bytes(ln)
    elif kind=="truncation": del b[p:]
    return bytes(b),kind,p,ln

def limit_memory(mib):
    def apply():
        lim=mib*1024*1024
        resource.setrlimit(resource.RLIMIT_AS,(lim,lim))
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    return apply

def render(template,archive,output,input_path=None):
    values={"{archive}":str(archive),"{output}":str(output),"{input}":str(input_path) if input_path is not None else ""}
    rendered=[]
    for arg in template:
        for key,value in values.items():
            arg=arg.replace(key,value)
        rendered.append(arg)
    return rendered

def prepare(adapter,input_path,archive):
    archive.unlink(missing_ok=True)
    cp=subprocess.run(render(adapter["compress"],archive,archive,input_path),
                      stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
    if cp.returncode < 0:
        raise SystemExit(f"compress crashed by signal {-cp.returncode}")
    if cp.returncode != 0:
        raise SystemExit("compress failed: "+cp.stderr[-2000:])
    if not archive.exists() or archive.stat().st_size == 0:
        raise SystemExit("compress produced no archive")
    version=adapter.get("version","unknown")
    vcmd=adapter.get("version_command")
    if vcmd:
        vp=subprocess.run(vcmd,text=True,capture_output=True)
        if vp.returncode != 0:
            raise SystemExit("version command failed")
        lines=(vp.stdout or vp.stderr).strip().splitlines()
        if lines: version=lines[0]
    return version

def run_case(adapter,archive,output,memory_mib):
    pre=adapter.get("preflight")
    if pre:
        cp=subprocess.run(render(pre,archive,output),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                          timeout=10,preexec_fn=limit_memory(memory_mib))
        if cp.returncode < 0: return "crash",cp.returncode,"preflight"
        if cp.returncode != 0: return "refused",cp.returncode,"preflight"
    try:
        cp=subprocess.run(render(adapter["decompress"],archive,output),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                          timeout=10,preexec_fn=limit_memory(memory_mib))
    except subprocess.TimeoutExpired:
        return "hang",None,"decode"
    if cp.returncode < 0: return "crash",cp.returncode,"decode"
    if cp.returncode != 0: return "caught",cp.returncode,"decode"
    return "ok",0,"decode"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--adapter",type=Path,required=True)
    ap.add_argument("--input",type=Path,required=True)
    ap.add_argument("--archive",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--memory-mib",type=int,default=2048)
    ap.add_argument("--cases",type=int,default=N)
    a=ap.parse_args()
    adapter=json.loads(a.adapter.read_text())
    source=a.input.read_bytes()
    a.archive.parent.mkdir(parents=True,exist_ok=True)
    version=prepare(adapter,a.input,a.archive)
    clean=a.archive.read_bytes()
    a.out.mkdir(parents=True,exist_ok=True)
    csvp=a.out/"cases.csv"; counts=Counter(); kind_counts=Counter()
    with tempfile.TemporaryDirectory(prefix="hw-corrupt-") as td, csvp.open("w",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=["case","kind","offset","length","outcome","returncode","phase"])
        w.writeheader()
        for i in range(a.cases):
            damaged,kind,off,ln=mutate(clean,i); kind_counts[kind]+=1
            arc=Path(td)/f"{i}.arc"; out=Path(td)/f"{i}.out"
            arc.write_bytes(damaged)
            if out.exists(): out.unlink()
            outcome,rc,phase=run_case(adapter,arc,out,a.memory_mib)
            if outcome=="ok":
                outcome="harmless" if out.exists() and out.read_bytes()==source else "SILENT"
            counts[outcome]+=1
            w.writerow({"case":i,"kind":kind,"offset":off,"length":ln,"outcome":outcome,"returncode":rc,"phase":phase})
            arc.unlink(missing_ok=True); out.unlink(missing_ok=True)
    summary={
      "schema":"corruption-robustness-v1","seed":SEED,"cases":a.cases,
      "codec":adapter["codec"],"version":version,"checksum_mode":adapter["checksum_mode"],
      "archive_bytes":len(clean),"archive_sha256":hashlib.sha256(clean).hexdigest(),
      "input_bytes":len(source),"input_sha256":hashlib.sha256(source).hexdigest(),
      "memory_limit_mib":a.memory_mib,"watchdog_seconds":10,
      "kind_counts":dict(kind_counts),"outcomes":dict(counts),
      "adapter":adapter,
    }
    (a.out/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,sort_keys=True))
if __name__=="__main__": main()
