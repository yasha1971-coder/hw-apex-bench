#!/usr/bin/env bash
# Shared recipe for pinned HTSlib configurations; no timing or result publication.
set -euo pipefail
source "${HB_ROOT:?}/harness/check_common.sh"
hts_pin=$1
hts_release=$2
deflate_pin=$3
hts="$HB_CHECK_WORK/deps/htslib"
deflate="$HB_CHECK_WORK/deps/libdeflate"
deflate_build="$HB_CHECK_WORK/libdeflate-build"
hb_checkout https://github.com/ebiggers/libdeflate.git "$deflate_pin" "$deflate"
cmake -S "$deflate" -B "$deflate_build" -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DLIBDEFLATE_BUILD_SHARED_LIB=OFF \
  -DLIBDEFLATE_BUILD_GZIP=OFF -DLIBDEFLATE_BUILD_TESTS=OFF
cmake --build "$deflate_build" --parallel "$HB_JOBS"
hb_checkout https://github.com/samtools/htslib.git "$hts_pin" "$hts"
git -C "$hts" submodule update --init --depth 1
(
  cd "$hts"
  # Existing generated zlib objects must never survive the backend switch.
  make clean
  autoreconf -i
  CPPFLAGS="-I$deflate" LDFLAGS="-L$deflate_build" \
    ./configure --with-libdeflate --disable-bz2 --disable-lzma \
      --disable-libcurl --disable-s3 --disable-gcs --disable-plugins
  make -j"$HB_JOBS" lib-static bgzip CFLAGS='-O3 -fPIC' PACKAGE_VERSION="$hts_release"
)
gcc -O3 -std=gnu11 -fPIC -shared -I"$HB_ROOT/harness" -I"$hts" \
  "$HB_ROOT/codecs/native/bgzip.c" "$hts/libhts.a" "$deflate_build/libdeflate.a" \
  -lz -lm -pthread -o "$HB_CHECK_WORK/context.so"
python3 "$HB_ROOT/codecs/bgzip_provenance.py" "$HB_CHECK_WORK" "$deflate_pin"
hb_checkout https://github.com/ebiggers/libdeflate.git "$deflate_pin" "$deflate"
hb_checkout https://github.com/samtools/htslib.git "$hts_pin" "$hts"
python3 "$HB_ROOT/codecs/counters.py" bgzip "$HB_CHECK_WORK"
