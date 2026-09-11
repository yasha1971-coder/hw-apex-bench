#!/usr/bin/env bash
set -euo pipefail
# Resident-context proof: capabilities describe this executable path only.
codec_supports() { echo 'decode region'; }
codec_unavailable() {
  cat <<'JSON'
{"ratio":"archive accounting not connected to context proof","encode":"encode timer not connected to context proof","amplification":"decoder counters not ported to context proof","c_g":"controlled curve runner not connected to context proof","batch":"no batch API","h_alpha":"block mapping callback not ported to context proof","break_even":"timing runner not connected to context proof"}
JSON
}
codec_context_build() {
  local root out
  root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
  out="$1"
  local x="${HB_XZ:?set HB_XZ to the XZ source tree providing headers}"
  gcc -O3 -std=gnu11 -Wall -Wextra -Werror -fPIC -shared -I"$root/harness" \
    -I"$x/src/liblzma/api" "$root/codecs/native/xz.c" -Wl,-l:liblzma.so.5 -o "$out"
}
# Sourcing exposes functions without running the historical CLI dispatcher.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then return 0; fi
if [[ "${1:-}" == context-build ]]; then codec_context_build "$2"; exit; fi
if [[ "${1:-}" == supports ]]; then codec_supports; exit; fi
if [[ "${1:-}" == unavailable ]]; then codec_unavailable; exit; fi
case "$1" in
 compress) env -u XZ_DEFAULTS -u XZ_OPT xz --threads=1 -6 --check=crc64 --block-size="$4" -c -- "$2" > "$3";;
 restore) xz -d -c -- "$2";;
 *) exit 2;;
esac
