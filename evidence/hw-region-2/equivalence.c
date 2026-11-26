/* SPDX-License-Identifier: Apache-2.0
 * Correctness-only lib2bit vs plain-FASTA/.fai witness. No timers.
 */
#define _FILE_OFFSET_BITS 64
#define _POSIX_C_SOURCE 200809L
#include <sys/types.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "2bit.h"

static int save(const char *path, const unsigned char *data, size_t n) {
    FILE *f = fopen(path, "wb");
    if (!f) return 0;
    int ok = fwrite(data, 1, n, f) == n;
    if (fclose(f)) ok = 0;
    return ok;
}

int main(int argc, char **argv) {
    if (argc != 9) {
        fprintf(stderr, "usage: equivalence FASTA FAI 2BIT CHROM START LENGTH EXPECTED_BIN ACTUAL_BIN\n");
        return 3;
    }
    uint64_t start = strtoull(argv[5], NULL, 10), length = strtoull(argv[6], NULL, 10);
    uint64_t size = 0, offset = 0, line_bases = 0, line_bytes = 0;
    char chrom[256], extra[2];
    FILE *fai = fopen(argv[2], "rb");
    if (!fai || fscanf(fai, "%255s\t%" SCNu64 "\t%" SCNu64 "\t%" SCNu64 "\t%" SCNu64,
                       chrom, &size, &offset, &line_bases, &line_bytes) != 5) return 3;
    if (fscanf(fai, "%1s", extra) == 1 || fclose(fai)) return 3;
    if (strcmp(chrom, argv[4]) || !length || !line_bases || line_bytes < line_bases ||
        start > size || length > size - start || start + length > UINT32_MAX) return 3;
    uint64_t first = offset + start / line_bases * line_bytes + start % line_bases;
    uint64_t last = offset + (start + length - 1) / line_bases * line_bytes + (start + length - 1) % line_bases + 1;
    if (last < first || last - first > SIZE_MAX || length > SIZE_MAX) return 3;
    size_t span = (size_t)(last - first);
    unsigned char *bytes = malloc(span), *reference = malloc((size_t)length);
    if (!bytes || !reference) return 3;
    FILE *fasta = fopen(argv[1], "rb");
    if (!fasta || fseeko(fasta, (off_t)first, SEEK_SET) || fread(bytes, 1, span, fasta) != span || fclose(fasta)) return 3;
    size_t bases = 0;
    for (size_t i = 0; i < span; ++i) {
        if (bytes[i] == '\r' || bytes[i] == '\n') continue;
        if (bases == length) return 3;
        reference[bases++] = bytes[i];
    }
    free(bytes);
    if (bases != length) return 3;
    TwoBit *tb = twobitOpen(argv[3], 1);
    if (!tb) { fprintf(stderr, "lib2bit open failed\n"); return 3; }
    if (twobitChromLen(tb, argv[4]) != size) return 3;
    char *actual = twobitSequence(tb, argv[4], (uint32_t)start, (uint32_t)(start + length));
    if (!actual || strlen(actual) != length) {
        fprintf(stderr, "lib2bit returned NULL or wrong length; this is not a lowercase-n witness\n");
        return 3;
    }
    if (!save(argv[7], reference, (size_t)length) || !save(argv[8], (unsigned char *)actual, (size_t)length)) return 3;
    uint64_t mismatches = 0, first_difference = UINT64_MAX;
    for (uint64_t i = 0; i < length; ++i) {
        if (reference[i] == (unsigned char)actual[i]) continue;
        if (!mismatches) first_difference = i;
        ++mismatches;
    }
    printf("{\"schema\":\"hw-region-2-equivalence-v1\",\"status\":\"%s\","
           "\"no_clocks\":true,\"storeMasked\":1,\"start0\":%" PRIu64 ",\"length\":%" PRIu64 ","
           "\"reference_byte_start\":%" PRIu64 ",\"reference_byte_span\":%zu,\"mismatches\":%" PRIu64,
           mismatches ? "KILL" : "PASS", start, length, first, span, mismatches);
    if (mismatches) {
        printf(",\"first_difference0\":%" PRIu64 ",\"first_difference1\":%" PRIu64
               ",\"expected_byte\":%u,\"actual_byte\":%u",
               start + first_difference, start + first_difference + 1,
               (unsigned)reference[first_difference], (unsigned)(unsigned char)actual[first_difference]);
    }
    puts("}");
    free(actual); free(reference); twobitClose(tb);
    return mismatches ? 2 : 0;
}
