#!/usr/bin/env bash
set -euo pipefail
# Resident-context proof: capabilities describe this executable path only.
codec_supports() { echo 'decode region'; }
codec_unavailable() {
  cat <<'JSON'
{"ratio":"archive accounting not connected to context proof","encode":"encode timer not connected to context proof","amplification":"decoder counters not ported to context proof","c_g":"no comparable single-parameter baseline","batch":"no batch API","h_alpha":"block mapping callback not ported to context proof","break_even":"timing runner not connected to context proof"}
JSON
}
codec_context_build() {
  local root out
  root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
  out="$1"
  local h="${HB_HTSLIB:?set HB_HTSLIB to a built HTSlib tree}"
  gcc -O3 -std=gnu11 -fPIC -shared -I"$root/harness" -I"$h" \
    "$root/codecs/native/bgzip.c" "$h/libhts.a" -lz -lm -pthread -o "$out"
}
# Sourcing exposes functions without running the historical CLI dispatcher.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then return 0; fi
if [[ "${1:-}" == context-build ]]; then codec_context_build "$2"; exit; fi
if [[ "${1:-}" == supports ]]; then codec_supports; exit; fi
if [[ "${1:-}" == unavailable ]]; then codec_unavailable; exit; fi
case "$1" in
 compress) bgzip -l 6 -@ 1 -i -I "$3.gzi" -c "$2" > "$3";;
 restore) bgzip -d -c "$2";;
 *) echo "bgzip.sh: compress INPUT OUTPUT | restore ARCHIVE" >&2; exit 2;;
esac
