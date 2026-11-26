/* SPDX-License-Identifier: Apache-2.0
 * Compile separately for each row. No library patch is present here.
 * Original/casefix lib2bit DSOs link different, separately pinned archives.
 */
#define _POSIX_C_SOURCE 200809L
#define _FILE_OFFSET_BITS 64
#include "coordinate.h"
#include <inttypes.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if (defined(COORD_ACE)+defined(COORD_ZSTD)+defined(COORD_BGZF)+defined(COORD_TWOBIT)) != 1
#error Select exactly one coordinate reader
#endif
#ifdef COORD_ACE
#include "aceapex_decode.h"
#endif
#ifdef COORD_ZSTD
#include "zstd_seekable.h"
#endif
#ifdef COORD_BGZF
#include <htslib/faidx.h>
#endif
#ifdef COORD_TWOBIT
#include "2bit.h"
#ifndef COORD_STORE_MASKED
#define COORD_STORE_MASKED 1
#endif
#ifndef COORD_ORIGINAL
#define COORD_ORIGINAL 0
#endif
#if COORD_STORE_MASKED != 0 && COORD_STORE_MASKED != 1
#error COORD_STORE_MASKED must be 0 or 1
#endif
#endif

#ifndef COORD_LABEL
#ifdef COORD_ACE
#define COORD_LABEL "ACEAPEX-v2.6.5@ce6b6740c7aae8a01720d615ae024c181b7d52b6/coordinate-v1"
#elif defined(COORD_ZSTD)
#define COORD_LABEL "zstd-seekable-v1.5.7@f8745da6ff1ad1e7bab384bd1f9d742439278e99/coordinate-v1"
#elif defined(COORD_BGZF)
#define COORD_LABEL "HTSlib-v1.24@4b705e4fada8ee2b6b15746f725ee8ac51631803/faidx-coordinate-v1"
#elif !COORD_STORE_MASKED
#define COORD_LABEL "lib2bit@58e20daa898a6fc338eae82e5d2ef7108d4fc07f/original/storeMasked=0"
#elif COORD_ORIGINAL
#define COORD_LABEL "lib2bit@58e20daa898a6fc338eae82e5d2ef7108d4fc07f/original/storeMasked=1"
#elif COORD_STORE_MASKED
#define COORD_LABEL "lib2bit@58e20daa898a6fc338eae82e5d2ef7108d4fc07f/softMask-casefix/storeMasked=1"
#endif
#endif

static const char *last_error = "none";
typedef struct {
    uint64_t size, fasta_bytes, offset, line_bases, line_bytes;
    size_t maximum, scratch_bytes;
    unsigned char *scratch;
    char *chrom;
#ifdef COORD_ACE
    aceapex_dec_t *reader;
#elif defined(COORD_ZSTD)
    ZSTD_seekable *reader;
#elif defined(COORD_BGZF)
    faidx_t *reader;
#else
    TwoBit *reader;
#endif
} State;

unsigned coordinate_abi(void) { return 1; }
const char *coordinate_label(void) { return COORD_LABEL; }
const char *coordinate_error(void) { return last_error; }
unsigned coordinate_uses_memory_archive(void) {
#if defined(COORD_ACE) || defined(COORD_ZSTD)
    return 1;
#else
    return 0;
#endif
}
unsigned coordinate_semantics(void) {
#ifdef COORD_TWOBIT
#if !COORD_STORE_MASKED
    return COORD_CASE_FOLDED;
#elif COORD_ORIGINAL
    return COORD_ORIGINAL_N_UPPER;
#endif
#endif
    return COORD_EXACT;
}

void coordinate_close(void *context) {
    State *s = context;
    if (!s) return;
#ifdef COORD_ACE
    if (s->reader) aceapex_dec_close(s->reader);
#elif defined(COORD_ZSTD)
    if (s->reader) ZSTD_seekable_free(s->reader);
#elif defined(COORD_BGZF)
    if (s->reader) fai_destroy(s->reader);
#else
    if (s->reader) twobitClose(s->reader);
#endif
    free(s->scratch); free(s->chrom); free(s);
}

#if !defined(COORD_TWOBIT)
static int geometry(State *s, const CoordinateConfig *cfg) {
    char name[256], extra[2]; uint64_t bases;
    FILE *f = fopen(cfg->fai_path, "rb");
    if (!f) return 0;
    int ok = fscanf(f, "%255s\t%" SCNu64 "\t%" SCNu64 "\t%" SCNu64 "\t%" SCNu64,
                    name, &bases, &s->offset, &s->line_bases, &s->line_bytes) == 5;
    if (ok && fscanf(f, "%1s", extra) == 1) ok = 0;
    if (fclose(f)) ok = 0;
    return ok && !strcmp(name,cfg->chrom) && bases == cfg->sequence_bases && s->line_bases && s->line_bases<=bases &&
           s->line_bytes >= s->line_bases && s->line_bytes-s->line_bases <= 2;
}
#endif

