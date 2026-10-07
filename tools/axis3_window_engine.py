"""Protocol v1.1 single-thread in-process window judge."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib,random,re,time
from bisect import bisect_right
from typing import Callable,Protocol
SEED=20261003; WINDOW_BYTES=(1024,8192,65536); OFFICIAL_REQUEST_COUNT=10000; SHA256=re.compile('[0-9a-f]{64}')
@dataclass(frozen=True)
class Window:
    id:int; assembly:str; contig:str; start0:int; end0:int; sha256:str
    @property
    def length(self): return self.end0-self.start0
    def canonical(self): return {'assembly_id':self.assembly,'contig_id':self.contig,'start0':self.start0,'end0':self.end0,'convention':'0-based-half-open'}
class Reader(Protocol):
    scope:str; decoder_threads:int
    def fetch(self,assembly:str,contig:str,start0:int,end0:int)->bytes:...
def sample_coordinates(contigs,w,*,count=OFFICIAL_REQUEST_COUNT,seed=SEED):
    if type(w) is not int or w<=0 or type(count) is not int or count<=0: raise ValueError('positive window length and count required')
    seen=set();spans=[];eligible=[];total=0
    for assembly,name,length in contigs:
        if (assembly,name) in seen: raise ValueError('duplicate assembly/contig')
        if not assembly or not name or type(length) is not int or length<0: raise ValueError('invalid contig record')
        seen.add((assembly,name))
        if length>=w: total+=length-w+1;spans.append(total);eligible.append((assembly,name))
    if not total: raise ValueError('no contig long enough for requested W')
    rng=random.Random(seed);result=[]
    for index in range(count):
        x=rng.randrange(total);i=bisect_right(spans,x);prev=spans[i-1] if i else 0;start0=x-prev
        result.append((index,*eligible[i],start0,start0+w))
    return result
def freeze_windows(coordinates,truth):
    out=[]
    for i,a,c,s,e in coordinates:
        ans=truth.fetch(a,c,s,e)
        if type(ans) is not bytes or len(ans)!=e-s: raise ValueError('truth accessor failed')
        out.append(Window(i,a,c,s,e,hashlib.sha256(ans.upper()).hexdigest()))
    return out
def nearest_rank(v,p):
    if not v: raise ValueError('no samples')
    return sorted(v)[(p*len(v)+99)//100-1]
def run_windows(reader,requests,*,expected_count=OFFICIAL_REQUEST_COUNT,calibration=False,clock:Callable[[],int]=time.perf_counter_ns):
    if reader.scope!='cpu-in-process' or reader.decoder_threads!=1: raise ValueError('one-thread CPU in-process reader required')
    if len(requests)!=expected_count or not requests: raise ValueError('request count differs from frozen contract')
    w=requests[0].length; allowed=(1,) if calibration else WINDOW_BYTES
    if w not in allowed: raise ValueError('W outside frozen set')
    seen=set();rows=[];lat=[]
    for r in requests:
        if r.id in seen or r.start0<0 or r.end0<=r.start0 or r.length!=w or not SHA256.fullmatch(r.sha256): raise ValueError('invalid frozen request')
        seen.add(r.id)
    for r in requests:
        row={'request_id':r.id,'canonical':r.canonical(),'expected_sha256':r.sha256,'status':'FAILED'}
        try:
            row['translated']=reader.translated(r) if hasattr(reader,'translated') else r.canonical()
            t0=clock();ans=reader.fetch(r.assembly,r.contig,r.start0,r.end0);t1=clock()
            if t1<=t0 or type(ans) is not bytes: raise ValueError('bad native answer/timing')
            sha=hashlib.sha256(ans.upper()).hexdigest();row.update(elapsed_ns=t1-t0,returned_bytes=len(ans),observed_sha256=sha)
            if len(ans)!=w or sha!=r.sha256: raise ValueError('answer differs from FASTA SHA')
            row['status']='PASS';lat.append(t1-t0)
        except Exception as exc:
            row['error']=f'{type(exc).__name__}: {exc}';rows.append(row)
            return {'status':'FAILED','verified':len(lat),'p50_us':None,'p95_us':None,'p99_us':None,'windows_per_second':None},rows
        rows.append(row)
    return {'status':'PASS','kind':'c0-probe' if calibration else 'axis3-window','W_bytes':w,'verified':len(rows),'p50_us':nearest_rank(lat,50)/1000,'p95_us':nearest_rank(lat,95)/1000,'p99_us':nearest_rank(lat,99)/1000,'windows_per_second':len(rows)*1e9/sum(lat)},rows
