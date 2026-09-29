#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")/../.." && pwd)
work=${1:?new build dir}
out=${2:?new output dir}
[[ ! -e "$work" && ! -e "$out" ]] || { echo "STOP: output exists" >&2; exit 1; }

# Reuse the benchmark's frozen zstd/htslib/libdeflate build contract.
bash "$root/review/t2t_regions/build.sh" "$work"
mkdir -p "$out"

checkout() {
  local name=$1 sha=$2
  git init -q "$work/$name"
  git -C "$work/$name" remote add origin https://github.com/yasha1971-coder/aceapex.git
  git -C "$work/$name" fetch -q --depth=1 origin "$sha"
  git -C "$work/$name" checkout -q --detach FETCH_HEAD
  [[ "$(git -C "$work/$name" rev-parse HEAD)" == "$sha" ]]
}
LEGACY=1b13df34ac8e839dd3232b59bc59560d689a435a
V210=50723533be48a8d9ed42e4b0f9e1f9106ef169b7
OPEN=ec3477877e7ed3f9792885a1a8beb26e48f4b717
checkout ace-legacy "$LEGACY"
checkout ace-v210 "$V210"
checkout ace-open "$OPEN"

for v in legacy v210 open; do
  g++ -O3 -std=c++17 -pthread -I"$work/ace-$v/src" -I"$work/zstd/lib"     "$work/ace-$v/aceapex_depth.cpp" "$work/zstd/lib/libzstd.a" -o "$out/ace-$v"
done

gcc -O3 -std=c11 -I"$root/harness" "$root/harness/native_measure.c" -ldl -o "$out/native_measure"

# Legacy control: preserve the historical one-shot C++ region API.
cp "$root/codecs/native/aceapex.c" "$out/ace-legacy-context.c"
gcc -O3 -fPIC -I"$root/harness" -I"$work/ace-legacy/src"   -c "$out/ace-legacy-context.c" -o "$out/ace-legacy-wrapper.o"
g++ -O3 -std=c++17 -fPIC -shared -pthread   -I"$root/harness" -I"$work/ace-legacy/src" -I"$work/zstd/lib"   "$out/ace-legacy-wrapper.o" "$work/ace-legacy/src/aceapex_api.cpp"   "$work/zstd/lib/libzstd.a" -o "$out/ace-legacy-context.so"

build_modern_context() {
  local name=$1 label=$2
  gcc -O3 -std=c99 -fPIC -shared -pthread     -I"$root/harness" -I"$work/ace-$name/c" -I"$work/zstd/lib"     -DHB_ACE_VERSION="\"$label\""     "$root/codecs/native/aceapex_persistent.c"     "$work/ace-$name/c/aceapex_decode.c" "$work/zstd/lib/libzstd.a"     -o "$out/ace-$name-context.so"
}
build_modern_context v210 "aceapex-v2.1.0@$V210"
build_modern_context open "aceapex-main-open@$OPEN"

cmake -S "$work/libdeflate" -B "$work/libdeflate-pic-build"   -DCMAKE_BUILD_TYPE=Release -DCMAKE_POSITION_INDEPENDENT_CODE=ON   -DLIBDEFLATE_BUILD_SHARED_LIB=OFF -DLIBDEFLATE_BUILD_GZIP=OFF   -DLIBDEFLATE_BUILD_TESTS=OFF
cmake --build "$work/libdeflate-pic-build" --parallel 4

gcc -O3 -fPIC -shared -I"$root/harness" -I"$work/htslib"   "$root/codecs/native/bgzip.c"   "$work/htslib/libhts.a" "$work/libdeflate-pic-build/libdeflate.a"   -lz -lm -pthread -o "$out/bgzf-context.so"

gcc -O3 -I"$work/htslib" "$root/review/matched_g/bgzf_encode_g.c"   "$work/htslib/libhts.a" "$work/libdeflate-build/libdeflate.a"   -lz -lm -pthread -o "$out/bgzf-encode-g"

{
  echo "legacy=$LEGACY"
  echo "v2.1.0=$V210"
  echo "main-open=$OPEN"
  echo "zstd=$(git -C "$work/zstd" rev-parse HEAD)"
  echo "htslib=$(git -C "$work/htslib" rev-parse HEAD)"
  echo "libdeflate=$(git -C "$work/libdeflate" rev-parse HEAD)"
} > "$out/PINS"
sha256sum "$out"/* > "$out/SHA256SUMS" || true
echo "PASS: ACEAPEX upgrade bundle built"
