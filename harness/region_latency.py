#!/usr/bin/env python3
import argparse,ctypes,hashlib,json,mmap,math,subprocess,time
from pathlib import Path
def nr(xs,q): return sorted(xs)[math.ceil(q*len(xs))-1]
def load_requests(tsv,refs):
    rr=[]; hs=[]
    for line in Path(tsv).read_text().splitlines():
        if line.startswith("#") or line.startswith("contig"): continue
        a,b,c=line.split("\t"); rr.append((a,int(b),int(c)))
    for line in Path(refs).read_text().splitlines():
        if line.startswith("#") or line.startswith("index"): continue
        p=line.split("\t"); hs.append(p[4])
    if len(rr)!=10000 or len(hs)!=10000: raise SystemExit("request/reference count mismatch")
    return rr,hs
def fai(path):
    d={}
    for line in Path(str(path)+".fai").read_text().splitlines():
        n,L,o,lb,lby,*_=line.split("\t"); d[n]=(int(L),int(o),int(lb),int(lby))
    return d
def raw_span(meta,start1,end1):
    L,o,lb,lby=meta; s=start1-1; e=end1-1
    a=o+(s//lb)*lby+(s%lb); z=o+(e//lb)*lby+(e%lb)+1
    return a,z-a
def verify(seq,want):
    return len(seq)==5000 and hashlib.sha256(seq.upper()).hexdigest()==want
def ace_c99(a,reqs,hashes):
    lib=ctypes.CDLL(str(a.library)); lib.hc_open.restype=ctypes.c_void_p; lib.hc_open.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_uint64]
    lib.hc_region.restype=ctypes.c_int64; lib.hc_region.argtypes=[ctypes.c_void_p,ctypes.c_uint64,ctypes.c_void_p,ctypes.c_size_t]; lib.hc_close.argtypes=[ctypes.c_void_p]
    idx=fai(a.fasta)
    with open(a.archive,"rb") as fh:
      mm=mmap.mmap(fh.fileno(),0,access=mmap.ACCESS_READ); buf=(ctypes.c_ubyte*len(mm)).from_buffer_copy(mm)
      ctx=lib.hc_open(buf,len(mm),None,2**64-1)
      if not ctx: raise SystemExit("ACE context open failed")
      times=[]
      try:
        for (name,s,e),want in zip(reqs,hashes):
          off,n=raw_span(idx[name],s,e); out=ctypes.create_string_buffer(n)
          t=time.perf_counter_ns(); got=lib.hc_region(ctx,off,out,n); dt=time.perf_counter_ns()-t
          if got!=n: raise SystemExit("ACE region read failed")
          seq=out.raw[:n].replace(b"\n",b"").replace(b"\r",b"")[:5000]
          if not verify(seq,want): raise SystemExit("ACE region hash mismatch")
          times.append(dt/1000)
      finally: lib.hc_close(ctx)
    return times
def ace_cpp(a,reqs,hashes):
    lib=ctypes.CDLL(str(a.library)); lib.axcpp_region.restype=ctypes.c_int64
    lib.axcpp_region.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint64,ctypes.c_uint64]
    idx=fai(a.fasta)
    with open(a.archive,"rb") as fh:
      mm=mmap.mmap(fh.fileno(),0,access=mmap.ACCESS_READ); buf=(ctypes.c_ubyte*len(mm)).from_buffer_copy(mm); times=[]
      for (name,s,e),want in zip(reqs,hashes):
        off,n=raw_span(idx[name],s,e); out=ctypes.create_string_buffer(n)
        t=time.perf_counter_ns(); got=lib.axcpp_region(buf,len(mm),out,n,off,n); dt=time.perf_counter_ns()-t
        if got!=n: raise SystemExit("ACE C++ region read failed")
        seq=out.raw[:n].replace(b"\n",b"").replace(b"\r",b"")[:5000]
        if not verify(seq,want): raise SystemExit("ACE C++ region hash mismatch")
        times.append(dt/1000)
    return times
def bgzf(a,reqs,hashes):
    lib=ctypes.CDLL(str(a.library)); lib.fx_open.restype=ctypes.c_void_p; lib.fx_open.argtypes=[ctypes.c_char_p]
    lib.fx_fetch.restype=ctypes.c_int64; lib.fx_fetch.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_int64,ctypes.c_int64,ctypes.c_void_p,ctypes.c_int64]; lib.fx_close.argtypes=[ctypes.c_void_p]
    ctx=lib.fx_open(str(a.archive).encode()); out=ctypes.create_string_buffer(5000); times=[]
    if not ctx: raise SystemExit("htslib faidx open failed")
    try:
      for (name,s,e),want in zip(reqs,hashes):
        t=time.perf_counter_ns(); got=lib.fx_fetch(ctx,name.encode(),s-1,e-1,out,5000); dt=time.perf_counter_ns()-t
        if got!=5000 or not verify(out.raw[:5000],want): raise SystemExit("BGZF region hash mismatch")
        times.append(dt/1000)
    finally: lib.fx_close(ctx)
    return times
def process_mode(a,reqs,hashes):
    times=[]
    for (name,s,e),want in zip(reqs,hashes):
      region=f"{name}:{s}-{e}"; cmd=[x.replace("{archive}",str(a.archive)).replace("{region}",region) for x in a.command]
      t=time.perf_counter_ns(); cp=subprocess.run(cmd,capture_output=True); dt=time.perf_counter_ns()-t
      if cp.returncode!=0: raise SystemExit("region process failed")
      lines=cp.stdout.splitlines(); seq=b"".join(x for x in lines if not x.startswith(b">"))
      if not verify(seq,want): raise SystemExit("process region hash mismatch")
      times.append(dt/1000)
    return times
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--mode",choices=("ace-cpp-in-process","ace-c99-in-process","bgzf-in-process","process"),required=True)
    ap.add_argument("--regions",required=True);ap.add_argument("--reference",required=True);ap.add_argument("--archive",type=Path,required=True);ap.add_argument("--fasta",type=Path)
    ap.add_argument("--library",type=Path);ap.add_argument("--codec",required=True);ap.add_argument("--version",required=True);ap.add_argument("--corpus",required=True);ap.add_argument("--command",nargs="+")
    ap.add_argument("--out",type=Path,required=True);a=ap.parse_args(); reqs,hs=load_requests(a.regions,a.reference)
    if a.mode=="ace-cpp-in-process": xs=ace_cpp(a,reqs,hs)
    elif a.mode=="ace-c99-in-process": xs=ace_c99(a,reqs,hs)
    elif a.mode=="bgzf-in-process": xs=bgzf(a,reqs,hs)
    else: xs=process_mode(a,reqs,hs)
    r={"schema":"single-region-latency-v1","codec":a.codec,"version":a.version,"corpus":a.corpus,"mode":a.mode,"device":"CPU","samples":len(xs),"region_bases":5000,"p50_us":nr(xs,.50),"p95_us":nr(xs,.95),"p99_us":nr(xs,.99),"bit_perfect":True}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,indent=2)+"\n");print(json.dumps(r))
if __name__=="__main__":main()
