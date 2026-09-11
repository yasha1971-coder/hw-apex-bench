#ifndef CABENCH_ADAPTER_UTIL_H
#define CABENCH_ADAPTER_UTIL_H
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <limits.h>
#include <sys/stat.h>

static inline unsigned char *cb_load(const char *path, size_t *size) {
    FILE *f = fopen(path, "rb");
    struct stat st;
    if (!f) return NULL;
    if (fstat(fileno(f), &st) || st.st_size < 0 || (uint64_t)st.st_size > (UINT64_C(1)<<30)) { fclose(f); return NULL; }
    *size = (size_t)st.st_size;
    unsigned char *b = (unsigned char *)malloc(*size ? *size : 1);
    if (!b) { fclose(f); return NULL; }
    int ok = fread(b, 1, *size, f) == *size;
    if (fclose(f)) ok = 0;
    if (!ok) { free(b); return NULL; }
    return b;
}
static inline int cb_save(const char *path, const void *data, size_t n) {
    FILE *f = fopen(path, "wb");
    if (!f) return -1;
    int ok = fwrite(data, 1, n, f) == n;
    if (fclose(f)) ok = 0;
    return ok ? 0 : -1;
}
static inline uint64_t cb_u64(const unsigned char *p) {
    uint64_t v=0; for (unsigned i=0;i<8;i++) v|=(uint64_t)p[i]<<(8*i); return v;
}
static inline uint32_t cb_u32(const unsigned char *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static inline int cb_bounds(uint64_t size, uint64_t offset, uint64_t length) {
    return offset <= size && length <= size-offset && length <= INT64_MAX;
}
#endif
