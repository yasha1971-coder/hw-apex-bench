#!/usr/bin/env python3
"""Native S2 readers. Importing performs no build, subprocess, or measurement."""
from __future__ import annotations
import ctypes,hashlib,json,mmap,os
from pathlib import Path

class RequestView:
    def __init__(self,a,c,s,e): self.assembly,self.contig,self.start0,self.end0=a,c,s,e
    @property
    def length(self): return self.end0-self.start0

def load_map(path):
    d=json.loads(Path(path).read_text()); rows=d['contigs']; seen=set();prefix=0;out={}
    for r in rows:
        k=(r['assembly_id'],r['contig_id']);n=r['length']
        if k in seen or type(n) is not int or n<0 or r.get('prefix')!=prefix: raise ValueError('invalid canonical contig map')
        seen.add(k);out[k]=(prefix,n);prefix+=n
    if d.get('canonical_bytes')!=prefix: raise ValueError('canonical map total mismatch')
    return out,prefix

def translated_half_open(a,c,s,e): return {'assembly_id':a,'contig_id':c,'start0':s,'end0':e,'convention':'0-based-half-open'}

class RawFastaReader:
    """FASTA truth reader; parsing occurs at open, fetch is persistent in-process."""
    scope='cpu-in-process';decoder_threads=1
    def __init__(self,assembly_to_fasta):
        self.seq={}
        for a,p in assembly_to_fasta.items():
            name=None;parts=[]
            for raw in Path(p).read_bytes().splitlines():
                if raw.startswith(b'>'):
                    if name is not None:self._put(a,name,b''.join(parts).upper())
                    name=raw[1:].split()[0].decode();parts=[]
                elif raw: parts.append(raw.strip())
            if name is not None:self._put(a,name,b''.join(parts).upper())
    def _put(self,a,c,s):
        if (a,c) in self.seq: raise ValueError('duplicate contig')
        self.seq[a,c]=s
    def contig_length(self,a,c): return len(self.seq[a,c])
    def translated(self,r): return translated_half_open(r.assembly,r.contig,r.start0,r.end0)
    def fetch(self,a,c,s,e):
        q=self.seq[a,c]
        if not 0<=s<e<=len(q): raise ValueError('window outside contig')
        return q[s:e]
    def decode_sequence(self): return b''.join(self.seq[k] for k in self.seq)

class ResidentOffsetReader:
    """resident_context ABI reader over canonical sequence-byte containers."""
    scope='cpu-in-process';decoder_threads=1
    def __init__(self,library,archive,contig_map,sidecar=None):
        self.map,self.total=load_map(contig_map);self.lib=ctypes.CDLL(str(Path(library).resolve()))
        L=self.lib;L.hc_abi.restype=ctypes.c_uint;L.hc_size.argtypes=[ctypes.c_void_p];L.hc_size.restype=ctypes.c_uint64
        L.hc_open.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_uint64];L.hc_open.restype=ctypes.c_void_p
        L.hc_region.argtypes=[ctypes.c_void_p,ctypes.c_uint64,ctypes.c_void_p,ctypes.c_size_t];L.hc_region.restype=ctypes.c_int64
        L.hc_decode.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t];L.hc_decode.restype=ctypes.c_int64;L.hc_close.argtypes=[ctypes.c_void_p]
        if L.hc_abi()!=2: raise ValueError('resident ABI != 2')
        self._fh=Path(archive).open('rb');self._mm=mmap.mmap(self._fh.fileno(),0,access=mmap.ACCESS_COPY);self._buf=(ctypes.c_char*len(self._mm)).from_buffer(self._mm)
        sc=str(Path(sidecar).resolve()).encode() if sidecar else None
        self.h=L.hc_open(self._buf,len(self._mm),sc,self.total)
        if not self.h or L.hc_size(self.h)!=self.total: self.close();raise ValueError('native open/size failed')
    def contig_length(self,a,c): return self.map[a,c][1]
    def translated(self,r):
        p,n=self.map[r.assembly,r.contig]
        if not 0<=r.start0<r.end0<=n: raise ValueError('window outside contig')
        return {'assembly_id':r.assembly,'contig_id':r.contig,'offset':p+r.start0,'length':r.length,'convention':'canonical-sequence-offset'}
    def fetch(self,a,c,s,e):
        p,n=self.map[a,c]
        if not 0<=s<e<=n: raise ValueError('window outside contig')
        out=ctypes.create_string_buffer(e-s);got=self.lib.hc_region(self.h,p+s,out,e-s)
        if got!=e-s: raise ValueError('native short read')
        return out.raw
    def decode_sequence(self):
        out=ctypes.create_string_buffer(self.total);got=self.lib.hc_decode(self.h,out,self.total)
        if got!=self.total: raise ValueError('native full decode failed')
        return out.raw
    def close(self):
        if getattr(self,'h',None): self.lib.hc_close(self.h);self.h=None
        if getattr(self,'_mm',None): self._buf=None;self._mm.close();self._mm=None
        if getattr(self,'_fh',None): self._fh.close();self._fh=None
    def __del__(self):
        try:self.close()
        except Exception:pass

