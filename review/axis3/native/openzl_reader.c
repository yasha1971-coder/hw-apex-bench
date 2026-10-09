#include <stdint.h>
#include <stddef.h>
#include "openzl/openzl.h"
long long hwa_openzl_decode(const void*src,size_t n,void*dst,size_t cap){ZL_Report sz=ZL_getDecompressedSize(src,n);if(ZL_isError(sz)||ZL_validResult(sz)>cap)return-1;ZL_Report r=ZL_decompress(dst,cap,src,n);return ZL_isError(r)?-1:(long long)ZL_validResult(r);}
