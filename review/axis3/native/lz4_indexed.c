/* Native block primitive for benchmark-local indexed LZ4 canonical container.
 * Container/index parsing is judge-side; every stored block is independent.
 */
#include <lz4.h>
long long hwa_lz4_block(const void*src,int n,void*dst,int cap){int r=LZ4_decompress_safe((const char*)src,(char*)dst,n,cap);return r<0?-1:r;}
const char* hwa_lz4_version(void){return LZ4_versionString();}
