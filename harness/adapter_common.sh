#!/usr/bin/env bash
# Helpers for trusted, executable adapters. No codec dispatch table lives here.
: "${CABENCH_ROOT:=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
: "${CABENCH_WORK:=$CABENCH_ROOT/.adapter-work}"
: "${CABENCH_JOBS:=2}"
cb_checkout() {
  local url=$1 sha=$2 target=$3
  [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo 'dependency needs a full SHA' >&2; return 1; }
  if [[ ! -e "$target" ]]; then
    mkdir -p "$target"
    git -C "$target" init -q
    git -C "$target" remote add origin "$url"
    git -C "$target" fetch -q --depth=1 --no-tags origin "$sha"
    git -C "$target" checkout -q --detach FETCH_HEAD
  fi
  [[ "$(git -C "$target" rev-parse HEAD)" == "$sha" ]] || { echo "wrong dependency SHA: $target" >&2; return 1; }
  [[ -z "$(git -C "$target" status --porcelain --untracked-files=no)" ]] || { echo "modified dependency: $target" >&2; return 1; }
}
cb_compile() {
  local language=$1; shift
  local -a compiler
  if [[ "$language" == cxx ]]; then read -r -a compiler <<< "${CXX:-g++}"; else read -r -a compiler <<< "${CC:-gcc}"; fi
  printf 'compile:' >&2; printf ' %q' "${compiler[@]}" "$@" >&2; printf '\n' >&2
  "${compiler[@]}" "$@"
}
cb_worker() { "$CABENCH_WORK/adapter_worker" "$(codec_library)" "$@"; }
# All shell operations are untimed. Performance timers must call the native ABI.
codec_compress() { cb_worker compress "$1" "$2" "$3"; }
codec_decompress() { cb_worker decompress "$1" "$2"; }
codec_region() { cb_worker region "$1" "$2" "$3" "$4"; }
codec_artifacts() { python3 -c 'import json,sys; print(json.dumps([sys.argv[1]]))' "$1"; }
codec_constraints() { printf '%s\n' '{"min_input_bytes":0,"min_input_reason":null,"granularity":16384}'; }
cb_entry() {
  [[ "${1:-}" == _call ]] || return 0
  shift
  local operation=${1:?missing adapter function}; shift
  case "$operation" in
    codec_name|codec_version|codec_supports|codec_unavailable|codec_build|codec_library|codec_sources|codec_constraints|codec_artifacts|codec_compress|codec_decompress|codec_region)
      declare -F "$operation" >/dev/null || { echo "missing adapter function: $operation" >&2; exit 2; }
      "$operation" "$@"; exit $?;;
    *) echo "unknown adapter operation: $operation" >&2; exit 2;;
  esac
}
