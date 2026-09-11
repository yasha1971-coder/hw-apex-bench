#!/usr/bin/env python3
"""Codec-owned instrumented copies; never modify pinned dependency checkouts."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'harness'))
from build_counters import replace_once


def build(codec,work):
    work=Path(work);deps=work/'deps';dst=work/'counter-build';dst.mkdir(exist_ok=True)
    def run(*args): subprocess.run(list(map(str,args)),check=True)
    wrapper=ROOT/'codecs/native'/(codec+'.c');target=work/'counter-context.so'
    common=['gcc','-O3','-fPIC','-DHC_COUNTERS','-I'+str(ROOT/'harness')]
    hashes={}
    def record(path,text):
        hashes[str(path)]=hashlib.sha256(text.encode()).hexdigest()
    if codec=='bgzip':
        hook=dst/'count.c';hook.write_text('''#include <stdint.h>
#include <zlib.h>
#include <libdeflate.h>
static uint64_t count;
void hc_count_reset(void *ctx){(void)ctx;count=0;}
uint64_t hc_count_bytes(void *ctx){(void)ctx;return count;}
int __real_inflate(z_streamp,int);
int __wrap_inflate(z_streamp s,int flush){uLong before=s->total_out;int r=__real_inflate(s,flush);count+=s->total_out-before;return r;}
enum libdeflate_result __real_libdeflate_deflate_decompress(struct libdeflate_decompressor*,const void*,size_t,void*,size_t,size_t*);
enum libdeflate_result __wrap_libdeflate_deflate_decompress(struct libdeflate_decompressor *d,const void *in,size_t ni,void *out,size_t no,size_t *actual){size_t got=0;enum libdeflate_result r=__real_libdeflate_deflate_decompress(d,in,ni,out,no,&got);if(r==LIBDEFLATE_SUCCESS)count+=got;if(actual)*actual=got;return r;}
''')
        run(*common,'-shared','-I'+str(deps/'htslib'),'-I'+str(deps/'libdeflate'),wrapper,hook,deps/'htslib/libhts.a',work/'libdeflate-build/libdeflate.a','-Wl,--wrap=inflate','-Wl,--wrap=libdeflate_deflate_decompress','-lz','-lm','-pthread','-o',target)
        record(hook,hook.read_text())
    elif codec=='zstd_seekable':
        src=deps/'zstd';copy=dst/'zstd'
        if copy.exists(): shutil.rmtree(copy)
        shutil.copytree(src,copy,ignore=shutil.ignore_patterns('.git','obj','*.o','*.a','*.so*'))
        path=Path('lib/decompress/zstd_decompress.c');text=(src/path).read_text();record(src/path,text)
        text='#include <stdint.h>\nstatic uint64_t cabench_zstd_count;\nvoid hc_count_reset(void *p){(void)p;cabench_zstd_count=0;}\nuint64_t hc_count_bytes(void *p){(void)p;return cabench_zstd_count;}\n'+text
        for old,new in (
            ('        FORWARD_IF_ERROR(decodedSize, "Block decompression failure");','        FORWARD_IF_ERROR(decodedSize, "Block decompression failure");\n        cabench_zstd_count += decodedSize;'),
            ('            dctx->decodedSize += rSize;','            cabench_zstd_count += rSize;\n            dctx->decodedSize += rSize;')):
            text=replace_once(text,old,new)
        (copy/path).write_text(text);record(copy/path,text)
        run('make','-C',copy/'lib','-j2','libzstd.a','CFLAGS=-O3 -fPIC')
        run(*common,'-shared','-DXXH_NAMESPACE=ZSTD_','-I'+str(src/'lib'),'-I'+str(src/'lib/common'),'-I'+str(src/'contrib/seekable_format'),wrapper,src/'contrib/seekable_format/zstdseek_decompress.c',copy/'lib/libzstd.a','-pthread','-o',target)
    elif codec=='aceapex':
        src=deps/'aceapex/src';main=(src/'aceapex_main.cpp').read_text();api=(src/'aceapex_api.cpp').read_text()
        for p in (src/'aceapex_main.cpp',src/'aceapex_api.cpp'): record(p,p.read_text())
        main='#include <stdint.h>\nstatic unsigned cabench_ace_stream;\nstatic uint64_t cabench_ace_counts[4];\nextern "C" void hc_count_reset(void *p){(void)p;for(unsigned i=0;i<4;i++)cabench_ace_counts[i]=0;}\nextern "C" uint64_t hc_count_bytes(void *p){(void)p;uint64_t n=0;for(unsigned i=0;i<4;i++)n+=cabench_ace_counts[i];return n;}\n'+main
        for marker in ('            uint8_t* dst=out+(d_off-win_lo);','            uint8_t* d2=out+(off-win_lo);'):
            main=replace_once(main,marker,'            cabench_ace_counts[cabench_ace_stream] += raw;\n'+marker)
        for i,marker in enumerate(('    uint8_t* lit = lit_range(','    uint8_t* off = fse_range(','    uint8_t* len = fse_range(','    uint8_t* cmd = fse_range(')):
            api=replace_once(api,marker,f'    cabench_ace_stream={i};\n'+marker)
        for name,text in (('aceapex_main.cpp',main),('aceapex_api.cpp',api)):
            p=dst/name;p.write_text(text);record(p,text)
        run(*common,'-I'+str(src),'-c',wrapper,'-o',dst/'wrapper.o')
        run('g++','-O3','-std=c++17','-shared','-fPIC','-pthread','-I'+str(src),'-I'+str(deps/'zstd/lib'),dst/'wrapper.o',dst/'aceapex_api.cpp',deps/'zstd/lib/libzstd.a','-o',target)
    else: raise ValueError('unknown counting adapter')
    (work/'counter-sources.json').write_text(json.dumps(hashes,indent=2)+'\n')

if __name__=='__main__': build(sys.argv[1],sys.argv[2])
