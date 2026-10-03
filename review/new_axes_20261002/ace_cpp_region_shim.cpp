#include <stdint.h>
#include <stddef.h>
#include "aceapex.h"

extern "C" int64_t axcpp_region(const void *archive,size_t archive_bytes,void *dst,size_t dst_capacity,uint64_t offset,uint64_t length){
    return aceapex_decompress_region(archive,archive_bytes,dst,dst_capacity,offset,length);
}
extern "C" const char *axcpp_decoder(void){ return "C++ aceapex_decompress_region"; }
