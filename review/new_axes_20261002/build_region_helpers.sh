#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/../.." && pwd)
OUT=${1:-"$ROOT/.work/axes-20261002/region"}
ACE=${2:-"$ROOT/.work/axes-20261002/ace/src"}
mkdir -p "$OUT"
gcc -O3 -fPIC -shared "$ROOT/review/new_axes_20261002/bgzf_faidx_context.c" $(pkg-config --cflags --libs htslib) -o "$OUT/bgzf-faidx-context.so"
gcc -O3 -std=c99 -fPIC -shared -pthread -I"$ROOT/harness" -I"$ACE/c" -DHB_ACE_VERSION='"207bf0042dfd410f908f3b8eeb7bc8701bdbf3ee"' "$ROOT/codecs/native/aceapex_persistent.c" "$ACE/c/aceapex_decode.c" -lzstd -o "$OUT/ace-context.so"
sha256sum "$OUT/bgzf-faidx-context.so" "$OUT/ace-context.so" > "$OUT/SHA256SUMS"
