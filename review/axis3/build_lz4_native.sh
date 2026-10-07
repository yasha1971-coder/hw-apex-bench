#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/../.." && pwd); OUT=${1:?output}; : "${LZ4_ROOT:?set LZ4_ROOT to retained LZ4 v1.10.0 source/build tree}"
version=$(grep -E '^#define LZ4_VERSION_STRING' "$LZ4_ROOT/lib/lz4.h" | sed -E 's/.*"([^"]+)".*/\1/')
test "$version" = 1.10.0 || { echo "LZ4 receipt requires v1.10.0, got $version" >&2; exit 2; }
cc -O3 -fPIC -shared -I"$LZ4_ROOT/lib" "$ROOT/review/axis3/native/lz4_indexed.c" "$LZ4_ROOT/lib/lz4.c" -o "$OUT"
printf 'version=%s\nsource=%s\n' "$version" "$LZ4_ROOT" > "$OUT.receipt"
