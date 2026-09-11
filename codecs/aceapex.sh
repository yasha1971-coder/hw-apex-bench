#!/usr/bin/env bash
set -euo pipefail
: "${CABENCH_ROOT:=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
source "$CABENCH_ROOT/harness/adapter_common.sh"

codec_name() { echo 'aceapex'; }
codec_version() { echo '2.0'; }
codec_supports() { echo 'ratio decode region c_g batch h_alpha break_even'; }
codec_unavailable() { echo '{"encode":"one-shot API writes compile-time block geometry; profile encoder not admitted; CLI compression is untimed","amplification":"native work counters not ported; historical counting harness remains separate"}'; }
codec_constraints() { echo '{"min_input_bytes":1,"min_input_reason":"upstream empty input produces no archive","granularity":16384,"compression_path":"untimed Makefile translation-unit CLI"}'; }
codec_sources() { echo '[{"url":"https://github.com/yasha1971-coder/aceapex.git","sha":"a194893b676a089e5916063d62c45e77483d2c10","directory":"aceapex"},{"url":"https://github.com/facebook/zstd.git","sha":"f8745da6ff1ad1e7bab384bd1f9d742439278e99","directory":"zstd"}]'; }
codec_library() { echo "$CABENCH_WORK/build/aceapex/plugin.so"; }
codec_compress() {
  [[ -s "$1" ]] || { echo 'empty ACEAPEX input unsupported' >&2; return 1; }
  env ACEAPEX_BS="$3" LIT_CHUNK=65536 FSE_CHUNK=4096 MIN_MATCH=0 "$CABENCH_WORK/build/aceapex/aceapex" c --in "$1" --out "$2" --threads 1 --level 2
}
codec_build() {
  local a="$CABENCH_WORK/deps/aceapex" z="$CABENCH_WORK/deps/zstd" b="$CABENCH_WORK/build/aceapex"
  mkdir -p "$b"
  cb_checkout https://github.com/yasha1971-coder/aceapex.git a194893b676a089e5916063d62c45e77483d2c10 "$a"
  cb_checkout https://github.com/facebook/zstd.git f8745da6ff1ad1e7bab384bd1f9d742439278e99 "$z"
  make -C "$z/lib" -j"$CABENCH_JOBS" libzstd.a CFLAGS='-O2 -fPIC'
  cb_compile cxx -O2 -std=c++17 -pthread -I"$a/src" -I"$z/lib" "$a/src/aceapex_main.cpp" "$z/lib/libzstd.a" -o "$b/aceapex"
  cat > "$b/plugin.cpp" <<'C'
#include "adapter_api.h"
#include "adapter_util.h"
#include "aceapex.h"
#include <vector>
struct State { unsigned char*arc;size_t bytes;uint64_t size;uint32_t block; };
static void settings(){setenv("LIT_CHUNK","65536",1);setenv("FSE_CHUNK","4096",1);setenv("MIN_MATCH","0",1);}
static void close_state(void*p){State*s=(State*)p;if(!s)return;free(s->arc);delete s;}
static void*open_state(const char*path,uint64_t limit){
 settings();State*s=new State{};s->arc=cb_load(path,&s->bytes);
 if(!s->arc||s->bytes<68||memcmp(s->arc,"ACEPX2\0\0",8)||cb_u32(s->arc+8)!=2)goto bad;
 s->size=cb_u64(s->arc+12);s->block=cb_u32(s->arc+20);
 if(!s->block||s->size>limit||!s->size)goto bad;
 {uint64_t nb=cb_u32(s->arc+24), expected=(s->size-1)/s->block+1;
  if(nb!=expected||nb>(s->bytes-68)/64)goto bad;
  uint64_t total=68+nb*64;
  for(unsigned off=36;off<=60;off+=8){uint64_t len=cb_u64(s->arc+off);if(len>s->bytes-total)goto bad;total+=len;}
  if(total!=s->bytes)goto bad;
 }
 return s;
 bad:close_state(s);return NULL;
}
static uint64_t size_state(void*p){return ((State*)p)->size;}
static int64_t read_state(void*p,uint64_t off,void*dst,size_t n){State*s=(State*)p;if(!cb_bounds(s->size,off,n))return -1;if(!n)return 0;return aceapex_decompress_region(s->arc,s->bytes,dst,n,off,n);}
static int64_t decode(void*p,void*dst,size_t cap){State*s=(State*)p;return cap<s->size?-1:aceapex_decompress(s->arc,s->bytes,dst,cap);}
static int batch(void*p,cb_range*r,size_t n,unsigned threads){State*s=(State*)p;if(threads!=1)return -1;if(!n)return 0;std::vector<aceapex_range_t> q(n);for(size_t i=0;i<n;i++){if(!cb_bounds(s->size,r[i].offset,r[i].length))return -1;q[i]={r[i].offset,r[i].length,r[i].dst,-1};}int64_t rc=aceapex_decompress_ranges(s->arc,s->bytes,q.data(),n,threads);if(rc<0)return -1;for(size_t i=0;i<n;i++){r[i].written=q[i].written;if(q[i].written!=(int64_t)q[i].length)return -1;}return 0;}
static int block(void*p,uint64_t off,uint64_t*id){State*s=(State*)p;if(off>=s->size)return -1;*id=off/s->block;return 0;}
extern "C" const cb_api*cabench_adapter_v1(void){static const cb_api a={CB_ABI_VERSION,sizeof(cb_api),"aceapex","2.0","CLI encode=1; full decode=8 internal workers; native batch=1 requested; caller=1",CB_RATIO|CB_DECODE|CB_REGION|CB_C_G|CB_BATCH|CB_H_ALPHA|CB_BREAK_EVEN,NULL,open_state,size_state,decode,read_state,batch,block,NULL,NULL,close_state};return &a;}
C
  cb_compile cxx -O2 -std=c++17 -pthread -fPIC -shared -I"$CABENCH_ROOT/harness" -I"$a/src" -I"$z/lib" "$b/plugin.cpp" "$a/src/aceapex_api.cpp" "$z/lib/libzstd.a" -o "$b/plugin.so"
  cb_checkout https://github.com/yasha1971-coder/aceapex.git a194893b676a089e5916063d62c45e77483d2c10 "$a"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  cb_entry "$@"
  # Historical command interface, retained for recorded runs.
case "$1" in
 build)
  read -r -a cxx <<< "${CXX:-g++}"
  "${cxx[@]}" -O3 -std=c++17 -pthread -I"$2/aceapex/src" -I"$2/zstd/lib" \
    "$2/aceapex/aceapex_depth.cpp" "$2/zstd/lib/libzstd.a" -o "$2/aceapex-cli"
  ;;
 compress) "$2/aceapex-cli" c --in "$3" --out "$4" --threads 1 --level 2 --profile "$5";;
 restore) "$2/aceapex-cli" d --in "$3" --out "$4" --profile "$5";;
 *) exit 2;;
esac
fi
