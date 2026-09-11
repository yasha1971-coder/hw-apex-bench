/* Controlled BGZF flush intervals, using the installed htslib encoder.
 * No alternate deflate encoder and no fictitious whole-file BGZF baseline. */
#include <stdio.h>
#include <stdlib.h>
#include <htslib/bgzf.h>

int main(int argc, char **argv) {
    if (argc != 4) return 2;
    unsigned long requested = strtoul(argv[3], NULL, 10);
    if (requested != 4096 && requested != 16384 && requested != 65536) return 2;
    size_t chunk = requested < BGZF_BLOCK_SIZE ? requested : BGZF_BLOCK_SIZE;
    unsigned char *buf = malloc(chunk);
    FILE *in = fopen(argv[1], "rb");
    BGZF *out = bgzf_open(argv[2], "w6");
    if (!buf || !in || !out || bgzf_index_build_init(out)) return 3;
    size_t n;
    while ((n = fread(buf, 1, chunk, in))) {
        if (bgzf_write(out, buf, n) != (ssize_t)n || bgzf_flush(out)) return 4;
    }
    if (ferror(in) || fclose(in) || bgzf_index_dump(out, argv[2], ".gzi")) return 5;
    if (bgzf_close(out)) return 6;
    free(buf);
    printf("{\"requested_g\":%lu,\"flush_bytes\":%zu,\"threads\":1}\n", requested, chunk);
    return 0;
}
