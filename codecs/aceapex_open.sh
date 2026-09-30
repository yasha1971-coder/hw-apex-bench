#!/usr/bin/env bash
set -euo pipefail
ACE_REF=0a143cd64b35a802835f18c361f981968edf25a1
ACE_LABEL=aceapex-v2.2.0-open
ACE_MODE=open
ACE_VERSION=aceapex-v2.2.0-open@0a143cd64b35a802835f18c361f981968edf25a1
source "${HB_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}/review/aceapex_upgrade/adapter_common.sh"
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then return 0; fi
hb_entry "$@"
case "${1:-}" in supports) codec_supports;; unavailable) codec_unavailable;; esac
