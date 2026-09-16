#!/usr/bin/env bash
# Isolated pinned dependencies only. Does not modify any upstream repository.
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")/../.." && pwd)
w=$(realpath -m "${1:?new build directory required}")
[[ ! -e "$w" ]] || { echo 'Build directory already exists' >&2; exit 1; }
mkdir -p "$w"
checkout() { git init -q "$w/$1"; git -C "$w/$1" remote add origin "$2"; git -C "$w/$1" fetch -q --depth=1 origin "$3"; git -C "$w/$1" checkout -q --detach FETCH_HEAD; [[ $(git -C "$w/$1" rev-parse HEAD) == "$3" ]]; }
checkout zstd https://github.com/facebook/zstd.git f8745da6ff1ad1e7bab384bd1f9d742439278e99
make -C "$w/zstd/lib" -j4 libzstd.a CFLAGS='-O3 -fPIC'
make -C "$w/zstd/programs" -j4 zstd
make -C "$w/zstd/contrib/seekable_format/examples" seekable_compression
checkout aceapex-source https://github.com/yasha1971-coder/aceapex.git 4915321bf118e564ef3883e58927992c7f9d8dc3
g++ -O3 -std=c++17 -march=native -funroll-loops -pthread -I"$w/zstd/lib" -I"$w/aceapex-source/src" "$w/aceapex-source/src/aceapex_main.cpp" "$w/zstd/lib/libzstd.a" -o "$w/aceapex"
checkout libdeflate https://github.com/ebiggers/libdeflate.git dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f
cmake -S "$w/libdeflate" -B "$w/libdeflate-build" -DCMAKE_BUILD_TYPE=Release -DLIBDEFLATE_BUILD_SHARED_LIB=OFF -DLIBDEFLATE_BUILD_GZIP=OFF -DLIBDEFLATE_BUILD_TESTS=OFF
cmake --build "$w/libdeflate-build" --parallel 4
checkout htslib https://github.com/samtools/htslib.git 8f7231035d0409d525767c66d9f49f1f967ee1df
git -C "$w/htslib" submodule update --init --depth=1
[[ $(git -C "$w/htslib/htscodecs" rev-parse HEAD) == ffda7310c4b3292955561d6c3b1743cb82bfe26b ]]
cp "$root/evidence/t2t-regions-20260916/htslib-config.h" "$w/htslib/config.h"
printf 'LIBS = %s -lz -lm -lpthread\nHTS_LIBS = %s -lz -lm -lpthread\nNONCONFIGURE_OBJS =\n' "$w/libdeflate-build/libdeflate.a" "$w/libdeflate-build/libdeflate.a" > "$w/htslib/config.mk"
make -C "$w/htslib" -j4 bgzip CPPFLAGS="-I$w/libdeflate" CFLAGS='-O3 -fPIC' PACKAGE_VERSION=1.19
