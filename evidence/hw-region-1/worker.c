#define _POSIX_C_SOURCE 200809L
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <inttypes.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "resident_context.h"

/* Only the latency and constant branches call stamp(). Counter/check/probe
 * branches do not read a timing clock. No serialization occurs in a region
 * interval; all returned regions are retained until all calls have finished. */
enum { REGION=16384, QUERIES=1000, WARMUPS=12, GUARD=16 };
typedef struct { unsigned char *p; size_t n; } Bytes;
typedef struct {
    uint64_t offset, ns, calls, zbytes, materialized, dctx, oneshot, stream;
    unsigned pass;
} Row;
static void fail(const char *s) { fprintf(stderr,"STOP: %s\n",s); exit(1); }
static void *allocate(size_t n) { void *p=malloc(n?n:1); if(!p) fail("allocation"); return p; }
static Bytes readall(const char *name) {
    FILE *f=fopen(name,"rb"); if(!f) fail(name);
    if(fseek(f,0,SEEK_END)) fail("input seek");
    long n=ftell(f); if(n<0) fail("input length"); rewind(f);
    Bytes b={(unsigned char*)allocate((size_t)n),(size_t)n};
    if(fread(b.p,1,b.n,f)!=b.n || fclose(f)) fail("input read"); return b;
}
static uint64_t little(const unsigned char *p) { uint64_t n=0; for(unsigned i=0;i<8;i++) n|=(uint64_t)p[i]<<(8*i); return n; }
static void *symbol(void *lib,const char *name) { void *p=dlsym(lib,name); if(!p) fail(name); return p; }
static uint64_t stamp(void) {
    struct timespec t; if(clock_gettime(CLOCK_MONOTONIC,&t)) fail("clock");
    return (uint64_t)t.tv_sec*UINT64_C(1000000000)+(uint64_t)t.tv_nsec;
}
static void timing_gate(void) {
    const char *s=getenv("OVH_BENCH_LOCK_HELD");
    if(!s || strcmp(s,"/run/lock/ovh-bench.lock")) fail("external OVH-BENCH lock required");
    cpu_set_t mask; if(sched_getaffinity(0,sizeof(mask),&mask) || CPU_COUNT(&mask)!=1 || !CPU_ISSET(0,&mask)) fail("CPU0 affinity required");
}
static void guards(const unsigned char *p,size_t n) { for(unsigned i=0;i<GUARD;i++) if(p[i]!=0xa5 || p[GUARD+n+i]!=0xa5) fail("output guard overwritten"); }
static FILE *newfile(const char *prefix,const char *suffix) {
    size_t n=strlen(prefix)+strlen(suffix)+1; char *name=allocate(n);
    if(snprintf(name,n,"%s%s",prefix,suffix)<0) fail("output name");
    FILE *f=fopen(name,"wbx"); free(name); if(!f) fail("output must be new"); return f;
}
static void checked_close(FILE *f) { if(fflush(f)||ferror(f)||fclose(f)) fail("output write"); }

