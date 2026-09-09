#!/usr/bin/env bash
set -euo pipefail
case "$1" in
 build)
  make -C "$2/zstd" -j"$3"
  make -C "$2/zstd/contrib/seekable_format/examples" seekable_compression
  ;;
 compress) "$2/zstd/contrib/seekable_format/examples/seekable_compression" "$3" 16384 3;;
 restore) "$2/zstd/programs/zstd" -d -c "$3";;
 *) exit 2;;
esac
