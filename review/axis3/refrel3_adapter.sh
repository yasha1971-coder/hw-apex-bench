#!/usr/bin/env bash
set -euo pipefail
: "${RR3_BIN:?}"
op=${1:?}; shift
case "$op" in
  build)
    ref=${1:?}; q=${2:?}; threads=${3:?}; asm=${4:?}; out=${5:?}
    case "$q" in q4k) Q=4096;; q16k) Q=16384;; *) echo "bad variant" >&2; exit 2;; esac
    "$RR3_BIN" encode "$ref" "$Q" "$threads" "$asm" "$out"
    ;;
  region)
    ref=${1:?}; arc=${2:?}; region=${3:?}
    "$RR3_BIN" fetch "$ref" "$arc" "$region"
    ;;
  decode)
    "$RR3_BIN" decode "$1" "$2" "$3"
    ;;
  info)
    "$RR3_BIN" info "$1"
    ;;
  *) echo "unknown op" >&2; exit 2;;
esac