static int regions(int argc,char **argv) {
    if(argc!=11) fail("usage: worker region latency|counter|check|probe LIB ARCHIVE ORIGINAL SIDECAR WARMUPS.bin TRACE.bin PREFIX PASSES");
    int timed=!strcmp(argv[2],"latency"), counts=!strcmp(argv[2],"counter")||!strcmp(argv[2],"probe");
    int check=!strcmp(argv[2],"check"), probe=!strcmp(argv[2],"probe");
    if(!timed&&!counts&&!check) fail("unknown region mode");
    if(timed) timing_gate();
    unsigned passes=!strcmp(argv[10],"1")?1:!strcmp(argv[10],"2")?2:0;
    if(!passes || (!timed&&passes!=1)) fail("one pass or two timed AA passes required");
    Bytes arc=readall(argv[4]), original=readall(argv[5]), warm=readall(argv[7]), trace=readall(argv[8]);
    if(trace.n%8 || !trace.n || warm.n%8 || (warm.n!=WARMUPS*8 && !(probe&&warm.n==0))) fail("trace/warmup shape");
    size_t queries=trace.n/8, warmups=warm.n/8;
    if((!probe&&queries!=QUERIES) || queries>5000 || original.n<REGION) fail("exactly 1000 production queries required");
    for(size_t i=0;i<queries;i++) if(little(trace.p+8*i)>original.n-REGION) fail("trace bounds");
    for(size_t i=0;i<warmups;i++) if(little(warm.p+8*i)>original.n-REGION) fail("warmup bounds");
    void *lib=dlopen(argv[3],RTLD_NOW|RTLD_LOCAL); if(!lib) fail(dlerror());
    unsigned (*abi)(void)=symbol(lib,"hc_abi");
    void *(*open_ctx)(const void*,size_t,const char*,uint64_t)=symbol(lib,"hc_open");
    uint64_t (*size_ctx)(void*)=symbol(lib,"hc_size");
    int64_t (*region)(void*,uint64_t,void*,size_t)=symbol(lib,"hc_region");
    int64_t (*decode)(void*,void*,size_t)=symbol(lib,"hc_decode");
    void (*close_ctx)(void*)=symbol(lib,"hc_close");
    void (*reset)(void*)=counts?symbol(lib,"hc_count_reset"):NULL;
    uint64_t (*nbytes)(void*)=counts?symbol(lib,"hc_count_bytes"):NULL;
    uint64_t (*zcalls)(void*)=counts?symbol(lib,"hc_count_zstd_calls"):NULL;
    uint64_t (*zbytes)(void*)=counts?symbol(lib,"hc_count_zstd_bytes"):NULL;
    uint64_t (*dctx)(void*)=counts?symbol(lib,"hc_count_dctx_calls"):NULL;
    uint64_t (*oneshot)(void*)=counts?symbol(lib,"hc_count_oneshot_calls"):NULL;
    uint64_t (*stream)(void*)=counts?symbol(lib,"hc_count_stream_calls"):NULL;
    if(abi()!=2) fail("resident ABI 2 required");
    const size_t stride=REGION+2*GUARD;
    unsigned char *outputs=allocate((size_t)passes*queries*stride), *warmbuf=allocate(stride);
    Row *rows=calloc((size_t)passes*queries,sizeof(*rows)); if(!rows) fail("row allocation");
    for(unsigned pass=0;pass<passes;pass++) {
        void *ctx=open_ctx(arc.p,arc.n,*argv[6]?argv[6]:NULL,UINT64_MAX);
        if(!ctx||size_ctx(ctx)!=original.n) fail("archive size/context");
        if(check) {
            unsigned char *whole=allocate(original.n+2*GUARD); memset(whole,0xa5,original.n+2*GUARD);
            int64_t n=decode(ctx,whole+GUARD,original.n);
            if(n!=(int64_t)original.n || memcmp(whole+GUARD,original.p,original.n)) fail("full restore");
            guards(whole,original.n); free(whole);
            close_ctx(ctx); ctx=open_ctx(arc.p,arc.n,*argv[6]?argv[6]:NULL,UINT64_MAX);
            if(!ctx||size_ctx(ctx)!=original.n) fail("fresh context after full restore");
        }
        memset(outputs+(size_t)pass*queries*stride,0xa5,queries*stride); memset(warmbuf,0xa5,stride);
        for(size_t q=0;q<warmups;q++) {
            uint64_t off=little(warm.p+8*q); int64_t n=region(ctx,off,warmbuf+GUARD,REGION);
            if(n!=REGION || memcmp(warmbuf+GUARD,original.p+off,REGION)) fail("warmup restore"); guards(warmbuf,REGION);
        }
        for(size_t q=0;q<queries;q++) {
            Row *row=rows+(size_t)pass*queries+q; row->offset=little(trace.p+8*q); row->pass=pass;
            unsigned char *destination=outputs+((size_t)pass*queries+q)*stride;
            if(counts) reset(ctx);
            uint64_t begin=0,end=0; if(timed) begin=stamp();
            int64_t n=region(ctx,row->offset,destination+GUARD,REGION);
            if(timed) end=stamp();
            if(timed) { if(end<=begin) fail("nonpositive interval"); row->ns=end-begin; }
            if(n!=REGION || memcmp(destination+GUARD,original.p+row->offset,REGION)) fail("returned region differs");
            guards(destination,REGION);
            if(counts) { row->calls=zcalls(ctx); row->zbytes=zbytes(ctx); row->materialized=nbytes(ctx); row->dctx=dctx(ctx); row->oneshot=oneshot(ctx); row->stream=stream(ctx); }
        }
        close_ctx(ctx);
    }
    FILE *returned=newfile(argv[9],".regions.bin");
    for(size_t i=0;i<(size_t)passes*queries;i++) if(fwrite(outputs+i*stride+GUARD,1,REGION,returned)!=REGION) fail("returned region write");
    checked_close(returned);
    for(size_t i=0;i<(size_t)passes*queries;i++) {
        Row *r=rows+i;
        printf("{\"schema\":\"hw-region-1-native-row-v1\",\"pass\":%u,\"query\":%zu,\"offset\":%"PRIu64",\"requested_bytes\":%u,\"verified\":true,\"elapsed_ns\":",r->pass,i%queries,r->offset,REGION);
        if(timed) printf("%"PRIu64,r->ns); else printf("null");
        if(counts) printf(",\"zstd_calls\":%"PRIu64",\"zstd_bytes\":%"PRIu64",\"materialized_bytes\":%"PRIu64",\"dctx_calls\":%"PRIu64",\"oneshot_calls\":%"PRIu64",\"stream_calls\":%"PRIu64,r->calls,r->zbytes,r->materialized,r->dctx,r->oneshot,r->stream);
        else printf(",\"zstd_calls\":null,\"zstd_bytes\":null,\"materialized_bytes\":null,\"dctx_calls\":null,\"oneshot_calls\":null,\"stream_calls\":null");
        printf("}\n");
    }
    if(fflush(stdout)||ferror(stdout)) fail("row output");
    dlclose(lib); free(arc.p); free(original.p); free(warm.p); free(trace.p); free(outputs); free(warmbuf); free(rows); return 0;
}