class BgzfReaderAdapter:
    scope='cpu-in-process';decoder_threads=1
    def __init__(self,inner,assembly_id): self.inner,self.assembly_id=inner,assembly_id
    def contig_length(self,a,c):
        if a!=self.assembly_id: raise KeyError(a)
        return self.inner.contig_length(c)
    def translated(self,r): return {'assembly_id':r.assembly,'contig_id':r.contig,'start':r.start0,'end':r.end0-1,'convention':'0-based-inclusive'}
    def fetch(self,a,c,s,e):
        if a!=self.assembly_id: raise KeyError(a)
        return self.inner.fetch(c,s,e-s)

class AgcReaderAdapter:
    scope='cpu-in-process';decoder_threads=1
    def __init__(self,inner): self.inner=inner
    def contig_length(self,a,c): return self.inner.contig_length(a,c)
    def translated(self,r): return {'assembly_id':r.assembly,'contig_id':r.contig,'start':r.start0,'end':r.end0-1,'convention':'0-based-inclusive'}
    def fetch(self,a,c,s,e): return self.inner.fetch(a,c,s,e-s)

# Registry is declarative: no missing tool silently falls back to a process.
VARIANTS=('refrel3-q4k','refrel3-q16k','bgzf-default','bgzf-matched-g','zstd-seekable','lz4-indexed','ozseg-openzl','agc-t2t','agc-noref','fasta-faidx')

class Refrel3Reader:
    scope='cpu-in-process';decoder_threads=1
    def __init__(self,library,reference,archive,assembly_id):
        self.assembly_id=assembly_id;L=self.lib=ctypes.CDLL(str(Path(library).resolve()));L.hwa_rr3_open.argtypes=[ctypes.c_char_p,ctypes.c_char_p];L.hwa_rr3_open.restype=ctypes.c_void_p;L.hwa_rr3_length.argtypes=[ctypes.c_void_p,ctypes.c_char_p];L.hwa_rr3_length.restype=ctypes.c_longlong;L.hwa_rr3_fetch.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_ulonglong,ctypes.c_ulonglong,ctypes.c_void_p,ctypes.c_size_t];L.hwa_rr3_fetch.restype=ctypes.c_longlong;L.hwa_rr3_q.argtypes=[ctypes.c_void_p];L.hwa_rr3_q.restype=ctypes.c_uint;L.hwa_rr3_close.argtypes=[ctypes.c_void_p];self.h=L.hwa_rr3_open(str(Path(reference).resolve()).encode(),str(Path(archive).resolve()).encode());
        if not self.h:raise ValueError('refrel3 native open refused')
    def contig_length(self,a,c):
        if a!=self.assembly_id:raise KeyError(a)
        n=self.lib.hwa_rr3_length(self.h,c.encode());
        if n<0:raise KeyError(c)
        return n
    def translated(self,r):return {'assembly_id':r.assembly,'contig_id':r.contig,'start':r.start0+1,'end':r.end0,'convention':'1-based-inclusive'}
    def fetch(self,a,c,s,e):
        n=self.contig_length(a,c)
        if not 0<=s<e<=n:raise ValueError('window outside contig')
        out=ctypes.create_string_buffer(e-s);got=self.lib.hwa_rr3_fetch(self.h,c.encode(),s,e,out,e-s)
        if got!=e-s:raise ValueError('refrel3 short read')
        return out.raw
    def q(self):return self.lib.hwa_rr3_q(self.h)
    def close(self):
        if self.h:self.lib.hwa_rr3_close(self.h);self.h=None

