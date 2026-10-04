#!/usr/bin/env bash
set -euo pipefail
OUT=${1:?output directory}
SHA=32246b48faee46807f84183dac4db479089f5445
SRC="$OUT/openzl"
rm -rf "$SRC"; mkdir -p "$OUT"
git clone --quiet --recurse-submodules https://github.com/facebook/openzl.git "$SRC"
git -C "$SRC" checkout --quiet "$SHA"
git -C "$SRC" submodule update --init --recursive --quiet
cmake -S "$SRC" -B "$OUT/build" -DCMAKE_BUILD_TYPE=Release -DOPENZL_BUILD_CLI=ON
cmake --build "$OUT/build" -j2
ZLI=$(find "$OUT/build" -type f -name zli -perm -111 | head -1)
test -n "$ZLI"
cp "$ZLI" "$OUT/zli"
"$OUT/zli" --version > "$OUT/VERSION.txt"
printf '%s\n' "$SHA" > "$OUT/OPENZL_COMMIT"
