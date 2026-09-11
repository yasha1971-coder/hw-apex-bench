#!/usr/bin/env bash
set -euo pipefail
# Resident-context proof: capabilities describe this executable path only.
codec_supports() { echo 'ratio decode region break_even'; }
codec_unavailable() {
  cat <<'JSON'
{"encode":"encode timer not connected to context proof","amplification":"decoder counters not ported to context proof","c_g":"controlled curve runner not connected to context proof","batch":"no batch API","h_alpha":"block mapping callback not ported to context proof"}
JSON
}
codec_context_build() {
  local root out
  root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
  out="$1"
  local z="${HB_ZSTD:?set HB_ZSTD to a built zstd 1.5.7 tree}"
  gcc -O3 -std=gnu11 -fPIC -shared -DXXH_NAMESPACE=ZSTD_ \
    -I"$root/harness" -I"$z/lib" -I"$z/lib/common" -I"$z/contrib/seekable_format" \
    "$root/codecs/native/zstd_seekable.c" "$z/contrib/seekable_format/zstdseek_decompress.c" \
    "$z/lib/libzstd.a" -pthread -o "$out"
}
source "${HB_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}/harness/check_common.sh"

codec_configuration() { echo '{"level": 3, "encoder_threads": 1, "decoder_threads": 1, "granularity": 16384}'; }
codec_inputs() { python3 -c 'import json,sys;print(json.dumps(sys.argv[1:]))' "$HB_ROOT/codecs/native/zstd_seekable.c"; }
codec_build_artifacts() { python3 -c 'import json,sys;print(json.dumps(sys.argv[1:]))' "$(codec_library)" "$HB_CHECK_WORK/deps/zstd/contrib/seekable_format/examples/seekable_compression" "$HB_CHECK_WORK/deps/zstd/programs/zstd"; }
codec_name() { echo 'zstd-seekable'; }
codec_version() { echo '1.5.7'; }
codec_build() (
  export HB_ZSTD="$HB_CHECK_WORK/deps/zstd"
  hb_checkout https://github.com/facebook/zstd.git f8745da6ff1ad1e7bab384bd1f9d742439278e99 "$HB_ZSTD"
  make -C "$HB_ZSTD/lib" -j"$HB_JOBS" libzstd.a CFLAGS='-O3 -fPIC'
  make -C "$HB_ZSTD/contrib/seekable_format/examples" seekable_compression
  make -C "$HB_ZSTD/programs" -j"$HB_JOBS" zstd
  codec_context_build "$(codec_library)"
)
codec_compress() (
  local tmp
  tmp=$(mktemp -d "$HB_CHECK_WORK/compress.XXXXXX")
  trap 'rm -rf -- "$tmp"' EXIT
  cp -- "$1" "$tmp/input"
  "$HB_CHECK_WORK/deps/zstd/contrib/seekable_format/examples/seekable_compression" "$tmp/input" "$3" 3
  mv -- "$tmp/input.zst" "$2"
)
codec_decompress() { "$HB_CHECK_WORK/deps/zstd/programs/zstd" -d -c "$1" > "$2"; }

# Sourcing exposes functions without running the historical CLI dispatcher.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then return 0; fi
hb_entry "$@"
if [[ "${1:-}" == context-build ]]; then codec_context_build "$2"; exit; fi
if [[ "${1:-}" == supports ]]; then codec_supports; exit; fi
if [[ "${1:-}" == unavailable ]]; then codec_unavailable; exit; fi
case "$1" in
 build)
  make -C "$2/zstd" -j"$3"
  make -C "$2/zstd/contrib/seekable_format/examples" seekable_compression
  ;;
 compress) "$2/zstd/contrib/seekable_format/examples/seekable_compression" "$3" 16384 3;;
 restore) "$2/zstd/programs/zstd" -d -c "$3";;
 *) exit 2;;
esac
