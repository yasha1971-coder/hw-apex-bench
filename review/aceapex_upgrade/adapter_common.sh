#!/usr/bin/env bash
set -euo pipefail

: "${ACE_REF:?}"
: "${ACE_LABEL:?}"
: "${ACE_MODE:?}"
: "${ACE_VERSION:?}"

codec_supports() { echo 'ratio encode decode region h_alpha batch break_even'; }
codec_unavailable() {
  cat <<'JSON'
{"amplification":"modern persistent adapter counter path not wired","c_g":"version-specific c(g) is measured in the ACEAPEX upgrade review"}
JSON
}

source "${HB_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)}/harness/check_common.sh"

codec_name() { echo "$ACE_LABEL"; }
codec_version() { echo "$ACE_VERSION"; }
codec_constraints() { echo '{"granularity":16384,"min_input_bytes":0}'; }
codec_configuration() {
  if [[ "$ACE_MODE" == open ]]; then
    printf '%s\n' '{"profile":"open","profile_selector":"AX_PROFILE=open","level":2,"encoder_requested_threads":1,"decoder_policy":"persistent C99 handle; one handle per benchmark context","granularity":16384,"lit_chunk":65536,"fse_chunk":4096,"reader_environment":{}}'
  else
    printf '%s\n' '{"profile":"interactive","level":2,"encoder_requested_threads":1,"decoder_policy":"persistent C99 handle; one handle per benchmark context","granularity":16384,"lit_chunk":65536,"fse_chunk":4096,"reader_environment":{}}'
  fi
}
codec_inputs() {
  python3 -c 'import json,sys;print(json.dumps(sys.argv[1:]))'     "$HB_ROOT/codecs/native/aceapex_persistent.c"     "$HB_ROOT/review/aceapex_upgrade/adapter_common.sh"     "${BASH_SOURCE[1]:-${BASH_SOURCE[0]}}"
}
codec_library() { echo "$HB_CHECK_WORK/context.so"; }
codec_build_artifacts() {
  python3 -c 'import json,sys;print(json.dumps(sys.argv[1:]))'     "$(codec_library)" "$HB_CHECK_WORK/aceapex-cli"
}
codec_artifacts() { python3 -c 'import json,sys;print(json.dumps([sys.argv[1]]))' "$1"; }

codec_context_build() {
  local a="$HB_CHECK_WORK/deps/aceapex" z="$HB_CHECK_WORK/deps/zstd" out="$1"
  local version_define="-DHB_ACE_VERSION=\"$ACE_VERSION\""
  gcc -O3 -std=c99 -fPIC -shared -pthread     -I"$HB_ROOT/harness" -I"$a/c" -I"$z/lib"     "$version_define"     "$HB_ROOT/codecs/native/aceapex_persistent.c"     "$a/c/aceapex_decode.c" "$z/lib/libzstd.a" -o "$out"
}

codec_build() (
  export HB_ZSTD="$HB_CHECK_WORK/deps/zstd"
  hb_checkout https://github.com/facebook/zstd.git f8745da6ff1ad1e7bab384bd1f9d742439278e99 "$HB_ZSTD"
  make -C "$HB_ZSTD/lib" -j"$HB_JOBS" libzstd.a CFLAGS='-O3 -fPIC'
  export HB_ACEAPEX="$HB_CHECK_WORK/deps/aceapex"
  hb_checkout https://github.com/yasha1971-coder/aceapex.git "$ACE_REF" "$HB_ACEAPEX"
  codec_context_build "$(codec_library)"
  # Canonical upstream CLI: CMakeLists.txt and README both build src/aceapex_main.cpp.
  g++ -O3 -std=c++17 -pthread -I"$HB_ACEAPEX/src" -I"$HB_ZSTD/lib"     "$HB_ACEAPEX/src/aceapex_main.cpp" "$HB_ZSTD/lib/libzstd.a" -o "$HB_CHECK_WORK/aceapex-cli"
)

codec_compress() {
  local input=$1 output=$2 g=$3
  [[ "$g" =~ ^[0-9]+$ && "$g" -ge 4096 && "$g" -le 4294967295 ]] || return 2
  if [[ "$ACE_MODE" == open ]]; then
    env -u MIN_MATCH -u AX_TOK -u AX_LIT       ACEAPEX_BS="$g" LIT_CHUNK=65536 FSE_CHUNK=4096 AX_PROFILE=open       "$HB_CHECK_WORK/aceapex-cli" c --in "$input" --out "$output" --threads 1 --level 2
  else
    env -u MIN_MATCH -u AX_PROFILE -u AX_TOK -u AX_LIT       ACEAPEX_BS="$g" LIT_CHUNK=65536 FSE_CHUNK=4096       "$HB_CHECK_WORK/aceapex-cli" c --in "$input" --out "$output" --threads 1 --level 2
  fi
}
codec_decompress() { "$HB_CHECK_WORK/aceapex-cli" d --in "$1" --out "$2"; }
codec_encode_command() {
  python3 -c 'import json,sys; b,i,o,g,m=sys.argv[1:]; e={"ACEAPEX_BS":g,"LIT_CHUNK":"65536","FSE_CHUNK":"4096"}; e.update({"AX_PROFILE":"open"} if m=="open" else {}); print(json.dumps({"argv":[b,"c","--in",i,"--out",o,"--threads","1","--level","2"],"environment":e}))'     "$HB_CHECK_WORK/aceapex-cli" "$1" "$2" "$3" "$ACE_MODE"
}
