#!/usr/bin/env bash
set -euo pipefail
case "$1" in
 compress) bgzip -l 6 -@ 1 -i -I "$3.gzi" -c "$2" > "$3";;
 restore) bgzip -d -c "$2";;
 *) echo "bgzip.sh: compress INPUT OUTPUT | restore ARCHIVE" >&2; exit 2;;
esac
