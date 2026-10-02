#include <htslib/faidx.h>
#include <stdint.h>
#include <stdlib.h>
typedef struct { faidx_t *f; } ctx_t;
void *fx_open(const char *path){ ctx_t *c=(ctx_t*)calloc(1,sizeof(*c)); if(!c) return NULL; c->f=fai_load(path); if(!c->f){free(c);return NULL;} return c; }
int64_t fx_fetch(void *v,const char *name,int64_t beg0,int64_t end0,char *dst,int64_t cap){
  ctx_t *c=(ctx_t*)v; hts_pos_t n=0; char *p=faidx_fetch_seq64(c->f,name,beg0,end0,&n);
  if(!p) return -1; if(n<0 || n>cap){free(p);return -2;} for(hts_pos_t i=0;i<n;i++) dst[i]=p[i]; free(p); return n;
}
void fx_close(void *v){ctx_t *c=(ctx_t*)v;if(c){if(c->f)fai_destroy(c->f);free(c);}}