static int constants(int argc,char **argv) {
    if(argc!=6) fail("usage: worker constants LIB RAW FRAME PREFIX"); timing_gate();
    Bytes raw=readall(argv[3]),frame=readall(argv[4]);
    if(raw.n!=4096 && raw.n!=16384 && raw.n!=65536 && raw.n!=262144) fail("constant frame size");
    void *lib=dlopen(argv[2],RTLD_NOW|RTLD_LOCAL); if(!lib) fail(dlerror());
    unsigned (*version)(void)=symbol(lib,"region_zstd_version_number");
    void *(*create)(void)=symbol(lib,"region_create_dctx");
    void (*release)(void*)=symbol(lib,"region_free_dctx");
    size_t (*unpack)(void*,void*,size_t,const void*,size_t)=symbol(lib,"region_decode_dctx");
    unsigned (*is_error)(size_t)=symbol(lib,"region_is_error");
    if(version()!=10507) fail("standalone zstd must be 1.5.7");
    void *ctx=create(); if(!ctx) fail("standalone DCtx");
    unsigned char *out=allocate(raw.n+2*GUARD); memset(out,0xa5,raw.n+2*GUARD);
    uint64_t ns[QUERIES];
    for(int i=-WARMUPS;i<QUERIES;i++) {
        uint64_t begin=0,end=0; if(i>=0) begin=stamp();
        size_t n=unpack(ctx,out+GUARD,raw.n,frame.p,frame.n);
        if(i>=0) end=stamp();
        if(is_error(n)||n!=raw.n||memcmp(out+GUARD,raw.p,raw.n)) fail("standalone restore"); guards(out,raw.n);
        if(i>=0) { if(end<=begin) fail("standalone interval"); ns[i]=end-begin; }
    }
    FILE *returned=newfile(argv[5],".decoded.bin"); if(fwrite(out+GUARD,1,raw.n,returned)!=raw.n) fail("standalone returned bytes"); checked_close(returned);
    for(unsigned i=0;i<QUERIES;i++) printf("{\"query\":%u,\"elapsed_ns\":%"PRIu64",\"decoded_bytes\":%zu,\"verified\":true}\n",i,ns[i],raw.n);
    if(fflush(stdout)||ferror(stdout)) fail("standalone rows");
    release(ctx); dlclose(lib); free(out); free(raw.p); free(frame.p); return 0;
}

int main(int argc,char **argv) {
    if(argc<2) fail("worker requires region or constants");
    if(!strcmp(argv[1],"region")) return regions(argc,argv);
    if(!strcmp(argv[1],"constants")) return constants(argc,argv);
    fail("unknown worker action"); return 1;
}
