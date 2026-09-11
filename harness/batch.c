/* Adapted from ACEAPEX scripts/batch_test_ci.c at 1b13df34ac8e839dd3232b59bc59560d689a435a.
   Unchanged snapshot and adaptation details are in harness/upstream/ and BATCH_METHOD.md. */
#include "codec_io.h"
#define LEN 16384
#define REPEATS 3
int main(int argc,char **argv) {
    if(argc!=7) cb_die("usage: batch CODEC ARCHIVE ORIGINAL RANGES N THREADS");
    CB c=cb_open(argv[1],argv[2],argv[3]);
    int n=atoi(argv[5]),threads=atoi(argv[6]); if(n<1||n>5000||threads<1) cb_die("batch parameters");
    int native=!c.bg&&!c.zs;
    uint64_t *offset=cb_alloc((size_t)n*sizeof(*offset));
    int64_t *status=cb_alloc((size_t)n*sizeof(*status));
    unsigned char *solo=cb_alloc((size_t)n*LEN),*bat=cb_alloc((size_t)n*LEN);
    memset(solo,0,(size_t)n*LEN); memset(bat,0,(size_t)n*LEN);
    aceapex_range_t *ranges=cb_alloc((size_t)n*sizeof(*ranges));
    FILE *f=fopen(argv[4],"r"); if(!f) cb_die("query trace");
    for(int i=0;i<n;i++) {
        unsigned long long off,len;
        if(fscanf(f,"%llu %llu",&off,&len)!=2||len!=LEN||off>c.size-LEN) cb_die("query bounds");
        offset[i]=(uint64_t)off; ranges[i].offset=off; ranges[i].length=LEN;
        ranges[i].dst=bat+(size_t)i*LEN; ranges[i].written=0;
    }
    unsigned long long extra; if(fscanf(f,"%llu",&extra)!=EOF) cb_die("extra queries"); fclose(f);
    unsigned char warm[LEN];
    for(int i=-2;i<10;i++) {
        uint64_t off=i==-2?0:i==-1?c.size-LEN:offset[i%n];
        if(cb_region(&c,warm,off,LEN)!=LEN||memcmp(warm,c.original+off,LEN)) cb_die("batch warmup differs");
    }
    if(native) {
        int w=n<10?n:10;

#define HWAPEX_EXTRACT_SECTION 5
#include "native/aceapex.inc"
#undef HWAPEX_EXTRACT_SECTION
        for(int i=0;i<w;i++) if(ranges[i].written!=LEN||memcmp(ranges[i].dst,c.original+offset[i],LEN)) cb_die("native warmup differs");
    }
    for(int rep=0;rep<REPEATS;rep++) {
        double loop_ms=0,batch_ms=0; int64_t ok=0;
        for(int order=0;order<(native?2:1);order++) {
            int batch=native && ((order+rep)%2==1);
            if(batch) {
                for(int i=0;i<n;i++) ranges[i].written=0;
                double t0=cb_ms();

#define HWAPEX_EXTRACT_SECTION 6
#include "native/aceapex.inc"
#undef HWAPEX_EXTRACT_SECTION
                batch_ms=cb_ms()-t0;
            } else {
                double t0=cb_ms();
                for(int i=0;i<n;i++) status[i]=cb_region(&c,solo+(size_t)i*LEN,offset[i],LEN);
                loop_ms=cb_ms()-t0;
            }
        }
        /* Full oracle and native-versus-single-call comparisons are untimed. */
        for(int i=0;i<n;i++) {
            if(status[i]!=LEN||memcmp(solo+(size_t)i*LEN,c.original+offset[i],LEN)) cb_die("loop result differs");
            if(native && (ok!=n||ranges[i].written!=LEN||memcmp(ranges[i].dst,solo+(size_t)i*LEN,LEN))) cb_die("batch result differs from single API");
        }
        if(loop_ms<=0||(native&&batch_ms<=0)) cb_die("invalid duration");
        printf("{\"repeat\":%d,\"method\":\"loop\",\"n\":%d,\"wall_ms\":%.9f,\"verified_responses\":%d,\"verified\":true}\n",rep,n,loop_ms,n);
        if(native) printf("{\"repeat\":%d,\"method\":\"batch\",\"n\":%d,\"wall_ms\":%.9f,\"verified_responses\":%d,\"matches_single_api\":true,\"verified\":true}\n",rep,n,batch_ms,n);
    }
    free(offset); free(status); free(solo); free(bat); free(ranges); cb_close(&c); return 0;
}
