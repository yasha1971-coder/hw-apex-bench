// OpenZL v0.3.0 exact LZ parameter helper for hw-apex Axis 3.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openzl/openzl.h"
#include "openzl/codecs/zl_lz.h"
#include "openzl/zl_reflection.h"

static void die_report(const char* what, ZL_Report r) {
    if (ZL_isError(r)) { fprintf(stderr,"%s failed: %s\n",what,ZL_ErrorCode_toString(ZL_errorCode(r))); exit(2); }
}
static unsigned char* slurp(const char* p,size_t* n){
    FILE* f=fopen(p,"rb"); if(!f){perror(p);exit(2);} fseek(f,0,SEEK_END); long z=ftell(f); rewind(f);
    unsigned char* b=(unsigned char*)malloc((size_t)z+1); if(!b) exit(2); if(fread(b,1,(size_t)z,f)!=(size_t)z) exit(2); fclose(f);*n=(size_t)z;return b;
}
static void spit(const char* p,const void* b,size_t n){FILE*f=fopen(p,"wb");if(!f){perror(p);exit(2);}if(fwrite(b,1,n,f)!=n)exit(2);fclose(f);}
static int lp_get(ZL_LocalParams lp,int id,int* out){
    for(size_t i=0;i<lp.intParams.nbIntParams;i++) if(lp.intParams.intParams[i].paramId==id){*out=lp.intParams.intParams[i].paramValue;return 1;} return 0;
}
static ZL_GraphID make_graph(ZL_Compressor* c,int level,int wlog){
    ZL_IntParam ints[2]={{ZL_LzParam_compressionLevel,level},{ZL_LzParam_windowLog,wlog}};
    ZL_LocalParams lp={0}; lp.intParams.intParams=ints; lp.intParams.nbIntParams=2;
    ZL_GraphParameters gp={0}; gp.localParams=&lp;
    ZL_RESULT_OF(ZL_GraphID) rr=ZL_Compressor_parameterizeGraph(c,ZL_GRAPH_LZ,&gp);
    if(ZL_isError(rr.report)){die_report("parameterizeGraph",rr.report);}
    ZL_GraphID g=rr.value;
    if(ZL_Compressor_Graph_getBaseGraphID(c,g).id != ZL_GRAPH_LZ.id){fprintf(stderr,"wrong base graph\n");exit(2);}
    ZL_LocalParams got=ZL_Compressor_Graph_getLocalParams(c,g); int gl=0,gw=0;
    if(!lp_get(got,ZL_LzParam_compressionLevel,&gl)||!lp_get(got,ZL_LzParam_windowLog,&gw)||gl!=level||gw!=wlog){
        fprintf(stderr,"reflection mismatch requested level=%d windowLog=%d got level=%d windowLog=%d\n",level,wlog,gl,gw);exit(3);
    }
    fprintf(stderr,"GRAPH_REFLECTION level=%d windowLog=%d windowBytes=%llu\n",gl,gw,1ULL<<gw);
    return g;
}
static int cmd_compress(int argc,char**argv){
    if(argc!=6)return 2; int level=atoi(argv[2]),wlog=atoi(argv[3]); if(!((level==1||level==3)&&(wlog==16||wlog==20)))return 2;
    size_t n=0;unsigned char*src=slurp(argv[4],&n);ZL_Compressor*c=ZL_Compressor_create();if(!c)return 2;
    die_report("formatVersion",ZL_Compressor_setParameter(c,ZL_CParam_formatVersion,27));
    ZL_GraphID g=make_graph(c,level,wlog);die_report("select",ZL_Compressor_selectStartingGraphID(c,g));
    ZL_CCtx*cc=ZL_CCtx_create();if(!cc)return 2;die_report("refCompressor",ZL_CCtx_refCompressor(cc,c));
    size_t cap=ZL_compressBound(n);unsigned char*out=(unsigned char*)malloc(cap);ZL_Report r=ZL_CCtx_compress(cc,out,cap,src,n);die_report("compress",r);size_t z=ZL_validResult(r);spit(argv[5],out,z);
    ZL_FrameInfo*fi=ZL_FrameInfo_create(out,z);if(!fi){fprintf(stderr,"frame info failed\n");return 4;}ZL_Report fv=ZL_FrameInfo_getFormatVersion(fi);die_report("frameVersion",fv);
    if(ZL_validResult(fv)!=27){fprintf(stderr,"frame version !=27\n");return 4;}fprintf(stderr,"FRAME_REFLECTION formatVersion=%zu\n",(size_t)ZL_validResult(fv));
    ZL_FrameInfo_free(fi);free(out);free(src);ZL_CCtx_free(cc);ZL_Compressor_free(c);return 0;
}
static int cmd_decompress(int argc,char**argv){
    if(argc!=4)return 2;size_t n=0;unsigned char*src=slurp(argv[2],&n);ZL_Report sr=ZL_getDecompressedSize(src,n);die_report("getSize",sr);size_t cap=ZL_validResult(sr);unsigned char*out=(unsigned char*)malloc(cap);ZL_Report r=ZL_decompress(out,cap,src,n);die_report("decompress",r);spit(argv[3],out,ZL_validResult(r));free(out);free(src);return 0;
}
int main(int argc,char**argv){if(argc<2)return 2;if(!strcmp(argv[1],"compress"))return cmd_compress(argc,argv);if(!strcmp(argv[1],"decompress"))return cmd_decompress(argc,argv);return 2;}
