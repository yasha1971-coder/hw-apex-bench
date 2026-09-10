/* Full-decode plateau sample. Archive and expected bytes are resident before
   timing; only the library decode call is inside the clock interval. */
#include "codec_io.h"

int main(int argc,char **argv) {
    if(argc!=5) cb_die("usage: throughput CODEC ARCHIVE ORIGINAL REPEATS");
    int repeats=atoi(argv[4]);
    if(repeats<0||repeats>20) cb_die("invalid repeats");
    CB c=cb_open(argv[1],argv[2],argv[3]);
    unsigned char *out=cb_alloc(c.size);
    memset(out,0,c.size); /* prefault output outside the timed region */
    for(int rep=-1;rep<repeats;rep++) {
        double t0=cb_ms();
        int64_t n=cb_full(&c,out);
        double elapsed=cb_ms()-t0;
        if(n!=(int64_t)c.size||memcmp(out,c.original,c.size))
            cb_die("full decode differs");
        if(rep>=0) printf("{\"repeat\":%d,\"wall_ms\":%.9f,"
                         "\"verified_bytes\":%zu,\"verified\":true}\n",
                         rep,elapsed,c.size);
    }
    free(out); cb_close(&c); return 0;
}