class OzsegReader:
    scope='cpu-in-process';decoder_threads=1
    def __init__(self,library,archive):
        import importlib.util
        spec=importlib.util.spec_from_file_location('ozseg_container',Path(__file__).with_name('openzl_segmented.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);self.mod=m
        self.f,self.meta,self.base=m.read_container(archive);self.lib=ctypes.CDLL(str(Path(library).resolve()));self.lib.hwa_openzl_decode.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t];self.lib.hwa_openzl_decode.restype=ctypes.c_longlong
        self.contigs={x['name']:(x['start'],x['length']) for x in self.meta['contigs']}
    def contig_length(self,a,c):return self.contigs[c][1]
    def translated(self,r):
        p,n=self.contigs[r.contig]
        if not 0<=r.start0<r.end0<=n:raise ValueError('window outside contig')
        return {'assembly_id':r.assembly,'contig_id':r.contig,'offset':p+r.start0,'length':r.length,'convention':'canonical-sequence-offset'}
    def _frame(self,i):
        x=self.meta['frames'][i];self.f.seek(self.base+x['coff']);z=self.f.read(x['clen']);src=ctypes.create_string_buffer(z);out=ctypes.create_string_buffer(x['ulen']);got=self.lib.hwa_openzl_decode(src,len(z),out,x['ulen'])
        if got!=x['ulen']:raise ValueError('OpenZL native frame decode failed')
        return out.raw
    def fetch(self,a,c,s,e):
        p,n=self.contigs[c]
        if not 0<=s<e<=n:raise ValueError('window outside contig')
        lo=p+s;hi=p+e;q=self.meta['Q'];ans=bytearray()
        for i in range(lo//q,(hi-1)//q+1):
            chunk=self._frame(i);u=self.meta['frames'][i]['uoff'];ans.extend(chunk[max(lo,u)-u:min(hi,u+len(chunk))-u])
        return bytes(ans)
    def decode_sequence(self):return b''.join(self._frame(i) for i in range(len(self.meta['frames'])))
    def close(self):self.f.close()

class IndexedLz4Reader:
    scope='cpu-in-process';decoder_threads=1
    def __init__(self,library,archive,index):
        self.arc=Path(archive).read_bytes();d=json.loads(Path(index).read_text());self.map={};prefix=0
        for c in d['contigs']:
            if c['prefix']!=prefix:raise ValueError('bad LZ4 contig prefix')
            self.map[c['assembly_id'],c['contig_id']]=(prefix,c['length']);prefix+=c['length']
        self.frames=d['frames'];self.total=prefix;self.lib=ctypes.CDLL(str(Path(library).resolve()));self.lib.hwa_lz4_block.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_int];self.lib.hwa_lz4_block.restype=ctypes.c_longlong;self.lib.hwa_lz4_version.restype=ctypes.c_char_p
        if self.lib.hwa_lz4_version().decode()!='1.10.0':raise ValueError('LZ4 runtime != retained v1.10.0 receipt')
    def contig_length(self,a,c):return self.map[a,c][1]
    def translated(self,r):p,n=self.map[r.assembly,r.contig];return {'assembly_id':r.assembly,'contig_id':r.contig,'offset':p+r.start0,'length':r.length,'convention':'canonical-sequence-offset'}
    def _frame(self,x):
        z=self.arc[x['coff']:x['coff']+x['clen']];src=ctypes.create_string_buffer(z);out=ctypes.create_string_buffer(x['ulen']);got=self.lib.hwa_lz4_block(src,len(z),out,x['ulen'])
        if got!=x['ulen']:raise ValueError('LZ4 block decode failed')
        return out.raw
    def fetch(self,a,c,s,e):
        p,n=self.map[a,c]
        if not 0<=s<e<=n:raise ValueError('window outside contig')
        lo=p+s;hi=p+e;ans=bytearray()
        for x in self.frames:
            u=x['uoff'];v=u+x['ulen']
            if v<=lo:continue
            if u>=hi:break
            q=self._frame(x);ans.extend(q[max(lo,u)-u:min(hi,v)-u])
        if len(ans)!=e-s:raise ValueError('LZ4 short read')
        return bytes(ans)
    def decode_sequence(self):return b''.join(self._frame(x) for x in self.frames)
