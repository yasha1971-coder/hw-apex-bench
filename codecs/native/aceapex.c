#include "resident_context.h"
#include "aceapex.h"
#include <stdlib.h>
#include <string.h>
typedef struct { const void *arc; size_t bytes; uint64_t size; } State;
unsigned hc_abi(void) { return 2; }
uint64_t hc_size(void *ctx) { return ((State*)ctx)->size; }
const char *hc_version(void) { return "aceapex@1b13df34ac8e839dd3232b59bc59560d689a435a"; }
void *hc_open(const void *arc, size_t bytes, const char *sidecar, uint64_t size) {
    (void)sidecar;
    if(bytes < 68 || memcmp(arc,"ACEPX2\0\0",8)) return NULL;
    uint64_t actual=0;
    for(unsigned i=0;i<8;i++) actual|=(uint64_t)((const unsigned char*)arc)[12+i]<<(8*i);
    if(actual>INT64_MAX || (size!=UINT64_MAX && size!=actual)) return NULL;
    size=actual;
    State *s=malloc(sizeof(*s)); if(s) *s=(State){arc,bytes,size}; return s;
}
int64_t hc_region(void *ctx, uint64_t off, void *dst, size_t len) {
    State *s=ctx; if(!hc_bounds(s->size,off,len)) return -1;
    if(!len) return 0;
    /* Preserve the published API call, including its per-call header parsing. */
    return aceapex_decompress_region(s->arc,s->bytes,dst,len,off,len);
}
int64_t hc_decode(void *ctx, void *dst, size_t cap) {
    State *s=ctx; if(cap<s->size) return -1;
    return aceapex_decompress(s->arc,s->bytes,dst,s->size);
}
void hc_close(void *ctx) { free(ctx); }

uint64_t hc_block_id(void *ctx,uint64_t off) {
    State *s=ctx;if(off>=s->size)return UINT64_MAX;
    const unsigned char *a=s->arc;uint32_t g=0;
    for(unsigned i=0;i<4;i++)g|=(uint32_t)a[20+i]<<(8*i);
    return g?off/g:UINT64_MAX;
}
typedef struct {State *ctx;aceapex_range_t *ranges;size_t count;} Batch;
void *hc_batch_open(void *ctx,const uint64_t *offset,size_t count,size_t length,void *out) {
    State *s=ctx;if(!count || count>5000 || length!=16384)return NULL;
    Batch *b=calloc(1,sizeof(*b));if(!b)return NULL;
    b->ctx=s;b->count=count;b->ranges=calloc(count,sizeof(*b->ranges));
    if(!b->ranges){free(b);return NULL;}
    for(size_t i=0;i<count;i++){
        if(!hc_bounds(s->size,offset[i],length)){free(b->ranges);free(b);return NULL;}
        b->ranges[i].offset=offset[i];b->ranges[i].length=length;
        b->ranges[i].dst=(char*)out+i*length;
    }
    return b;
}
void hc_batch_reset(void *ctx){Batch *b=ctx;for(size_t i=0;i<b->count;i++)b->ranges[i].written=0;}
int64_t hc_batch_run(void *ctx,size_t count,int threads){
    Batch *b=ctx;if(count>b->count || threads!=1)return -1;
    return aceapex_decompress_ranges(b->ctx->arc,b->ctx->bytes,b->ranges,count,threads);
}
int hc_batch_valid(void *ctx,size_t count){
    Batch *b=ctx;if(count>b->count)return 0;
    for(size_t i=0;i<count;i++)if(b->ranges[i].written!=16384)return 0;
    return 1;
}
void hc_batch_close(void *ctx){Batch *b=ctx;if(b){free(b->ranges);free(b);}}

int hc_geometry(void *ctx,uint64_t *units,uint64_t *empty,uint64_t *raw,uint64_t *largest){
    State *s=ctx;const unsigned char *a=s->arc;uint32_t g=0,n=0;
    for(unsigned i=0;i<4;i++){g|=(uint32_t)a[20+i]<<(8*i);n|=(uint32_t)a[24+i]<<(8*i);}
    if(!g||n!=(s->size+g-1)/g)return -1;
    *units=n;*empty=0;*raw=s->size;*largest=s->size<g?s->size:g;return 0;
}
