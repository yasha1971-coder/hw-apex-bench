#!/usr/bin/env bash
set -euo pipefail
: "${OPENZL_HELPER:?}"
op=${1:?}; shift
case "$op" in
 build)
   variant=${1:?}; in=${2:?}; out=${3:?}
   case "$variant" in
     l1_w64k) level=1; wlog=16;;
     l1_w1m) level=1; wlog=20;;
     l3_w64k) level=3; wlog=16;;
     l3_w1m) level=3; wlog=20;;
     *) exit 2;;
   esac
   "$OPENZL_HELPER" compress "$level" "$wlog" "$in" "$out"
   ;;
 decode) "$OPENZL_HELPER" decompress "$1" "$2";;
 *) exit 2;;
esac
