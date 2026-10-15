/* dq_others.c - Axis 3 window-law D_Q for the foreign formats on the same corpus and protocol as dq_refrel3.cpp:
 * full sequential decode with exactly one decode thread, in process; one run = every archive of the list decoded in
 * order into memory; after each run (outside timing) SHA-256 of every output (OpenSSL libcrypto) == source FASTA.
 *   dq_others bgzf <warmups> <runs> <archive.bgz> <sha256> [...]   htslib bgzf_open + bgzf_read loop (no bgzf_mt), file
 *                                                                  in the page cache (htslib reads through its hFILE)
 *   dq_others zsk  <warmups> <runs> <archive.zst> <sha256> [...]   zstd seekable format: ZSTD_seekable_initBuff on the
 *                                                                  archive in memory + ZSTD_seekable_decompress of all
 *   dq_others lz4  <warmups> <runs> <archive.lz4> <sha256> [...]   LZ4F_decompress of the frame in memory
 * DQGEOM: output bytes and the number of independently decodable units read from the archive itself (BGZF blocks with
 * ISIZE > 0 by walking BSIZE; seekable frames from the seek table; LZ4 data blocks by walking block headers).
 * DQRUN: run, warmup|timed, total s, output bytes, per-archive s, SHA result. */
#define _POSIX_C_SOURCE 199309L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <htslib/bgzf.h>
#define ZSTD_STATIC_LINKING_ONLY
#include "zstd.h"
#include "zstd_seekable.h"
#include "lz4frame.h"
unsigned char* SHA256(const unsigned char* d, size_t n, unsigned char* md);
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
static unsigned char* slurp(const char* p, size_t* n) { FILE* f = fopen(p, "rb"); if (!f) { perror(p); exit(1); } fseek(f, 0, SEEK_END); long s = ftell(f); fseek(f, 0, SEEK_SET);
    unsigned char* b = malloc((size_t)s + 1); if (!b || fread(b, 1, (size_t)s, f) != (size_t)s) exit(1); fclose(f); *n = (size_t)s; return b; }
static void hex(const unsigned char* m, char* o) { for (int i = 0; i < 32; i++) sprintf(o + 2 * i, "%02x", m[i]); }
static uint32_t rd32(const unsigned char* p) { return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24; }
typedef struct { const char* path; const char* want; unsigned char* a; size_t an; size_t out; long units; unsigned char* buf; } Arc;
static long bgzf_units(const unsigned char* a, size_t n, size_t* out) { long u = 0; size_t i = 0; *out = 0;
    while (i + 18 <= n) { const size_t bs = (size_t)(a[i + 16] | a[i + 17] << 8) + 1; if (i + bs > n) { fprintf(stderr, "bad BGZF\n"); exit(2); }
        const uint32_t is = rd32(a + i + bs - 4); if (is) u++; *out += is; i += bs; } return u; }
static long lz4_units(const unsigned char* a, size_t n) { if (n < 7 || rd32(a) != 0x184D2204u) { fprintf(stderr, "not an LZ4 frame\n"); exit(2); }
    const unsigned flg = a[4]; size_t i = 6 + ((flg & 8) ? 8 : 0) + ((flg & 1) ? 4 : 0) + 1; const int bcs = (flg >> 4) & 1; long u = 0;
    for (;;) { const uint32_t h = rd32(a + i); i += 4; if (h == 0) break; i += (h & 0x7FFFFFFFu) + (bcs ? 4 : 0); u++; if (i > n) { fprintf(stderr, "bad LZ4\n"); exit(2); } } return u; }
