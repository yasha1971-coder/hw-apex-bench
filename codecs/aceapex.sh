#!/usr/bin/env bash
set -euo pipefail
case "$1" in
 build)
  g++ -O3 -std=c++17 -pthread -I"$2/aceapex/src" -I"$2/zstd/lib" \
    "$2/aceapex/src/aceapex_main.cpp" "$2/zstd/lib/libzstd.a" -o "$2/aceapex-cli"
  ;;
 compress) "$2/aceapex-cli" c --in "$3" --out "$4" --threads 1;;
 restore) "$2/aceapex-cli" d --in "$3" --out "$4";;
 *) exit 2;;
esac
