#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")/../.." && pwd)
work=${1:?new work directory required}
out=${2:?new output directory required}
[[ ! -e "$work" && ! -e "$out" ]] || { echo "STOP: output exists" >&2; exit 1; }

bash "$root/review/t2t_regions/build.sh" "$work"
cmake -S "$work/libdeflate" -B "$work/libdeflate-pic-build" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
  -DLIBDEFLATE_BUILD_SHARED_LIB=OFF -DLIBDEFLATE_BUILD_GZIP=OFF \
  -DLIBDEFLATE_BUILD_TESTS=OFF
cmake --build "$work/libdeflate-pic-build" --parallel 4
mkdir -p "$out"
cp "$work/aceapex" "$out/aceapex"

gcc -O3 -std=c11 -I"$root/harness" "$root/harness/native_measure.c" -ldl -o "$out/native_measure"

gcc -O3 \
  -I"$work/htslib" -I"$work/libdeflate" \
  "$root/review/matched_g/bgzf_encode_g.c" \
  "$work/htslib/libhts.a" "$work/libdeflate-build/libdeflate.a" \
  -lz -lm -pthread -o "$out/bgzf_encode_g"

mkdir -p "$out/stage/codecs/native" "$out/stage/harness"
cp "$root/harness/resident_context.h" "$out/stage/harness/resident_context.h"
python3 - "$root/codecs/native/aceapex.c" "$out/stage/codecs/native/aceapex.c" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]).read_text()
old="1b13df34ac8e839dd3232b59bc59560d689a435a"
new="4915321bf118e564ef3883e58927992c7f9d8dc3"
assert src.count(old)==1
Path(sys.argv[2]).write_text(src.replace(old,new))
PY
cp "$root/codecs/native/bgzip.c" "$out/stage/codecs/native/bgzip.c"

gcc -O3 -fPIC -I"$out/stage/harness" -I"$work/aceapex-source/src" \
  -c "$out/stage/codecs/native/aceapex.c" -o "$out/ace_wrapper.o"
g++ -O3 -std=c++17 -fPIC -shared -pthread \
  -I"$out/stage/harness" -I"$work/aceapex-source/src" -I"$work/zstd/lib" \
  "$out/ace_wrapper.o" "$work/aceapex-source/src/aceapex_api.cpp" \
  "$work/zstd/lib/libzstd.a" -o "$out/ace_context.so"

gcc -O3 -fPIC -shared \
  -I"$out/stage/harness" -I"$work/htslib" \
  "$out/stage/codecs/native/bgzip.c" \
  "$work/htslib/libhts.a" "$work/libdeflate-pic-build/libdeflate.a" \
  -lz -lm -pthread -o "$out/bgzf_context.so"

sha256sum "$out/aceapex" "$out/native_measure" "$out/bgzf_encode_g" "$out/ace_context.so" "$out/bgzf_context.so" > "$out/SHA256SUMS"
test "$("$out/bgzf_encode_g" 2>&1 || true)" != ""
echo "PASS: matched-g native bundle built"
