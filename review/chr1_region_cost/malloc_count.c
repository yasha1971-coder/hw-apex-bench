#define _GNU_SOURCE
#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

extern void *__libc_malloc(size_t);
extern void __libc_free(void *);
extern void *__libc_calloc(size_t,size_t);
extern void *__libc_realloc(void *,size_t);

static _Atomic int enabled=0;
static _Atomic uint64_t n_malloc=0,n_free=0,n_calloc=0,n_realloc=0;
static _Atomic uint64_t b_malloc=0,b_calloc=0,b_realloc=0;

void mc_reset(void) {
    atomic_store(&n_malloc,0); atomic_store(&n_free,0);
    atomic_store(&n_calloc,0); atomic_store(&n_realloc,0);
    atomic_store(&b_malloc,0); atomic_store(&b_calloc,0); atomic_store(&b_realloc,0);
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

void *malloc(size_t n) {
    void *p=__libc_malloc(n);
    if(atomic_load(&enabled)){atomic_fetch_add(&n_malloc,1);atomic_fetch_add(&b_malloc,n);}
    return p;
}
void free(void *p) {
    if(atomic_load(&enabled) && p) atomic_fetch_add(&n_free,1);
    __libc_free(p);
}
void *calloc(size_t a,size_t b) {
    void *p=__libc_calloc(a,b);
    if(atomic_load(&enabled)){atomic_fetch_add(&n_calloc,1);atomic_fetch_add(&b_calloc,a*b);}
    return p;
}
void *realloc(void *p,size_t n) {
    void *q=__libc_realloc(p,n);
    if(atomic_load(&enabled)){atomic_fetch_add(&n_realloc,1);atomic_fetch_add(&b_realloc,n);}
    return q;
}
