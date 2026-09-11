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
source "${HB_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}/harness/check_common.sh"

codec_name() { echo 'bgzip+htslib'; }
codec_version() { echo '1.24'; }
codec_constraints() { echo '{"granularity":65280,"min_input_bytes":0}'; }
codec_sidecar() { echo "$1.gzi"; }
codec_artifacts() { python3 -c 'import json,sys;print(json.dumps([sys.argv[1],sys.argv[1]+".gzi"]))' "$1"; }
codec_build() (
  export HB_HTSLIB="$HB_CHECK_WORK/deps/htslib"
  hb_checkout https://github.com/samtools/htslib.git 4b705e4fada8ee2b6b15746f725ee8ac51631803 "$HB_HTSLIB"
  git -C "$HB_HTSLIB" submodule update --init --depth 1
  printf '%s\n' '#define _XOPEN_SOURCE 700' '#define HAVE_DRAND48 1' > "$HB_HTSLIB/config.h"
  printf '%s\n' 'LIBS = -lz -lm -lpthread' 'HTS_LIBS = -lz -lm -lpthread' 'NONCONFIGURE_OBJS =' > "$HB_HTSLIB/config.mk"
  make -C "$HB_HTSLIB" -j"$HB_JOBS" lib-static bgzip CFLAGS='-O3 -fPIC' PACKAGE_VERSION=1.24
  codec_context_build "$(codec_library)"
  hb_checkout https://github.com/samtools/htslib.git 4b705e4fada8ee2b6b15746f725ee8ac51631803 "$HB_HTSLIB"
)
codec_compress() {
  [[ "$3" == 65280 ]] || { echo 'BGZF CLI granularity is fixed; expected 65280 ceiling' >&2; return 1; }
  "$HB_CHECK_WORK/deps/htslib/bgzip" -l 6 -@ 1 -i -I "$2.gzi" -c "$1" > "$2"
}
codec_decompress() { "$HB_CHECK_WORK/deps/htslib/bgzip" -d -c "$1" > "$2"; }

# Sourcing exposes functions without running the historical CLI dispatcher.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then return 0; fi
hb_entry "$@"
if [[ "${1:-}" == context-build ]]; then codec_context_build "$2"; exit; fi
if [[ "${1:-}" == supports ]]; then codec_supports; exit; fi
if [[ "${1:-}" == unavailable ]]; then codec_unavailable; exit; fi
case "$1" in
 compress) bgzip -l 6 -@ 1 -i -I "$3.gzi" -c "$2" > "$3";;
 restore) bgzip -d -c "$2";;
 *) echo "bgzip.sh: compress INPUT OUTPUT | restore ARCHIVE" >&2; exit 2;;
esac
