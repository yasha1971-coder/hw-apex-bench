#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export LC_ALL=C
# Upstream environment overrides --profile. Never inherit accidental overrides.
unset ACEAPEX_BS LIT_CHUNK FSE_CHUNK MIN_MATCH LIT_LEVEL LIT_LANES
unset NO_REP DIRECT8 FORCED_BIN ACEAPEX_DUMP LD_PRELOAD
if [[ "${1:-}" == --measure ]]; then
  shift
  exec python3 harness/native_execution.py "$@"
fi
if [[ "${1:-}" == --plan ]]; then
  shift
  exec python3 harness/axis_planner.py "$@"
fi
if [[ "${1:-}" == --check ]]; then
  shift
  exec python3 harness/check_adapter.py "$@"
fi
if [[ "${1:-}" == --audit-axes ]]; then
  shift
  exec python3 harness/axes.py "$@"
fi
if [[ "${1:-}" == --default-refresh ]]; then
  shift
  exec python3 harness/default_refresh.py "$@"
fi
if [[ "${1:-}" == --cg-curve ]]; then
  shift
  exec python3 harness/cg_curve.py "$@"
fi
exec python3 harness/stage1.py "$@"
