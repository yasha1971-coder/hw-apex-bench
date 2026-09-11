#!/usr/bin/env bash
# Trusted shell adapters; helpers contain no codec-name dispatch.
: "${HB_ROOT:=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
: "${HB_CHECK_WORK:=$HB_ROOT/.work/adapter-check}"
: "${HB_JOBS:=2}"
hb_checkout() {
  local url=$1 sha=$2 target=$3
  [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || return 1
  if [[ ! -e "$target" ]]; then
    mkdir -p "$target"
    git -C "$target" init -q
    git -C "$target" remote add origin "$url"
    git -C "$target" fetch -q --depth=1 --no-tags origin "$sha"
    git -C "$target" checkout -q --detach FETCH_HEAD
  fi
  [[ "$(git -C "$target" rev-parse HEAD)" == "$sha" ]] || { echo 'dependency SHA mismatch' >&2; return 1; }
  [[ -z "$(git -C "$target" status --porcelain --untracked-files=no)" ]] || { echo 'dirty dependency source' >&2; return 1; }
}
codec_library() { echo "$HB_CHECK_WORK/context.so"; }
codec_sidecar() { :; }
codec_constraints() { echo '{"granularity":16384,"min_input_bytes":0}'; }
codec_artifacts() { python3 -c 'import json,sys; print(json.dumps([sys.argv[1]]))' "$1"; }
codec_region() {
  python3 "$HB_ROOT/harness/check_region.py" "$(codec_library)" "$1" "$2" "$3" "$4" "$(codec_sidecar "$1")"
}
hb_entry() {
  [[ "${1:-}" == _call ]] || return 0
  shift
  local op=${1:?missing operation}; shift
  case "$op" in
    codec_name|codec_version|codec_supports|codec_unavailable|codec_build|codec_compress|codec_decompress|codec_region|codec_constraints|codec_library|codec_sidecar|codec_artifacts)
      declare -F "$op" >/dev/null || { echo "missing function: $op" >&2; exit 2; }
      "$op" "$@"; exit $?;;
    *) echo 'unknown adapter operation' >&2; exit 2;;
  esac
}
