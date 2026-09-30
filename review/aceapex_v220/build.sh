#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")/../.." && pwd)
work=$(realpath -m "${1:?new build dir}")
out=$(realpath -m "${2:?new output dir}")
[[ ! -e "$work" && ! -e "$out" ]] || { echo "STOP: output exists" >&2; exit 1; }

# Frozen benchmark dependencies.
bash "$root/review/t2t_regions/build.sh" "$work"
mkdir -p "$out"

ACE_SHA=0a143cd64b35a802835f18c361f981968edf25a1
git init -q "$work/ace-v220"
git -C "$work/ace-v220" remote add origin https://github.com/yasha1971-coder/aceapex.git
git -C "$work/ace-v220" fetch -q --depth=1 origin "$ACE_SHA"
git -C "$work/ace-v220" checkout -q --detach FETCH_HEAD
[[ "$(git -C "$work/ace-v220" rev-parse HEAD)" == "$ACE_SHA" ]]

# Required upstream build path: make, linked to the benchmark-pinned libzstd.
make -C "$work/ace-v220" clean
make -C "$work/ace-v220" -j4 \
  ZSTD_CFLAGS="-I$work/zstd/lib" \
  ZSTD_LIBS="$work/zstd/lib/libzstd.a"
cp "$work/ace-v220/aceapex" "$out/aceapex-v220"

# Runtime version and exact binary digest are normative provenance.
"$work/zstd/programs/zstd" --version > "$out/zstd-version.txt"
sha256sum "$out/aceapex-v220" > "$out/aceapex-v220.sha256"

gcc -O3 -std=c11 -I"$root/harness" "$root/harness/native_measure.c" -ldl -o "$out/native_measure"

# Clean persistent v2.2 reader.
gcc -O3 -std=c99 -fPIC -shared -pthread \
  -I"$root/harness" -I"$work/ace-v220/c" -I"$work/zstd/lib" \
  -DHB_ACE_VERSION='"aceapex-v2.2.0@0a143cd64b35a802835f18c361f981968edf25a1"' \
  "$root/codecs/native/aceapex_persistent.c"   "$work/ace-v220/c/aceapex_decode.c" "$work/zstd/lib/libzstd.a"   -o "$out/ace-context.so"

# Separate instrumented persistent reader for decoded-byte amplification.
mkdir -p "$out/ace-counter/deps"
ln -s "$work/ace-v220" "$out/ace-counter/deps/aceapex"
ln -s "$work/zstd" "$out/ace-counter/deps/zstd"
python3 "$root/review/aceapex_v220/build_counter.py"   "$out/ace-counter" "aceapex-v2.2.0@0a143cd64b35a802835f18c361f981968edf25a1"
cp "$out/ace-counter/counter-context.so" "$out/ace-counter-context.so"
cp "$out/ace-counter/counter-sources.json" "$out/ace-counter-sources.json"

# Exact-g zstd-seekable encoder and resident reader.
cp "$work/zstd/contrib/seekable_format/examples/seekable_compression" "$out/seekable_compression"
gcc -O3 -std=gnu11 -fPIC -shared -DXXH_NAMESPACE=ZSTD_ \
  -I"$root/harness" -I"$work/zstd/lib" -I"$work/zstd/lib/common" -I"$work/zstd/contrib/seekable_format" \
  "$root/codecs/native/zstd_seekable.c" "$work/zstd/contrib/seekable_format/zstdseek_decompress.c"   "$work/zstd/lib/libzstd.a" -pthread -o "$out/zstd-context.so"

# zstd decoded-byte counter.
mkdir -p "$out/zstd-counter/deps"
ln -s "$work/zstd" "$out/zstd-counter/deps/zstd"
python3 "$root/codecs/counters.py" zstd_seekable "$out/zstd-counter"
cp "$out/zstd-counter/counter-context.so" "$out/zstd-counter-context.so"
cp "$out/zstd-counter/counter-sources.json" "$out/zstd-counter-sources.json"

# BGZF exact-g writer, resident reader and decoded-byte counter.
cmake -S "$work/libdeflate" -B "$work/libdeflate-pic-build" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
  -DLIBDEFLATE_BUILD_SHARED_LIB=OFF -DLIBDEFLATE_BUILD_GZIP=OFF -DLIBDEFLATE_BUILD_TESTS=OFF
cmake --build "$work/libdeflate-pic-build" --parallel 4
gcc -O3 -fPIC -shared -I"$root/harness" -I"$work/htslib" \
  "$root/codecs/native/bgzip.c" "$work/htslib/libhts.a" "$work/libdeflate-pic-build/libdeflate.a" \
  -lz -lm -pthread -o "$out/bgzf-context.so"
gcc -O3 -I"$work/htslib" "$root/review/matched_g/bgzf_encode_g.c" \
  "$work/htslib/libhts.a" "$work/libdeflate-build/libdeflate.a"   -lz -lm -pthread -o "$out/bgzf-encode-g"
mkdir -p "$out/bgzf-counter/deps"
ln -s "$work/htslib" "$out/bgzf-counter/deps/htslib"
ln -s "$work/libdeflate" "$out/bgzf-counter/deps/libdeflate"
ln -s "$work/libdeflate-build" "$out/bgzf-counter/libdeflate-build"
python3 "$root/codecs/counters.py" bgzip "$out/bgzf-counter"
cp "$out/bgzf-counter/counter-context.so" "$out/bgzf-counter-context.so"
cp "$out/bgzf-counter/counter-sources.json" "$out/bgzf-counter-sources.json"

{
  echo "aceapex=v2.2.0@$ACE_SHA"
  echo "doi=10.5281/zenodo.23061934"
  echo "zstd=$(git -C "$work/zstd" rev-parse HEAD)"
  echo "zstd_version=$("$work/zstd/programs/zstd" --version | head -1)"
  echo "htslib=$(git -C "$work/htslib" rev-parse HEAD)"
  echo "libdeflate=$(git -C "$work/libdeflate" rev-parse HEAD)"
  echo "ace_binary_sha256=$(sha256sum "$out/aceapex-v220" | awk '{print $1}')"
} > "$out/PINS"

sha256sum "$out"/*.so "$out"/native_measure "$out"/seekable_compression "$out"/bgzf-encode-g > "$out/SHA256SUMS"
echo "PASS: v2.2.0 bundle built through upstream make"
