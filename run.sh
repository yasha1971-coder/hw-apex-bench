#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export LC_ALL=C
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
  cat <<'HELP'
hw-apex-bench: compare resident byte-range access to compressed data.

  ./run.sh --check codecs/xz.sh       Build and verify; no performance timing
  ./run.sh --plan --codec xz          Inspect axes after qualification
  ./run.sh --measure --help          Native measurement options
  ./run.sh --audit-axes              Audit existing nine-axis evidence
  python3 web/validate_publication.py  Verify published data without downloads

Start here: docs/GETTING_STARTED.md
Supported first-run environment: Ubuntu 24.04 Linux; see prerequisites there.
No arguments starts the expensive historical benchmark (downloads/builds/timings).
--stage N (1..5) runs the historical benchmark through the specified stage.
--default-refresh and --cg-curve are explicit historical measurement entry points.
HELP
  exit 0
fi
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
if [[ "${1:-}" == --stage ]]; then
  if [[ $# == 2 && $2 =~ ^[1-5]$ ]]; then
    exec python3 harness/stage1.py "$@"
  fi
  printf 'Usage: ./run.sh --stage 1|2|3|4|5. No measurement started.\n' >&2
  exit 2
fi
if (( $# )); then
  printf 'Unknown entry point: %s. Use ./run.sh --help. No measurement started.\n' "$1" >&2
  exit 2
fi
exec python3 harness/stage1.py
