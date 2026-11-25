/* One-frame mechanism probe. No timers, no corpus or upstream source writes.
 * Usage: frame_probe INPUT OUTPUT LEVEL HINT CHUNK empty|one_end
 * OUTPUT must not already exist. Link the pinned zstd 1.5.7 static library.
 */
#define ZSTD_STATIC_LINKING_ONLY
#include <zstd.h>
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if ZSTD_VERSION_NUMBER != 10507
#error "frame_probe requires the pinned zstd 1.5.7 headers"
#endif

typedef struct { unsigned char *data; size_t size, capacity; } Bytes;
typedef struct {
    unsigned descriptor, window_descriptor, checksum, dict_id;
    int has_window, has_content_size;
    uint64_t window_size, content_size;
    size_t size;
} Header;

static void fail(const char *message) { fprintf(stderr, "frame_probe: %s\n", message); exit(1); }
static void zcheck(size_t result) { if (ZSTD_isError(result)) fail(ZSTD_getErrorName(result)); }
static void *allocate(size_t size) { void *p = malloc(size ? size : 1); if (!p) fail("allocation failed"); return p; }
static unsigned long long number(const char *text) {
    char *end; unsigned long long n;
    if (!*text || *text == '-') fail("expected nonnegative integer");
    errno = 0; n = strtoull(text, &end, 10);
    if (errno || *end) fail("invalid integer argument");
    return n;
}
static Bytes read_input(const char *path) {
    Bytes b = { NULL, 0, 0 }; long length; FILE *f = fopen(path, "rb");
    if (!f) fail("cannot open input");
    if (fseek(f, 0, SEEK_END) || (length = ftell(f)) < 0 || fseek(f, 0, SEEK_SET)) fail("cannot size input");
    if ((unsigned long long)length > SIZE_MAX) fail("input exceeds address space");
    b.size = b.capacity = (size_t)length; b.data = allocate(b.size);
    if (fread(b.data, 1, b.size, f) != b.size || ferror(f)) fail("input read failed");
    if (fclose(f)) fail("input close failed");
    return b;
}
static void append(Bytes *b, const void *data, size_t size) {
    size_t needed; void *next;
    if (size > SIZE_MAX - b->size) fail("output size overflow");
    needed = b->size + size;
    if (needed > b->capacity) {
        size_t capacity = b->capacity ? b->capacity : 1024;
        while (capacity < needed) {
            if (capacity > SIZE_MAX / 2) { capacity = needed; break; }
            capacity *= 2;
        }
        next = realloc(b->data, capacity); if (!next) fail("output allocation failed");
        b->data = next; b->capacity = capacity;
    }
    if (size) memcpy(b->data + b->size, data, size);
    b->size = needed;
}
static uint64_t little(const unsigned char *p, unsigned size) {
    uint64_t result = 0; unsigned i;
    for (i = 0; i < size; ++i) result |= (uint64_t)p[i] << (8 * i);
    return result;
}
static void need(size_t available, size_t position, size_t count) {
    if (position > available || count > available - position) fail("truncated frame header");
}
/* Decode the wire header independently, then cross-check libzstd's decoder. */
static Header header(const Bytes *frame) {
    Header h = { 0 }; ZSTD_frameHeader library; size_t pos = 5, ret;
    unsigned single, fcs_code, fcs_bytes, dict_bytes, dict_code;
    need(frame->size, 0, 5);
    if (little(frame->data, 4) != 0xFD2FB528U) fail("unexpected frame magic");
    h.descriptor = frame->data[4];
    if (h.descriptor & 8) fail("reserved header bit set");
    single = (h.descriptor >> 5) & 1; fcs_code = h.descriptor >> 6;
    dict_code = h.descriptor & 3; h.checksum = (h.descriptor >> 2) & 1;
    h.has_window = !single;
    if (h.has_window) {
        uint64_t base;
        need(frame->size, pos, 1); h.window_descriptor = frame->data[pos++];
        base = UINT64_C(1) << (10 + (h.window_descriptor >> 3));
        h.window_size = base + (base >> 3) * (h.window_descriptor & 7);
    }
    dict_bytes = dict_code == 3 ? 4 : dict_code;
    need(frame->size, pos, dict_bytes); h.dict_id = (unsigned)little(frame->data + pos, dict_bytes); pos += dict_bytes;
    fcs_bytes = fcs_code == 0 ? single : (1U << fcs_code);
    h.has_content_size = fcs_bytes != 0;
    need(frame->size, pos, fcs_bytes);
    if (h.has_content_size) {
        h.content_size = little(frame->data + pos, fcs_bytes);
        if (fcs_bytes == 2) h.content_size += 256;
        if (single) h.window_size = h.content_size;
    }
    h.size = pos + fcs_bytes;
    ret = ZSTD_getFrameHeader(&library, frame->data, frame->size); zcheck(ret);
    if (ret || library.headerSize != h.size || library.windowSize != h.window_size ||
        library.checksumFlag != h.checksum || library.dictID != h.dict_id ||
        library.frameContentSize != (h.has_content_size ? h.content_size : ZSTD_CONTENTSIZE_UNKNOWN))
        fail("independent header decoder disagrees with ZSTD_getFrameHeader");
    return h;
}
static void compress_call(ZSTD_CCtx *context, Bytes *encoded, void *buffer, size_t buffer_size,
                          ZSTD_inBuffer *input, ZSTD_EndDirective mode) {
    size_t remaining;
    do {
        size_t before = input->pos; ZSTD_outBuffer output = { buffer, buffer_size, 0 };
        remaining = ZSTD_compressStream2(context, &output, input, mode); zcheck(remaining);
        append(encoded, buffer, output.pos);
        if (!output.pos && input->pos == before && (input->pos < input->size || (mode == ZSTD_e_end && remaining)))
            fail("compression made no progress");
    } while (input->pos < input->size || (mode == ZSTD_e_end && remaining));
}
int main(int argc, char **argv) {
    Bytes input, encoded = { NULL, 0, 0 }; Header h; ZSTD_CCtx *context;
    ZSTD_compressionParameters policy; size_t chunk, hint, capacity, offset, restored, context_bytes;
    unsigned char *buffer, *decoded, *damaged; unsigned long long value, policy_size;
    long level_long; int level, one_end, workers; char *end; FILE *output;
    if (argc != 7) fail("usage: frame_probe INPUT OUTPUT LEVEL HINT CHUNK empty|one_end");
    if (ZSTD_versionNumber() != 10507) fail("frame_probe requires the pinned zstd 1.5.7 library");
    errno = 0; level_long = strtol(argv[3], &end, 10);
    if (errno || !*argv[3] || *end || level_long < INT_MIN || level_long > INT_MAX) fail("invalid level");
    level = (int)level_long;
    value = number(argv[4]); if (value > INT_MAX) fail("hint exceeds zstd integer range"); hint = (size_t)value;
    value = number(argv[5]); if (!value || value > SIZE_MAX) fail("invalid chunk size"); chunk = (size_t)value;
    one_end = !strcmp(argv[6], "one_end");
    if (!one_end && strcmp(argv[6], "empty")) fail("finish must be empty or one_end");
    input = read_input(argv[1]); context = ZSTD_createCCtx(); if (!context) fail("cannot create CCtx");
    zcheck(ZSTD_initCStream(context, level));
    zcheck(ZSTD_CCtx_setParameter(context, ZSTD_c_srcSizeHint, (int)hint));
    zcheck(ZSTD_CCtx_getParameter(context, ZSTD_c_nbWorkers, &workers));
    if (workers != 0) fail("fresh context is not single-threaded");
    capacity = ZSTD_compressBound(input.size); zcheck(capacity);
    if (capacity < ZSTD_CStreamOutSize()) capacity = ZSTD_CStreamOutSize();
    buffer = allocate(capacity);
    if (one_end) {
        ZSTD_inBuffer in = { input.data, input.size, 0 };
        compress_call(context, &encoded, buffer, capacity, &in, ZSTD_e_end);
    } else {
        for (offset = 0; offset < input.size;) {
            size_t size = input.size - offset; ZSTD_inBuffer in;
            if (size > chunk) size = chunk;
            in.src = input.data + offset; in.size = size; in.pos = 0;
            compress_call(context, &encoded, buffer, capacity, &in, ZSTD_e_continue); offset += size;
        }
        { ZSTD_inBuffer in = { NULL, 0, 0 }; compress_call(context, &encoded, buffer, capacity, &in, ZSTD_e_end); }
    }
    context_bytes = ZSTD_sizeof_CCtx(context); h = header(&encoded);
    decoded = allocate(input.size); restored = ZSTD_decompress(decoded, input.size, encoded.data, encoded.size); zcheck(restored);
    if (restored != input.size || memcmp(decoded, input.data, input.size)) fail("round-trip bytes differ");
    damaged = allocate(encoded.size); memcpy(damaged, encoded.data, encoded.size); memcpy(damaged, "BAD!", 4);
    if (!ZSTD_isError(ZSTD_decompress(decoded, input.size, damaged, encoded.size))) fail("corrupted magic did not raise a native error");
    output = fopen(argv[2], "wbx"); if (!output) fail("cannot create output (must not exist)");
    if (fwrite(encoded.data, 1, encoded.size, output) != encoded.size || ferror(output)) fail("output write failed");
    if (fclose(output)) fail("output close failed");
    policy_size = one_end ? (unsigned long long)input.size : (hint ? (unsigned long long)hint : ZSTD_CONTENTSIZE_UNKNOWN);
    policy = ZSTD_getCParams(level, policy_size, 0);
    printf("{\"version\":\"%s\",\"input_bytes\":%zu,\"frame_bytes\":%zu,\"requested_hint\":%zu,\"chunk\":%zu,\"finish\":\"%s\",\"context_bytes\":%zu,\"roundtrip\":true,\"corrupted_magic_error\":true,\"header\":{\"descriptor\":%u,\"window_descriptor\":", ZSTD_versionString(), input.size, encoded.size, hint, chunk, argv[6], context_bytes, h.descriptor);
    if (h.has_window) printf("%u", h.window_descriptor); else printf("null");
    printf(",\"window_size\":%" PRIu64 ",\"content_size\":", h.window_size);
    if (h.has_content_size) printf("%" PRIu64, h.content_size); else printf("null");
    printf(",\"header_size\":%zu,\"checksum_flag\":%s,\"dict_id\":%u,\"header_hex\":\"", h.size, h.checksum ? "true" : "false", h.dict_id);
    for (offset = 0; offset < h.size; ++offset) printf("%02x", encoded.data[offset]);
    printf("\"},\"cparams_from_policy\":{\"windowLog\":%u,\"chainLog\":%u,\"hashLog\":%u,\"searchLog\":%u,\"minMatch\":%u,\"targetLength\":%u,\"strategy\":%d}}\n", policy.windowLog, policy.chainLog, policy.hashLog, policy.searchLog, policy.minMatch, policy.targetLength, (int)policy.strategy);
    if (fflush(stdout) || ferror(stdout)) fail("JSON output failed");
    ZSTD_freeCCtx(context); free(input.data); free(encoded.data); free(buffer); free(decoded); free(damaged);
    return 0;
}
