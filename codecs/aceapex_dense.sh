#!/usr/bin/env bash
set -euo pipefail
source "${HB_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}/codecs/aceapex.sh"
ACE_PROFILE=dense
codec_constraints() { echo '{"granularity":262144,"min_input_bytes":1,"min_input_reason":"pinned ACE CLI does not support empty input"}'; }
codec_configuration() { echo '{"profile":"dense","level":2,"encoder_requested_threads":1,"decoder_policy":"pinned native API defaults; no thread argument","granularity":262144,"lit_chunk":1048576,"fse_chunk":32768,"min_match":0,"reader_environment":{"ACEAPEX_BS":"262144","LIT_CHUNK":"1048576","FSE_CHUNK":"32768","MIN_MATCH":"0"}}'; }
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then return 0; fi
hb_entry "$@"
case "${1:-}" in supports) codec_supports;; unavailable) codec_unavailable;; *) exit 2;; esac
