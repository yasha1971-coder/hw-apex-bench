/* Adapted from ACEAPEX scripts/breakeven.c at 1b13df34ac8e839dd3232b59bc59560d689a435a.
   Full decode duration is auxiliary to N; this is not a plateau-throughput claim. */
#include "codec_io.h"
int main(int argc,char **argv) {
    if(argc!=4) cb_die("usage: breakeven CODEC ARCHIVE ORIGINAL");
    CB c=cb_open(argv[1],argv[2],argv[3]);
    unsigned char *out=cb_alloc(c.size); memset(out,0,c.size);
    for(int rep=-1;rep<5;rep++) {
        double t0=cb_ms();
        int64_t n=cb_full(&c,out);
        double elapsed=cb_ms()-t0;
        if(n!=(int64_t)c.size||memcmp(out,c.original,c.size)) cb_die("full decode differs");
        if(rep>=0) printf("{\"repeat\":%d,\"wall_ms\":%.9f,\"verified_bytes\":%zu,\"verified\":true}\n",rep,elapsed,c.size);
    }
    free(out); cb_close(&c); return 0;
}
