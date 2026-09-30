#!/usr/bin/env python3
"""Build an instrumented copy of the modern C99 ACEAPEX decoder.

Timed libraries remain untouched. The counter increments only when a decoded
entropy chunk is actually materialized on a cache miss.
"""
import hashlib,json,subprocess,sys
from pathlib import Path

root=Path(__file__).resolve().parents[2]
work=Path(sys.argv[1])
ace=work/"deps/aceapex"
zstd=work/"deps/zstd"
out=work/"counter-context.so"
dst=work/"counter-build"
dst.mkdir(exist_ok=True)

src=(ace/"c/aceapex_decode.c").read_text()
orig=src
prefix='''\nstatic unsigned long long cabench_decoded_bytes;\nvoid hc_count_reset(void *p){(void)p;cabench_decoded_bytes=0;}\nunsigned long long hc_count_bytes(void *p){(void)p;return cabench_decoded_bytes;}\n'''
marker='#include <zstd.h>\n'
if src.count(marker)!=1: raise SystemExit("counter include marker changed")
src=src.replace(marker,marker+prefix)
old='''        if(!cur_chunk(c,i,b,raw)){ *err=ACEAPEX_ERR_DATA; return 0; }\n        c->cc[slot].idx=i; c->cc[slot].raw=raw; }'''
new='''        if(!cur_chunk(c,i,b,raw)){ *err=ACEAPEX_ERR_DATA; return 0; }\n        cabench_decoded_bytes += raw;\n        c->cc[slot].idx=i; c->cc[slot].raw=raw; }'''
if src.count(old)!=1: raise SystemExit("counter cache-miss marker changed")
src=src.replace(old,new)
patched=dst/"aceapex_decode_count.c"
patched.write_text(src)

wrapper=root/"codecs/native/aceapex_persistent.c"
version=sys.argv[2]
cmd=[
 "gcc","-O3","-std=c99","-fPIC","-shared","-pthread","-DHC_COUNTERS",
 "-I"+str(root/"harness"),"-I"+str(ace/"c"),"-I"+str(zstd/"lib"),
 f'-DHB_ACE_VERSION="{version}"',
 str(wrapper),str(patched),str(zstd/"lib/libzstd.a"),"-o",str(out)
]
subprocess.run(cmd,check=True)
hashes={
 "upstream_c_decoder_sha256":hashlib.sha256(orig.encode()).hexdigest(),
 "instrumented_c_decoder_sha256":hashlib.sha256(src.encode()).hexdigest(),
 "wrapper_sha256":hashlib.sha256(wrapper.read_bytes()).hexdigest(),
 "counter_library_sha256":hashlib.sha256(out.read_bytes()).hexdigest(),
 "instrumentation":"count decoded raw chunk bytes only on persistent-cache miss"
}
(work/"counter-sources.json").write_text(json.dumps(hashes,indent=2)+"\n")
