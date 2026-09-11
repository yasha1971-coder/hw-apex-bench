/* Full exactness restore through the pinned seekable library, outside region timers. */
#include <stdio.h>
#include <stdlib.h>
#include "zstd_seekable.h"
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    FILE *in = fopen(argv[1], "rb");
    ZSTD_seekable *s = ZSTD_seekable_create();
    if (!in || !s || ZSTD_isError(ZSTD_seekable_initFile(s, in))) return 3;
    unsigned n = ZSTD_seekable_getNumFrames(s);
    void *buf = malloc(1 << 20);
    if (!buf) return 4;
    unsigned long long off = 0, total = 0;
    for (unsigned i=0; i<n; i++) {
        size_t size = ZSTD_seekable_getFrameDecompressedSize(s,i);
        if (ZSTD_isError(size)) return 5;
        total += size;
    }
    while (off < total) {
        size_t want = total-off < (1<<20) ? (size_t)(total-off) : (1<<20);
        size_t got = ZSTD_seekable_decompress(s,buf,want,off);
        if (ZSTD_isError(got) || got != want || fwrite(buf,1,got,stdout) != got) return 6;
        off += got;
    }
    free(buf); ZSTD_seekable_free(s);
    return fclose(in) || fflush(stdout) ? 7 : 0;
}
