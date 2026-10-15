#!/usr/bin/env bash
# PROTOCOL_AXIS4_N10 v1.1 executor (sections 3-5). Resumable: each finished step leaves a marker in $STATE.
# Every heavy build/hash step and every timed row runs under `flock $LOCK` (machine-wide rule); rows hold the
# lock for all 12 runs incl. their A6 gates. Strictly one job at a time. Nothing outside $ROOT/$LOGS/$AGCB is written.
# Usage: bash run_n10.sh build|check|rows|verify
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
WK=$HOME/pubrepo/.wk
ROOT=$WK/axis4n10; LOGS=${N10_LOGS:-$WK/axis4n10_logs}; STATE=$LOGS/state; AGCB=$WK/agc_native_v020; RUNS=${N10_RUNS:-runs12}
LOCK=$WK/measure.lock
export PATH=$WK/hwvenv/bin:$PATH
mkdir -p "$LOGS" "$STATE"; touch "$LOCK"
PAT='rv2 |rr3bench|run_law|run_bench|run_diag|perf stat'
IDS=(y1_HG00438.1 y1_HG00438.2 y1_HG00621.1 y1_HG00621.2 y1_HG00673.1 y1_HG00673.2 y1_HG00735.1 y1_HG00735.2 y1_HG00741.1 y1_HG00741.2)
NEW=(y1_HG00673.1 y1_HG00673.2 y1_HG00735.1 y1_HG00735.2 y1_HG00741.1 y1_HG00741.2)

log() { echo "[$(date -Is)] $*" | tee -a "$LOGS/run_n10.log"; }
foreign() { ps -eo args= | grep -E "$PAT" | grep -v -e shell-snapshots -e "grep -E" -e ugrep >/dev/null; }
L() { flock "$LOCK" nice -n 19 ionice -c3 "$@"; }      # heavy build/hash job under the machine lock
step() {   # step NAME CMD... : run once, log, marker
  local name=$1; shift
  [ -e "$STATE/$name.done" ] && { log "skip $name (done)"; return 0; }
  log "start $name: $*"
  "$@" > "$LOGS/$name.log" 2>&1 || { log "FAILED $name (see $LOGS/$name.log)"; tail -5 "$LOGS/$name.log"; exit 1; }
  touch "$STATE/$name.done"; log "done $name"
}
quiet() {  # pre-wait (the A6 gate itself decides): load1 < 0.3 and no refrel-v2 process, for up to 6 h
  local t0; t0=$(date +%s)
  while :; do
    if ! foreign && awk '{exit !($1 < 0.3)}' /proc/loadavg; then return 0; fi
    [ $(( $(date +%s) - t0 )) -ge 21600 ] && { log "quiet wait timeout"; return 1; }
    sleep 15
  done
}
py() { (cd "$REPO" && python3 "$HERE/build_v11.py" --root "$ROOT" "$@"); }

build() {
  step agc_build L env AGC_PLATFORM=native bash "$REPO/review/axis3/build_agc_v324.sh" "$AGCB"
  step static L bash -c "cd '$REPO' && python3 '$HERE/build_v11.py' --root '$ROOT' static"
  for a in "${NEW[@]}"; do step "fasta_$a" L bash -c "cd '$REPO' && python3 '$HERE/build_v11.py' --root '$ROOT' fasta $a"; done
  step fai L bash -c "cd '$REPO' && python3 '$HERE/build_v11.py' --root '$ROOT' fai"
  for a in "${NEW[@]}"; do step "bgzf_$a" L bash -c "cd '$REPO' && python3 '$HERE/build_v11.py' --root '$ROOT' bgzf $a"; done
  for a in "${NEW[@]}"; do step "zstd_$a" L bash -c "cd '$REPO' && python3 '$HERE/build_v11.py' --root '$ROOT' zstd $a"; done
  step agclib L bash -c "cd '$REPO' && python3 '$HERE/build_v11.py' --root '$ROOT' --agc-build '$AGCB' agclib"
  for m in t2t noref; do step "agc_$m" L bash -c "cd '$REPO' && python3 '$HERE/build_v11.py' --root '$ROOT' --agc-build '$AGCB' agc $m"; done
  step plans L bash -c "cd '$REPO' && python3 '$HERE/build_v11.py' --root '$ROOT' plans"
  df -B1 "$HOME" | tail -1 | tee -a "$LOGS/run_n10.log"
}

