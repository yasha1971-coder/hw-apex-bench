#include "resident_context.h"
#include "zstd_seekable.h"
#include <stdlib.h>
typedef struct { ZSTD_seekable *seek; uint64_t size; } State;
unsigned hc_abi(void) { return 1; }
const char *hc_version(void) { return ZSTD_versionString(); }
void hc_close(void *ctx) { State *s=ctx; if(s) { ZSTD_seekable_free(s->seek); free(s); } }
void *hc_open(const void *arc, size_t bytes, const char *sidecar, uint64_t size) {
    (void)sidecar; if(size>INT64_MAX) return NULL;
    State *s=calloc(1,sizeof(*s)); if(!s) return NULL;
    s->size=size; s->seek=ZSTD_seekable_create();
    if(!s->seek || ZSTD_isError(ZSTD_seekable_initBuff(s->seek,arc,bytes))) {hc_close(s); return NULL;}
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
