#!/usr/bin/env python3
import argparse,hashlib,json,os,subprocess,tempfile
from pathlib import Path

MAGIC = bytes.fromhex("4f5a534547310a")
VERSION = 1
assert MAGIC == bytes.fromhex("4f5a534547310a") and len(MAGIC) == 7

def cfg(v):
 d={"l1_w64k":(1,16,65536),"l1_w1m":(1,20,1048576),"l3_w64k":(3,16,65536),"l3_w1m":(3,20,1048576)}
 if v not in d: raise SystemExit("bad variant")
 return d[v]
def iter_fasta(path):
    name=None; parts=[]
    with open(path,"rb") as fh:
        for raw in fh:
            if raw.startswith(b">"):
                if name is not None: yield name,b"".join(parts).upper()
                name=raw[1:].split()[0].decode();parts=[]
            else: parts.append(raw.strip())
    if name is not None: yield name,b"".join(parts).upper()
def build(a):
    level,wlog,q=cfg(a.variant);contigs=[];frames=[];data=bytearray();global_off=0;pending=bytearray()
    with tempfile.TemporaryDirectory() as td:
      src=Path(td)/"in";arc=Path(td)/"out"
      def emit(buf):
        nonlocal global_off
        src.write_bytes(buf);cp=subprocess.run([a.helper,"compress",str(level),str(wlog),str(src),str(arc)],capture_output=True,text=True)
        if cp.returncode: raise SystemExit(cp.stderr)
        z=arc.read_bytes();frames.append({"uoff":global_off,"ulen":len(buf),"coff":len(data),"clen":len(z)});data.extend(z);global_off+=len(buf)
      logical=0
      for name,seq in iter_fasta(a.input):
        contigs.append({"name":name,"start":logical,"length":len(seq)});logical+=len(seq);pending.extend(seq)
        while len(pending)>=q: emit(bytes(pending[:q]));del pending[:q]
      if pending: emit(bytes(pending))
    meta={"schema":"openzl-segmented-v1","variant":a.variant,"level":level,"windowLog":wlog,"lz_window_bytes":1<<wlog,"Q":q,"uncompressed_bases":logical,"contigs":contigs,"frames":frames}
    m=json.dumps(meta,separators=(",",":"),sort_keys=True).encode()
    table_sha=hashlib.sha256(m).digest()
    write_container(a.output,m,data)
def write_container(path,table_bytes,payload):
    table_sha=hashlib.sha256(table_bytes).digest()
    Path(path).write_bytes(MAGIC+bytes([VERSION])+len(table_bytes).to_bytes(8,"little")+table_sha+table_bytes+payload)
def read_container(path):
    f=open(path,"rb")
    magic=f.read(len(MAGIC))
    if magic!=MAGIC: raise ValueError(f"bad OZSEG magic: {magic!r}")
    version=f.read(1)
    if version!=bytes([VERSION]): raise ValueError(f"bad OZSEG version: {version!r}")
    n=int.from_bytes(f.read(8),"little")
    want=f.read(32);raw=f.read(n);got=hashlib.sha256(raw).digest()
    if got!=want: raise ValueError("OZSEG table checksum mismatch")
    return f,json.loads(raw),len(MAGIC)+1+8+32+n
def openarc(path):
    return read_container(path)
def frame(f,m,base,i,helper,td):
 x=m["frames"][i];f.seek(base+x["coff"]);z=f.read(x["clen"]);arc=Path(td)/"a";out=Path(td)/"o";arc.write_bytes(z)
 subprocess.run([helper,"decompress",str(arc),str(out)],check=True);return out.read_bytes()
def fetch(a):
 f,m,base=openarc(a.archive); name,span=a.region.split(":");s,e=map(int,span.split("-")); c=next(x for x in m["contigs"] if x["name"]==name)
 lo=c["start"]+s-1;hi=c["start"]+e; q=m["Q"]; ans=bytearray()
 with tempfile.TemporaryDirectory() as td:
  for i in range(lo//q,(hi-1)//q+1):
   b=frame(f,m,base,i,a.helper,td);u=m["frames"][i]["uoff"];ans+=b[max(lo,u)-u:min(hi,u+len(b))-u]
 os.write(1,bytes(ans))
def decode(a):
 f,m,base=openarc(a.archive)
 with open(a.output,"wb") as o, tempfile.TemporaryDirectory() as td:
  for i in range(len(m["frames"])): o.write(frame(f,m,base,i,a.helper,td))
def info(a):
 f,m,base=openarc(a.archive);print(json.dumps(m))
def main():
 ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest="op",required=True)
 p=sp.add_parser("build");p.add_argument("--helper",required=True);p.add_argument("--variant",required=True);p.add_argument("--input",required=True);p.add_argument("--output",required=True)
 p=sp.add_parser("fetch");p.add_argument("--helper",required=True);p.add_argument("--archive",required=True);p.add_argument("--region",required=True)
 p=sp.add_parser("decode");p.add_argument("--helper",required=True);p.add_argument("--archive",required=True);p.add_argument("--output",required=True)
 p=sp.add_parser("info");p.add_argument("--archive",required=True)
 a=ap.parse_args();{"build":build,"fetch":fetch,"decode":decode,"info":info}[a.op](a)
if __name__=="__main__":main()
