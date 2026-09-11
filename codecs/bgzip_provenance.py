"""Verify compiled HTSlib features; --version alone does not identify the backend."""
import ctypes as C
import hashlib
import json
from pathlib import Path
import subprocess
import sys

work=Path(sys.argv[1]);pin=sys.argv[2]
library=C.CDLL(str(work/'context.so'))
library.hts_features.restype=C.c_uint
library.hts_feature_string.restype=C.c_char_p
if not library.hts_features() & (1 << 20):
    raise SystemExit('HTSlib lacks the required libdeflate feature')
archive=work/'libdeflate-build/libdeflate.a'
value={'backend':'libdeflate','version':'1.19','commit':pin,
       'static_library_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
       'htslib_features':library.hts_feature_string().decode(),
       'bgzip_version_output':subprocess.check_output([str(work/'deps/htslib/bgzip'),'--version'],text=True),
       'configure_option':'--with-libdeflate','bgzip_level':6,'effective_libdeflate_level':7}
(work/'bgzip-build.json').write_text(json.dumps(value,indent=2)+'\n')
