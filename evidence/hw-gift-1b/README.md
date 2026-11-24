# HW-GIFT-1b execution

The original [protocol](CALIBRATION.md) was committed first as
`c4809624beb0ad7a243163455d9c05545bc52d99`. The owner's exact pre-measurement
host amendment was committed separately as
`0bd4ab29794f610884e66fdb3ca6c6c93495a4e4`, before any new measurement.
The OVH-BENCH execution rule was then preregistered as
`3e7201a0933030de8d3011eb658270e577e6eced` and supersedes zero-activity admission.
Predictions (a) and (b) are unchanged. Keep PR #90 draft; do not merge or contact
external parties. Accepted HW-GIFT-1 data and its GitHub branch stay unchanged.

Both new readers run on **ace-core, AMD EPYC 4344P, pinned CPU 0**. The original
C timed worker hardcodes CPU 0, so it must be available to both readers.

## OVH-BENCH and rejected attempts

Builds, tests and correctness checks may run in parallel. Each timed repeat is
launched by `ovh_bench.py` through the blocking command
`flock /run/lock/ovh-bench.lock <measurement command>`. If another project holds
the lock, wait. Never use a separate lock or a nonblocking bypass.

Every repeat receipt retains literal `date -u`, `/proc/loadavg` and `nproc`
outputs at both boundaries. If the one-minute average exceeds 1.0 at either
boundary, its status is **LOADED**. Preserve that attempt, exclude it and repeat
the checkpoint in a new attempt. Exactly 1.0 is accepted. Original start/resume/end
CPU, kernel, governor and other-process observations remain as context; process
activity alone does not reject a result under the new rule.

The orchestration commands below acquire the shared lock only for timed worker
subcommands, leaving archive encoding and long compilation outside it. Do not
wrap the entire orchestration/build command in the shared benchmark lock.
Both readers also share a private project lock so they cannot overlap each other.
The [earlier admission observations](admission/) predate the OVH-BENCH rule.

## Prepare local dependencies

The server's system Python 3.10 is left unchanged. From this repository root on
ace-core, `prepare_host.py` downloads and verifies prerequisites entirely inside
this repository's `.work/`, recording load without blocking parallel setup:

```sh
set -euo pipefail
python3 -B evidence/hw-gift-1b/prepare_host.py
BOOT="$PWD/.work/hw-gift-1b/python/bin/python3.12"
"$BOOT" -B evidence/hw-gift-1b/setup_env.py
PYTHON="$PWD/.work/hw-gift-1b/venv/bin/python"
RECEIPT="$PWD/.work/hw-gift-1b/install-receipt.json"
INPUTS="$PWD/.work/inputs"
ZSTD="$PWD/.work/hw-gift-1b/zstd"
```

The bootstrap pins standalone CPython 3.12.16 / release 20261123, archive SHA-256
`c85811d35971d06612585a057db3b71806378df6ea8476275fb16aa5c9fe56a0`, the exact
corpus hashes in `corpora.json`, and zstd commit
`f8745da6ff1ad1e7bab384bd1f9d742439278e99`. It performs no compilation or timing.

Setup pins pyzstd 0.20.0 and wheel SHA-256
`9c6aff5aa9b12bb14d51f724915f176db9b187214d66d93d990c75ff054483c6`, verifies
all dependency wheels against exact-version PyPI metadata and installs offline
with hashes. It records imported versions and verifies installed payload bytes.
It stops if PyPI latest changed. Preserve setup receipts and wheels.

Build the pinned C CLI before invoking the original
shell (which builds the static library and reader, but does not build the CLI):

```sh
make -C "$ZSTD/lib" -j1 libzstd.a CFLAGS='-O3 -fPIC'
make -C "$ZSTD/programs" -j1 zstd CFLAGS='-O3 -fPIC'
```

## Matched-host C checkpoints

