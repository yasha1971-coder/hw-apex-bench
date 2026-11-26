/* SPDX-License-Identifier: Apache-2.0
 * Fresh-process base-coordinate worker. No codec work or I/O in query timers
 * except the declared coordinate_read() API, including its malloc/conversion.
 */
#define _POSIX_C_SOURCE 200809L
#define _FILE_OFFSET_BITS 64
#define _GNU_SOURCE
#include "coordinate.h"
#include <dlfcn.h>
#include <fcntl.h>
#include <inttypes.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

enum { R=16384 };
typedef struct { unsigned char *data; size_t bytes; } Mapping;
typedef struct { char name[256]; uint64_t bases,offset,line_bases,line_bytes; } Fai;
typedef struct { uint64_t start,ns,open_ns,differences,n_upper,first_mismatch; unsigned expected_byte,actual_byte; } Row;
static int timed;
static volatile unsigned char touched;
static void fail(const char *why) { fprintf(stderr,"STOP: %s\n",why); exit(3); }
static void *alloc(size_t n) { void *v=malloc(n?n:1); if(!v)fail("allocation"); return v; }
static void *symbol(void *dso,const char *name) { void *v=dlsym(dso,name); if(!v)fail(name);return v; }
static uint64_t stamp(void) {
    if(!timed)fail("clock forbidden in check mode");
    struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))fail("clock");
    return (uint64_t)t.tv_sec*UINT64_C(1000000000)+(uint64_t)t.tv_nsec;
}
static Mapping mapped(const char *path) {
    int fd=open(path,O_RDONLY);struct stat st;if(fd<0||fstat(fd,&st)||st.st_size<=0||(uintmax_t)st.st_size>SIZE_MAX)fail("saved file mapping");
    Mapping m={(unsigned char*)mmap(NULL,(size_t)st.st_size,PROT_READ,MAP_PRIVATE,fd,0),(size_t)st.st_size};
    if(close(fd)||m.data==MAP_FAILED)fail("saved mmap");
    return m;
}
static void prefault(Mapping m) { for(size_t i=0;i<m.bytes;i+=4096)touched^=m.data[i];touched^=m.data[m.bytes-1]; }
static void release(Mapping m) { if(m.data&&munmap(m.data,m.bytes))fail("munmap"); }
static void warm_file(const char *path) { if(strcmp(path,"-")){Mapping m=mapped(path);prefault(m);release(m);} }
static uint64_t le64(const unsigned char *p) { uint64_t v=0;for(unsigned i=0;i<8;i++)v|=(uint64_t)p[i]<<(8*i);return v; }
static Fai read_fai(const char *path) {
    Fai v;char extra[2];FILE *f=fopen(path,"rb");
    if(!f||fscanf(f,"%255s\t%" SCNu64 "\t%" SCNu64 "\t%" SCNu64 "\t%" SCNu64,v.name,&v.bases,&v.offset,&v.line_bases,&v.line_bytes)!=5)fail("reference FAI");
    if(fscanf(f,"%1s",extra)==1||fclose(f)||!v.bases||!v.line_bases||v.line_bases>v.bases||v.line_bytes<v.line_bases||v.line_bytes-v.line_bases>2)fail("reference FAI geometry");
    return v;
}
static void expected(Mapping fasta,Fai f,uint64_t start,unsigned char *dst) {
    if(start>f.bases||R>f.bases-start)fail("trace base bounds");
    uint64_t last=start+R-1,begin=f.offset+(start/f.line_bases)*f.line_bytes+start%f.line_bases;
    uint64_t end=f.offset+(last/f.line_bases)*f.line_bytes+last%f.line_bases+1;
    if(end<begin||end>fasta.bytes)fail("reference FAI byte bounds");
    size_t n=0;
    for(uint64_t i=begin;i<end;i++) { unsigned char c=fasta.data[i];if(c=='\r'||c=='\n')continue;if(n==R)fail("long reference");dst[n++]=c; }
    if(n!=R)fail("short reference");
}
static uint64_t rss(void) {
    FILE *f=fopen("/proc/self/statm","r");unsigned long pages,resident;
    if(!f||fscanf(f,"%lu %lu",&pages,&resident)!=2||fclose(f))fail("RSS statm");
    long n=sysconf(_SC_PAGESIZE);if(n<=0)fail("page size");return (uint64_t)resident*(uint64_t)n/1024;
}
static uint64_t peak(void) { struct rusage r;if(getrusage(RUSAGE_SELF,&r))fail("peak RSS");return (uint64_t)r.ru_maxrss; }
static void json_string(const char *s) {
    putchar('"');for(const unsigned char *p=(const unsigned char*)s;*p;p++){if(*p=='"'||*p=='\\')putchar('\\');if(*p<32)printf("\\u%04x",*p);else putchar(*p);}putchar('"');
}
static void save(const char *prefix,const char *suffix,const void *data,size_t bytes) {
    size_t n=strlen(prefix)+strlen(suffix)+1;char *path=alloc(n);snprintf(path,n,"%s%s",prefix,suffix);FILE *f=fopen(path,"wbx");free(path);
    if(!f||fwrite(data,1,bytes,f)!=bytes||fflush(f)||fclose(f))fail("capture write (must be new)");
}
static int compare(const unsigned char *reference,const char *actual,unsigned semantics,Row *row) {
    if(!actual||strlen(actual)!=R)fail("coordinate API NULL/wrong string length");
    int kill=0;
    for(size_t i=0;i<R;i++) {
        unsigned char want=reference[i],got=(unsigned char)actual[i];
        if(semantics==COORD_CASE_FOLDED&&want>='a'&&want<='z')want=(unsigned char)(want-'a'+'A');
        if(want==got)continue;
        if(!row->differences) { row->first_mismatch=row->start+i;row->expected_byte=want;row->actual_byte=got; }
        row->differences++;
        if(semantics==COORD_ORIGINAL_N_UPPER&&want=='n'&&got=='N')row->n_upper++;
        else kill=1;
    }
    return kill;
}

