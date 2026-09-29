#!/usr/bin/env bash
set -euo pipefail
ACE_REF=ec3477877e7ed3f9792885a1a8beb26e48f4b717
ACE_LABEL=aceapex-main-open
ACE_MODE=open
ACE_VERSION=aceapex-main@ec3477877e7ed3f9792885a1a8beb26e48f4b717
source "${HB_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}/codecs/aceapex_modern_common.sh"
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then return 0; fi
hb_entry "$@"
