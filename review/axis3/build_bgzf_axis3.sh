#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/../.." && pwd)
OUT=${1:?output directory}
mkdir -p "$OUT"
OUT=$(cd -- "$OUT" && pwd)
HTS_PIN=4b705e4fada8ee2b6b15746f725ee8ac51631803
DEFLATE_PIN=dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f
checkout() {
  local url=$1 pin=$2 dir=$3
  if [ -e "$dir" ]; then
    test "$(git -C "$dir" rev-parse HEAD)" = "$pin"
    test -z "$(git -C "$dir" status --porcelain)"
  else
    git clone --quiet "$url" "$dir"
    git -C "$dir" checkout --quiet "$pin"
  fi
}
checkout https://github.com/ebiggers/libdeflate.git "$DEFLATE_PIN" "$OUT/libdeflate"
checkout https://github.com/samtools/htslib.git "$HTS_PIN" "$OUT/htslib"
cmake -S "$OUT/libdeflate" -B "$OUT/libdeflate-build" -DCMAKE_BUILD_TYPE=Release -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DLIBDEFLATE_BUILD_SHARED_LIB=OFF -DLIBDEFLATE_BUILD_GZIP=OFF -DLIBDEFLATE_BUILD_TESTS=OFF
cmake --build "$OUT/libdeflate-build" --parallel 2
git -C "$OUT/htslib" submodule update --init --recursive
(
  cd "$OUT/htslib"
  autoreconf -i
  CPPFLAGS="-I$OUT/libdeflate" LDFLAGS="-L$OUT/libdeflate-build" ./configure --with-libdeflate --disable-bz2 --disable-lzma --disable-libcurl --disable-s3 --disable-gcs --disable-plugins
  make -j2 lib-static bgzip CFLAGS='-O3 -fPIC' PACKAGE_VERSION=1.24
)
set -x
gcc -O3 -std=gnu11 -fPIC -shared -I"$OUT/htslib" "$ROOT/review/axis3/bgzf_shim.c" "$OUT/htslib/libhts.a" "$OUT/libdeflate-build/libdeflate.a" -lz -lm -pthread -o "$OUT/libhwa_bgzf.so"
set +x
cp "$OUT/htslib/bgzip" "$OUT/bgzip"
printf 'HTS_PIN=%s\nDEFLATE_PIN=%s\n' "$HTS_PIN" "$DEFLATE_PIN" > "$OUT/PINS.txt"
sha256sum "$OUT/bgzip" "$OUT/libhwa_bgzf.so" > "$OUT/SHA256SUMS"