int main(int argc,char **argv) {
    if(argc<12||argc>14)fail("usage: worker check|latency DSO ARCHIVE READER_FAI GZI CHROM REF_FASTA REF_FAI WARMUPS.bin TRACE.bin PREFIX [--fresh] [--probe]");
    timed=!strcmp(argv[1],"latency");if(!timed&&strcmp(argv[1],"check"))fail("mode");
    int fresh=0,probe=0;
    for(int i=12;i<argc;i++) {if(!strcmp(argv[i],"--fresh")&&!fresh)fresh=1;else if(!strcmp(argv[i],"--probe")&&!probe)probe=1;else fail("unknown/duplicate flag");}
    if(timed) {
        const char *lock=getenv("OVH_BENCH_LOCK_HELD");cpu_set_t mask;
        if(!lock||strcmp(lock,"/run/lock/ovh-bench.lock")||sched_getaffinity(0,sizeof(mask),&mask)||CPU_COUNT(&mask)!=1||!CPU_ISSET(0,&mask))fail("shared OVH lock and CPU0 required");
    }
    Fai f=read_fai(argv[8]);if(strcmp(f.name,argv[6]))fail("reference chromosome name");
    Mapping trace=mapped(argv[10]);
    /* Empty warmup files are allowed only by the explicit probe contract. */
    struct stat ws;if(stat(argv[9],&ws)||ws.st_size<0)fail("warmup file");
    Mapping warm={0};if(ws.st_size)warm=mapped(argv[9]);
    if(trace.bytes%8||warm.bytes%8)fail("trace encoding");
    size_t n=trace.bytes/8,w=warm.bytes/8;
    if((!probe&&(n!=1000||w!=12))||(probe&&(!n||n>5000||w>1000)))fail("trace/warmup count");
    Mapping reference=mapped(argv[7]);uint64_t source_bytes=reference.bytes;
    unsigned char *answers=alloc(n*R),*warm_answers=alloc(w*R),*outputs=alloc(n*R);
    Row *rows=calloc(n,sizeof(*rows));if(!rows)fail("rows");memset(outputs,0,n*R);
    for(size_t i=0;i<w;i++)expected(reference,f,le64(warm.data+8*i),warm_answers+i*R);
    for(size_t i=0;i<n;i++){rows[i].start=le64(trace.data+8*i);expected(reference,f,rows[i].start,answers+i*R);}
    release(reference); /* peak-process RSS still honestly includes preparation. */
    void *lib=dlopen(argv[2],RTLD_NOW|RTLD_LOCAL);if(!lib)fail(dlerror());
    unsigned(*abi)(void)=symbol(lib,"coordinate_abi"),(*sem)(void)=symbol(lib,"coordinate_semantics"),(*memory)(void)=symbol(lib,"coordinate_uses_memory_archive");
    const char *(*label)(void)=symbol(lib,"coordinate_label"),*(*error)(void)=symbol(lib,"coordinate_error");
    void *(*open_ctx)(const CoordinateConfig*)=symbol(lib,"coordinate_open");char *(*query)(void*,uint64_t,size_t)=symbol(lib,"coordinate_read");void(*close_ctx)(void*)=symbol(lib,"coordinate_close");
    if(abi()!=1||sem()>COORD_CASE_FOLDED)fail("coordinate ABI/semantics");
    unsigned semantics=sem();
    Mapping archive=mapped(argv[3]);prefault(archive);warm_file(argv[4]);warm_file(argv[5]);warm_file(argv[8]);
    CoordinateConfig cfg={argv[3],archive.data,archive.bytes,argv[4],argv[5],argv[6],f.bases,source_bytes,R};
    if(!memory()){release(archive);archive.data=NULL;cfg.archive_data=NULL;}
    uint64_t before=timed?rss():0,after_open=0,open_total=0,open_first=0,opens=0;void *ctx=NULL;
    /* Initial open is the reported single-handle startup. Fresh controls use
     * this handle for their first warmup/query, then replace it each time. */
    uint64_t a=0,b=0;if(timed)a=stamp();ctx=open_ctx(&cfg);if(timed)b=stamp();if(!ctx)fail(error());
    opens++;if(timed){if(b<=a)fail("open interval");open_first=b-a;open_total+=open_first;after_open=rss();}
    for(size_t i=0;i<w;i++) {
        if(fresh&&i) {close_ctx(ctx);if(timed)a=stamp();ctx=open_ctx(&cfg);if(timed)b=stamp();if(!ctx)fail(error());opens++;if(timed)open_total+=b-a;}
        uint64_t off=le64(warm.data+8*i);char *s=query(ctx,off,R);Row wr={0};wr.start=off;
        int kill=compare(warm_answers+i*R,s,semantics,&wr);
        if(kill){save(argv[11],".warmup-expected.bin",warm_answers+i*R,R);save(argv[11],".warmup-actual.bin",s,R);printf("{\"schema\":\"hw-region-2-coordinate-failure-v1\",\"phase\":\"warmup\",\"query\":%zu,\"status\":\"KILL\",\"first_difference0\":%"PRIu64",\"expected_byte\":%u,\"actual_byte\":%u}\n",i,wr.first_mismatch,wr.expected_byte,wr.actual_byte);free(s);close_ctx(ctx);return 2;}
        free(s);
    }
    size_t completed=0;int killed=0;
    for(size_t i=0;i<n;i++) {
        if(fresh&&(w||i)){close_ctx(ctx);if(timed)a=stamp();ctx=open_ctx(&cfg);if(timed)b=stamp();if(!ctx)fail(error());opens++;if(timed){if(b<=a)fail("open interval");rows[i].open_ns=b-a;open_total+=b-a;}}
        else if(fresh&&timed)rows[i].open_ns=open_first;
        if(timed)a=stamp();
        char *s=query(ctx,rows[i].start,R);
        if(timed)b=stamp();
        if(timed){if(b<=a)fail("query interval");rows[i].ns=b-a;}
        killed=compare(answers+i*R,s,semantics,&rows[i]);memcpy(outputs+i*R,s,R);free(s);completed=i+1;
        if(killed)break;
    }
    uint64_t after_queries=timed?rss():0,peak_rss=timed?peak():0;close_ctx(ctx);
    save(argv[11],".returned.bin",outputs,completed*R);save(argv[11],".expected.bin",answers,completed*R);
    printf("{\"schema\":\"hw-region-2-coordinate-summary-v1\",\"mode\":");json_string(argv[1]);printf(",\"label\":");json_string(label());
    printf(",\"status\":\"%s\",\"semantics\":%u,\"byte_equivalent\":%s,\"fresh_per_request\":%s,\"queries\":%zu,\"planned_queries\":%zu,\"warmups\":%zu,\"request_bases\":%u,\"measurements_of_time\":%s,\"no_clocks\":%s,\"query_clock_calls\":%zu,\"open_clock_calls\":%"PRIu64",\"opens\":%"PRIu64,
           killed?"KILL":"PASS",semantics,semantics==COORD_EXACT?"true":"false",fresh?"true":"false",completed,n,w,R,timed?"true":"false",timed?"false":"true",timed?2*completed:0,timed?2*opens:0,opens);
    printf(",\"open_ns\":");if(timed)printf("%"PRIu64,open_first);else printf("null");printf(",\"open_ns_total\":");if(timed)printf("%"PRIu64,open_total);else printf("null");
    printf(",\"rss_before_open_kib\":");if(timed)printf("%"PRIu64,before);else printf("null");printf(",\"rss_after_open_kib\":");if(timed)printf("%"PRIu64,after_open);else printf("null");
    printf(",\"rss_after_queries_kib\":");if(timed)printf("%"PRIu64,after_queries);else printf("null");printf(",\"peak_process_rss_kib\":");if(timed)printf("%"PRIu64,peak_rss);else printf("null");
    printf(",\"memory_scope\":\"fresh process including resident reader archive, reference preparation, capture buffers and reader allocations; not library-exclusive\",\"memory_archive_bytes\":%zu}\n",memory()?cfg.archive_bytes:0);
    for(size_t i=0;i<completed;i++) {
        printf("{\"schema\":\"hw-region-2-coordinate-row-v1\",\"query\":%zu,\"start0\":%"PRIu64",\"requested_bases\":%u,\"verified\":%s,\"semantics\":%u,\"differences\":%"PRIu64",\"permitted_n_to_N\":%"PRIu64",\"elapsed_ns\":",i,rows[i].start,R,killed&&i+1==completed?"false":"true",semantics,rows[i].differences,rows[i].n_upper);
        if(timed)printf("%"PRIu64,rows[i].ns);else printf("null");printf(",\"open_ns\":");if(timed&&fresh)printf("%"PRIu64,rows[i].open_ns);else printf("null");puts("}");
    }
    if(archive.data)release(archive);
    release(trace);if(warm.data)release(warm);free(answers);free(warm_answers);free(outputs);free(rows);dlclose(lib);
    return killed?2:0;
}