static size_t decode(const char* mode, Arc* A) {
    if (!strcmp(mode, "bgzf")) { BGZF* f = bgzf_open(A->path, "r"); if (!f) exit(3); size_t o = 0; ssize_t k;
        while ((k = bgzf_read(f, A->buf + o, 1 << 20)) > 0) o += (size_t)k; if (k < 0) exit(3); bgzf_close(f); return o; }
    if (!strcmp(mode, "zsk")) { ZSTD_seekable* z = ZSTD_seekable_create(); if (ZSTD_isError(ZSTD_seekable_initBuff(z, A->a, A->an))) exit(3);
        const size_t r = ZSTD_seekable_decompress(z, A->buf, A->out, 0); ZSTD_seekable_free(z); if (ZSTD_isError(r)) exit(3); return r; }
    LZ4F_dctx* d; if (LZ4F_isError(LZ4F_createDecompressionContext(&d, LZ4F_VERSION))) exit(3);
    size_t o = 0, i = 0; for (;;) { size_t dst = A->out + 64 - o, src = A->an - i; const size_t r = LZ4F_decompress(d, A->buf + o, &dst, A->a + i, &src, NULL);
        if (LZ4F_isError(r)) { fprintf(stderr, "LZ4F: %s\n", LZ4F_getErrorName(r)); exit(3); } o += dst; i += src; if (r == 0) break; if (!dst && !src) exit(3); }
    LZ4F_freeDecompressionContext(d); return o;
}
int main(int argc, char** argv) {
    if (argc < 6 || (argc - 4) % 2) { fprintf(stderr, "usage: dq_others bgzf|zsk|lz4 <warmups> <runs> <archive> <sha256> [...]\n"); return 1; }
    const char* mode = argv[1]; const int WU = atoi(argv[2]), R = atoi(argv[3]); const int N = (argc - 4) / 2; Arc* A = calloc(N, sizeof(Arc)); int bad = 0;
    for (int i = 0; i < N; i++) { A[i].path = argv[4 + 2 * i]; A[i].want = argv[5 + 2 * i]; A[i].a = slurp(A[i].path, &A[i].an);
        if (!strcmp(mode, "bgzf")) A[i].units = bgzf_units(A[i].a, A[i].an, &A[i].out);
        else if (!strcmp(mode, "zsk")) { ZSTD_seekable* z = ZSTD_seekable_create(); if (ZSTD_isError(ZSTD_seekable_initBuff(z, A[i].a, A[i].an))) return 2;
            A[i].units = (long)ZSTD_seekable_getNumFrames(z); A[i].out = 0; for (unsigned k = 0; k < (unsigned)A[i].units; k++) A[i].out += ZSTD_seekable_getFrameDecompressedSize(z, k); ZSTD_seekable_free(z); }
        else { A[i].units = lz4_units(A[i].a, A[i].an); unsigned long long cs = 0; const unsigned flg = A[i].a[4]; if (!(flg & 8)) { fprintf(stderr, "no content size\n"); return 2; } memcpy(&cs, A[i].a + 6, 8); A[i].out = cs; }
        A[i].buf = malloc(A[i].out + (1 << 20) + 64);
        if (!strcmp(mode, "bgzf")) { free(A[i].a); A[i].a = NULL; }                        /* htslib reads the file itself */
        printf("DQGEOM\t%s\t%s\tunits %ld\toutput_bytes %zu\tarchive_bytes %zu\n", mode, A[i].path, A[i].units, A[i].out, A[i].an); }
    fflush(stdout);
    for (int r = 0; r < WU + R; r++) { double tot = 0; size_t out = 0; double* t = calloc(N, sizeof(double)); size_t* got = calloc(N, sizeof(size_t));
        for (int i = 0; i < N; i++) { const double t0 = now(); got[i] = decode(mode, &A[i]); t[i] = now() - t0; tot += t[i]; out += got[i]; }
        int ok = 0; for (int i = 0; i < N; i++) { unsigned char md[32]; char h[65]; SHA256(A[i].buf, got[i], md); hex(md, h); ok += got[i] == A[i].out && !strcmp(h, A[i].want); }
        if (ok != N) bad++;
        printf("DQRUN\t%d\t%s\t%.6f\t%zu\t", r, r < WU ? "warmup" : "timed", tot, out); for (int i = 0; i < N; i++) printf("%s%.6f", i ? "," : "", t[i]); printf("\tsha256 %d/%d\n", ok, N); fflush(stdout);
        free(t); free(got); }
    return bad ? 4 : 0;
}
