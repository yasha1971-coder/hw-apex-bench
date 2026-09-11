/* Reuse only codec-independent resident I/O/clock helpers. */
#define main resident_sample_entry
#include "native_measure.c"
#undef main
#define LEN 16384
int main(int argc,char **argv) {
    if(argc!=8)die("usage: native_batch LIB ARCHIVE ORIGINAL SIDECAR TRACE N batch|loop");
    char *end;long n=strtol(argv[6],&end,10);
    if(!*argv[6]||*end||n<1||n>5000)die("batch count");
    int native=!strcmp(argv[7],"batch");if(!native&&strcmp(argv[7],"loop"))die("batch mode");
    size_t an,fn;unsigned char *arc=readall(argv[2],&an),*original=readall(argv[3],&fn);
    if(fn<LEN)die("batch corpus size");
    void *lib=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);if(!lib)die("batch library");
    unsigned (*abi)(void)=symbol(lib,"hc_abi");
    void *(*open_ctx)(const void*,size_t,const char*,uint64_t)=symbol(lib,"hc_open");
    uint64_t (*size_ctx)(void*)=symbol(lib,"hc_size");
    int64_t (*region)(void*,uint64_t,void*,size_t)=symbol(lib,"hc_region");
    void (*close_ctx)(void*)=symbol(lib,"hc_close");
    if(abi()!=2)die("batch ABI");
    void *ctx=open_ctx(arc,an,*argv[4]?argv[4]:NULL,UINT64_MAX);
    if(!ctx || size_ctx(ctx)!=fn)die("batch archive size");
    uint64_t *offset=alloc(n*sizeof(*offset));int64_t *status=alloc(n*sizeof(*status));
    unsigned char *solo=alloc(n*LEN),*bat=alloc(n*LEN);memset(solo,0,n*LEN);memset(bat,0,n*LEN);
    FILE *f=fopen(argv[5],"r");if(!f)die("trace open");
    for(long i=0;i<n;i++) {unsigned long long o,l;if(fscanf(f,"%llu %llu",&o,&l)!=2||l!=LEN||o>fn-LEN)die("trace bounds");offset[i]=o;}
    unsigned long long extra;if(fscanf(f,"%llu",&extra)!=EOF)die("extra queries");fclose(f);
    void *batch=NULL;
    void *(*batch_open)(void*,const uint64_t*,size_t,size_t,void*)=NULL;
    int64_t (*batch_run)(void*,size_t,int)=NULL;
    void (*batch_reset)(void*)=NULL;
    int (*batch_valid)(void*,size_t)=NULL;
    void (*batch_close)(void*)=NULL;
    if(native){
        batch_open=symbol(lib,"hc_batch_open");batch_run=symbol(lib,"hc_batch_run");
        batch_reset=symbol(lib,"hc_batch_reset");batch_valid=symbol(lib,"hc_batch_valid");batch_close=symbol(lib,"hc_batch_close");
        batch=batch_open(ctx,offset,n,LEN,bat);if(!batch)die("batch preparation");
    }
    unsigned char warm[LEN];
    for(int i=-2;i<10;i++){
        uint64_t o=i==-2?0:i==-1?fn-LEN:offset[i%n];
        if(region(ctx,o,warm,LEN)!=LEN||memcmp(warm,original+o,LEN))die("batch warmup");
    }
    if(native){
        size_t count=n<10?(size_t)n:10;
        if(batch_run(batch,count,1)!=(int64_t)count||!batch_valid(batch,count))die("native warmup status");
        for(size_t i=0;i<count;i++)if(memcmp(bat+i*LEN,original+offset[i],LEN))die("native warmup bytes");
    }
    for(int rep=0;rep<3;rep++){
        double loop_ms=0,batch_ms=0;int64_t ok=0;
        for(int order=0;order<(native?2:1);order++){
            if(native&&((order+rep)%2==1)){
                batch_reset(batch);double t0=now();ok=batch_run(batch,n,1);batch_ms=(now()-t0)*1000;
            }else{
                double t0=now();for(long i=0;i<n;i++)status[i]=region(ctx,offset[i],solo+i*LEN,LEN);loop_ms=(now()-t0)*1000;
            }
        }
        if(native&&(ok!=n||!batch_valid(batch,n)))die("native batch status");
        for(long i=0;i<n;i++){
            if(status[i]!=LEN||memcmp(solo+i*LEN,original+offset[i],LEN))die("loop bytes");
            if(native&&memcmp(bat+i*LEN,solo+i*LEN,LEN))die("batch bytes");
        }
        if(loop_ms<=0||(native&&batch_ms<=0))die("batch duration");
        printf("{\"repeat\":%d,\"method\":\"loop\",\"n\":%ld,\"wall_ms\":%.9f,\"verified\":true}\n",rep,n,loop_ms);
        if(native)printf("{\"repeat\":%d,\"method\":\"batch\",\"n\":%ld,\"wall_ms\":%.9f,\"verified\":true}\n",rep,n,batch_ms);
    }
    if(native)batch_close(batch);
    close_ctx(ctx);dlclose(lib);free(arc);free(original);free(offset);free(status);free(solo);free(bat);
    return fflush(stdout)||ferror(stdout)?1:0;
}
