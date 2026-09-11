#include "resident_context.h"
#include <lzma.h>
#include <stdlib.h>
#include <string.h>
typedef struct {
    const uint8_t *arc; size_t bytes, index_start;
    uint64_t size; lzma_index *index; lzma_check check;
} State;
unsigned hc_abi(void) { return 2; }
uint64_t hc_size(void *ctx) { return ((State*)ctx)->size; }
const char *hc_version(void) { return lzma_version_string(); }
void hc_close(void *ctx) { State *s=ctx; if(s) {lzma_index_end(s->index,NULL); free(s);} }
void *hc_open(const void *arc, size_t bytes, const char *sidecar, uint64_t size) {
    (void)sidecar;
    if(bytes<2*LZMA_STREAM_HEADER_SIZE) return NULL;
    State *s=calloc(1,sizeof(*s)); if(!s) return NULL;
    s->arc=arc; s->bytes=bytes; s->size=size;
    lzma_stream_flags head, foot;
    if(lzma_stream_header_decode(&head,s->arc)!=LZMA_OK ||
       lzma_stream_footer_decode(&foot,s->arc+bytes-LZMA_STREAM_HEADER_SIZE)!=LZMA_OK ||
       lzma_stream_flags_compare(&head,&foot)!=LZMA_OK ||
       !lzma_check_is_supported(foot.check) ||
       foot.backward_size>bytes-2*LZMA_STREAM_HEADER_SIZE) goto bad;
    s->index_start=bytes-LZMA_STREAM_HEADER_SIZE-foot.backward_size;
    size_t pos=s->index_start; uint64_t memlimit=64*1024*1024;
    if(lzma_index_buffer_decode(&s->index,&memlimit,NULL,s->arc,&pos,
                               bytes-LZMA_STREAM_HEADER_SIZE)!=LZMA_OK ||
       pos!=bytes-LZMA_STREAM_HEADER_SIZE ||
       (size!=UINT64_MAX && lzma_index_uncompressed_size(s->index)!=size) ||
       lzma_index_stream_size(s->index)!=bytes) goto bad;
    /* First adapter supports one Stream without Stream Padding. Never silently
       treat a concatenated file's final Stream as the complete archive. */
    s->size=lzma_index_uncompressed_size(s->index);
    if(s->size>INT64_MAX) goto bad;
    s->check=foot.check; return s;
    bad: hc_close(s); return NULL;
}
int64_t hc_region(void *ctx, uint64_t off, void *dst, size_t len) {
    State *s=ctx;
    if(!hc_bounds(s->size,off,len)) return -1;
    if(!len) return 0;
    lzma_index_iter it; lzma_index_iter_init(&it,s->index);
    if(lzma_index_iter_locate(&it,off)) return -1;
    size_t done=0;
    while(done<len) {
        uint64_t start=it.block.uncompressed_file_offset, raw=it.block.uncompressed_size;
        uint64_t compressed=it.block.compressed_file_offset;
        if(compressed>=s->index_start || raw>SIZE_MAX || raw>256*1024*1024 ||
           off<start || off-start>=raw || it.block.total_size>s->index_start-compressed) return -1;
        lzma_filter filters[LZMA_FILTERS_MAX+1];
        for(unsigned i=0;i<=LZMA_FILTERS_MAX;i++) filters[i]=(lzma_filter){LZMA_VLI_UNKNOWN,NULL};
        lzma_block block={0}; block.version=0; block.check=s->check; block.filters=filters;
        block.header_size=lzma_block_header_size_decode(s->arc[compressed]);
        if(block.header_size>it.block.total_size ||
           lzma_block_header_decode(&block,NULL,s->arc+compressed)!=LZMA_OK) {
            lzma_filters_free(filters,NULL); return -1;
        }
        if(lzma_block_compressed_size(&block,it.block.unpadded_size)!=LZMA_OK ||
           (block.uncompressed_size!=LZMA_VLI_UNKNOWN && block.uncompressed_size!=raw) ||
           lzma_raw_decoder_memusage(filters)>256*1024*1024) {
            lzma_filters_free(filters,NULL); return -1;
        }
        block.uncompressed_size=raw;
        uint8_t *buffer=malloc(raw?raw:1);
        if(!buffer) {lzma_filters_free(filters,NULL); return -1;}
        size_t in_pos=compressed+block.header_size, out_pos=0;
        lzma_ret ret=lzma_block_buffer_decode(&block,NULL,s->arc,&in_pos,
                         compressed+it.block.total_size,buffer,&out_pos,raw);
        lzma_filters_free(filters,NULL);
        if(ret!=LZMA_OK || out_pos!=raw || in_pos!=compressed+it.block.total_size) {free(buffer); return -1;}
        size_t skip=(size_t)(off-start), take=raw-skip;
        if(take>len-done) take=len-done;
        memcpy((char*)dst+done,buffer+skip,take); free(buffer);
        done+=take; off+=take;
        if(done<len && lzma_index_iter_next(&it,LZMA_INDEX_ITER_NONEMPTY_BLOCK)) return -1;
    }
    return (int64_t)done;
}
int64_t hc_decode(void *ctx, void *dst, size_t cap) {
    State *s=ctx; if(cap<s->size) return -1;
    uint64_t limit=256*1024*1024; size_t in=0,out=0;
    lzma_ret r=lzma_stream_buffer_decode(&limit,0,NULL,s->arc,&in,s->bytes,dst,&out,cap);
    return r==LZMA_OK && in==s->bytes && out==s->size?(int64_t)out:-1;
}
