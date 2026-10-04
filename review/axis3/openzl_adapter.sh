#!/usr/bin/env bash
set -euo pipefail
: "${OPENZL_ZLI:?}"
op=${1:?}; shift
case "$op" in
 build)
   variant=${1:?}; in=${2:?}; out=${3:?}
   case "$variant" in
     l1_w64k) level=1; chunk=64KiB; wlog=16;;
     l1_w1m) level=1; chunk=1MiB; wlog=20;;
     l3_w64k) level=3; chunk=64KiB; wlog=16;;
     l3_w1m) level=3; chunk=1MiB; wlog=20;;
     *) exit 2;;
   esac
   # v0.3.0 zli exposes level and independent serial chunk size, but not LZ windowLog.
   # Until the custom parameterized graph helper lands, refuse to claim the requested window variant.
   echo "OpenZL variant requires LZ windowLog=$wlog; zli alone cannot assert it" >&2
   exit 78
   ;;
 *) exit 2;;
esac
