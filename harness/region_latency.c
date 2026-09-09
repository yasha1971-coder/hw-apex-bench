#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/mman.h>
#include <dlfcn.h>
#include <htslib/faidx.h>
#include "zstd_seekable.h"
#include "aceapex.h"

#define LENGTH 16384
#define QUERIES 200
#define BASES UINT64_C(248956422)

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
static uint64_t byteoff(uint64_t base) { return 6+(base/50)*51+base%50; }
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
    faidx_t *fai=NULL; ZSTD_seekable *seek=NULL;
    int fd=-1; uint32_t block=0; uint64_t original=0;
    void (*reset_counts)(void)=NULL;
    uint64_t (*get_counts)(void)=NULL;
    if(bg) {
        /* Anonymous memory-backed file: no physical disk reads inside faidx.
           Existing FAI/GZI files are loaded during setup, outside the timer. */
        fd=memfd_create("cabench-bgzf",MFD_CLOEXEC); if(fd<0) die("memfd_create");
        size_t done=0;
        while(done<an) { ssize_t n=write(fd,arc+done,an-done); if(n<=0) die("memfd write"); done+=(size_t)n; }
        if(lseek(fd,0,SEEK_SET)<0) die("memfd rewind");
        char name[64]; snprintf(name,sizeof(name),"/proc/self/fd/%d",fd);
        char *fai_path=alloc(strlen(argv[2])+5),*gzi_path=alloc(strlen(argv[2])+5);
        sprintf(fai_path,"%s.fai",argv[2]); sprintf(gzi_path,"%s.gzi",argv[2]);
        fai=fai_load3(name,fai_path,gzi_path,0); if(!fai) die("fai_load3");
        free(fai_path); free(gzi_path);
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
    unsigned char *raw=alloc(LENGTH+1024),*out=alloc(LENGTH);
    uint64_t seed=20260909;
    for(int q=-12;q<QUERIES;q++) {
        uint64_t pos=q==-12 ? 0 : q==-11 ? BASES-LENGTH : rng(&seed)%(BASES-LENGTH+1);
        uint64_t start=byteoff(pos),end=byteoff(pos+LENGTH-1)+1,span=end-start;
        if(end>fn || span>LENGTH+1024) die("query bounds");
        uint64_t decoded=0;
        if(counts&&bg) reset_counts();
#ifdef COUNT_ZSTD
        zstd_output=0;
#endif
        double t0=now();
        char *fai_result=NULL; hts_pos_t length=0;
        if(bg) {
            fai_result=faidx_fetch_seq64(fai,"chr1",(hts_pos_t)pos,(hts_pos_t)(pos+LENGTH-1),&length);
            if(!fai_result||length!=LENGTH) die("faidx query");
        } else {
            if(zs) {
                size_t r=ZSTD_seekable_decompress(seek,raw,(size_t)span,start);
                if(ZSTD_isError(r)||r!=span) die("zstd region");
            } else {
                int64_t r=aceapex_decompress_region(arc,an,raw,LENGTH+1024,start,span);
                if(r!=(int64_t)span) die("ACEAPEX region");
            }
            size_t k=0;
            for(size_t j=0;j<span;j++) if(raw[j]!='\n') {
                if(k>=LENGTH) die("too many bases");
                out[k++]=raw[j];
            }
            if(k!=LENGTH) die("too few bases");
        }
        double elapsed=(now()-t0)*1000;
        /* Oracle comparison and output serialization are outside the timer. */
        const unsigned char *answer=bg?(const unsigned char*)fai_result:out;
        for(size_t j=0;j<LENGTH;j++)
            if(answer[j]!=fasta[byteoff(pos+j)]) die("region differs from original");
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
        free(fai_result);
        if(q>=0) {
            printf("{\"query\":%d,\"base_offset\":%llu,\"requested_bytes\":%d,"
                   "\"fasta_byte_offset\":%llu,\"fasta_span_bytes\":%llu,\"verified\":true,",
                   q,(unsigned long long)pos,LENGTH,(unsigned long long)start,(unsigned long long)span);
            if(counts) printf("\"decoded_output_bytes\":%llu}\n",(unsigned long long)decoded);
            else printf("\"latency_ms\":%.9f}\n",elapsed);
        }
    }
    if(fai) fai_destroy(fai);
    if(seek) ZSTD_seekable_free(seek);
    if(fd>=0) close(fd);
    free(arc); free(fasta); free(raw); free(out);
    return 0;
}
