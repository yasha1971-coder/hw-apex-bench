#!/usr/bin/env bash
set -euo pipefail
ACE_REF=50723533be48a8d9ed42e4b0f9e1f9106ef169b7
ACE_LABEL=aceapex-v2.1.0-interactive
ACE_MODE=interactive
ACE_VERSION=aceapex-v2.1.0@50723533be48a8d9ed42e4b0f9e1f9106ef169b7
source "${HB_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}/codecs/aceapex_modern_common.sh"
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then return 0; fi
hb_entry "$@"
