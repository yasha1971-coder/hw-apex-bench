#!/usr/bin/env bash
# PROTOCOL_AXIS4_N10 v1.1 truth staging: data root with hard links to the 10 local source .fa.gz (0 new bytes),
# the frozen groups, then the independent truth check (stage), A6 prepare --truth-version 1.1, and compare.
# Usage: stage_v11.sh DATA_ROOT LOG_DIR      (DATA_ROOT and LOG_DIR must not exist)
set -euo pipefail
ROOT=$1; LOGS=$2
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
HPRC50=${HPRC50:-$HOME/pubrepo/.wk/hprc50}
test ! -e "$ROOT"; test ! -e "$LOGS"
mkdir -p "$ROOT/src" "$LOGS"
tail -n +2 "$HERE/inputs/selection_n10.tsv" | while IFS=$'\t' read -r _ aid _ _ local _; do
  ln "$(readlink -f "$HPRC50/$(basename "$local")")" "$ROOT/src/$aid.fa.gz"
done
cp "$HERE/inputs/groups_n10.json" "$HERE/inputs/groups_n10_check.json" "$ROOT/"
{ date -Is; df -B1 "$ROOT" | tail -1; uptime; } > "$LOGS/env.txt"
python3 "$HERE/truth_v11_check.py" stage --root "$ROOT" --hprc50 "$HPRC50" \
  --out-tsv "$LOGS/truth_v11_check.tsv" 2>&1 | tee "$LOGS/stage.log"
(cd "$REPO" && python3 -m tools.axis4 prepare --root "$ROOT" --manifest cohort.json \
  --groups groups_n10.json --out prepared-v11 --truth-version 1.1) 2>&1 | tee "$LOGS/prepare.log"
(cd "$REPO" && python3 -m tools.axis4 prepare --root "$ROOT" --manifest cohort.json \
  --groups groups_n10_check.json --out prepared-v11-check --truth-version 1.1) 2>&1 | tee "$LOGS/prepare_check.log"
python3 "$HERE/truth_v11_check.py" compare --check-tsv "$LOGS/truth_v11_check.tsv" \
  --prepared "$ROOT/prepared-v11/prepared.json" 2>&1 | tee "$LOGS/compare.log"
sha256sum "$ROOT/cohort.json" "$ROOT"/groups_n10*.json "$ROOT"/prepared-v11*/prepared.json "$LOGS"/*.log "$LOGS"/*.tsv | tee "$LOGS/SHA256SUMS.txt"
