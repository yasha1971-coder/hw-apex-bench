#define _POSIX_C_SOURCE 200809L
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static volatile uint64_t sinkv=0;
static void die(const char*s){fprintf(stderr,"STOP: %s\n",s);exit(1);}
static unsigned char*readall(const char*p,size_t*n){
    FILE*f=fopen(p,"rb");if(!f)die("open");fseek(f,0,SEEK_END);long z=ftell(f);rewind(f);
    if(z<0)die("size");*n=(size_t)z;unsigned char*b=malloc(*n?*n:1);if(!b)die("malloc");
    if(fread(b,1,*n,f)!=*n)die("read");fclose(f);return b;
}
static void*sym(void*h,const char*n){void*p=dlsym(h,n);if(!p)die(n);return p;}
static uint64_t rng(uint64_t*s){
    *s=*s*UINT64_C(6364136223846793005)+UINT64_C(1442695040888963407);return *s;
}
int main(int argc,char**argv){
    if(argc!=4)die("usage: perf_loop LIB ARCHIVE N");
    char*e=NULL;long N=strtol(argv[3],&e,10);if(!argv[3][0]||*e||N<0||N>200000)die("N");
    size_t an=0;unsigned char*arc=readall(argv[2],&an);
    void*lib=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);if(!lib)die("dlopen");
    unsigned(*abi)(void)=sym(lib,"hc_abi");
    void*(*open_ctx)(const void*,size_t,const char*,uint64_t)=sym(lib,"hc_open");
    uint64_t(*size_ctx)(void*)=sym(lib,"hc_size");
    int64_t(*region)(void*,uint64_t,void*,size_t)=sym(lib,"hc_region");
    void(*close_ctx)(void*)=sym(lib,"hc_close");
    if(abi()!=2)die("abi");
    void*ctx=open_ctx(arc,an,NULL,UINT64_MAX);if(!ctx)die("context");
    uint64_t size=size_ctx(ctx);if(size<16384)die("size");
    unsigned char*out=malloc(16384);if(!out)die("out");
    uint64_t seed=20260909;
    for(int q=-12;q<0;q++){
        uint64_t off=q==-12?0:q==-11?size-16384:rng(&seed)%(size-16384+1);
        if(region(ctx,off,out,16384)!=16384)die("warmup");
        sinkv+=out[0];
    }
    uint64_t *offs=malloc((size_t)(N?N:1)*sizeof(uint64_t));if(!offs)die("offsets");
    for(long i=0;i<N;i++)offs[i]=rng(&seed)%(size-16384+1);
    for(long i=0;i<N;i++){
        if(region(ctx,offs[i],out,16384)!=16384)die("region");
        sinkv+=out[(unsigned)i&16383];
    }
    printf("{\"queries\":%ld,\"sink\":%llu}\n",N,(unsigned long long)sinkv);
    free(offs);free(out);close_ctx(ctx);dlclose(lib);free(arc);return 0;
}