void *coordinate_open(const CoordinateConfig *cfg) {
    last_error = "invalid open configuration";
    if (!cfg || !cfg->archive_path || !cfg->chrom || !cfg->sequence_bases ||
        !cfg->max_query_bases || cfg->max_query_bases > 16384 || !cfg->archive_bytes) return NULL;
#if defined(COORD_ACE) || defined(COORD_ZSTD)
    if (!cfg->archive_data) return NULL;
#endif
    State *s = calloc(1,sizeof(*s));
    if (!s) { last_error="context allocation"; return NULL; }
    s->size=cfg->sequence_bases; s->fasta_bytes=cfg->reference_fasta_bytes; s->maximum=cfg->max_query_bases;
    s->chrom=strdup(cfg->chrom);
    if (!s->chrom) goto bad;
#if !defined(COORD_TWOBIT)
    if (!cfg->fai_path || !geometry(s,cfg)) { last_error="reader FAI geometry"; goto bad; }
#endif
#if defined(COORD_ACE) || defined(COORD_ZSTD)
    /* Worst byte span for a range beginning at the final base of a line.
     * Allocate/prefault once at open; never allocate scratch inside a query. */
    uint64_t crossed=((uint64_t)s->maximum+s->line_bases-2)/s->line_bases;
    uint64_t capacity=s->maximum+crossed*(s->line_bytes-s->line_bases);
    s->scratch_bytes=(size_t)capacity; s->scratch=malloc(s->scratch_bytes);
    if (!s->scratch) { last_error="scratch allocation"; goto bad; }
    memset(s->scratch,0,s->scratch_bytes);
#endif
#ifdef COORD_ACE
    s->reader=aceapex_dec_open(cfg->archive_data,cfg->archive_bytes);
    if (!s->reader || aceapex_dec_size(s->reader)<0 || (uint64_t)aceapex_dec_size(s->reader)!=s->fasta_bytes) {
        last_error="ACE archive/source byte size"; goto bad;
    }
#elif defined(COORD_ZSTD)
    s->reader=ZSTD_seekable_create();
    if (!s->reader || ZSTD_isError(ZSTD_seekable_initBuff(s->reader,cfg->archive_data,cfg->archive_bytes))) {
        last_error="seekable initialization"; goto bad;
    }
    unsigned count=ZSTD_seekable_getNumFrames(s->reader);
    if (!count) { last_error="empty seekable archive"; goto bad; }
    uint64_t pos=ZSTD_seekable_getFrameDecompressedOffset(s->reader,count-1);
    size_t n=ZSTD_seekable_getFrameDecompressedSize(s->reader,count-1);
    if (ZSTD_isError(n) || pos>s->fasta_bytes || n!=s->fasta_bytes-pos) { last_error="seekable/source byte size"; goto bad; }
#elif defined(COORD_BGZF)
    if (!cfg->gzi_path || !strcmp(cfg->fai_path,"-") || !strcmp(cfg->gzi_path,"-")) { last_error="explicit BGZF indexes required"; goto bad; }
    s->reader=fai_load3(cfg->archive_path,cfg->fai_path,cfg->gzi_path,0);
    if (!s->reader || faidx_seq_len64(s->reader,cfg->chrom)!=(hts_pos_t)s->size) { last_error="faidx initialization/size"; goto bad; }
#else
    if (s->size>UINT32_MAX) { last_error="lib2bit coordinate range"; goto bad; }
    s->reader=twobitOpen((char*)cfg->archive_path,COORD_STORE_MASKED);
    if (!s->reader || twobitChromLen(s->reader,s->chrom)!=s->size) { last_error="lib2bit initialization/size"; goto bad; }
#endif
    last_error="none"; return s;
bad:
    coordinate_close(s); return NULL;
}

char *coordinate_read(void *context, uint64_t start, size_t length) {
    State *s=context; last_error="coordinate bounds";
    if (!s || !length || length>s->maximum || start>s->size || length>s->size-start) return NULL;
#if defined(COORD_ACE) || defined(COORD_ZSTD)
    /* All coordinate arithmetic and newline removal are inside this API. */
    uint64_t last=start+length-1;
    uint64_t begin=s->offset+(start/s->line_bases)*s->line_bytes+start%s->line_bases;
    uint64_t end=s->offset+(last/s->line_bases)*s->line_bytes+last%s->line_bases+1;
    if (end<begin || end>s->fasta_bytes || end-begin>s->scratch_bytes) { last_error="FAI byte-span bounds"; return NULL; }
    size_t span=(size_t)(end-begin);
    char *out=malloc(length+1);
    if (!out) { last_error="output allocation"; return NULL; }
#ifdef COORD_ACE
    int64_t got=aceapex_dec_region(s->reader,s->scratch,span,begin,span);
    if (got<0 || (uint64_t)got!=span) { last_error="ACE coordinate span"; free(out); return NULL; }
#else
    size_t got=ZSTD_seekable_decompress(s->reader,s->scratch,span,begin);
    if (ZSTD_isError(got) || got!=span) { last_error="seekable coordinate span"; free(out); return NULL; }
#endif
    size_t used=0;
    for (size_t i=0;i<span;i++) {
        unsigned char c=s->scratch[i];
        if (c=='\n' || c=='\r') continue;
        if (used==length) { last_error="excess bases in FAI span"; free(out); return NULL; }
        out[used++]=(char)c;
    }
    if (used!=length) { last_error="short bases in FAI span"; free(out); return NULL; }
    out[length]=0; last_error="none"; return out;
#elif defined(COORD_BGZF)
    hts_pos_t got=0;
    char *out=faidx_fetch_seq64(s->reader,s->chrom,(hts_pos_t)start,(hts_pos_t)(start+length-1),&got);
    if (!out || got!=(hts_pos_t)length) { free(out); last_error="faidx coordinate read"; return NULL; }
    last_error="none"; return out;
#else
    if (start+length>UINT32_MAX) return NULL;
    char *out=twobitSequence(s->reader,s->chrom,(uint32_t)start,(uint32_t)(start+length));
    if (!out) { last_error="lib2bit coordinate read"; return NULL; }
    last_error="none"; return out;
#endif
}
