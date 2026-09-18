#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <htslib/bgzf.h>

static void die(const char *s) {
    fprintf(stderr, "STOP: %s: %s\n", s, strerror(errno));
    exit(1);
}

int main(int argc, char **argv) {
    if (argc != 4) {
        fprintf(stderr, "usage: bgzf_encode_g INPUT OUTPUT INDEX G\n");
        return 2;
    }
    char *end = NULL;
    unsigned long parsed = strtoul(argv[3], &end, 10);
    if (!argv[3][0] || *end || parsed < 1 || parsed > 65280) {
        fprintf(stderr, "STOP: G must be 1..65280 bytes\n");
        return 2;
    }
    size_t g = (size_t)parsed;
    FILE *in = fopen(argv[1], "rb");
    if (!in) die("open input");
    BGZF *out = bgzf_open(argv[2], "w6");
    if (!out) die("open output");
    if (bgzf_index_build_init(out) < 0) die("index init");

    unsigned char *buf = malloc(g);
    if (!buf) die("allocate");
    for (;;) {
        size_t n = fread(buf, 1, g, in);
        if (n) {
            if (bgzf_write(out, buf, n) != (ssize_t)n) die("bgzf_write");
            if (bgzf_flush(out) < 0) die("bgzf_flush");
        }
        if (n < g) {
            if (ferror(in)) die("read input");
            break;
        }
    }
    free(buf);
    if (fclose(in)) die("close input");
    if (bgzf_index_dump(out, argv[2], ".gzi") < 0) die("index dump");
    if (bgzf_close(out) < 0) die("close output");
    return 0;
}
