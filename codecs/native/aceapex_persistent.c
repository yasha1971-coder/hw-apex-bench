#include "resident_context.h"
#include "aceapex_decode.h"
#include <stdlib.h>
#include <string.h>

#ifndef HB_ACE_VERSION
#define HB_ACE_VERSION "aceapex-modern"
#endif

typedef struct {
    const void *arc;
    size_t bytes;
    uint64_t size;
    aceapex_dec_t *dec;
} State;

unsigned hc_abi(void) { return 2; }
uint64_t hc_size(void *ctx) { return ((State*)ctx)->size; }
const char *hc_version(void) { return HB_ACE_VERSION; }

void *hc_open(const void *arc, size_t bytes, const char *sidecar, uint64_t size) {
    (void)sidecar;
    aceapex_dec_t *dec=aceapex_dec_open(arc,bytes);
    if(!dec) return NULL;
    int64_t actual=aceapex_dec_size(dec);
    if(actual<0 || (size!=UINT64_MAX && size!=(uint64_t)actual)) {
        aceapex_dec_close(dec); return NULL;
    }
    State *s=(State*)calloc(1,sizeof(*s));
    if(!s){ aceapex_dec_close(dec); return NULL; }
    s->arc=arc; s->bytes=bytes; s->size=(uint64_t)actual; s->dec=dec;
    return s;
}

int64_t hc_region(void *ctx, uint64_t off, void *dst, size_t len) {
    State *s=(State*)ctx;
    if(!hc_bounds(s->size,off,len)) return -1;
    return aceapex_dec_region(s->dec,dst,len,off,len);
}

int64_t hc_decode(void *ctx, void *dst, size_t cap) {
    State *s=(State*)ctx;
    if(cap<s->size) return -1;
    return aceapex_decompress(s->arc,s->bytes,dst,cap);
}

void hc_close(void *ctx) {
    State *s=(State*)ctx;
    if(s){ aceapex_dec_close(s->dec); free(s); }
}

uint64_t hc_block_id(void *ctx,uint64_t off) {
    State *s=(State*)ctx;
    if(off>=s->size || s->bytes<28) return UINT64_MAX;
    const unsigned char *a=(const unsigned char*)s->arc;
    uint32_t g=0;
    for(unsigned i=0;i<4;i++) g|=(uint32_t)a[20+i]<<(8*i);
    return g?off/g:UINT64_MAX;
}

typedef struct {
    State *ctx;
    aceapex_range_t *ranges;
    size_t count;
} Batch;

void *hc_batch_open(void *ctx,const uint64_t *offset,size_t count,size_t length,void *out) {
    State *s=(State*)ctx;
    if(!count || count>5000 || length!=16384) return NULL;
    Batch *b=(Batch*)calloc(1,sizeof(*b));
    if(!b) return NULL;
    b->ctx=s; b->count=count;
    b->ranges=(aceapex_range_t*)calloc(count,sizeof(*b->ranges));
    if(!b->ranges){ free(b); return NULL; }
    for(size_t i=0;i<count;i++){
        if(!hc_bounds(s->size,offset[i],length)){ free(b->ranges); free(b); return NULL; }
        b->ranges[i].offset=offset[i];
        b->ranges[i].length=length;
        b->ranges[i].dst=(char*)out+i*length;
    }
    return b;
}
void hc_batch_reset(void *ctx){
    Batch *b=(Batch*)ctx;
    for(size_t i=0;i<b->count;i++) b->ranges[i].written=0;
}
int64_t hc_batch_run(void *ctx,size_t count,int threads){
    Batch *b=(Batch*)ctx;
    if(count>b->count || threads!=1) return -1;
    return aceapex_dec_ranges(b->ctx->dec,b->ranges,count);
}
int hc_batch_valid(void *ctx,size_t count){
    Batch *b=(Batch*)ctx;
    if(count>b->count) return 0;
    for(size_t i=0;i<count;i++) if(b->ranges[i].written!=16384) return 0;
    return 1;
}
void hc_batch_close(void *ctx){
    Batch *b=(Batch*)ctx;
    if(b){ free(b->ranges); free(b); }
}

int hc_geometry(void *ctx,uint64_t *units,uint64_t *empty,uint64_t *raw,uint64_t *largest){
    State *s=(State*)ctx;
    const unsigned char *a=(const unsigned char*)s->arc;
    if(s->bytes<28) return -1;
    uint32_t g=0,n=0;
    for(unsigned i=0;i<4;i++){ g|=(uint32_t)a[20+i]<<(8*i); n|=(uint32_t)a[24+i]<<(8*i); }
    if(!g || n!=(s->size+g-1)/g) return -1;
    *units=n; *empty=0; *raw=s->size; *largest=s->size<g?s->size:g;
    return 0;
}
