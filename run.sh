#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export LC_ALL=C ACEAPEX_BS=16384 LIT_CHUNK=65536 FSE_CHUNK=32768 MIN_MATCH=0
exec python3 harness/stage1.py "$@"
