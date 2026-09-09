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
#ifdef COUNT_ZSTD
static uint64_t zstd_output;
size_t __real_ZSTD_decompressStream(ZSTD_DStream*,ZSTD_outBuffer*,ZSTD_inBuffer*);
size_t __wrap_ZSTD_decompressStream(ZSTD_DStream *s,ZSTD_outBuffer *o,ZSTD_inBuffer *i) {
    size_t before=o->pos, r=__real_ZSTD_decompressStream(s,o,i);
    if(!ZSTD_isError(r)) zstd_output += o->pos-before;
    return r;
}
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
        /* Copy archive to anonymous RAM-backed storage before any timed call.
           Keep one htslib handle and the .gzi index for the entire query trace. */
        fd=memfd_create("cabench-bgzf",MFD_CLOEXEC); if(fd<0) die("memfd_create");
        size_t done=0;
        while(done<an) { ssize_t n=write(fd,arc+done,an-done); if(n<=0) die("memfd write"); done+=(size_t)n; }
        if(lseek(fd,0,SEEK_SET)<0) die("memfd rewind");
        bgzf=bgzf_dopen(dup(fd),"r"); if(!bgzf) die("bgzf_dopen");
        if(bgzf_index_load(bgzf,argv[2],".gzi")) die("bgzf_index_load");
        if(counts) {
            reset_counts=(void(*)(void))dlsym(RTLD_DEFAULT,"cabench_reset");
            get_counts=(uint64_t(*)(void))dlsym(RTLD_DEFAULT,"cabench_bytes");
            if(!reset_counts||!get_counts) die("missing BGZF counters");
        }
    } else if(zs) {
        seek=ZSTD_seekable_create(); if(!seek) die("seekable create");
        size_t r=ZSTD_seekable_initBuff(seek,arc,an);
        if(ZSTD_isError(r)) die(ZSTD_getErrorName(r));
#ifndef COUNT_ZSTD
        if(counts) die("amplification needs instrumented binary");
#endif
    } else {
        /* Pinned ACEPX2 header, little endian; source reconstruction span is
           derived from the actual archive, not from the requested block setting. */
        if(an<68 || memcmp(arc,"ACEPX2\0\0",8)) die("ACEPX2 header");
        memcpy(&original,arc+12,8); memcpy(&block,arc+20,4);
        if(!block||original!=fn) die("ACEPX2 geometry");
    }
    unsigned char *raw=alloc(LENGTH);
    uint64_t seed=20260909;
    for(int q=-12;q<QUERIES;q++) {
        uint64_t start=q==-12 ? 0 : q==-11 ? fn-LENGTH : rng(&seed)%(fn-LENGTH+1);
        uint64_t end=start+LENGTH,span=LENGTH;
        if(end>fn) die("query bounds");
        uint64_t decoded=0;
        if(counts&&bg) reset_counts();
#ifdef COUNT_ZSTD
        zstd_output=0;
#endif
        double elapsed;
        if(bg) {
            double t0=now();
            int seek_rc=bgzf_useek(bgzf,(off_t)start,SEEK_SET);
            ssize_t r=bgzf_read(bgzf,raw,LENGTH);
            elapsed=(now()-t0)*1000;
            if(seek_rc!=0 || r!=LENGTH) die("BGZF region");
        } else if(zs) {
            double t0=now();
            size_t r=ZSTD_seekable_decompress(seek,raw,LENGTH,start);
            elapsed=(now()-t0)*1000;
            if(ZSTD_isError(r)||r!=LENGTH) die("zstd region");
        } else {
            double t0=now();
            int64_t r=aceapex_decompress_region(arc,an,raw,LENGTH,start,span);
            elapsed=(now()-t0)*1000;
            if(r!=LENGTH) die("ACEAPEX region");
        }
        /* Return checks, byte comparison and serialization are outside the timer.
           No FASTA parsing or newline removal occurs for any codec. */
        if(memcmp(raw,fasta+start,LENGTH)) die("region differs from original");
        if(counts) {
            if(bg) decoded=get_counts();
#ifdef COUNT_ZSTD
            else if(zs) decoded=zstd_output;
#endif
            else {
                uint64_t lo=(start/block)*block,hi=((end-1)/block+1)*block;
                if(hi>original) hi=original;
                decoded=hi-lo;
            }
        }
        if(q>=0) {
            printf("{\"query\":%d,\"byte_offset\":%llu,\"requested_bytes\":%d,\"verified\":true,",
                   q,(unsigned long long)start,LENGTH);
            if(counts) printf("\"decoded_output_bytes\":%llu}\n",(unsigned long long)decoded);
            else printf("\"latency_ms\":%.9f}\n",elapsed);
        }
    }
    if(bgzf && bgzf_close(bgzf)) die("bgzf_close");
    if(seek) ZSTD_seekable_free(seek);
    if(fd>=0) close(fd);
    free(arc); free(fasta); free(raw);
    return 0;
}
