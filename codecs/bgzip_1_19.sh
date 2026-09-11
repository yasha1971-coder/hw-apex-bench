#!/usr/bin/env bash
set -euo pipefail
source "${HB_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}/codecs/bgzip.sh"
# Matched release for comparison with the 435-row historical publication.
HTS_PIN=8f7231035d0409d525767c66d9f49f1f967ee1df
HTS_RELEASE=1.19
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then return 0; fi
hb_entry "$@"
case "${1:-}" in supports) codec_supports;; unavailable) codec_unavailable;; *) exit 2;; esac
