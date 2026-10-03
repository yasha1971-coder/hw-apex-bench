#!/usr/bin/env python3
import argparse,hashlib,json,random
from pathlib import Path
SEED=20261003
COUNT=10000
def read_manifest(p):
    rows=[]
    for line in Path(p).read_text().splitlines():
        if not line or line.startswith("#") or line.startswith("assembly_id"): continue
        q=line.split("\t"); rows.append({"id":q[0],"fasta":Path(q[1]),"sha256":q[2] if len(q)>2 else ""})
    return rows
def fai(path):
    rows=[]
    for line in Path(str(path)+".fai").read_text().splitlines():
        n,L,o,lb,lby,*_=line.split("\t"); rows.append((n,int(L),int(o),int(lb),int(lby)))
    return rows
def fetch(path,row,s,n):
    name,L,o,lb,lby=row; out=bytearray(); p=s
    with Path(path).open("rb") as fh:
      while len(out)<n:
        li=p//lb; col=p%lb; take=min(n-len(out),lb-col); fh.seek(o+li*lby+col); out+=fh.read(take); p+=take
    return bytes(out).upper()
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--manifest",required=True);ap.add_argument("--n",required=True);ap.add_argument("--window",type=int,required=True);ap.add_argument("--out-prefix",required=True);a=ap.parse_args()
    rows=read_manifest(a.manifest); n=len(rows) if a.n=="all" else int(a.n); rows=rows[:n]
    spans=[];total=0
    for asm in rows:
      for r in fai(asm["fasta"]):
        if r[1]>=a.window: total+=r[1]-a.window+1; spans.append((total,asm,r))
    rng=random.Random(SEED); req=[]; refs=[]
    for i in range(COUNT):
      x=rng.randrange(total); prev=0
      for lim,asm,r in spans:
        if x<lim:
          s0=x-prev; s1=s0+1;e=s1+a.window-1; seq=fetch(asm["fasta"],r,s0,a.window)
          req.append((asm["id"],r[0],s1,e));refs.append(hashlib.sha256(seq).hexdigest());break
        prev=lim
    p=Path(a.out_prefix);p.parent.mkdir(parents=True,exist_ok=True)
    rq=Path(str(p)+".tsv");rh=Path(str(p)+".sha256.tsv")
    rq.write_text(f"# seed={SEED}\n# count={COUNT}\n# window={a.window}\nassembly_id\tcontig\tstart\tend\n"+"\n".join("\t".join(map(str,x)) for x in req)+"\n")
    rh.write_text("# digest=sha256(uppercase FASTA bases, line breaks removed)\nindex\tassembly_id\tcontig\tstart\tend\tsha256\n"+"\n".join(f"{i}\t{a0}\t{c}\t{s}\t{e}\t{h}" for i,((a0,c,s,e),h) in enumerate(zip(req,refs)))+"\n")
    print(json.dumps({"requests_sha256":hashlib.sha256(rq.read_bytes()).hexdigest(),"references_sha256":hashlib.sha256(rh.read_bytes()).hexdigest()}))
if __name__=="__main__":main()
