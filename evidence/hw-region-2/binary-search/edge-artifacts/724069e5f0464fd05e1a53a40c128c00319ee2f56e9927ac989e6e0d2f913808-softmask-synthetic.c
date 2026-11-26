
#include <ctype.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    uint32_t *maskBlockCount;
    uint32_t **maskBlockStart;
    uint32_t **maskBlockSizes;
} TwoBitMaskedIdx;
typedef struct { TwoBitMaskedIdx *idx; } TwoBit;

static void softMask_linear(char *seq, TwoBit *tb, uint32_t tid, uint32_t start, uint32_t end) {
    uint32_t i, width, pos = 0;
    uint32_t blockStart, blockEnd;

    if(!tb->idx->maskBlockStart) return;

    for(i=0; i<tb->idx->maskBlockCount[tid]; i++) {
        blockStart = tb->idx->maskBlockStart[tid][i];
        blockEnd = blockStart + tb->idx->maskBlockSizes[tid][i];
        if(blockEnd <= start) continue;
        if(blockStart >= end) break;
        if(blockStart < start) {
            blockEnd = (blockEnd < end) ? blockEnd : end;
            pos = 0;
            width = blockEnd - start;
        } else {
            blockEnd = (blockEnd < end) ? blockEnd : end;
            pos = blockStart - start;
            width = blockEnd - blockStart;
        }
        width += pos;
        for(; pos < width; pos++) {
            seq[pos] = tolower(seq[pos]);
        }
    }
}

static void softMask_binary(char *seq, TwoBit *tb, uint32_t tid, uint32_t start, uint32_t end) {
    uint32_t i, width, pos = 0;
    uint32_t blockStart, blockEnd;

    if(!tb->idx->maskBlockStart) return;

    uint32_t lo = 0, hi = tb->idx->maskBlockCount[tid];
    while(lo < hi) {
        uint32_t mid = lo + (hi - lo) / 2;
        uint64_t limit = (uint64_t)tb->idx->maskBlockStart[tid][mid]
                       + tb->idx->maskBlockSizes[tid][mid];
        if(limit <= start) lo = mid + 1;
        else hi = mid;
    }
    for(i=lo; i<tb->idx->maskBlockCount[tid]; i++) {
        blockStart = tb->idx->maskBlockStart[tid][i];
        blockEnd = blockStart + tb->idx->maskBlockSizes[tid][i];
        if(blockEnd <= start) continue;
        if(blockStart >= end) break;
        if(blockStart < start) {
            blockEnd = (blockEnd < end) ? blockEnd : end;
            pos = 0;
            width = blockEnd - start;
        } else {
            blockEnd = (blockEnd < end) ? blockEnd : end;
            pos = blockStart - start;
            width = blockEnd - blockStart;
        }
        width += pos;
        for(; pos < width; pos++) {
            seq[pos] = tolower(seq[pos]);
        }
    }
}

/* Verbatim production search, with an independent linear index oracle below. */
static uint32_t candidate_index(TwoBit *tb, uint32_t tid, uint32_t start) {
    if(!tb->idx->maskBlockStart) return 0;
    uint32_t lo = 0, hi = tb->idx->maskBlockCount[tid];
    while(lo < hi) {
        uint32_t mid = lo + (hi - lo) / 2;
        uint64_t limit = (uint64_t)tb->idx->maskBlockStart[tid][mid]
                       + tb->idx->maskBlockSizes[tid][mid];
        if(limit <= start) lo = mid + 1;
        else hi = mid;
    }
    return lo;
}

