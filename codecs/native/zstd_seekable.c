#include "resident_context.h"
#include "zstd_seekable.h"
#include <stdlib.h>
typedef struct { ZSTD_seekable *seek; uint64_t size; } State;
unsigned hc_abi(void) { return 2; }
uint64_t hc_size(void *ctx) { return ((State*)ctx)->size; }
const char *hc_version(void) { return ZSTD_versionString(); }
void hc_close(void *ctx) { State *s=ctx; if(s) { ZSTD_seekable_free(s->seek); free(s); } }
void *hc_open(const void *arc, size_t bytes, const char *sidecar, uint64_t size) {
    (void)sidecar;
    State *s=calloc(1,sizeof(*s)); if(!s) return NULL;
    s->size=size; s->seek=ZSTD_seekable_create();
    if(!s->seek || ZSTD_isError(ZSTD_seekable_initBuff(s->seek,arc,bytes))) {hc_close(s); return NULL;}
    unsigned frames=ZSTD_seekable_getNumFrames(s->seek);
    uint64_t actual=0;
    if(frames) {
        uint64_t off=ZSTD_seekable_getFrameDecompressedOffset(s->seek,frames-1);
        size_t last=ZSTD_seekable_getFrameDecompressedSize(s->seek,frames-1);
        if(ZSTD_isError(last) || off>INT64_MAX || last>INT64_MAX-off) {hc_close(s); return NULL;}
        actual=off+last;
    }
    if(size!=UINT64_MAX && size!=actual) {hc_close(s); return NULL;}
    s->size=actual;
    return s;
}
int64_t hc_region(void *ctx, uint64_t off, void *dst, size_t len) {
    State *s=ctx; if(!hc_bounds(s->size,off,len)) return -1;
    if(!len) return 0;
    size_t r=ZSTD_seekable_decompress(s->seek,dst,len,off); return ZSTD_isError(r)?-1:(int64_t)r;
}
int64_t hc_decode(void *ctx, void *dst, size_t cap) {
    State *s=ctx; if(cap<s->size) return -1;
    size_t r=ZSTD_seekable_decompress(s->seek,dst,s->size,0); return ZSTD_isError(r)?-1:(int64_t)r;
}

uint64_t hc_block_id(void *ctx,uint64_t off) {
    State *s=ctx; return off<s->size?ZSTD_seekable_offsetToFrameIndex(s->seek,off):UINT64_MAX;
}

int hc_geometry(void *ctx,uint64_t *units,uint64_t *empty,uint64_t *raw,uint64_t *largest){
    State *s=ctx;*units=ZSTD_seekable_getNumFrames(s->seek);*empty=0;*raw=0;*largest=0;
    for(unsigned i=0;i<*units;i++){
        size_t n=ZSTD_seekable_getFrameDecompressedSize(s->seek,i);if(ZSTD_isError(n))return -1;
        *empty+=n==0;*raw+=n;if(n>*largest)*largest=n;
    }
    return *raw==s->size?0:-1;
}
