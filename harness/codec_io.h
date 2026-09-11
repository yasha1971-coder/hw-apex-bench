#ifndef CABENCH_CODEC_IO_H
#define CABENCH_CODEC_IO_H
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/mman.h>
#include <htslib/bgzf.h>
#include "zstd_seekable.h"
#include "aceapex.h"

static void cb_die(const char *s) { fprintf(stderr,"STOP: %s\n",s); exit(1); }
static void *cb_alloc(size_t n) { void *p=malloc(n?n:1); if(!p) cb_die("allocation"); return p; }
static double cb_ms(void) { struct timespec t; if(clock_gettime(CLOCK_MONOTONIC,&t)) cb_die("clock"); return t.tv_sec*1000.0+t.tv_nsec*1e-6; }
static unsigned char *cb_readall(const char *path,size_t *n) {
    FILE *f=fopen(path,"rb"); if(!f) cb_die(path);
    if(fseek(f,0,SEEK_END)) cb_die("file seek"); long len=ftell(f); if(len<0) cb_die("file length");
    *n=(size_t)len; rewind(f); unsigned char *p=cb_alloc(*n);
    if(fread(p,1,*n,f)!=*n) cb_die("file read"); fclose(f); return p;
}
typedef struct {
    unsigned char *arc,*original;
    size_t archive_size,size;
    int bg,zs,fd;
    BGZF *bgzf;
    ZSTD_seekable *seek;
} CB;
static CB cb_open(const char *codec,const char *archive,const char *original) {
    CB c={0}; c.fd=-1;
    c.bg=!strcmp(codec,"bgzip+htslib"); c.zs=!strcmp(codec,"zstd-seekable");
    if(!c.bg&&!c.zs&&strcmp(codec,"aceapex")) cb_die("unknown codec");
    c.arc=cb_readall(archive,&c.archive_size); c.original=cb_readall(original,&c.size);
    if(c.bg) {
#define HWAPEX_EXTRACT_SECTION 3
#include "native/bgzip.inc"
#undef HWAPEX_EXTRACT_SECTION
    } else if(c.zs) {
#define HWAPEX_EXTRACT_SECTION 3
#include "native/zstd_seekable.inc"
#undef HWAPEX_EXTRACT_SECTION
    }
    return c;
}
static int64_t cb_region(CB *c,void *dst,uint64_t off,size_t len) {
    if(c->bg) {
#define HWAPEX_EXTRACT_SECTION 4
#include "native/bgzip.inc"
#undef HWAPEX_EXTRACT_SECTION
    }
    if(c->zs) {
#define HWAPEX_EXTRACT_SECTION 4
#include "native/zstd_seekable.inc"
#undef HWAPEX_EXTRACT_SECTION
 }

#define HWAPEX_EXTRACT_SECTION 3
#include "native/aceapex.inc"
#undef HWAPEX_EXTRACT_SECTION

}
static int64_t cb_full(CB *c,void *dst) {
    if(c->bg) {
#define HWAPEX_EXTRACT_SECTION 5
#include "native/bgzip.inc"
#undef HWAPEX_EXTRACT_SECTION
 }
    if(c->zs) {
#define HWAPEX_EXTRACT_SECTION 5
#include "native/zstd_seekable.inc"
#undef HWAPEX_EXTRACT_SECTION
 }

#define HWAPEX_EXTRACT_SECTION 4
#include "native/aceapex.inc"
#undef HWAPEX_EXTRACT_SECTION

}
static void cb_close(CB *c) {
    if(c->bgzf && bgzf_close(c->bgzf)) cb_die("bgzf close");
    if(c->seek) ZSTD_seekable_free(c->seek);
    if(c->fd>=0) close(c->fd);
    free(c->arc); free(c->original);
}
#endif
