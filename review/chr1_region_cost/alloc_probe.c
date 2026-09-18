#define _POSIX_C_SOURCE 200809L
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void die(const char *s){fprintf(stderr,"STOP: %s\n",s);exit(1);}
static unsigned char *readall(const char *p,size_t *n){
    FILE*f=fopen(p,"rb");if(!f)die("open");fseek(f,0,SEEK_END);long z=ftell(f);rewind(f);
    if(z<0)die("size");*n=(size_t)z;unsigned char*b=malloc(*n?*n:1);if(!b)die("malloc");
    if(fread(b,1,*n,f)!=*n)die("read");fclose(f);return b;
}
static void *sym(void *h,const char*n){void*p=dlsym(h,n);if(!p)die(n);return p;}
static uint64_t rng(uint64_t *s){
    *s=*s*UINT64_C(6364136223846793005)+UINT64_C(1442695040888963407);return *s;
}
int main(int argc,char**argv){
    if(argc!=4)die("usage: alloc_probe LIB ARCHIVE ORIGINAL");
    size_t an=0,on=0;unsigned char*arc=readall(argv[2],&an),*orig=readall(argv[3],&on);
    void*lib=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);if(!lib)die("dlopen");
    unsigned(*abi)(void)=sym(lib,"hc_abi");
    void*(*open_ctx)(const void*,size_t,const char*,uint64_t)=sym(lib,"hc_open");
    uint64_t(*size_ctx)(void*)=sym(lib,"hc_size");
    int64_t(*region)(void*,uint64_t,void*,size_t)=sym(lib,"hc_region");
    void(*close_ctx)(void*)=sym(lib,"hc_close");
    if(abi()!=2)die("abi");
    void*ctx=open_ctx(arc,an,NULL,UINT64_MAX);if(!ctx||size_ctx(ctx)!=on)die("context");
    unsigned char*out=malloc(16384);if(!out)die("out");

    void(*calibrate)(void)=sym(RTLD_DEFAULT,"mc_calibrate");
    void(*reset)(void)=sym(RTLD_DEFAULT,"mc_reset");
    void(*enable)(void)=sym(RTLD_DEFAULT,"mc_enable");
    void(*disable)(void)=sym(RTLD_DEFAULT,"mc_disable");
    uint64_t(*gm)(void)=sym(RTLD_DEFAULT,"mc_malloc_calls");
    uint64_t(*gf)(void)=sym(RTLD_DEFAULT,"mc_free_calls");
    uint64_t(*gc)(void)=sym(RTLD_DEFAULT,"mc_calloc_calls");
    uint64_t(*gr)(void)=sym(RTLD_DEFAULT,"mc_realloc_calls");
    uint64_t(*gbm)(void)=sym(RTLD_DEFAULT,"mc_malloc_bytes");
    uint64_t(*gbc)(void)=sym(RTLD_DEFAULT,"mc_calloc_bytes");
    uint64_t(*gbr)(void)=sym(RTLD_DEFAULT,"mc_realloc_bytes");
    uint64_t(*gan)(void)=sym(RTLD_DEFAULT,"mc_alloc_ns");
    uint64_t(*gfn)(void)=sym(RTLD_DEFAULT,"mc_free_ns");
    uint64_t(*gco)(void)=sym(RTLD_DEFAULT,"mc_clock_overhead_ns");
    calibrate();

    uint64_t seed=20260909;
    for(int q=-12;q<200;q++){
        uint64_t off=q==-12?0:q==-11?on-16384:rng(&seed)%(on-16384+1);
        if(q<0){
            if(region(ctx,off,out,16384)!=16384||memcmp(out,orig+off,16384))die("warmup");
            continue;
        }
        reset();enable();
        int64_t n=region(ctx,off,out,16384);
        disable();
        if(n!=16384||memcmp(out,orig+off,16384))die("mismatch");
        printf("{\"query\":%d,\"offset\":%llu,\"malloc\":%llu,\"free\":%llu,"
               "\"calloc\":%llu,\"realloc\":%llu,\"malloc_bytes\":%llu,"
               "\"calloc_bytes\":%llu,\"realloc_bytes\":%llu,"
               "\"alloc_ns\":%llu,\"free_ns\":%llu,\"clock_pair_overhead_ns\":%llu}\n",
               q,(unsigned long long)off,(unsigned long long)gm(),(unsigned long long)gf(),
               (unsigned long long)gc(),(unsigned long long)gr(),
               (unsigned long long)gbm(),(unsigned long long)gbc(),(unsigned long long)gbr(),
               (unsigned long long)gan(),(unsigned long long)gfn(),(unsigned long long)gco());
    }
    close_ctx(ctx);dlclose(lib);free(out);free(orig);free(arc);return 0;
}
