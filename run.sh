#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export LC_ALL=C
# Upstream environment overrides --profile. Never inherit accidental overrides.
unset ACEAPEX_BS LIT_CHUNK FSE_CHUNK MIN_MATCH LIT_LEVEL LIT_LANES
unset NO_REP DIRECT8 FORCED_BIN ACEAPEX_DUMP LD_PRELOAD
exec python3 harness/stage1.py "$@"
