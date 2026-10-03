#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/../.." && pwd)
MANIFEST=${AXIS3_MANIFEST:?set AXIS3_MANIFEST to the frozen HPRC URL+sha256 manifest}
OUT=${AXIS3_OUT:-"$ROOT/.work/axis3"}
SEED=20261003
mkdir -p "$OUT"/{source,requests,results}
{
  echo "axis=cohort-random-access"
  echo "seed=$SEED"
  echo "git_commit=$(git -C "$ROOT" rev-parse HEAD)"
  uname -a
  lscpu
  /usr/bin/time --version 2>&1 | head -1
  samtools --version 2>/dev/null || true
  bgzip --version 2>/dev/null || true
  agc --version 2>/dev/null || true
} > "$OUT/RUN.txt"
# This runner is intentionally not invoked by CI.
# Phase 1: download each manifest URL into source/<assembly_id>.fa[.gz], verify source_sha256 before decompression/use.
# Phase 2: index FASTA truth, then freeze N=4/50/all × W=256/4096/65536/1048576 request+reference files.
# Phase 3: build each available adapter once per N/configuration and record wall time, peak RSS, exact bytes including sidecars.
# Phase 4: execute the identical 10,000 requests per N/W/scope; judge every window before emitting a valid throughput row.
# Phase 5: for each eligible in-process codec/config measure one-thread full decode D_Q, derive actual Q geometry, and emit window-law predicted p50 + signed error.
# AGC capability probing must record whether exact windows or larger contig/set extraction was required.
# ACEAPEX-refrel remains n/a until its format is frozen.
printf '%s\n' "prepared-only: no official axis3 measurement has been run" > "$OUT/STATUS.txt"
