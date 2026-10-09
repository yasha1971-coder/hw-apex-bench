#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/../.." && pwd)
OUT=${1:?output directory}
SHA=32246b48faee46807f84183dac4db479089f5445
SRC="$OUT/openzl"
mkdir -p "$OUT"
if [ -d "$SRC/.git" ] && [ "$(git -C "$SRC" rev-parse HEAD)" = "$SHA" ]; then
  echo "PINNED_OPENZL_SOURCE_CACHE_VERIFIED=$SHA"
else
  rm -rf "$SRC" "$OUT/build"
  git clone --quiet --recurse-submodules https://github.com/facebook/openzl.git "$SRC"
  git -C "$SRC" checkout --quiet "$SHA"
fi
git -C "$SRC" submodule update --init --recursive --quiet
cmake -S "$SRC" -B "$OUT/build" -DCMAKE_BUILD_TYPE=Release -DOPENZL_BUILD_CLI=ON
cmake --build "$OUT/build" -j2
ZLI=$(find "$OUT/build" -type f -name zli -perm -111 | head -1)
test -n "$ZLI"
cp "$ZLI" "$OUT/zli"
"$OUT/zli" --version > "$OUT/VERSION.txt"
LIB=$(find "$OUT/build" -type f -name 'libopenzl.a' | head -1)
ZSTD_LIB=$(find "$OUT/build" "$SRC" -type f -name 'libzstd.a' | head -1)
LZ4_LIB=$(find "$OUT/build" "$SRC" -type f -name 'liblz4.a' | head -1)
test -n "$LIB"
test -n "$ZSTD_LIB"
test -n "$LZ4_LIB"
cc -O3 -I"$SRC/include" -c "$ROOT/review/axis3/openzl_lz_helper.c" -o "$OUT/openzl_lz_helper.o"
printf 'LINK_COMMAND=cc %q %q %q %q -lstdc++ -lpthread -lm -o %q\n' "$OUT/openzl_lz_helper.o" "$LIB" "$ZSTD_LIB" "$LZ4_LIB" "$OUT/openzl-lz-helper"
cc "$OUT/openzl_lz_helper.o" "$LIB" "$ZSTD_LIB" "$LZ4_LIB" -lstdc++ -lpthread -lm -o "$OUT/openzl-lz-helper"
cat > "$OUT/dependency_versions.c" <<'EOF'
#include <stdio.h>
#include "zstd.h"
#include "lz4.h"
int main(void) {
    printf("ZSTD_versionString=%s\n", ZSTD_versionString());
    printf("LZ4_versionString=%s\n", LZ4_versionString());
    return 0;
}
EOF
printf 'OPENZL_STATIC=%s\nZSTD_STATIC=%s\nLZ4_STATIC=%s\n' "$LIB" "$ZSTD_LIB" "$LZ4_LIB"
# This diagnostic is not a build/correctness gate. The helper link above remains fatal.
# Do not substitute system libraries; retain the pinned static paths printed above.
probe_status="$OUT/dependency_versions.status"
if cc -I"$SRC/src/openzl/zstd" -I"$SRC/src/openzl/lz4" "$OUT/dependency_versions.c" "$ZSTD_LIB" "$LZ4_LIB" -lpthread -lm -o "$OUT/dependency-versions" > "$OUT/dependency_versions.build.log" 2>&1; then
  if "$OUT/dependency-versions" > "$OUT/dependency_versions.txt" 2> "$OUT/dependency_versions.err"; then
    printf 'DEPENDENCY_VERSION_PROBE_OK\n' > "$probe_status"
    cat "$OUT/dependency_versions.txt"
  else
    rc=$?
    printf 'DEPENDENCY_VERSION_PROBE_UNAVAILABLE stage=run rc=%s; dependency versions unverified\n' "$rc" > "$probe_status"
    cat "$OUT/dependency_versions.err" >&2
  fi
else
  rc=$?
  printf 'DEPENDENCY_VERSION_PROBE_UNAVAILABLE stage=compile rc=%s; dependency versions unverified\n' "$rc" > "$probe_status"
  cat "$OUT/dependency_versions.build.log" >&2
fi
cat "$probe_status"
printf '%s\n' "$SHA" > "$OUT/OPENZL_COMMIT"
