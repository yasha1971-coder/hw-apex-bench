#define _POSIX_C_SOURCE 200809L
/* Codec-independent resident worker. No shell, Python or file I/O is timed.
 * Region workload and decode warmup/repetitions match the historical workers.
 * stdout is a candidate artifact: accept only after process exit status is zero.
 */
#include "resident_context.h"
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static void die(const char *s) { fprintf(stderr,"STOP: %s\n",s); exit(1); }
static void *alloc(size_t n) {
    void *p=malloc(n?n:1); if(!p) die("allocation"); return p;
}
static unsigned char *readall(const char *path,size_t *n) {
    FILE *f=fopen(path,"rb"); if(!f) die("open input");
    if(fseek(f,0,SEEK_END)) die("seek input");
    long length=ftell(f); if(length<0) die("input size");
    *n=(size_t)length; rewind(f);
    unsigned char *p=alloc(*n);
    if(fread(p,1,*n,f)!=*n || fclose(f)) die("read input");
    return p;
}
static double now(void) {
    struct timespec t; if(clock_gettime(CLOCK_MONOTONIC,&t)) die("clock");
    return (double)t.tv_sec+(double)t.tv_nsec*1e-9;
}
static void *symbol(void *lib,const char *name) {
    void *p=dlsym(lib,name); if(!p) die(name); return p;
}
static uint64_t rng(uint64_t *s) {
    *s=*s*UINT64_C(6364136223846793005)+UINT64_C(1442695040888963407);
    return *s;
}
int main(int argc,char **argv) {
    if(argc!=6 && argc!=7) die("usage: native_measure LIB ARCHIVE ORIGINAL region|decode SIDECAR [REPEATS]");
    int region=!strcmp(argv[4],"region");
    if(!region && strcmp(argv[4],"decode")) die("unknown phase");
    int repeats=5;
    if(argc==7) {
        char *end; long n=strtol(argv[6],&end,10);
        if(!*argv[6] || *end || n<0 || n>20 || region) die("invalid repeats");
        repeats=(int)n;
    }
    size_t an,fn;
    unsigned char *arc=readall(argv[2],&an),*original=readall(argv[3],&fn);
    if(region && fn<16384) die("region corpus must contain at least 16384 bytes");
    void *lib=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL); if(!lib) die("load context library");
    unsigned (*abi)(void)=symbol(lib,"hc_abi");
    void *(*open_ctx)(const void*,size_t,const char*,uint64_t)=symbol(lib,"hc_open");
    uint64_t (*size_ctx)(void*)=symbol(lib,"hc_size");
    int64_t (*read_region)(void*,uint64_t,void*,size_t)=symbol(lib,"hc_region");
    int64_t (*decode)(void*,void*,size_t)=symbol(lib,"hc_decode");
    void (*close_ctx)(void*)=symbol(lib,"hc_close");
    if(abi()!=2) die("unsupported context ABI");
    void *ctx=open_ctx(arc,an,*argv[5]?argv[5]:NULL,UINT64_MAX);
    if(!ctx || size_ctx(ctx)!=fn) die("archive size mismatch");
    size_t length=region?16384:fn;
    if(length>SIZE_MAX-32) die("output size overflow");
    unsigned char *guard=alloc(length+32),*out=guard+16;
    memset(guard,0xa5,length+32); /* prefault and guards outside timing */
    uint64_t seed=20260909;
    for(int q=region?-12:-1;q<(region?200:repeats);q++) {
        uint64_t start=region?(q==-12?0:q==-11?fn-length:rng(&seed)%(fn-length+1)):0;
        int64_t n; double elapsed;
        if(region) {
            double t0=now(); n=read_region(ctx,start,out,length); elapsed=(now()-t0)*1000.;
        } else {
            double t0=now(); n=decode(ctx,out,length); elapsed=(now()-t0)*1000.;
        }
        if(n!=(int64_t)length || memcmp(out,original+start,length)) die("decoded bytes differ");
        for(unsigned i=0;i<16;i++)
            if(guard[i]!=0xa5 || guard[16+length+i]!=0xa5) die("destination guard overwritten");
        if(q<0) continue;
        if(region) printf("{\"query\":%d,\"byte_offset\":%llu,\"requested_bytes\":16384,\"verified\":true,\"latency_ms\":%.9f}\n",q,(unsigned long long)start,elapsed);
        else printf("{\"repeat\":%d,\"wall_ms\":%.9f,\"verified_bytes\":%zu,\"verified\":true}\n",q,elapsed,fn);
    }
    close_ctx(ctx); dlclose(lib); free(guard); free(original); free(arc);
    if(fflush(stdout) || ferror(stdout)) die("write samples");
    return 0;
}