one_run() {  # one_run PLAN OUTREL THREADS -> 0 PASS, 1 gate refused/other FAILED, 2 NOT_SUPPORTED, 3 wrong answer
  local plan=$1 out=$2 thr=$3 st err
  quiet
  (cd "$REPO" && python3 -m tools.axis4 run --root "$ROOT" --plan "$plan" --out "$out" --decoder-threads "$thr") \
    >> "$LOGS/runs.log" 2>&1 || true
  st=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['status'])" "$ROOT/$out/evidence.json")
  err=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d.get('error'))" "$ROOT/$out/evidence.json")
  log "run $out status=$st error=$err"
  case "$st" in PASS) return 0 ;; NOT_SUPPORTED) return 2 ;; esac
  case "$err" in *"differs from prepare"*|*"must be bytes"*) return 3 ;; esac
  return 1
}
slot() {   # slot PLAN BASE THREADS : retries only gate refusals (attempt dirs retained), max 6
  local k rc
  for k in 1 2 3 4 5 6; do
    rc=0; one_run "$1" "$2_a$k" "$3" || rc=$?
    case $rc in 0) echo "$2_a$k" >> "$LOGS/accepted.txt"; return 0 ;; 2) echo "$2_a$k" >> "$LOGS/not_supported.txt"; return 0 ;;
      3) log "WRONG ANSWER in $2_a$k: STOP"; exit 3 ;; esac
    sleep 60
  done
  log "slot $2 failed 6 attempts: STOP"; exit 4
}
row() {   # row NAME THREADS : 3 warm-ups + 9 recorded, under one lock hold
  local name=$1 thr=$2
  [ -e "$STATE/row_${name}_t$thr.done" ] && { log "skip row $name t$thr"; return 0; }
  log "row $name t$thr start"
  flock "$LOCK" bash -c "source '$HERE/run_n10.sh' __lib__; for i in 1 2 3; do slot plans/$name.json $RUNS/$name/t$thr/w\$i $thr; done; for i in 1 2 3 4 5 6 7 8 9; do slot plans/$name.json $RUNS/$name/t$thr/r\$i $thr; done"
  touch "$STATE/row_${name}_t$thr.done"; log "row $name t$thr done"
}
ns_row() {  # NOT_SUPPORTED row: one explicit run at 16 decoder threads (no decoder started)
  local name=$1
  [ -e "$STATE/ns_${name}.done" ] && return 0
  flock "$LOCK" bash -c "source '$HERE/run_n10.sh' __lib__; rc=0; one_run plans/$name.json $RUNS/$name/t16/not_supported 16 || rc=\$?; [ \$rc = 2 ]"
  echo "$RUNS/$name/t16/not_supported" >> "$LOGS/not_supported.txt"
  touch "$STATE/ns_${name}.done"; log "NOT_SUPPORTED row $name t16 recorded"
}
check() {
  [ -e "$STATE/check.done" ] && { log "skip check"; return 0; }
  flock "$LOCK" bash -c "source '$HERE/run_n10.sh' __lib__; slot plans/check_refrel3_q4k.json $RUNS/check/refrel3_q4k_t1 1"
  local ev; ev=$(tail -1 "$LOGS/accepted.txt")
  (cd "$REPO" && L python3 -m tools.axis4 verify --evidence "$ROOT/$ev/evidence.json" --input-root "$ROOT" \
     --prepared-sha256 "$(sha256sum "$ROOT/prepared-v11-check/prepared.json" | cut -d' ' -f1)") | tee "$LOGS/check_verify.json"
  python3 -c "import json,sys;d=json.load(open(sys.argv[1]));sys.exit(0 if d.get('verified')==20 else 1)" "$LOGS/check_verify.json"
  touch "$STATE/check.done"; log "method check PASS ($ev, 20 verified)"
}
rows() {
  for r in refrel3_q4k refrel3_q16k bgzf_default zstd_seekable faidx_plain agc_t2t agc_noref; do row "$r" 1; done
  row bgzf_default 16
  for r in refrel3_q4k refrel3_q16k zstd_seekable faidx_plain agc_t2t agc_noref; do ns_row "$r"; done
}
verify_all() {   # independent verify of every accepted run, 8 in parallel inside one lock hold
  local P; P=$(sha256sum "$ROOT/prepared-v11/prepared.json" | cut -d' ' -f1)
  grep -v "^$RUNS/check/" "$LOGS/accepted.txt" > "$LOGS/verify_list.txt"
  export ROOT LOGS REPO P
  flock "$LOCK" nice -n 19 ionice -c3 xargs -P 8 -I{} bash -c '
    ev={}; tag=$(echo "$ev" | tr / _)
    [ -e "$LOGS/state/verify_$tag.done" ] && exit 0
    (cd "$REPO" && python3 -m tools.axis4 verify --evidence "$ROOT/$ev/evidence.json" --input-root "$ROOT" \
       --prepared-sha256 "$P") > "$LOGS/verify_$tag.json" 2> "$LOGS/verify_$tag.err" \
      && touch "$LOGS/state/verify_$tag.done" || echo "VERIFY FAILED $ev"' < "$LOGS/verify_list.txt"
  log "verified $(ls "$STATE"/verify_*.done 2>/dev/null | wc -l) of $(wc -l < "$LOGS/verify_list.txt")"
}

if [ "${1:-}" = __lib__ ]; then return 0 2>/dev/null || exit 0; fi
case "${1:-}" in
  build) build ;; check) check ;; rows) rows ;; verify) verify_all ;;
  *) echo "usage: $0 build|check|rows|verify" >&2; exit 2 ;;
esac