static uint64_t checks, index_checks, empty_checks, null_checks, n_lowered;
static uint32_t rng_state = UINT32_C(0x5eed2765);
static uint32_t random32(void) {
    uint32_t x = rng_state;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    return rng_state = x;
}
static void failure(const char *what, uint32_t start, uint32_t end, size_t at) {
    fprintf(stderr, "%s start=%"PRIu32" end=%"PRIu32" at=%zu\n", what,start,end,at);
    exit(1);
}
static void run_case(uint32_t *starts, uint32_t *sizes, uint32_t count,
                     uint32_t start, uint32_t end, int null_tables, unsigned phase) {
    enum { GUARD = 32 }; const unsigned char sentinel = 0xa7;
    static const unsigned char pattern[] = "ACGTNNacgtnn";
    if(end < start || end-start > 16384) failure("invalid synthetic query",start,end,0);
    uint64_t previous = 0;
    for(uint32_t k=0;k<count;k++) {
        uint64_t limit = (uint64_t)starts[k] + sizes[k];
        if(!sizes[k] || starts[k] < previous || limit > UINT32_MAX)
            failure("invalid sorted/nonoverlapping synthetic geometry",start,end,k);
        previous = limit;
    }
    size_t n = (size_t)(end-start), bytes = GUARD+n+1+GUARD;
    unsigned char *a = malloc(bytes), *b = malloc(bytes), *expected = malloc(bytes);
    if(!a || !b || !expected) failure("allocation",start,end,0);
    memset(a,sentinel,bytes);
    for(size_t j=0;j<n;j++) a[GUARD+j]=pattern[(j+phase)%(sizeof(pattern)-1)];
    a[GUARD+n]=0; memcpy(b,a,bytes); memcpy(expected,a,bytes);
    TwoBitMaskedIdx idx={&count,&starts,&sizes}; TwoBit tb={&idx};
    if(null_tables) { idx.maskBlockCount=NULL; idx.maskBlockStart=NULL; idx.maskBlockSizes=NULL; }
    uint32_t want=0;
    if(!null_tables) {
        while(want<count && (uint64_t)starts[want]+sizes[want] <= start) want++;
        for(size_t j=0;j<n;j++) {
            uint64_t coordinate=(uint64_t)start+j;
            for(uint32_t k=0;k<count;k++) {
                if(coordinate >= starts[k] && coordinate < (uint64_t)starts[k]+sizes[k]) {
                    if(expected[GUARD+j]=='N') n_lowered++;
                    expected[GUARD+j]=(unsigned char)tolower(expected[GUARD+j]);
                    break;
                }
            }
        }
    }
    uint32_t actual=candidate_index(&tb,0,start);
    if(actual!=want) failure("first intersecting index differs",start,end,actual);
    index_checks++;
    softMask_linear((char*)a+GUARD,&tb,0,start,end);
    softMask_binary((char*)b+GUARD,&tb,0,start,end);
    for(size_t j=0;j<bytes;j++) {
        if(a[j]!=expected[j] || b[j]!=expected[j])
            failure("linear/binary/oracle bytes or guards differ",start,end,j);
    }
    checks++; empty_checks+=(start==end); null_checks+=(null_tables!=0);
    free(a);free(b);free(expected);
}

int main(void) {
    uint32_t starts[]={3,11,15,31}, sizes[]={4,1,5,9};
    uint32_t adjacent[]={3,7,11}, adjacent_sizes[]={4,4,4};
    /* Every empty/nonempty interval: before/inside/end/after and multi-block. */
    for(uint32_t start=0;start<=48;start++) {
        for(uint32_t end=start;end<=48;end++) {
            for(unsigned phase=0;phase<3;phase++) {
                run_case(starts,sizes,4,start,end,0,phase);
                run_case(adjacent,adjacent_sizes,3,start,end,0,phase);
                run_case(NULL,NULL,0,start,end,0,phase);
            }
        }
    }
    /* storeMasked=0 absence: neither count nor per-contig pointers may be read. */
    run_case(NULL,NULL,0,0,0,1,0);run_case(NULL,NULL,0,10,25,1,1);
    /* Valid exclusive ends near UINT32_MAX; addition/index arithmetic stays safe. */
    uint32_t high[]={UINT32_MAX-90,UINT32_MAX-40}, high_sizes[]={20,40};
    for(uint32_t d=0;d<=100;d++) {
        uint32_t start=UINT32_MAX-d;
        for(uint32_t n=0;n<=d;n++) run_case(high,high_sizes,2,start,start+n,0,n%3);
    }
    /* Fixed seed, valid disjoint runs, many gaps and multiple touched blocks. */
    for(unsigned table=0;table<256;table++) {
        uint32_t s[64],z[64],count=random32()%65,position=0;
        for(uint32_t k=0;k<count;k++) {
            position+=random32()%13;s[k]=position;z[k]=1+random32()%19;position+=z[k];
        }
        uint32_t limit=position+64;
        for(unsigned q=0;q<128;q++) {
            uint32_t start=random32()%(limit+1), n=random32()%513;
            if(n>limit-start)n=limit-start;
            run_case(s,z,count,start,start+n,0,q%3);
        }
    }
    /* The production query length, independent of an archive or decoder. */
    uint32_t long_s[]={0,1024,8192,20000}, long_n[]={32,6000,4000,300};
    run_case(long_s,long_n,4,0,16384,0,0);run_case(long_s,long_n,4,4000,20384,0,1);
    if(!n_lowered || !empty_checks || null_checks!=2 || checks!=index_checks)
        failure("required coverage missing",0,0,0);
    printf("{\"status\":\"PASS\",\"byte_equality_cases\":%"PRIu64
           ",\"first_index_cases\":%"PRIu64",\"empty_ranges\":%"PRIu64
           ",\"null_table_cases\":%"PRIu64",\"masked_N_to_n_bytes\":%"PRIu64
           ",\"guard_bytes_each_side\":32,\"random_tables\":256,\"seed\":%"PRIu32"}\n",
           checks,index_checks,empty_checks,null_checks,n_lowered,UINT32_C(0x5eed2765));
    return 0;
}
