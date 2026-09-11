#!/usr/bin/env python3
"""Correctness-only native plugin probe; contains no codec names or timers."""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import random
import subprocess

AXES = {'ratio','encode','decode','region','amplification','c_g','batch','h_alpha','break_even'}

def capabilities(adapter, env=None):
    supported = subprocess.check_output(['bash', str(adapter), 'supports'], text=True, env=env).split()
    missing = json.loads(subprocess.check_output(['bash', str(adapter), 'unavailable'], text=True, env=env))
    if len(set(supported)) != len(supported) or set(supported) & missing.keys():
        raise ValueError('duplicate or conflicting capability')
    if set(supported) | missing.keys() != AXES:
        raise ValueError('every axis must be supported or have a reason')
    if any(not isinstance(v,str) or not v.strip() for v in missing.values()):
        raise ValueError('n/a requires a nonempty reason')
    return {a: 'available' if a in supported else 'n/a — '+missing[a] for a in sorted(AXES)}

class Context:
    def __init__(self, library, archive, expected_size=None, sidecar=None):
        self.lib = C.CDLL(str(Path(library).resolve()))
        self.lib.hc_abi.restype = C.c_uint
        if self.lib.hc_abi() != 2:
            raise ValueError('unsupported context ABI')
        self.lib.hc_size.argtypes = [C.c_void_p]
        self.lib.hc_size.restype = C.c_uint64
        self.lib.hc_version.restype = C.c_char_p
        self.lib.hc_open.argtypes = [C.c_void_p,C.c_size_t,C.c_char_p,C.c_uint64]
        self.lib.hc_open.restype = C.c_void_p
        self.lib.hc_region.argtypes = [C.c_void_p,C.c_uint64,C.c_void_p,C.c_size_t]
        self.lib.hc_region.restype = C.c_int64
        self.lib.hc_decode.argtypes = [C.c_void_p,C.c_void_p,C.c_size_t]
        self.lib.hc_decode.restype = C.c_int64
        self.lib.hc_close.argtypes = [C.c_void_p]
        self.lib.hc_close.restype = None
        self.data = C.create_string_buffer(archive)
        self.ptr = self.lib.hc_open(self.data,len(archive),str(sidecar).encode() if sidecar else None,(1<<64)-1 if expected_size is None else expected_size)
        if not self.ptr:
            raise ValueError('archive/index rejected')
        self.size = self.lib.hc_size(self.ptr)
    def close(self):
        if self.ptr:
            self.lib.hc_close(self.ptr)
            self.ptr = None
    def region(self, offset, length):
        buf = C.create_string_buffer(b'\xa5'*(length+32),length+32)
        n = self.lib.hc_region(self.ptr,offset,C.byref(buf,16),length)
        if buf.raw[:16] != b'\xa5'*16 or buf.raw[16+length:] != b'\xa5'*16:
            raise AssertionError('destination guard overwritten')
        return n,buf.raw[16:16+length]

def probe(library, archive, original, granularity, sidecar=None):
    if granularity <= 0:
        raise ValueError('positive granularity required')
    raw = Path(original).read_bytes()
    ctx = Context(library,Path(archive).read_bytes(),sidecar=sidecar)
    try:
        if ctx.size != len(raw):
            raise AssertionError('archive-derived size differs from original')
        out = C.create_string_buffer(max(1,len(raw)))
        if ctx.lib.hc_decode(ctx.ptr,out,len(raw)) != len(raw) or out.raw[:len(raw)] != raw:
            raise AssertionError('full decode mismatch')
        cases = {(0,0),(len(raw),0),(0,len(raw))}
        for boundary in range(0,len(raw),granularity):
            for start in (max(0,boundary-1),boundary,min(len(raw),boundary+1)):
                for length in (1,17,granularity,3*granularity+7):
                    cases.add((start,min(length,len(raw)-start)))
        rng=random.Random(20260911)
        for _ in range(100):
            start=rng.randrange(len(raw)+1)
            cases.add((start,rng.randrange(min(len(raw)-start,4*granularity)+1)))
        # Deliberately alternate forwards/backwards seeks on the same context.
        ordered=sorted(cases); rng.shuffle(ordered)
        for start,length in ordered:
            n,data=ctx.region(start,length)
            if n!=length or data!=raw[start:start+length]:
                raise AssertionError(f'region mismatch at {start}+{length}')
        for start,length in ((len(raw)+1,0),(len(raw),1),((1<<64)-1,1)):
            if ctx.region(start,length)[0]>=0:
                raise AssertionError('out-of-bounds range accepted')
        return dict(version=ctx.lib.hc_version().decode(),region_checks=len(cases),
                    invalid_ranges=3,full_restore='byte-exact',
                    corpus_sha256=hashlib.sha256(raw).hexdigest(),timings_collected=False)
    finally:
        ctx.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adapter',type=Path,required=True)
    p.add_argument('--library',required=True)
    p.add_argument('--archive',required=True)
    p.add_argument('--original',required=True)
    p.add_argument('--granularity',type=int,required=True)
    p.add_argument('--sidecar')
    a=p.parse_args()
    axes=capabilities(a.adapter)
    result=probe(a.library,a.archive,a.original,a.granularity,a.sidecar)
    print(json.dumps(dict(result,capabilities=axes),sort_keys=True))
