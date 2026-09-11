#define _GNU_SOURCE
#include "resident_context.h"
#include <stdlib.h>
#include <unistd.h>
#include <sys/mman.h>
#include <htslib/bgzf.h>
#include <htslib/hts.h>
typedef struct { BGZF *bgzf; uint64_t size; } State;
unsigned hc_abi(void) { return 1; }
const char *hc_version(void) { return hts_version(); }
void hc_close(void *ctx) { State *s=ctx; if(s) { if(s->bgzf) bgzf_close(s->bgzf); free(s); } }
void *hc_open(const void *arc, size_t bytes, const char *sidecar, uint64_t size) {
    if(!sidecar || size>INT64_MAX) return NULL;
    State *s=calloc(1,sizeof(*s)); if(!s) return NULL; s->size=size;
    int fd=memfd_create("hwbench-context",MFD_CLOEXEC); if(fd<0) goto bad;
    for(size_t pos=0;pos<bytes;) {
        ssize_t n=write(fd,(const char*)arc+pos,bytes-pos);
        if(n<=0) {close(fd); goto bad;} pos+=(size_t)n;
    }
    if(lseek(fd,0,SEEK_SET)<0) {close(fd); goto bad;}
    s->bgzf=bgzf_dopen(fd,"r"); if(!s->bgzf) {close(fd); goto bad;}
    if(bgzf_index_load(s->bgzf,sidecar,NULL)) goto bad;
    return s;
    bad: hc_close(s); return NULL;
}
int64_t hc_region(void *ctx, uint64_t off, void *dst, size_t len) {
    State *s=ctx; if(!hc_bounds(s->size,off,len)) return -1;
    if(!len) return 0;
    if(bgzf_useek(s->bgzf,(off_t)off,SEEK_SET)) return -1;
    return bgzf_read(s->bgzf,dst,len);
}
int64_t hc_decode(void *ctx, void *dst, size_t cap) {
    State *s=ctx; if(cap<s->size || bgzf_seek(s->bgzf,0,SEEK_SET)) return -1;
    return bgzf_read(s->bgzf,dst,s->size);
}