`c_baseline.py` executes the byte-for-byte original HW-GIFT-1 `reproduce.sh` in
an isolated scratch Git repository with a **local bare origin**. It cannot push
to the accepted `hw-gift-1` GitHub branch. Only the copied metadata dispatcher
changes its obsolete host gate and adds start/end load boundaries; the exact
[diff](c-baseline/host-gate.patch) is retained. The shell, C paired timer, C
adapter, timed Python worker and original report stay unchanged.

Run one chunk, verify it, commit and push it before running the next:

```sh
chunk=enwik8-L3
"$PYTHON" -B evidence/hw-gift-1b/c_baseline.py run "$chunk" --inputs "$INPUTS" --zstd "$ZSTD" --python "$PYTHON"
"$PYTHON" -B evidence/hw-gift-1b/report.py verify-c "$chunk"
mapfile -t files < <("$PYTHON" -B evidence/hw-gift-1b/c_baseline.py files "$chunk")
test "${#files[@]}" -eq 12
git add -- "${files[@]}"
git commit --only -m "Record clean matched-host C checkpoint $chunk" -- "${files[@]}"
git push origin HEAD:refs/heads/hw-gift-1b
```

Repeat for `enwik8-L19`, `silesia-L3`, `silesia-L19`, stopping on every failure.
This C grid has six frame sizes; the new pyzstd default-1-GiB point is separate.
A LOADED C attempt is quarantined in `.work/hw-gift-1b/c-rejected/` before
local checkpoint acceptance. Retry after the one-minute load average has fallen;
the next worker still waits for and acquires the shared lock itself.

## pyzstd checkpoints

Again, run and deliver one chunk at a time in the same order:

```sh
chunk=enwik8-L3
attempt=1
"$PYTHON" -B evidence/hw-gift-1b/measure.py run "$chunk" --inputs "$INPUTS" --receipt "$RECEIPT" --cpu 0 --attempt "$attempt"
"$PYTHON" -B evidence/hw-gift-1b/report.py verify "$chunk"
mapfile -t files < <("$PYTHON" -B evidence/hw-gift-1b/measure.py files "$chunk")
test "${#files[@]}" -eq 11
git add -- "${files[@]}"
git commit --only -m "Record clean HW-GIFT-1b pyzstd checkpoint $chunk" -- "${files[@]}"
git push origin HEAD:refs/heads/hw-gift-1b
```

Exit 2 means a timed repeat was LOADED or host conditions changed. Preserve it
and use a new explicit `--attempt` number for the retry. Archive bytes remain
shared and immutable across pyzstd attempts; rejected timing samples are never
reused. Ordinary interruptions resume the same non-rejected attempt, retaining
all completed CLEAN repeats and the original and resumed observations. Within a
timed repeat, samples stay in RAM and the complete raw row is saved once after
the loop; no synchronous checkpoint files are written between timed API calls.
An interrupted repeat without a complete boundary receipt stops for inspection.

If the executor has no GitHub write credential, preserve its local checkpoint
commit and transfer a Git bundle to the Windows HW checkout for a fast-forward
push. Confirm that GitHub contains the exact commit before advancing. No token
transfer or mutation of another project's credentials is needed.

## Complete report and synthetic tests

Only after all eight clean, same-host/core checkpoints have been pushed:

```sh
"$PYTHON" -B evidence/hw-gift-1b/report.py report --output evidence/hw-gift-1b/RESULTS.md
git add -- evidence/hw-gift-1b/RESULTS.md
git commit --only -m "Report HW-GIFT-1b and matched-host C baseline" -- evidence/hw-gift-1b/RESULTS.md
git push origin HEAD:refs/heads/hw-gift-1b
```

Prediction (a) compares exact default and 1 MiB first-read p50 integer ns.
Prediction (b) still compares all 24 shared pyzstd archive sizes to the accepted
HW-GIFT-1 **main** bytes, using integer arithmetic before rounding. Both gates
must pass; a miss is reported without retuning. The new C/pyzstd comparison is
informational and records the different reader paths and linked zstd versions.

Synthetic checks execute no codecs or real timings:

```sh
python3 -B -m unittest discover -s evidence/hw-gift-1b -p 'test_*.py' -v
```
