#include "resident_context.h"
#include "aceapex.h"
#include <stdlib.h>
#include <string.h>
typedef struct { const void *arc; size_t bytes; uint64_t size; } State;
unsigned hc_abi(void) { return 1; }
const char *hc_version(void) { return "aceapex@1b13df34ac8e839dd3232b59bc59560d689a435a"; }
void *hc_open(const void *arc, size_t bytes, const char *sidecar, uint64_t size) {
    (void)sidecar;
    if(bytes < 68 || memcmp(arc,"ACEPX2\0\0",8) || size > INT64_MAX) return NULL;
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
