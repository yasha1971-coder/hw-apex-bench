#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/../.." && pwd); OUT=${1:?existing OpenZL v0.3.0 build directory}; SRC="$OUT/openzl"; PIN=32246b48faee46807f84183dac4db479089f5445
test "$(git -C "$SRC" rev-parse HEAD)" = "$PIN"
LIB=$(find "$OUT/build" -type f -name libopenzl.a | head -1);ZSTD=$(find "$OUT/build" "$SRC" -type f -name libzstd.a | head -1);LZ4=$(find "$OUT/build" "$SRC" -type f -name liblz4.a | head -1);test -n "$LIB";test -n "$ZSTD";test -n "$LZ4"
cc -O3 -fPIC -I"$SRC/include" -c "$ROOT/review/axis3/native/openzl_reader.c" -o "$OUT/openzl_reader.o"
cc -shared "$OUT/openzl_reader.o" "$LIB" "$ZSTD" "$LZ4" -lstdc++ -lpthread -lm -o "$OUT/libhwa_openzl.so"
sha256sum "$OUT/libhwa_openzl.so" > "$OUT/libhwa_openzl.so.sha256"
