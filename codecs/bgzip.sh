#!/usr/bin/env bash
set -euo pipefail
: "${CABENCH_ROOT:=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
source "$CABENCH_ROOT/harness/adapter_common.sh"

codec_name() { echo 'bgzip+htslib'; }
codec_version() { echo '1.24'; }
codec_supports() { echo 'ratio encode decode region h_alpha break_even'; }
codec_unavailable() { echo '{"amplification":"native work counters not ported; historical counting harness remains separate","c_g":"no comparable one-block BGZF baseline above the format limit","batch":"no native batch API"}'; }
codec_sources() { echo '[{"url":"https://github.com/samtools/htslib.git","sha":"4b705e4fada8ee2b6b15746f725ee8ac51631803","directory":"htslib"}]'; }
codec_library() { echo "$CABENCH_WORK/build/bgzip/plugin.so"; }
codec_artifacts() { python3 -c 'import json,sys; print(json.dumps([sys.argv[1],sys.argv[1]+".gzi"]))' "$1"; }
codec_build() {
  local h="$CABENCH_WORK/deps/htslib" b="$CABENCH_WORK/build/bgzip"
  mkdir -p "$b"
  cb_checkout https://github.com/samtools/htslib.git 4b705e4fada8ee2b6b15746f725ee8ac51631803 "$h"
  git -C "$h" submodule update --init --depth 1
  # Generated build configuration: zlib-only, no optional HTTP/CRAM codecs.
  # Tracked dependency sources remain unchanged.
  if [[ ! -f "$h/.cabench-zlib-only" ]]; then
    make -C "$h" clean
    printf '%s\n' '#define _XOPEN_SOURCE 700' '#define HAVE_DRAND48 1' > "$h/config.h"
    printf '%s\n' 'LIBS = -lz -lm -lpthread' 'HTS_LIBS = -lz -lm -lpthread' > "$h/config.mk"
    touch "$h/.cabench-zlib-only"
  fi
  make -C "$h" -j"$CABENCH_JOBS" lib-static CFLAGS='-O2 -fPIC' PACKAGE_VERSION=1.24
  cat > "$b/plugin.c" <<'C'
#define _GNU_SOURCE
#include "adapter_api.h"
#include "adapter_util.h"
#include <unistd.h>
#include <sys/mman.h>
#include <htslib/bgzf.h>
#include <htslib/hts.h>
typedef struct { BGZF *fp; uint64_t size; uint64_t *starts; size_t blocks; } State;
static void close_state(void *p){State *s=p;if(!s)return;if(s->fp)bgzf_close(s->fp);free(s->starts);free(s);}
static int encode(const void *src,size_t n,const char *path,size_t g,unsigned threads){
 if(!g||g>65536||threads!=1)return -1;size_t step=g<BGZF_BLOCK_SIZE?g:BGZF_BLOCK_SIZE;
 BGZF *f=bgzf_open(path,"w6");if(!f)return -1;
 int rc=bgzf_index_build_init(f);
 for(size_t p=0;!rc&&p<n;){size_t len=n-p<step?n-p:step;if(bgzf_write(f,(const char*)src+p,len)!=(ssize_t)len||bgzf_flush(f))rc=-1;p+=len;}
 if(!rc)rc=bgzf_index_dump(f,path,".gzi");if(bgzf_close(f))rc=-1;return rc;
}
static void *open_state(const char *path,uint64_t limit){
 size_t n;unsigned char *a=cb_load(path,&n);if(!a)return NULL;
 State *s=calloc(1,sizeof(*s));if(!s){free(a);return NULL;}
 s->starts=malloc((n/26+1)*sizeof(uint64_t));if(!s->starts)goto bad;
 for(size_t p=0;p<n;){
  if(n-p<26||a[p]!=31||a[p+1]!=139||a[p+2]!=8||a[p+12]!='B'||a[p+13]!='C')goto bad;
  size_t b=(size_t)a[p+16]+((size_t)a[p+17]<<8)+1;
  if(b<26||b>n-p)goto bad;uint32_t u=cb_u32(a+p+b-4);
  if(u>65536||u>limit-s->size)goto bad;
  if(u){s->starts[s->blocks++]=s->size;s->size+=u;}p+=b;
 }
 int fd=memfd_create("cabench-bgzf",MFD_CLOEXEC);if(fd<0)goto bad;
 for(size_t p=0;p<n;){ssize_t w=write(fd,a+p,n-p);if(w<=0){close(fd);goto bad;}p+=(size_t)w;}
 if(lseek(fd,0,SEEK_SET)<0){close(fd);goto bad;}
 s->fp=bgzf_dopen(fd,"r");if(!s->fp){close(fd);goto bad;}
 if(bgzf_index_load(s->fp,path,".gzi"))goto bad;
 free(a);return s;
 bad:free(a);close_state(s);return NULL;
}
static uint64_t size_state(void *p){return ((State*)p)->size;}
static int64_t read_state(void *p,uint64_t off,void *dst,size_t n){State *s=p;if(!cb_bounds(s->size,off,n))return -1;if(!n)return 0;if(bgzf_useek(s->fp,off,SEEK_SET))return -1;return bgzf_read(s->fp,dst,n);}
static int64_t decode(void *p,void *dst,size_t cap){State*s=p;return cap<s->size?-1:read_state(p,0,dst,s->size);}
static int block(void *p,uint64_t off,uint64_t *id){State*s=p;if(off>=s->size)return -1;size_t lo=0,hi=s->blocks;while(lo+1<hi){size_t m=lo+(hi-lo)/2;if(s->starts[m]<=off)lo=m;else hi=m;}*id=lo;return 0;}
const cb_api *cabench_adapter_v1(void){static cb_api a={CB_ABI_VERSION,sizeof(cb_api),"bgzip+htslib",NULL,"encode=1; decode=1; caller=1; zlib-only HTSlib",CB_RATIO|CB_ENCODE|CB_DECODE|CB_REGION|CB_H_ALPHA|CB_BREAK_EVEN,encode,open_state,size_state,decode,read_state,NULL,block,NULL,NULL,close_state};a.version=hts_version();return &a;}
C
  cb_compile c -O2 -fPIC -shared -I"$CABENCH_ROOT/harness" -I"$h" "$b/plugin.c" "$h/libhts.a" -lz -lm -lpthread -o "$b/plugin.so"
  cb_checkout https://github.com/samtools/htslib.git 4b705e4fada8ee2b6b15746f725ee8ac51631803 "$h"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  cb_entry "$@"
  # Historical command interface, retained for recorded runs.
case "$1" in
 compress) bgzip -l 6 -@ 1 -i -I "$3.gzi" -c "$2" > "$3";;
 restore) bgzip -d -c "$2";;
 *) echo "bgzip.sh: compress INPUT OUTPUT | restore ARCHIVE" >&2; exit 2;;
esac
fi
