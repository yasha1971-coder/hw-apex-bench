# HW-GIFT-1b execution

The original [protocol](CALIBRATION.md) was committed first as
`c4809624beb0ad7a243163455d9c05545bc52d99`. The owner's exact pre-measurement
host amendment was committed separately as
`0bd4ab29794f610884e66fdb3ca6c6c93495a4e4`, before any new measurement.
Predictions (a) and (b) are unchanged. Keep PR #90 draft; do not merge or contact
external parties. Accepted HW-GIFT-1 data and its GitHub branch stay unchanged.

Both new readers run on **ace-core, AMD EPYC 4344P, pinned CPU 0**. The original
C timed worker hardcodes CPU 0, so it must be available to both readers.

## Admission and rejected attempts

`load_guard.py` records a two-second process observation, CPU, kernel, governor,
pinned core and load averages. Any observed foreign CPU tick, known compiler or
measurement process, or inspection error rejects admission. Interactive agents
are included as foreign work. OS-daemon activity is recorded separately. Load
averages are context; the gate uses observed current process activity.

Each checkpoint retains start, resume and end observations. A changed governor
also rejects the checkpoint. A dirty start starts no measurement; dirty end
results and interrupted attempts rejected on resume remain in `.work/` and are
excluded from accepted evidence. Never delete rejected raw data to hide a retry.
Both readers share one exclusive lock and must run sequentially.

The retained [admission observations](admission/) show why timing has not started
yet. A quiet window must pass the same gate before work proceeds.

## Prepare local dependencies

The server's system Python 3.10 is left unchanged. From this repository root on
ace-core, `prepare_host.py` first requires idle admission, then downloads and
verifies prerequisites entirely inside this repository's `.work/`:

```sh
set -euo pipefail
python3 -B evidence/hw-gift-1b/prepare_host.py --allow-control-load-for-preparation
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
The optional flag permits named control-session processes only for these
downloads/unpacking steps. Compilers, measurement processes, unknown active
processes and inspection errors still block preparation. It does not change
checkpoint admission: accepted timing checkpoints always require zero foreign
activity, including control processes.

Setup pins pyzstd 0.20.0 and wheel SHA-256
`9c6aff5aa9b12bb14d51f724915f176db9b187214d66d93d990c75ff054483c6`, verifies
all dependency wheels against exact-version PyPI metadata and installs offline
with hashes. It records imported versions and verifies installed payload bytes.
It stops if PyPI latest changed. Preserve setup receipts and wheels.

On an admitted idle host, build the pinned C CLI before invoking the original
shell (which builds the static library and reader, but does not build the CLI):

```sh
"$PYTHON" -B evidence/hw-gift-1b/load_guard.py --cpu 0 --output .work/hw-gift-1b/pre-build-load.json
make -C "$ZSTD/programs" -j1 zstd
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
A rejected C attempt is quarantined in `.work/hw-gift-1b/c-rejected/` before
local checkpoint acceptance. Retry the chunk only after idle admission.

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

Exit 2 means the load/host admission rejected the attempt. Preserve it and use a
new explicit `--attempt` number after the host is idle. Archive bytes remain
shared and immutable across pyzstd attempts; rejected timing samples are never
reused. Ordinary interruptions resume the same non-rejected attempt, retaining
all completed pairs and the original and resumed admission receipts.

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
