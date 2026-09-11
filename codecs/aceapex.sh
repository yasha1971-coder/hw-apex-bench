#!/usr/bin/env bash
set -euo pipefail
# Resident-context proof: capabilities describe this executable path only.
codec_supports() { echo 'decode region'; }
codec_unavailable() {
  cat <<'JSON'
{"ratio":"archive accounting not connected to context proof","encode":"encode timer not connected to context proof","amplification":"decoder counters not ported to context proof","c_g":"controlled curve runner not connected to context proof","batch":"native batch callback not ported in context proof","h_alpha":"block mapping callback not ported to context proof","break_even":"timing runner not connected to context proof"}
JSON
}
codec_context_build() {
  local root out
  root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
  out="$1"
  local a="${HB_ACEAPEX:?set HB_ACEAPEX to source exported from published 1b13df3}" z="${HB_ZSTD:?set HB_ZSTD}"
  python3 "$root/harness/verify_context_sources.py" "$a"
  gcc -O3 -std=gnu11 -fPIC -I"$root/harness" -I"$a/src" -c "$root/codecs/native/aceapex.c" -o "$out.o"
  g++ -O3 -std=c++17 -fPIC -shared -pthread -I"$a/src" -I"$z/lib" \
    "$out.o" "$a/src/aceapex_api.cpp" "$z/lib/libzstd.a" -o "$out"
}
# Sourcing exposes functions without running the historical CLI dispatcher.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then return 0; fi
if [[ "${1:-}" == context-build ]]; then codec_context_build "$2"; exit; fi
if [[ "${1:-}" == supports ]]; then codec_supports; exit; fi
if [[ "${1:-}" == unavailable ]]; then codec_unavailable; exit; fi
case "$1" in
 build)
  read -r -a cxx <<< "${CXX:-g++}"
  "${cxx[@]}" -O3 -std=c++17 -pthread -I"$2/aceapex/src" -I"$2/zstd/lib" \
    "$2/aceapex/aceapex_depth.cpp" "$2/zstd/lib/libzstd.a" -o "$2/aceapex-cli"
  ;;
 compress) "$2/aceapex-cli" c --in "$3" --out "$4" --threads 1 --level 2 --profile "$5";;
 restore) "$2/aceapex-cli" d --in "$3" --out "$4" --profile "$5";;
 *) exit 2;;
esac
