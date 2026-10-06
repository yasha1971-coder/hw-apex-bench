"""Single-thread, in-process window judge. No work runs on import.

A reader is a persistent object exposing fetch(assembly,contig,start1,end1).
Requests and truth SHA are frozen before this engine is invoked. Timings contain
only the reader call; length and SHA checks are outside that interval, on every
answer. No subprocess fallback is allowed for an in-process row.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import math
import random
import re
import time
from bisect import bisect_right
from typing import Callable, Protocol

SEED = 20261003
WINDOW_BYTES = (1024, 8192, 65536)
OFFICIAL_REQUEST_COUNT = 10000
SHA256 = re.compile('[0-9a-f]{64}')

@dataclass(frozen=True)
class Window:
    id: int
    assembly: str
    contig: str
    start: int
    end: int
    sha256: str

    @property
    def length(self): return self.end - self.start + 1


class Reader(Protocol):
    scope: str
    decoder_threads: int
    def fetch(self, assembly: str, contig: str, start1: int, end1: int) -> bytes: ...


def sample_coordinates(contigs: list[tuple[str,str,int]], w: int, *, count=OFFICIAL_REQUEST_COUNT,
                       seed=SEED):
    if type(w) is not int or w <= 0 or type(count) is not int or count <= 0:
        raise ValueError('positive window length and count required')
    seen=set(); spans=[];eligible=[];total=0
    for assembly,name,length in contigs:
        if (assembly,name) in seen: raise ValueError('duplicate assembly/contig')
        if not assembly or not name or type(length) is not int or length<0:
            raise ValueError('invalid contig record')
        seen.add((assembly,name))
        if length >= w:
            total += length - w + 1
            spans.append(total);eligible.append((assembly,name))
    if not total: raise ValueError('no contig long enough for requested W')
    rng=random.Random(seed);result=[]
    for index in range(count):
        x=rng.randrange(total);i=bisect_right(spans,x);prev=spans[i-1] if i else 0
        start=x-prev+1
        result.append((index,*eligible[i],start,start+w-1))
    return result


def freeze_windows(coordinates, truth: Reader):
    result=[]
    for index,assembly,contig,start,end in coordinates:
        answer=truth.fetch(assembly,contig,start,end)
        if type(answer) is not bytes or len(answer)!=end-start+1:
            raise ValueError('truth accessor failed')
        result.append(Window(index,assembly,contig,start,end,hashlib.sha256(answer.upper()).hexdigest()))
    return result


def nearest_rank(values, percent):
    if not values: raise ValueError('no samples')
    return sorted(values)[(percent*len(values)+99)//100 - 1]


def run_windows(reader: Reader, requests: list[Window], *, expected_count=OFFICIAL_REQUEST_COUNT,
                clock: Callable[[],int] = time.perf_counter_ns):
    if reader.scope!='cpu-in-process' or reader.decoder_threads!=1:
        raise ValueError('one-thread CPU in-process reader required')
    if len(requests)!=expected_count or not requests:
        raise ValueError('request count differs from frozen contract')
    w=requests[0].length
    if w not in WINDOW_BYTES: raise ValueError('W is outside the frozen set')
    seen=set()
    for r in requests:
        if r.id in seen or type(r.start) is not int or type(r.end) is not int or r.start<1 or r.length!=w:
            raise ValueError('invalid or duplicate frozen request')
        if not SHA256.fullmatch(r.sha256): raise ValueError('invalid truth digest')
        seen.add(r.id)
    rows=[];latencies=[]
    for r in requests:
        row={'request_id':r.id,'assembly':r.assembly,'contig':r.contig,'start':r.start,'end':r.end,
             'expected_sha256':r.sha256,'status':'FAILED'}
        try:
            start=clock();answer=reader.fetch(r.assembly,r.contig,r.start,r.end);stop=clock()
            if stop<=start: raise ValueError('non-positive elapsed time')
            if type(answer) is not bytes: raise TypeError('reader returned non-bytes')
            sha=hashlib.sha256(answer.upper()).hexdigest()
            row.update(elapsed_ns=stop-start,returned_bytes=len(answer),observed_sha256=sha)
            if len(answer)!=w or sha!=r.sha256: raise ValueError('answer differs from FASTA SHA')
            row['status']='PASS';latencies.append(stop-start)
        except Exception as exc:
            row['error']=f'{type(exc).__name__}: {exc}'
            rows.append(row)
            return {'status':'FAILED','expected':len(requests),'attempted':len(rows),'verified':len(latencies),
                    'p50_us':None,'p95_us':None,'p99_us':None,'windows_per_second':None},rows
        rows.append(row)
    return {'status':'PASS','expected':len(requests),'attempted':len(rows),'verified':len(rows),
            'W_bytes':w,'threads':1,'scope':'cpu-in-process',
            'p50_us':nearest_rank(latencies,50)/1000,'p95_us':nearest_rank(latencies,95)/1000,
            'p99_us':nearest_rank(latencies,99)/1000,
            'windows_per_second':len(rows)*1e9/sum(latencies)},rows
