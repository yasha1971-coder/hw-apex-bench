#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/../.." && pwd)
OUT=${1:?output directory}
ACE_SHA=5b6d5cec0f5962a561ac48822a1b5c48793a5b47
SRC="$OUT/aceapex"
rm -rf "$SRC"
mkdir -p "$OUT"
git clone --quiet --branch refrel https://github.com/yasha1971-coder/aceapex.git "$SRC"
git -C "$SRC" checkout --quiet "$ACE_SHA"
test "$(git -C "$SRC" rev-parse HEAD)" = "$ACE_SHA"
test -f "$SRC/research/refrel/FORMAT.md"
grep -Fq 'frozen as v1 on 2026-10-04' "$SRC/research/refrel/FORMAT.md"
g++ -std=c++17 -O3 -march=native -funroll-loops -I"$SRC/src" -I"$SRC/research/refrel" "$SRC/research/refrel/refrel3v1.cpp" "$SRC/src/aceapex_api.cpp" -lzstd -lpthread -o "$OUT/refrel3v1"
sha256sum "$OUT/refrel3v1" > "$OUT/refrel3v1.sha256"
printf '%s\n' "$ACE_SHA" > "$OUT/ACEAPEX_REFREL_COMMIT"
