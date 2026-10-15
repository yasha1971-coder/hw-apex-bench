#!/usr/bin/env bash
set -euo pipefail
task_repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$task_repo_dir"
task_python="${PYTHON:-python3}"
if [[ $# -lt 1 ]]; then
  echo 'Usage: reproduce_v020.sh synthetic --out NEW_DIR | real --input CONFIG --data-root ROOT --native-so SO [--native-so SO ...] --require-silence --out NEW_DIR' >&2
  exit 2
fi
task_mode="$1"
shift
case "$task_mode" in
  synthetic) exec "$task_python" -m tools.release_synthetic "$@" ;;
  real) exec "$task_python" -m tools.release_v020 --mode real "$@" ;;
  *) echo 'Unknown reproduction mode' >&2; exit 2 ;;
esac
