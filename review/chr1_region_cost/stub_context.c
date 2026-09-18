#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef struct{uint64_t size;} S;
unsigned hc_abi(void){return 2;}
uint64_t hc_size(void *p){return ((S*)p)->size;}
const char *hc_version(void){return "perf-loop-stub";}
void *hc_open(const void *arc,size_t bytes,const char *sidecar,uint64_t expected){
    (void)sidecar;
    if(!arc||bytes<20||memcmp(arc,"ACEPX2\0\0",8))return NULL;
    const unsigned char *a=arc;uint64_t n=0;for(int i=0;i<8;i++)n|=(uint64_t)a[12+i]<<(8*i);
    if(expected!=UINT64_MAX&&expected!=n)return NULL;
    S*s=malloc(sizeof(*s));if(s)s->size=n;return s;
}
int64_t hc_region(void *p,uint64_t off,void *dst,size_t len){
    S*s=p;if(off>s->size||len>s->size-off)return -1;
    if(len)((unsigned char*)dst)[0]=0;
    return (int64_t)len;
}
int64_t hc_decode(void *p,void *dst,size_t cap){(void)p;(void)dst;(void)cap;return -1;}
void hc_close(void *p){free(p);}
