#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/../.." && pwd); OUT=${1:?existing refrel3 build directory}; SRC="$OUT/aceapex"; PIN=5b6d5cec0f5962a561ac48822a1b5c48793a5b47
test "$(git -C "$SRC" rev-parse HEAD)" = "$PIN"
g++ -std=c++17 -O3 -fPIC -shared -march=native -funroll-loops -I"$SRC/src" -I"$SRC/research/refrel" "$ROOT/review/axis3/native/refrel3_reader.cpp" "$SRC/src/aceapex_api.cpp" -lzstd -lpthread -o "$OUT/libhwa_refrel3.so"
sha256sum "$OUT/libhwa_refrel3.so" > "$OUT/libhwa_refrel3.so.sha256"
