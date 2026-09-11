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
  local -a link=(-Wl,-l:liblzma.so.5)
  if [[ -n "${HB_XZ_BUILD:-}" ]]; then link=("$HB_XZ_BUILD/liblzma.a"); fi
  gcc -O3 -std=gnu11 -Wall -Wextra -Werror -fPIC -shared -I"$root/harness" \
    -I"$x/src/liblzma/api" "$root/codecs/native/xz.c" "${link[@]}" -pthread -o "$out"
}
source "${HB_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}/harness/check_common.sh"

codec_name() { echo 'xz-blocked'; }
codec_version() { echo '5.4.5'; }
codec_build() (
  export HB_XZ="$HB_CHECK_WORK/deps/xz" HB_XZ_BUILD="$HB_CHECK_WORK/xz-build"
  hb_checkout https://github.com/tukaani-project/xz.git 49053c0a649f4c8bd2b8d97ce915f401fbc0f3d9 "$HB_XZ"
  cmake -S "$HB_XZ" -B "$HB_XZ_BUILD" -DCMAKE_BUILD_TYPE=Release -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DBUILD_SHARED_LIBS=OFF -DBUILD_TESTING=OFF
  cmake --build "$HB_XZ_BUILD" --target xz --parallel "$HB_JOBS"
  codec_context_build "$(codec_library)"
)
codec_compress() { env -u XZ_DEFAULTS -u XZ_OPT "$HB_CHECK_WORK/xz-build/xz" --threads=1 -6 --check=crc64 --block-size="$3" -c -- "$1" > "$2"; }
codec_decompress() { env -u XZ_DEFAULTS -u XZ_OPT "$HB_CHECK_WORK/xz-build/xz" -d -c -- "$1" > "$2"; }

# Sourcing exposes functions without running the historical CLI dispatcher.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then return 0; fi
hb_entry "$@"
if [[ "${1:-}" == context-build ]]; then codec_context_build "$2"; exit; fi
if [[ "${1:-}" == supports ]]; then codec_supports; exit; fi
if [[ "${1:-}" == unavailable ]]; then codec_unavailable; exit; fi
case "$1" in
 compress) env -u XZ_DEFAULTS -u XZ_OPT xz --threads=1 -6 --check=crc64 --block-size="$4" -c -- "$2" > "$3";;
 restore) xz -d -c -- "$2";;
 *) exit 2;;
esac
