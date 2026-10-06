/* Existing repository pins: htslib 1.24 + libdeflate 1.19, not system htslib.
 * Public API coordinates: faidx_fetch_seq64 is 0-based inclusive.
 * Matched-g uses bgzf_flush; the default path is the stock bgzip CLI.
 */
#include <htslib/bgzf.h>
#include <htslib/faidx.h>
#include <htslib/hts.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

const char *hwa_bgzf_version(void) { return hts_version(); }
int hwa_bgzf_matched(const char *source, const char *archive, size_t granule) {
    if (granule == 0 || granule > BGZF_BLOCK_SIZE) return -1;
    FILE *in = fopen(source, "rb");
    if (in == NULL) return -2;
    BGZF *out = bgzf_open(archive, "w");
    if (out == NULL) { fclose(in); return -3; }
    unsigned char *buffer = malloc(granule);
    if (buffer == NULL) { fclose(in); bgzf_close(out); return -4; }
    int rc = 0;
    for (;;) {
        size_t n = fread(buffer, 1, granule, in);
        if (n > 0 && (bgzf_write(out, buffer, n) != (ssize_t)n || bgzf_flush(out) != 0)) {
            rc = -5; break;
        }
        if (n < granule) { if (ferror(in)) rc = -6; break; }
    }
    free(buffer);
    if (fclose(in) != 0) rc = -7;
    if (bgzf_close(out) != 0) rc = -8;
    return rc;
}
int hwa_bgzf_index(const char *archive) { return fai_build3(archive, NULL, NULL); }
void *hwa_bgzf_open(const char *archive) {
    /* Loading may not silently build missing sidecars inside a measured read. */
    return fai_load3(archive, NULL, NULL, 0);
}
int64_t hwa_bgzf_length(void *context, const char *contig) {
    if (context == NULL || contig == NULL || *contig == 0) return -1;
    return faidx_seq_len64((faidx_t *)context, contig);
}
int64_t hwa_bgzf_fetch(void *context, const char *contig, uint64_t start0,
                       uint64_t length, void *destination, size_t capacity) {
    int64_t total = hwa_bgzf_length(context, contig);
    if (total < 0 || destination == NULL || length == 0 || length > capacity
        || start0 > (uint64_t)total || length > (uint64_t)total - start0) return -1;
    hts_pos_t got = 0;
    char *p = faidx_fetch_seq64((faidx_t *)context, contig, (hts_pos_t)start0,
                               (hts_pos_t)(start0 + length - 1), &got);
    if (p == NULL || got < 0 || (uint64_t)got != length) { free(p); return -2; }
    memcpy(destination, p, (size_t)got);
    free(p);
    return got;
}
void hwa_bgzf_close(void *context) { if (context != NULL) fai_destroy((faidx_t *)context); }
