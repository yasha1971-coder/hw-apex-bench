#include <stdint.h>
#include <time.h>
#include <stddef.h>
extern int64_t hc_region(void *,uint64_t,void *,size_t);
static int64_t now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec*INT64_C(1000000000)+t.tv_nsec;}
int pair(void *ctx,uint64_t off,size_t n,void *a,void *b,int64_t *ns){
 int64_t t=now(),r=hc_region(ctx,off,a,n),u=now();
 if(r!=(int64_t)n)return -1;
 int64_t v=now();r=hc_region(ctx,off,b,n);ns[1]=now()-v;ns[0]=u-t;
 return r==(int64_t)n?0:-1;
}
