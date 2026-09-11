#define _GNU_SOURCE
#include "adapter_api.h"
#include "adapter_util.h"
#include <dlfcn.h>
#include <errno.h>

static const cb_api *api;
static void die(const char *s) { fprintf(stderr,"adapter error: %s\n",s); exit(1); }
static uint64_t number(const char *s) {
    char *end; errno=0;
    if (!s[0] || s[0]=='-') die("invalid nonnegative integer");
    unsigned long long n=strtoull(s,&end,10);
    if (errno || *end) die("invalid integer");
    return n;
}
static void quote(const char *s) {
    putchar('"');
    for (;*s;s++) { unsigned char c=(unsigned char)*s;
        if (c=='"'||c=='\\') { putchar('\\');putchar(c); }
        else if(c<32) printf("\\u%04x",c); else putchar(c);
    } putchar('"');
}
static void *open_archive(const char *path) {
    void *ctx=api->open(path,UINT64_C(1)<<30);
    if(!ctx) die("cannot open archive (invalid data, missing index or size limit)");
    if(api->size(ctx)>(UINT64_C(1)<<30)) die("adapter violated output limit");
    return ctx;
}
static void check_guard(const unsigned char *b,size_t len) {
    for(size_t i=0;i<32;i++) if(b[i]!=0xa5 || b[32+len+i]!=0xa5) die("decoder wrote outside output buffer");
}
static uint64_t random64(uint64_t *s) { *s=*s*UINT64_C(6364136223846793005)+UINT64_C(1442695040888963407);return *s; }
static int check(const char *archive,const char *original) {
    size_t n; unsigned char *src=cb_load(original,&n); if(!src)die("cannot load expected input");
    void *ctx=open_archive(archive); if(api->size(ctx)!=n)die("decoded size differs from original");
    unsigned char *out=(unsigned char*)malloc(n+64);if(!out)die("allocation");
    memset(out,0xa5,n+64);
    if(api->decode(ctx,out+32,n)!=(int64_t)n || memcmp(out+32,src,n))die("full restore is not byte-exact");
    check_guard(out,n);
    unsigned reads=0;
    if(api->capabilities&CB_REGION) {
        uint64_t state=20260909;
        for(unsigned i=0;i<208;i++) {
            size_t len=n<16384?n:16384;
            uint64_t off=0;
            if(i==0)len=0;
            else if(i==1){off=n;len=0;}
            else if(i==2&&n){off=n-1;len=1;}
            else if(i==3&&n>16384){off=16383;len=n-off<16384?n-off:16384;}
            else if(i==4){off=n-len;}
            else if(i>=8)off=random64(&state)%(n-len+1);
            memset(out,0xa5,n+64);
            if(api->region(ctx,off,out+32,len)!=(int64_t)len || memcmp(out+32,src+off,len))die("region is not byte-exact");
            check_guard(out,len); reads++;
            if((api->capabilities&CB_H_ALPHA)&&off<n){uint64_t block;if(api->block_id(ctx,off,&block))die("block index lookup failed");}
        }
        if(api->region(ctx,n+1,out+32,0)>=0 || api->region(ctx,n,out+32,1)>=0 || api->region(ctx,UINT64_MAX,out+32,2)>=0)die("out-of-range read was accepted");
    }
    unsigned batches=0;
    if(api->capabilities&CB_BATCH) {
        cb_range ranges[4]; unsigned char buffers[4][96];
        for(unsigned i=0;i<4;i++){memset(buffers[i],0xa5,96);size_t len=n<32?n:32;uint64_t off=(i&1)?n-len:0;
            ranges[i]=(cb_range){off,len,buffers[i]+32,-1};}
        if(api->batch(ctx,ranges,4,1))die("native batch failed");
        for(unsigned i=0;i<4;i++){if(ranges[i].written!=(int64_t)ranges[i].length || memcmp(ranges[i].dst,src+ranges[i].offset,ranges[i].length))die("batch is not byte-exact");check_guard(buffers[i],ranges[i].length);}
        if(api->batch(ctx,ranges,0,1))die("empty batch failed");
        ranges[0].offset=UINT64_MAX;ranges[0].length=2;
        if(api->batch(ctx,ranges,1,1)==0)die("out-of-range batch was accepted");
        batches=2;
    }
    if(api->capabilities&CB_AMPLIFICATION){api->reset_counter(ctx);size_t len=n<16384?n:16384;
        if(api->region(ctx,0,out+32,len)!=(int64_t)len)die("counter read failed");
        (void)api->decoded_bytes(ctx); /* Counter semantics require a codec-specific reference test. */
    }
    api->close(ctx);free(out);free(src);
    printf("{\"verified\":\"byte-exact\",\"input_bytes\":%zu,\"region_checks\":%u,\"batch_checks\":%u,\"timed\":false}\n",n,reads,batches);
    return 0;
}
int main(int argc,char **argv) {
    if(sizeof(size_t)!=8)die("ABI v1 requires a 64-bit process");
    if(argc<3)die("usage: adapter_worker LIBRARY probe|compress|decompress|region|check ...");
    void *lib=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);if(!lib)die(dlerror());
    const cb_api *(*get)(void)=(const cb_api*(*)(void))dlsym(lib,"cabench_adapter_v1");
    if(!get)die("missing cabench_adapter_v1 export");
    api=get();
    if(!api||api->abi_version!=CB_ABI_VERSION||api->struct_size!=sizeof(cb_api))die("incompatible native ABI");
    if(!api->name||!api->version||!api->thread_policy||!api->open||!api->size||!api->decode||!api->close)die("missing required callback");
    if((api->capabilities&CB_ENCODE)&&!api->compress)die("declared encoder has no callback");
    if(api->capabilities & ~((UINT64_C(1)<<9)-1))die("unknown native capability bit");
    if((api->capabilities&CB_REGION)&&!api->region)die("declared region has no callback");
    if((api->capabilities&CB_BATCH)&&!api->batch)die("declared batch has no callback");
    if((api->capabilities&CB_H_ALPHA)&&!api->block_id)die("declared entropy has no block lookup");
    if((api->capabilities&CB_AMPLIFICATION)&&(!api->region||!api->reset_counter||!api->decoded_bytes))die("declared amplification has no counters");
    if(!strcmp(argv[2],"probe")) {
        printf("{\"abi\":1,\"capabilities\":%llu,\"name\":",(unsigned long long)api->capabilities);quote(api->name);
        printf(",\"version\":");quote(api->version);printf(",\"thread_policy\":");quote(api->thread_policy);puts("}");return 0;
    }
    if(!strcmp(argv[2],"compress")&&argc==6){if(!api->compress)die("native encoder not admitted; use the adapter's untimed codec_compress command");size_t n;unsigned char *in=cb_load(argv[3],&n);if(!in)die("cannot load input");uint64_t g=number(argv[5]);if(!g||g>UINT32_MAX)die("invalid granularity");int r=api->compress(in,n,argv[4],g,1);free(in);if(r)die("compression failed");return 0;}
    if(!strcmp(argv[2],"check")&&argc==5)return check(argv[3],argv[4]);
    if(!strcmp(argv[2],"decompress")&&argc==5){void *ctx=open_archive(argv[3]);size_t n=api->size(ctx);unsigned char *out=(unsigned char*)malloc(n?n:1);if(!out)die("allocation");if(api->decode(ctx,out,n)!=(int64_t)n||cb_save(argv[4],out,n))die("decompression failed");free(out);api->close(ctx);return 0;}
    if(!strcmp(argv[2],"region")&&argc==7){if(!(api->capabilities&CB_REGION))die("region unsupported");void *ctx=open_archive(argv[3]);uint64_t off=number(argv[4]),n=number(argv[5]);if(!cb_bounds(api->size(ctx),off,n))die("invalid region bounds");unsigned char *out=(unsigned char*)malloc(n?n:1);if(!out)die("allocation");if(api->region(ctx,off,out,n)!=(int64_t)n||cb_save(argv[6],out,n))die("region failed");free(out);api->close(ctx);return 0;}
    die("invalid command arguments");return 1;
}
