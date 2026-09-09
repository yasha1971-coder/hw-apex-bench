#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <zlib.h>
static uint64_t bytes;
void cabench_reset(void) { bytes=0; }
uint64_t cabench_bytes(void) { return bytes; }
static void *resolve(const char *s) {
    void *p=dlsym(RTLD_NEXT,s);
    if(!p) { fprintf(stderr,"counter cannot resolve %s\n",s); abort(); }
    return p;
}
int inflate(z_streamp s,int flush) {
    static int (*real)(z_streamp,int);
    if(!real) real=(int(*)(z_streamp,int))resolve("inflate");
    uLong before=s->total_out; int r=real(s,flush);
    bytes+=(uint64_t)(s->total_out-before); return r;
}
struct libdeflate_decompressor;
int libdeflate_deflate_decompress(struct libdeflate_decompressor *d,
        const void *in,size_t in_n,void *out,size_t out_n,size_t *actual) {
    typedef int (*fn)(struct libdeflate_decompressor*,const void*,size_t,void*,size_t,size_t*);
    static fn real;
    if(!real) real=(fn)resolve("libdeflate_deflate_decompress");
    size_t written=0;
    int r=real(d,in,in_n,out,out_n,actual?actual:&written);
    if(r==0) bytes+=actual?*actual:written;
    return r;
}
