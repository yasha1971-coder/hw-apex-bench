#include <zstd.h>
#include <stddef.h>
unsigned region_zstd_version_number(void) { return ZSTD_versionNumber(); }
const char *region_zstd_version_string(void) { return ZSTD_versionString(); }
size_t region_compress_bound(size_t n) { return ZSTD_compressBound(n); }
size_t region_compress(void *dst,size_t capacity,const void *src,size_t n) { return ZSTD_compress(dst,capacity,src,n,3); }
void *region_create_dctx(void) { return ZSTD_createDCtx(); }
void region_free_dctx(void *ctx) { ZSTD_freeDCtx((ZSTD_DCtx*)ctx); }
size_t region_decode_dctx(void *ctx,void *dst,size_t capacity,const void *src,size_t n) { return ZSTD_decompressDCtx((ZSTD_DCtx*)ctx,dst,capacity,src,n); }
unsigned region_is_error(size_t code) { return ZSTD_isError(code); }
