/* xxh3sum FILE... : XXH3_64bits of each file, 16 lowercase hex digits (MANIFEST fasta_xxh3 format), then the path.
   Build: cc -O2 -I <dir with xxhash.h> -o xxh3sum xxh3sum.c   (xxhash.h = aceapex src/xxhash.h, xxHash 0.8) */
#define XXH_INLINE_ALL
#include "xxhash.h"
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    static unsigned char buf[1 << 20];
    int rc = 0;
    for (int i = 1; i < argc; i++) {
        FILE *f = fopen(argv[i], "rb");
        if (!f) { perror(argv[i]); rc = 1; continue; }
        XXH3_state_t *s = XXH3_createState();
        XXH3_64bits_reset(s);
        size_t n;
        while ((n = fread(buf, 1, sizeof buf, f)) > 0) XXH3_64bits_update(s, buf, n);
        if (ferror(f)) { perror(argv[i]); rc = 1; }
        printf("%016llx  %s\n", (unsigned long long)XXH3_64bits_digest(s), argv[i]);
        XXH3_freeState(s);
        fclose(f);
    }
    return rc;
}
