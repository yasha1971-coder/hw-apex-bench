#define _GNU_SOURCE
#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <time.h>

extern void *__libc_malloc(size_t);
extern void __libc_free(void *);
extern void *__libc_calloc(size_t,size_t);
extern void *__libc_realloc(void *,size_t);

static _Atomic int enabled=0;
static _Atomic uint64_t n_malloc=0,n_free=0,n_calloc=0,n_realloc=0;
static _Atomic uint64_t b_malloc=0,b_calloc=0,b_realloc=0;
static _Atomic uint64_t ns_alloc=0,ns_free=0;
static _Atomic uint64_t clock_overhead=0;

static inline uint64_t ns_now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC_RAW,&t);
    return (uint64_t)t.tv_sec*UINT64_C(1000000000)+(uint64_t)t.tv_nsec;
}
void mc_calibrate(void) {
    uint64_t best=UINT64_MAX;
    for(int i=0;i<20000;i++) {
        uint64_t a=ns_now(),b=ns_now(),d=b-a;
        if(d<best) best=d;
    }
    atomic_store(&clock_overhead,best==UINT64_MAX?0:best);
}
static inline uint64_t corrected(uint64_t a,uint64_t b) {
    uint64_t d=b-a,o=atomic_load(&clock_overhead);
    return d>o?d-o:0;
}
void mc_reset(void) {
    atomic_store(&n_malloc,0); atomic_store(&n_free,0);
    atomic_store(&n_calloc,0); atomic_store(&n_realloc,0);
    atomic_store(&b_malloc,0); atomic_store(&b_calloc,0); atomic_store(&b_realloc,0);
    atomic_store(&ns_alloc,0); atomic_store(&ns_free,0);
}
void mc_enable(void){ atomic_store(&enabled,1); }
void mc_disable(void){ atomic_store(&enabled,0); }
uint64_t mc_malloc_calls(void){return atomic_load(&n_malloc);}
uint64_t mc_free_calls(void){return atomic_load(&n_free);}
uint64_t mc_calloc_calls(void){return atomic_load(&n_calloc);}
uint64_t mc_realloc_calls(void){return atomic_load(&n_realloc);}
uint64_t mc_malloc_bytes(void){return atomic_load(&b_malloc);}
uint64_t mc_calloc_bytes(void){return atomic_load(&b_calloc);}
uint64_t mc_realloc_bytes(void){return atomic_load(&b_realloc);}
uint64_t mc_alloc_ns(void){return atomic_load(&ns_alloc);}
uint64_t mc_free_ns(void){return atomic_load(&ns_free);}
uint64_t mc_clock_overhead_ns(void){return atomic_load(&clock_overhead);}

void *malloc(size_t n) {
    if(!atomic_load(&enabled)) return __libc_malloc(n);
    uint64_t a=ns_now(); void *p=__libc_malloc(n); uint64_t b=ns_now();
    atomic_fetch_add(&n_malloc,1); atomic_fetch_add(&b_malloc,n);
    atomic_fetch_add(&ns_alloc,corrected(a,b));
    return p;
}
void free(void *p) {
    if(!atomic_load(&enabled)) { __libc_free(p); return; }
    uint64_t a=ns_now(); __libc_free(p); uint64_t b=ns_now();
    if(p) atomic_fetch_add(&n_free,1);
    atomic_fetch_add(&ns_free,corrected(a,b));
}
void *calloc(size_t a,size_t b) {
    if(!atomic_load(&enabled)) return __libc_calloc(a,b);
    uint64_t t0=ns_now(); void *p=__libc_calloc(a,b); uint64_t t1=ns_now();
    atomic_fetch_add(&n_calloc,1); atomic_fetch_add(&b_calloc,a*b);
    atomic_fetch_add(&ns_alloc,corrected(t0,t1));
    return p;
}
void *realloc(void *p,size_t n) {
    if(!atomic_load(&enabled)) return __libc_realloc(p,n);
    uint64_t a=ns_now(); void *q=__libc_realloc(p,n); uint64_t b=ns_now();
    atomic_fetch_add(&n_realloc,1); atomic_fetch_add(&b_realloc,n);
    atomic_fetch_add(&ns_alloc,corrected(a,b));
    return q;
}
