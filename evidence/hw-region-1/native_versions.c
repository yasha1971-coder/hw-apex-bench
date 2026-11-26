#include <zstd.h>
unsigned region_zstd_version_number(void) { return ZSTD_versionNumber(); }
const char *region_zstd_version_string(void) { return ZSTD_versionString(); }
