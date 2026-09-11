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
source "${HB_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}/harness/check_common.sh"

codec_name() { echo 'aceapex-interactive'; }
codec_version() { echo 'aceapex@1b13df34ac8e839dd3232b59bc59560d689a435a'; }
codec_constraints() { echo '{"granularity":16384,"min_input_bytes":1,"min_input_reason":"pinned ACE CLI does not support empty input"}'; }
codec_build() (
  export HB_ZSTD="$HB_CHECK_WORK/deps/zstd"
  hb_checkout https://github.com/facebook/zstd.git f8745da6ff1ad1e7bab384bd1f9d742439278e99 "$HB_ZSTD"
  make -C "$HB_ZSTD/lib" -j"$HB_JOBS" libzstd.a CFLAGS='-O3 -fPIC'
  export HB_ACEAPEX="$HB_CHECK_WORK/deps/aceapex"
  hb_checkout https://github.com/yasha1971-coder/aceapex.git 1b13df34ac8e839dd3232b59bc59560d689a435a "$HB_ACEAPEX"
  codec_context_build "$(codec_library)"
  g++ -O3 -std=c++17 -pthread -I"$HB_ACEAPEX/src" -I"$HB_ZSTD/lib" "$HB_ACEAPEX/aceapex_depth.cpp" "$HB_ZSTD/lib/libzstd.a" -o "$HB_CHECK_WORK/aceapex-cli"
)
codec_compress() {
  [[ "$3" == 16384 && -s "$1" ]] || { echo 'pinned interactive preset requires nonempty input and granularity 16384' >&2; return 1; }
  env -u ACEAPEX_BS -u LIT_CHUNK -u FSE_CHUNK -u MIN_MATCH "$HB_CHECK_WORK/aceapex-cli" c --in "$1" --out "$2" --threads 1 --level 2 --profile interactive
}
codec_decompress() { "$HB_CHECK_WORK/aceapex-cli" d --in "$1" --out "$2" --profile interactive; }

# Sourcing exposes functions without running the historical CLI dispatcher.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then return 0; fi
hb_entry "$@"
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
