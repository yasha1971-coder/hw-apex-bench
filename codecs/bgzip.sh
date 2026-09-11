#!/usr/bin/env bash
set -euo pipefail
HTS_PIN=4b705e4fada8ee2b6b15746f725ee8ac51631803
HTS_RELEASE=1.24
# Resident-context proof: capabilities describe this executable path only.
codec_supports() { echo 'ratio encode decode region amplification h_alpha break_even'; }
codec_unavailable() {
  cat <<'JSON'
{"c_g":"no comparable single-parameter baseline","batch":"no batch API"}
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

codec_configuration() { echo '{"level": 6, "encoder_threads": 1, "decoder_threads": 1, "granularity": 65280, "granularity_note": "BGZF CLI ceiling; actual blocks may be shorter"}'; }
codec_inputs() { python3 -c 'import json,sys;print(json.dumps(sys.argv[1:]))' "$HB_ROOT/codecs/native/bgzip.c" "$HB_ROOT/codecs/bgzip.sh" "$HB_ROOT/codecs/counters.py" "$HB_ROOT/harness/build_counters.py"; }
codec_build_artifacts() { python3 -c 'import json,sys;print(json.dumps(sys.argv[1:]))' "$(codec_library)" "$(codec_counter_library)" "$HB_CHECK_WORK/counter-sources.json" "$HB_CHECK_WORK/deps/htslib/bgzip"; }
codec_name() { echo 'bgzip+htslib'; }
codec_version() { echo "$HTS_RELEASE"; }
codec_constraints() { echo '{"granularity":65280,"min_input_bytes":0}'; }
codec_sidecar() { echo "$1.gzi"; }
codec_artifacts() { python3 -c 'import json,sys;print(json.dumps([sys.argv[1],sys.argv[1]+".gzi"]))' "$1"; }
codec_build() (
  export HB_HTSLIB="$HB_CHECK_WORK/deps/htslib"
  hb_checkout https://github.com/samtools/htslib.git "$HTS_PIN" "$HB_HTSLIB"
  git -C "$HB_HTSLIB" submodule update --init --depth 1
  printf '%s\n' '#define _XOPEN_SOURCE 700' '#define HAVE_DRAND48 1' > "$HB_HTSLIB/config.h"
  printf '%s\n' 'LIBS = -lz -lm -lpthread' 'HTS_LIBS = -lz -lm -lpthread' 'NONCONFIGURE_OBJS =' > "$HB_HTSLIB/config.mk"
  make -C "$HB_HTSLIB" -j"$HB_JOBS" lib-static bgzip CFLAGS='-O3 -fPIC' PACKAGE_VERSION="$HTS_RELEASE"
  codec_context_build "$(codec_library)"
  hb_checkout https://github.com/samtools/htslib.git "$HTS_PIN" "$HB_HTSLIB"
  python3 "$HB_ROOT/codecs/counters.py" bgzip "$HB_CHECK_WORK"
)
codec_compress() {
  [[ "$3" == 65280 ]] || { echo 'BGZF CLI granularity is fixed; expected 65280 ceiling' >&2; return 1; }
  "$HB_CHECK_WORK/deps/htslib/bgzip" -l 6 -@ 1 -i -I "$2.gzi" -c "$1" > "$2"
}
codec_decompress() { "$HB_CHECK_WORK/deps/htslib/bgzip" -d -c "$1" > "$2"; }

codec_encode_command() { python3 -c 'import json,sys; b,i,o,g=sys.argv[1:]; assert g=="65280"; print(json.dumps({"argv":[b,"-l","6","-@","1","-i","-I",o+".gzi","-c",i],"stdout_archive":True}))' "$HB_CHECK_WORK/deps/htslib/bgzip" "$1" "$2" "$3"; }

codec_counter_library() { echo "$HB_CHECK_WORK/counter-context.so"; }

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
