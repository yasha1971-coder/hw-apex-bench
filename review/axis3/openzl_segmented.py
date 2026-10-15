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
    try:
        total=os.fstat(f.fileno()).st_size
        fixed=len(MAGIC)+1+8+32
        if total<fixed: raise ValueError("truncated OZSEG header")
        if f.read(len(MAGIC))!=MAGIC: raise ValueError("bad OZSEG magic")
        if f.read(1)!=bytes([VERSION]): raise ValueError("bad OZSEG version")
        n=int.from_bytes(f.read(8),"little")
        if n>total-fixed: raise ValueError("truncated OZSEG table")
        want=f.read(32);raw=f.read(n)
        if hashlib.sha256(raw).digest()!=want: raise ValueError("OZSEG table checksum mismatch")
        def unique_pairs(items):
            result={}
            for key,value in items:
                if key in result: raise ValueError("duplicate OZSEG table key")
                result[key]=value
            return result
        m=json.loads(raw,object_pairs_hook=unique_pairs)
        if not isinstance(m,dict): raise ValueError("OZSEG table must be an object")
        q=m.get("Q");size=m.get("uncompressed_bases");frames=m.get("frames")
        if type(q) is not int or q<=0 or type(size) is not int or size<0 or not isinstance(frames,list):
            raise ValueError("invalid OZSEG geometry types")
        if len(frames)!=(size+q-1)//q: raise ValueError("wrong OZSEG frame count")
        uoff=coff=0
        for frame_info in frames:
            if not isinstance(frame_info,dict): raise ValueError("invalid OZSEG index row")
            values=[frame_info.get(k) for k in ("uoff","ulen","coff","clen")]
            if any(type(v) is not int for v in values): raise ValueError("OZSEG offsets must be integers")
            u,l,c,z=values
            if u!=uoff or c!=coff or l!=min(q,size-uoff) or l<=0 or z<=0:
                raise ValueError("OZSEG gap, overlap or invalid segment length")
            uoff+=l;coff+=z
        base=fixed+n
        if uoff!=size or coff!=total-base: raise ValueError("OZSEG payload size mismatch")
        return f,m,base
    except Exception:
        f.close()
        raise
def openarc(path):
    return read_container(path)
def frame(f,m,base,i,helper,td):
    x=m["frames"][i];f.seek(base+x["coff"]);z=f.read(x["clen"])
    if len(z)!=x["clen"]: raise ValueError("short OZSEG compressed segment")
    arc=Path(td)/"a";out=Path(td)/"o";arc.write_bytes(z)
    subprocess.run([helper,"decompress",str(arc),str(out)],check=True)
    result=out.read_bytes()
    if len(result)!=x["ulen"]: raise ValueError("OZSEG decoded segment length mismatch")
    return result

def fetch(a):
    f,m,base=openarc(a.archive)
    try:
        name,span=a.region.rsplit(":",1);s,e=map(int,span.split("-"))
        matches=[x for x in m["contigs"] if x["name"]==name]
        if len(matches)!=1: raise ValueError("unknown or ambiguous OZSEG contig")
        c=matches[0]
        if not 1<=s<=e<=c["length"]: raise ValueError("window outside OZSEG contig")
        lo=c["start"]+s-1;hi=c["start"]+e;q=m["Q"];ans=bytearray()
        with tempfile.TemporaryDirectory() as td:
            for i in range(lo//q,(hi-1)//q+1):
                chunk=frame(f,m,base,i,a.helper,td);u=m["frames"][i]["uoff"]
                ans.extend(chunk[max(lo,u)-u:min(hi,u+len(chunk))-u])
        if len(ans)!=e-s+1: raise ValueError("short OZSEG window")
        view=memoryview(ans)
        while view:
            written=os.write(1,view)
            if written<=0: raise OSError("failed OZSEG stdout write")
            view=view[written:]
    finally:
        f.close()

def decode(a):
    f,m,base=openarc(a.archive)
    try:
        with open(a.output,"wb") as o, tempfile.TemporaryDirectory() as td:
            for i in range(len(m["frames"])): o.write(frame(f,m,base,i,a.helper,td))
    finally:
        f.close()

def info(a):
    f,m,base=openarc(a.archive)
    try: print(json.dumps(m))
    finally: f.close()
def main():
 ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest="op",required=True)
 p=sp.add_parser("build");p.add_argument("--helper",required=True);p.add_argument("--variant",required=True);p.add_argument("--input",required=True);p.add_argument("--output",required=True)
 p=sp.add_parser("fetch");p.add_argument("--helper",required=True);p.add_argument("--archive",required=True);p.add_argument("--region",required=True)
 p=sp.add_parser("decode");p.add_argument("--helper",required=True);p.add_argument("--archive",required=True);p.add_argument("--output",required=True)
 p=sp.add_parser("info");p.add_argument("--archive",required=True)
 a=ap.parse_args();{"build":build,"fetch":fetch,"decode":decode,"info":info}[a.op](a)
if __name__=="__main__":main()
