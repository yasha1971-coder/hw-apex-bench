#!/usr/bin/env bash
set -euo pipefail
: "${OPENZL_HELPER:?}"
ROOT=$(cd -- "$(dirname -- "$0")/../.." && pwd)
op=${1:?}; shift
case "$op" in
 build) variant=${1:?}; in=${2:?}; out=${3:?}; python3 "$ROOT/review/axis3/openzl_segmented.py" build --helper "$OPENZL_HELPER" --variant "$variant" --input "$in" --output "$out";;
 decode) python3 "$ROOT/review/axis3/openzl_segmented.py" decode --helper "$OPENZL_HELPER" --archive "$1" --output "$2";;
 fetch) python3 "$ROOT/review/axis3/openzl_segmented.py" fetch --helper "$OPENZL_HELPER" --archive "$1" --region "$2";;
 info) python3 "$ROOT/review/axis3/openzl_segmented.py" info --archive "$1";;
 *) exit 2;;
esac
