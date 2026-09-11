#ifndef CABENCH_ADAPTER_API_H
#define CABENCH_ADAPTER_API_H
#include <stdint.h>
#include <stddef.h>

/* Native ABI v1, POSIX, 64-bit process. No codec headers belong in this file. */
#define CB_ABI_VERSION 1
#define CB_RATIO (UINT64_C(1) << 0)
#define CB_ENCODE (UINT64_C(1) << 1)
#define CB_DECODE (UINT64_C(1) << 2)
#define CB_REGION (UINT64_C(1) << 3)
#define CB_AMPLIFICATION (UINT64_C(1) << 4)
#define CB_C_G (UINT64_C(1) << 5)
#define CB_BATCH (UINT64_C(1) << 6)
#define CB_H_ALPHA (UINT64_C(1) << 7)
#define CB_BREAK_EVEN (UINT64_C(1) << 8)
typedef struct { uint64_t offset, length; void *dst; int64_t written; } cb_range;
typedef struct {
    uint32_t abi_version, struct_size;
    const char *name, *version, *thread_policy;
    uint64_t capabilities;
    /* Writes complete archive files, not payload-only streams; zero = success. */
    int (*compress)(const void *, size_t, const char *, size_t, unsigned);
    /* Load resident archive/index. Never receives the original input. */
    void *(*open)(const char *, uint64_t max_output_bytes);
    uint64_t (*size)(void *);
    int64_t (*decode)(void *, void *, size_t);
    int64_t (*region)(void *, uint64_t, void *, size_t);
    int (*batch)(void *, cb_range *, size_t, unsigned);
    int (*block_id)(void *, uint64_t, uint64_t *);
    /* Actual expanded bytes, separate counter pass; NULL is not an estimate. */
    void (*reset_counter)(void *);
    uint64_t (*decoded_bytes)(void *);
    void (*close)(void *);
} cb_api;
#ifdef __cplusplus
extern "C" {
#endif
const cb_api *cabench_adapter_v1(void);
#ifdef __cplusplus
}
#endif
#endif
