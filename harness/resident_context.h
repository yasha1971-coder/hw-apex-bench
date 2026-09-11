#ifndef HWBENCH_RESIDENT_CONTEXT_H
#define HWBENCH_RESIDENT_CONTEXT_H
#include <stddef.h>
#include <stdint.h>
#include <limits.h>
/* Experimental correctness interface, not yet a timing ABI.
 * Caller owns resident archive bytes until close. expected_size is metadata,
 * never the original byte buffer. sidecar is optional and codec-owned.
 * Contexts are single-caller; open/close are outside region timing.
 * Negative result means failure; destination is unspecified on failure.
 */
#ifdef __cplusplus
extern "C" {
#endif
unsigned hc_abi(void);
const char *hc_version(void);
void *hc_open(const void *archive, size_t bytes, const char *sidecar,
              uint64_t expected_size);
int64_t hc_region(void *context, uint64_t offset, void *dst, size_t length);
int64_t hc_decode(void *context, void *dst, size_t capacity);
void hc_close(void *context);
#ifdef __cplusplus
}
#endif
static inline int hc_bounds(uint64_t size, uint64_t offset, size_t length) {
    return offset <= size && length <= size - offset && length <= INT64_MAX;
}
#endif
