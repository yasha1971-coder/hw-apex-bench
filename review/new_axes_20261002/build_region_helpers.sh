#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/../.." && pwd)
OUT=${1:-"$ROOT/.work/axes-20261002/region"}
ACE=${2:-"$ROOT/.work/axes-20261002/ace/src"}
ACE_SHA=${3:-af5f56b3d4e9d54d25c58bfee25973bebbf9027a}
mkdir -p "$OUT"
gcc -O3 -fPIC -shared "$ROOT/review/new_axes_20261002/bgzf_faidx_context.c" $(pkg-config --cflags --libs htslib) -o "$OUT/bgzf-faidx-context.so"
gcc -O3 -std=c99 -fPIC -shared -pthread -I"$ROOT/harness" -I"$ACE/c" -DHB_ACE_VERSION='"'${ACE_SHA}'"' "$ROOT/codecs/native/aceapex_persistent.c" "$ACE/c/aceapex_decode.c" -lzstd -o "$OUT/ace-c99-context.so"
g++ -O3 -std=c++17 -fPIC -shared -pthread -I"$ACE/src" "$ROOT/review/new_axes_20261002/ace_cpp_region_shim.cpp" "$ACE/src/aceapex_api.cpp" -lzstd -o "$OUT/ace-cpp-region.so"
sha256sum "$OUT/bgzf-faidx-context.so" "$OUT/ace-c99-context.so" "$OUT/ace-cpp-region.so" > "$OUT/SHA256SUMS"
