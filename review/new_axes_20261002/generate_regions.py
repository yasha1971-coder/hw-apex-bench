#!/usr/bin/env python3
import argparse,hashlib,json,random
from pathlib import Path
REGION_LEN=5000
COUNT=10000
SEED=20261002

class IndexedFasta:
    def __init__(self,path):
        self.path=Path(path); self.rows=[]
        fai=Path(str(path)+".fai")
        if not fai.exists(): raise SystemExit("missing FASTA index: "+str(fai))
        for line in fai.read_text().splitlines():
            name,length,offset,line_bases,line_bytes,*_=line.split("\t")
            self.rows.append((name,int(length),int(offset),int(line_bases),int(line_bytes)))
    def fetch(self,row,start0,length):
        name,n,offset,line_bases,line_bytes=row
        if start0<0 or start0+length>n: raise ValueError("region outside contig")
        out=bytearray(); p=start0
        with self.path.open("rb") as fh:
            while len(out)<length:
                line=p//line_bases; col=p%line_bases
                take=min(length-len(out),line_bases-col)
                fh.seek(offset+line*line_bytes+col)
                b=fh.read(take)
                if len(b)!=take: raise IOError("short FASTA read")
                out.extend(b); p+=take
        return bytes(out).upper()

def make_regions(fa,corpus,outdir):
    eligible=[r for r in fa.rows if r[1]>=REGION_LEN]
    spans=[r[1]-REGION_LEN+1 for r in eligible]; total=sum(spans)
    rng=random.Random(SEED); rows=[]; hashes=[]
    cumulative=[]; acc=0
    for row,span in zip(eligible,spans):
        acc+=span; cumulative.append((acc,row))
    for _ in range(COUNT):
        pick=rng.randrange(total); prev=0
        for limit,row in cumulative:
            if pick<limit:
                start0=pick-prev; start1=start0+1; end1=start1+REGION_LEN-1
                seq=fa.fetch(row,start0,REGION_LEN)
                rows.append((row[0],start1,end1)); hashes.append(hashlib.sha256(seq).hexdigest()); break
            prev=limit
    outdir.mkdir(parents=True,exist_ok=True)
    tsv=outdir/f"{corpus}-10000x5000.tsv"; sha=outdir/f"{corpus}-10000x5000.sha256.tsv"
    tsv.write_text("\n".join([f"# seed={SEED}","# prng=python-random-MT19937",f"# count={COUNT}",f"# region_length={REGION_LEN}","# coordinates=1-based-inclusive","# sampling=uniform-over-all-valid-start-positions-across-eligible-contigs","contig\tstart\tend"]+ [f"{a}\t{b}\t{c}" for a,b,c in rows])+"\n")
    sha.write_text("\n".join([f"# seed={SEED}","# digest=sha256(uppercase FASTA bases, line breaks removed)","index\tcontig\tstart\tend\tsha256"]+[f"{i}\t{a}\t{b}\t{c}\t{h}" for i,((a,b,c),h) in enumerate(zip(rows,hashes))])+"\n")
    return tsv,sha
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--fasta",type=Path,required=True);ap.add_argument("--corpus",choices=("chr1","t2t"),required=True);ap.add_argument("--outdir",type=Path,default=Path("regions"));a=ap.parse_args()
    t,s=make_regions(IndexedFasta(a.fasta),a.corpus,a.outdir)
    print(json.dumps({"regions":str(t),"regions_sha256":hashlib.sha256(t.read_bytes()).hexdigest(),"reference":str(s),"reference_sha256":hashlib.sha256(s.read_bytes()).hexdigest()},sort_keys=True))
if __name__=="__main__":main()
