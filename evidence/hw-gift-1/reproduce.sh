#!/usr/bin/env bash
set -euo pipefail
# Run from the directory containing the two verified raw inputs.
# GIFT_ZSTD is the upstream checkout; keep measurements out of the source tree.
z=${GIFT_ZSTD:?}
here=$(cd "$(dirname "$0")" && pwd)
r=$(cd "$here/../.." && pwd)
test "$(git -C "$z" rev-parse HEAD)" = f8745da6ff1ad1e7bab384bd1f9d742439278e99
make -s -C "$z/lib" -j8 libzstd.a CFLAGS='-O3 -fPIC'
make -s -C "$z/contrib/seekable_format/examples" seekable_compression
export GIFT_LIB="$PWD/libgift.so" GIFT_ENC="$z/contrib/seekable_format/examples/seekable_compression"
gcc -O3 -fPIC -shared -DXXH_NAMESPACE=ZSTD_ -I"$r/harness" -I"$z/lib" -I"$z/lib/common" -I"$z/contrib/seekable_format" "$here/pair.c" "$r/codecs/native/zstd_seekable.c" "$z/contrib/seekable_format/zstdseek_decompress.c" "$z/lib/libzstd.a" -pthread -o "$GIFT_LIB"
python3 "$here/sweep.py" > samples.jsonl
python3 "$here/report.py" samples.jsonl > table.md
