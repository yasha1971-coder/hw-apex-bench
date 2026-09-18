#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#pragma pack(push,1)
typedef struct {
    char magic[8];
    uint32_t version;
    uint64_t orig_size;
    uint32_t block_size;
    uint32_t num_blocks;
    uint8_t xxhash[8];
    uint64_t zlit_sz, zoff_sz, zlen_sz, zcmd_sz;
} AetHeader;
typedef struct {
    uint64_t lit_off, off_off, len_off, cmd_off;
    uint64_t lit_sz, off_sz, len_sz, cmd_sz;
} BlockOffsets;
#pragma pack(pop)

typedef struct {
    size_t lf,lt,of,ot,nf,nt,cf,ct;
} Ranges;

static volatile uint64_t sinkv=0;
static double ns_now(void) {
    struct timespec t;
    if(clock_gettime(CLOCK_MONOTONIC_RAW,&t)) { perror("clock_gettime"); exit(1); }
    return (double)t.tv_sec*1e9+(double)t.tv_nsec;
}
static uint64_t rng(uint64_t *s) {
    *s=*s*UINT64_C(6364136223846793005)+UINT64_C(1442695040888963407);
    return *s;
}
static unsigned char *readall(const char *p,size_t *n) {
    FILE *f=fopen(p,"rb"); if(!f){perror("open");exit(1);}
    fseek(f,0,SEEK_END); long z=ftell(f); rewind(f);
    if(z<0){perror("ftell");exit(1);} *n=(size_t)z;
    unsigned char *b=malloc(*n); if(!b){perror("malloc");exit(1);}
    if(fread(b,1,*n,f)!=*n){perror("read");exit(1);}
    fclose(f); return b;
}
__attribute__((noinline))
static int parse_locate(const unsigned char *src,size_t src_size,uint64_t offset,uint64_t length,Ranges *r) {
    if(!src || src_size<sizeof(AetHeader)) return -1;
    AetHeader h; memcpy(&h,src,sizeof(h));
    if(memcmp(h.magic,"ACEPX2\0\0",8)!=0 || h.block_size==0 || h.num_blocks==0) return -1;
    if(length==0 || offset>h.orig_size || length>h.orig_size-offset) return -1;
    uint64_t need=(uint64_t)sizeof(h)+(uint64_t)h.num_blocks*sizeof(BlockOffsets)
        +h.zlit_sz+h.zoff_sz+h.zlen_sz+h.zcmd_sz;
    if(need>src_size) return -1;
    const BlockOffsets *b=(const BlockOffsets*)(src+sizeof(h));
    size_t b0=(size_t)(offset/h.block_size);
    size_t b1=(size_t)((offset+length-1)/h.block_size);
    if(b1>=h.num_blocks) return -1;
    r->lf=b[b0].lit_off; r->lt=b[b1].lit_off+b[b1].lit_sz;
    r->of=b[b0].off_off; r->ot=b[b1].off_off+b[b1].off_sz;
    r->nf=b[b0].len_off; r->nt=b[b1].len_off+b[b1].len_sz;
    r->cf=b[b0].cmd_off; r->ct=b[b1].cmd_off+b[b1].cmd_sz;
    sinkv += h.version+b0+b1+r->lt+r->ot+r->nt+r->ct;
    return 0;
}
static uint64_t scan_fse(const unsigned char *src,size_t orig_sz,size_t chunk) {
    if(!src || chunk==0) return 0;
    const uint64_t *cs=(const uint64_t*)(src+8);
    size_t nc=(orig_sz+chunk-1)/chunk;
    size_t p_off=8+nc*8;
    for(size_t i=0;i<nc;i++) {
        size_t raw=chunk;
        size_t d=i*chunk;
        if(d+raw>orig_sz) raw=orig_sz-d;
        size_t csz=(cs[i]>>63)?raw:(size_t)(cs[i]&~(UINT64_C(1)<<63));
        p_off+=csz;
    }
    return (uint64_t)p_off + nc;
}
static uint64_t scan_lit(const unsigned char *src,size_t src_sz) {
    if(!src || src_sz<8) return 0;
    uint64_t h; memcpy(&h,src,8);
    int entropy=(h&(UINT64_C(1)<<62))!=0;
    int chunked=(h&(UINT64_C(1)<<61))!=0;
    uint64_t orig=h&~((UINT64_C(1)<<62)|(UINT64_C(1)<<61)|(UINT64_C(1)<<60));
    if(!entropy) return 0;
    size_t csz=chunked?(size_t)(*(const uint64_t*)(src+8)):(size_t)((orig+3)/4);
    int nw=chunked?(int)((orig+csz-1)/csz):4;
    const uint64_t *zsz=(const uint64_t*)(src+(chunked?16:8));
    size_t p=(chunked?16:8)+(size_t)nw*8;
    for(int i=0;i<nw;i++) p+=(size_t)zsz[i];
    return (uint64_t)p+(uint64_t)nw;
}
static int cmpd(const void *a,const void *b) {
    double x=*(const double*)a,y=*(const double*)b; return x<y?-1:x>y?1:0;
}
int main(int argc,char **argv) {
    if(argc!=2){fprintf(stderr,"usage: micro_paths ARCHIVE\n");return 2;}
    size_t n=0; unsigned char *src=readall(argv[1],&n);
    if(n<sizeof(AetHeader)){fprintf(stderr,"small archive\n");return 1;}
    AetHeader h; memcpy(&h,src,sizeof(h));
    if(memcmp(h.magic,"ACEPX2\0\0",8)||h.block_size!=16384){fprintf(stderr,"unexpected archive\n");return 1;}
    const BlockOffsets *b=(const BlockOffsets*)(src+sizeof(h));
    const unsigned char *zlit=(const unsigned char*)(b+h.num_blocks);
    const unsigned char *zoff=zlit+h.zlit_sz;
    const unsigned char *zlen=zoff+h.zoff_sz;
    const unsigned char *zcmd=zlen+h.zlen_sz;
    size_t os=*(const uint64_t*)zoff & ~(UINT64_C(1)<<63);
    size_t ns=*(const uint64_t*)zlen & ~(UINT64_C(1)<<63);
    size_t cs=*(const uint64_t*)zcmd & ~(UINT64_C(1)<<63);
    const size_t FSE_CHUNK=512*1024;

    enum {Q=200, REPS=101, INNER=100};
    uint64_t offs[Q],seed=20260909;
    for(int i=0;i<Q;i++) offs[i]=rng(&seed)%(h.orig_size-16384+1);
    Ranges rr[Q];
    for(int i=0;i<Q;i++) if(parse_locate(src,n,offs[i],16384,&rr[i])) return 1;

    double parse[REPS],scan[REPS];
    for(int r=0;r<REPS;r++) {
        double t0=ns_now();
        for(int k=0;k<INNER;k++) for(int i=0;i<Q;i++) {
            Ranges x; if(parse_locate(src,n,offs[i],16384,&x)) return 1;
        }
        parse[r]=(ns_now()-t0)/(INNER*Q);

        t0=ns_now();
        for(int k=0;k<INNER;k++) for(int i=0;i<Q;i++) {
            uint64_t v=0;
            v+=scan_lit(zlit,h.zlit_sz);
            v+=scan_fse(zoff,os,FSE_CHUNK);
            v+=scan_fse(zlen,ns,FSE_CHUNK);
            v+=scan_fse(zcmd,cs,FSE_CHUNK);
            sinkv+=v+(uint64_t)rr[i].of+(uint64_t)rr[i].cf;
        }
        scan[r]=(ns_now()-t0)/(INNER*Q);
    }
    qsort(parse,REPS,sizeof(double),cmpd); qsort(scan,REPS,sizeof(double),cmpd);

    uint64_t lit_h=0; memcpy(&lit_h,zlit,8);
    int lit_chunked=(lit_h&(UINT64_C(1)<<61))!=0;
    uint64_t lit_orig=lit_h&~((UINT64_C(1)<<62)|(UINT64_C(1)<<61)|(UINT64_C(1)<<60));
    size_t lit_chunk=lit_chunked?(size_t)(*(const uint64_t*)(zlit+8)):(size_t)((lit_orig+3)/4);
    size_t lit_chunks=lit_chunk?((lit_orig+lit_chunk-1)/lit_chunk):0;

    printf("{\"header_locate_us\":%.6f,\"linear_index_scan_us\":%.6f,"
           "\"block_count\":%u,\"lit_chunks\":%zu,\"off_chunks\":%zu,\"len_chunks\":%zu,\"cmd_chunks\":%zu,"
           "\"fse_chunk_bytes\":%zu,\"sink\":%llu}\n",
           parse[REPS/2]/1000.0,scan[REPS/2]/1000.0,h.num_blocks,lit_chunks,
           (os+FSE_CHUNK-1)/FSE_CHUNK,(ns+FSE_CHUNK-1)/FSE_CHUNK,(cs+FSE_CHUNK-1)/FSE_CHUNK,
           FSE_CHUNK,(unsigned long long)sinkv);
    free(src); return 0;
}
