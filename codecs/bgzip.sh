#!/usr/bin/env bash
set -euo pipefail
HTS_PIN=4b705e4fada8ee2b6b15746f725ee8ac51631803
HTS_RELEASE=1.24
LIBDEFLATE_PIN=dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f
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
    "$root/codecs/native/bgzip.c" "$h/libhts.a" "$HB_CHECK_WORK/libdeflate-build/libdeflate.a" -lz -lm -pthread -o "$out"
}
source "${HB_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}/harness/check_common.sh"

codec_configuration() { echo '{"level": 6, "compression_backend": {"name":"libdeflate","version":"1.19","commit":"dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f","configure_option":"--with-libdeflate","effective_level":7}, "encoder_threads": 1, "decoder_threads": 1, "granularity": 65280, "granularity_note": "BGZF CLI ceiling; actual blocks may be shorter"}'; }
codec_inputs() { python3 -c 'import json,sys;print(json.dumps(sys.argv[1:]))' "$HB_ROOT/codecs/native/bgzip.c" "$HB_ROOT/codecs/bgzip.sh" "$HB_ROOT/codecs/native/bgzip_build.sh" "$HB_ROOT/codecs/bgzip_provenance.py" "$HB_ROOT/codecs/counters.py" "$HB_ROOT/harness/build_counters.py"; }
codec_build_artifacts() { python3 -c 'import json,sys;print(json.dumps(sys.argv[1:]))' "$(codec_library)" "$(codec_counter_library)" "$HB_CHECK_WORK/counter-sources.json" "$HB_CHECK_WORK/deps/htslib/bgzip" "$HB_CHECK_WORK/bgzip-build.json" "$HB_CHECK_WORK/libdeflate-build/libdeflate.a"; }
codec_name() { echo 'bgzip+htslib'; }
codec_version() { echo "$HTS_RELEASE"; }
codec_constraints() { echo '{"granularity":65280,"min_input_bytes":0}'; }
codec_sidecar() { echo "$1.gzi"; }
codec_artifacts() { python3 -c 'import json,sys;print(json.dumps([sys.argv[1],sys.argv[1]+".gzi"]))' "$1"; }
codec_build() {
  bash "$HB_ROOT/codecs/native/bgzip_build.sh" "$HTS_PIN" "$HTS_RELEASE" "$LIBDEFLATE_PIN"
}

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
