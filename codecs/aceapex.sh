#!/usr/bin/env bash
set -euo pipefail
ACE_REF=ce6b6740c7aae8a01720d615ae024c181b7d52b6
ACE_LABEL=aceapex-v2.6.5-interactive
ACE_MODE=interactive
ACE_VERSION=aceapex-v2.6.5@ce6b6740c7aae8a01720d615ae024c181b7d52b6
source "${HB_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}/review/aceapex_upgrade/adapter_common.sh"
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then return 0; fi
hb_entry "$@"
case "${1:-}" in supports) codec_supports;; unavailable) codec_unavailable;; esac
