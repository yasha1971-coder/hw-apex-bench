#define _GNU_SOURCE
#include "resident_context.h"
#include <stdlib.h>
#include <unistd.h>
#include <sys/mman.h>
#include <htslib/bgzf.h>
#include <htslib/hts.h>
typedef struct { BGZF *bgzf; uint64_t size; uint64_t *starts; size_t blocks; } State;
unsigned hc_abi(void) { return 2; }
uint64_t hc_size(void *ctx) { return ((State*)ctx)->size; }
const char *hc_version(void) { return hts_version(); }
void hc_close(void *ctx) { State *s=ctx; if(s) { if(s->bgzf) bgzf_close(s->bgzf); free(s->starts); free(s); } }
void *hc_open(const void *arc, size_t bytes, const char *sidecar, uint64_t size) {
    if(!sidecar) return NULL;
    const unsigned char *a=arc; uint64_t actual=0; size_t blocks=0;
    for(size_t p=0;p<bytes;) {
        if(bytes-p<26 || a[p]!=31 || a[p+1]!=139 || a[p+2]!=8 || a[p+3]!=4 ||
           a[p+10]!=6 || a[p+11]!=0 || a[p+12]!='B' || a[p+13]!='C' ||
           a[p+14]!=2 || a[p+15]!=0) return NULL;
        size_t b=(size_t)a[p+16]+((size_t)a[p+17]<<8)+1;
        if(b<26 || b>bytes-p) return NULL;
        uint64_t u=0;
        for(unsigned i=0;i<4;i++) u|=(uint64_t)a[p+b-4+i]<<(8*i);
        if(u>65536 || u>INT64_MAX-actual) return NULL;
        actual+=u; p+=b; blocks++;
    }
    if(size!=UINT64_MAX && size!=actual) return NULL;
    size=actual;
    State *s=calloc(1,sizeof(*s)); if(!s) return NULL; s->size=size;
    s->starts=calloc(blocks?blocks:1,sizeof(uint64_t)); if(!s->starts) {free(s);return NULL;}
    s->blocks=blocks;
    uint64_t total=0; size_t index=0;
    for(size_t p=0;p<bytes;) {
        s->starts[index++]=total;
        size_t b=(size_t)a[p+16]+((size_t)a[p+17]<<8)+1;
        uint64_t u=0;for(unsigned i=0;i<4;i++)u|=(uint64_t)a[p+b-4+i]<<(8*i);
        total+=u;p+=b;
    }
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

uint64_t hc_block_id(void *ctx,uint64_t off) {
    State *s=ctx; if(off>=s->size) return UINT64_MAX;
    size_t lo=0,hi=s->blocks;
    while(lo<hi) {size_t mid=lo+(hi-lo)/2;if(s->starts[mid]<=off)lo=mid+1;else hi=mid;}
    return lo?lo-1:UINT64_MAX;
}
