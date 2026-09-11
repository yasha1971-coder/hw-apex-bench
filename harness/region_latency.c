#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/mman.h>
#include <dlfcn.h>
#include <htslib/bgzf.h>
#include "zstd_seekable.h"
#include "aceapex.h"

#define LENGTH 16384
#define QUERIES 200

static void die(const char *s) { fprintf(stderr,"STOP: %s\n",s); exit(1); }
static void *alloc(size_t n) { void *p=malloc(n?n:1); if(!p) die("allocation"); return p; }
static unsigned char *readall(const char *path,size_t *n) {
    FILE *f=fopen(path,"rb"); if(!f) die(path);
    if(fseek(f,0,SEEK_END)) die("seek");
    long size=ftell(f); if(size<0) die("size"); *n=(size_t)size;
    rewind(f); unsigned char *p=alloc(*n);
    if(fread(p,1,*n,f)!=*n) die("short read");
    fclose(f); return p;
}
static uint64_t rng(uint64_t *s) {
    *s=*s*UINT64_C(6364136223846793005)+UINT64_C(1442695040888963407);
    return *s;
}
static double now(void) {
    struct timespec t; if(clock_gettime(CLOCK_MONOTONIC,&t)) die("clock");
    return (double)t.tv_sec+(double)t.tv_nsec*1e-9;
}
#ifdef COUNT_DECODER
void cabench_ace_reset(void);
uint64_t cabench_ace_bytes(unsigned);
void cabench_zstd_reset(void);
uint64_t cabench_zstd_bytes(void);
#endif
int main(int argc,char **argv) {
    if(argc!=5) die("usage: region_latency CODEC ARCHIVE FASTA latency|amplification");
    const char *codec=argv[1];
    int bg=!strcmp(codec,"bgzip+htslib"), zs=!strcmp(codec,"zstd-seekable");
    if(!bg&&!zs&&strcmp(codec,"aceapex")) die("unknown codec");
    int counts=!strcmp(argv[4],"amplification");
    if(!counts && strcmp(argv[4],"latency")) die("unknown phase");
    size_t an,fn;
    unsigned char *arc=readall(argv[2],&an),*fasta=readall(argv[3],&fn);
    if(fn!=253935557 || memcmp(fasta,">chr1\n",6)) die("unexpected FASTA layout");
    BGZF *bgzf=NULL; ZSTD_seekable *seek=NULL;
    int fd=-1; uint32_t block=0; uint64_t original=0;
    void (*reset_counts)(void)=NULL;
    uint64_t (*get_counts)(void)=NULL;
    if(bg) {
#define HWAPEX_EXTRACT_SECTION 1
#include "native/bgzip.inc"
#undef HWAPEX_EXTRACT_SECTION
    } else if(zs) {
#define HWAPEX_EXTRACT_SECTION 1
#include "native/zstd_seekable.inc"
#undef HWAPEX_EXTRACT_SECTION
    } else {
#define HWAPEX_EXTRACT_SECTION 1
#include "native/aceapex.inc"
#undef HWAPEX_EXTRACT_SECTION
    }
    unsigned char *raw=alloc(LENGTH);
    uint64_t seed=20260909;
    for(int q=-12;q<QUERIES;q++) {
        uint64_t start=q==-12 ? 0 : q==-11 ? fn-LENGTH : rng(&seed)%(fn-LENGTH+1);
        uint64_t end=start+LENGTH,span=LENGTH;
        if(end>fn) die("query bounds");
        uint64_t decoded=0;
        if(counts&&bg) reset_counts();
#ifdef COUNT_DECODER
        cabench_ace_reset(); cabench_zstd_reset();
#endif
        double elapsed;
        if(bg) {
#define HWAPEX_EXTRACT_SECTION 2
#include "native/bgzip.inc"
#undef HWAPEX_EXTRACT_SECTION
        } else if(zs) {
#define HWAPEX_EXTRACT_SECTION 2
#include "native/zstd_seekable.inc"
#undef HWAPEX_EXTRACT_SECTION
        } else {
#define HWAPEX_EXTRACT_SECTION 2
#include "native/aceapex.inc"
#undef HWAPEX_EXTRACT_SECTION
        }
        /* Return checks, byte comparison and serialization are outside the timer.
           No FASTA parsing or newline removal occurs for any codec. */
        if(memcmp(raw,fasta+start,LENGTH)) die("region differs from original");
        if(counts) {
            if(bg) decoded=get_counts();
#ifdef COUNT_DECODER
            else if(zs) decoded=cabench_zstd_bytes();
            else for(unsigned i=0;i<4;i++) decoded+=cabench_ace_bytes(i);
#endif

        }
        if(q>=0) {
            printf("{\"query\":%d,\"byte_offset\":%llu,\"requested_bytes\":%d,\"verified\":true,",
                   q,(unsigned long long)start,LENGTH);
            if(counts) {
                printf("\"decoded_bytes\":%llu",(unsigned long long)decoded);
#ifdef COUNT_DECODER
                if(!bg&&!zs) printf(",\"stream_decoded_bytes\":[%llu,%llu,%llu,%llu]",
                    (unsigned long long)cabench_ace_bytes(0),(unsigned long long)cabench_ace_bytes(1),
                    (unsigned long long)cabench_ace_bytes(2),(unsigned long long)cabench_ace_bytes(3));
#endif
                printf("}\n");
            }
            else printf("\"latency_ms\":%.9f}\n",elapsed);
        }
    }
    if(bgzf && bgzf_close(bgzf)) die("bgzf_close");
    if(seek) ZSTD_seekable_free(seek);
    if(fd>=0) close(fd);
    free(arc); free(fasta); free(raw);
    return 0;
}
