#!/usr/bin/env bash
set -euo pipefail
: "${CABENCH_ROOT:=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
source "$CABENCH_ROOT/harness/adapter_common.sh"

codec_name() { echo 'zstd-seekable'; }
codec_version() { echo '1.5.7'; }
codec_supports() { echo 'ratio encode decode region c_g h_alpha break_even'; }
codec_unavailable() { echo '{"amplification":"native work counters not ported; historical counting harness remains separate","batch":"no native batch API"}'; }
codec_sources() { echo '[{"url":"https://github.com/facebook/zstd.git","sha":"f8745da6ff1ad1e7bab384bd1f9d742439278e99","directory":"zstd"}]'; }
codec_library() { echo "$CABENCH_WORK/build/zstd_seekable/plugin.so"; }
codec_build() {
  local z="$CABENCH_WORK/deps/zstd" b="$CABENCH_WORK/build/zstd_seekable"
  mkdir -p "$b"
  cb_checkout https://github.com/facebook/zstd.git f8745da6ff1ad1e7bab384bd1f9d742439278e99 "$z"
  make -C "$z/lib" -j"$CABENCH_JOBS" libzstd.a CFLAGS='-O2 -fPIC'
  cat > "$b/plugin.c" <<'C'
#include "adapter_api.h"
#include "adapter_util.h"
#include "zstd_seekable.h"
typedef struct { unsigned char *arc; size_t bytes; uint64_t size; ZSTD_seekable *zs; } State;
static void close_state(void *p){State*s=p;if(!s)return;ZSTD_seekable_free(s->zs);free(s->arc);free(s);}
static int encode(const void*src,size_t n,const char*path,size_t g,unsigned threads){
 if(!g||g>UINT32_MAX||threads!=1)return -1;
 ZSTD_seekable_CStream *z=ZSTD_seekable_createCStream();if(!z)return -1;
 size_t r=ZSTD_seekable_initCStream(z,3,1,(unsigned)g);FILE*f=NULL;int rc=-1;
 if(ZSTD_isError(r))goto done;f=fopen(path,"wb");if(!f)goto done;
 unsigned char buf[131072];ZSTD_inBuffer in={src,n,0};
 while(in.pos<in.size){ZSTD_outBuffer out={buf,sizeof(buf),0};r=ZSTD_seekable_compressStream(z,&out,&in);if(ZSTD_isError(r)||fwrite(buf,1,out.pos,f)!=out.pos)goto done;}
 do{ZSTD_outBuffer out={buf,sizeof(buf),0};r=ZSTD_seekable_endStream(z,&out);if(ZSTD_isError(r)||fwrite(buf,1,out.pos,f)!=out.pos)goto done;}while(r);
 rc=0;
 done:if(f&&fclose(f))rc=-1;ZSTD_seekable_freeCStream(z);return rc;
}
static void *open_state(const char *path,uint64_t limit){
 State*s=calloc(1,sizeof(*s));if(!s)return NULL;s->arc=cb_load(path,&s->bytes);if(!s->arc)goto bad;
 s->zs=ZSTD_seekable_create();if(!s->zs||ZSTD_isError(ZSTD_seekable_initBuff(s->zs,s->arc,s->bytes)))goto bad;
 unsigned n=ZSTD_seekable_getNumFrames(s->zs);
 if(n){uint64_t off=ZSTD_seekable_getFrameDecompressedOffset(s->zs,n-1);size_t last=ZSTD_seekable_getFrameDecompressedSize(s->zs,n-1);if(ZSTD_isError(last)||off>limit||last>limit-off)goto bad;s->size=off+last;}
 return s;
 bad:close_state(s);return NULL;
}
static uint64_t size_state(void*p){return ((State*)p)->size;}
static int64_t read_state(void*p,uint64_t off,void*dst,size_t n){State*s=p;if(!cb_bounds(s->size,off,n))return -1;if(!n)return 0;size_t r=ZSTD_seekable_decompress(s->zs,dst,n,off);return ZSTD_isError(r)?-1:(int64_t)r;}
static int64_t decode(void*p,void*dst,size_t cap){State*s=p;return cap<s->size?-1:read_state(p,0,dst,s->size);}
static int block(void*p,uint64_t off,uint64_t*id){State*s=p;if(off>=s->size)return -1;unsigned i=ZSTD_seekable_offsetToFrameIndex(s->zs,off);if(i>=ZSTD_seekable_getNumFrames(s->zs))return -1;*id=i;return 0;}
const cb_api*cabench_adapter_v1(void){static cb_api a={CB_ABI_VERSION,sizeof(cb_api),"zstd-seekable",NULL,"encode=1; decode=1; caller=1",CB_RATIO|CB_ENCODE|CB_DECODE|CB_REGION|CB_C_G|CB_H_ALPHA|CB_BREAK_EVEN,encode,open_state,size_state,decode,read_state,NULL,block,NULL,NULL,close_state};a.version=ZSTD_versionString();return &a;}
C
  cb_compile c -O2 -fPIC -shared -DXXH_NAMESPACE=ZSTD_ -I"$CABENCH_ROOT/harness" -I"$z/lib" -I"$z/lib/common" -I"$z/contrib/seekable_format" "$b/plugin.c" "$z/contrib/seekable_format/zstdseek_compress.c" "$z/contrib/seekable_format/zstdseek_decompress.c" "$z/lib/libzstd.a" -pthread -o "$b/plugin.so"
  cb_checkout https://github.com/facebook/zstd.git f8745da6ff1ad1e7bab384bd1f9d742439278e99 "$z"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  cb_entry "$@"
  # Historical command interface, retained for recorded runs.
case "$1" in
 build)
  make -C "$2/zstd" -j"$3"
  make -C "$2/zstd/contrib/seekable_format/examples" seekable_compression
  ;;
 compress) "$2/zstd/contrib/seekable_format/examples/seekable_compression" "$3" 16384 3;;
 restore) "$2/zstd/programs/zstd" -d -c "$3";;
 *) exit 2;;
esac
fi
