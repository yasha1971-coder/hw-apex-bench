/* SPDX-License-Identifier: Apache-2.0
 * Base-coordinate ABI 1. All intervals are zero-based [start,start+length).
 * This is deliberately distinct from the repository's byte-region hc ABI.
 */
#ifndef HW_REGION2_COORDINATE_H
#define HW_REGION2_COORDINATE_H
#include <stddef.h>
#include <stdint.h>

enum { COORD_EXACT = 0, COORD_ORIGINAL_N_UPPER = 1, COORD_CASE_FOLDED = 2 };
typedef struct {
    const char *archive_path;
    const void *archive_data;       /* caller-owned, resident until close */
    size_t archive_bytes;
    const char *fai_path;           /* explicit reader index, or "-" */
    const char *gzi_path;           /* explicit BGZF index, or "-" */
    const char *chrom;
    uint64_t sequence_bases;
    uint64_t reference_fasta_bytes;
    size_t max_query_bases;
} CoordinateConfig;

unsigned coordinate_abi(void);
const char *coordinate_label(void);
unsigned coordinate_semantics(void);
unsigned coordinate_uses_memory_archive(void);
const char *coordinate_error(void);
void *coordinate_open(const CoordinateConfig *config);
/* Returned string is malloc-owned and NUL-terminated. Allocation, FAI span
 * calculation, codec access and CR/LF removal all occur inside this call.
 * The caller verifies and free()s it outside the query timer. */
char *coordinate_read(void *context, uint64_t start, size_t length);
void coordinate_close(void *context);
#endif
