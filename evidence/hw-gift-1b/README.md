# HW-GIFT-1b execution

[CALIBRATION.md](CALIBRATION.md) is the unchanged owner protocol, committed first
as `c4809624beb0ad7a243163455d9c05545bc52d99`, before any HW-GIFT-1b measurement.
Keep branch `hw-gift-1b` and PR #90 draft. Do not merge or contact external parties.

The measurement host must match HW-GIFT-1's AMD EPYC 9V74 class, using one pinned
CPU. The currently reachable `ace-core` has EPYC 4344P and is not an accepted
measurement host under the current protocol. The runner is prepared pending
accepted host access; no HW-GIFT-1b timing results exist yet.

On the accepted Linux host, from this repository root, first inspect the allowed
CPU set (`python3 -c 'import os; print(sorted(os.sched_getaffinity(0)))'`) and set
`CPU` to one member of that set:

```sh
python3 evidence/hw-gift-1b/setup_env.py
PYTHON="$PWD/.work/hw-gift-1b/venv/bin/python"
RECEIPT="$PWD/.work/hw-gift-1b/install-receipt.json"
INPUTS="$PWD/.work/inputs"
CPU=CHOOSE_ONE_ALLOWED_CPU
```

The setup pins pyzstd 0.20.0 and wheel SHA-256
`9c6aff5aa9b12bb14d51f724915f176db9b187214d66d93d990c75ff054483c6`,
verified against PyPI on 2026-11-24. It stops if PyPI latest has changed.
It resolves binary dependencies for the chosen CPython, verifies each wheel
against exact-version PyPI metadata, installs offline with hashes, and retains
the complete dependency pins, metadata, wheel payload hashes and imported zstd
version. A completed setup is reused only after its receipt verifies. A partial
setup stops for inspection; it is not silently replaced.

`INPUTS` must contain the unchanged `enwik8` and `silesia.tar` with the hashes
recorded in HW-GIFT-1. The runner reads original HW-GIFT-1 offsets directly.
Run one corpus/level checkpoint at a time, verify it, and push it before starting
the next checkpoint. Use Bash, and stop on any command failure:

```sh
set -euo pipefail
test "$(git branch --show-current)" = hw-gift-1b
git diff --quiet
git diff --cached --quiet
for chunk in enwik8-L3 enwik8-L19 silesia-L3 silesia-L19; do
    "$PYTHON" -B evidence/hw-gift-1b/measure.py run "$chunk" --inputs "$INPUTS" --receipt "$RECEIPT" --cpu "$CPU"
    "$PYTHON" -B evidence/hw-gift-1b/report.py verify "$chunk"
    mapfile -t files < <("$PYTHON" -B evidence/hw-gift-1b/measure.py files "$chunk")
    test "${#files[@]}" -eq 11
    if git ls-files --error-unmatch -- "${files[@]}" >/dev/null 2>&1; then
        git diff --quiet HEAD -- "${files[@]}"
    else
        git add -- "${files[@]}"
        git commit --only -m "Record verified HW-GIFT-1b checkpoint $chunk" -- "${files[@]}"
    fi
    git push origin HEAD:refs/heads/hw-gift-1b
    git fetch --no-tags origin refs/heads/hw-gift-1b:refs/remotes/origin/hw-gift-1b
    test "$(git rev-parse HEAD)" = "$(git rev-parse refs/remotes/origin/hw-gift-1b)"
done
```

Only complete, verified chunks belong in Git. The loop stops if commit, push or
remote confirmation fails, before advancing to another checkpoint. Preserve
`.work/hw-gift-1b/` across interruptions;
never discard partial timed samples to rerun them. No RESULTS table exists until
all four complete chunks have passed independent offline verification.

After the fourth pushed checkpoint, generate the complete report from saved
samples only, then commit and push it for review while retaining the draft PR:

```sh
"$PYTHON" -B evidence/hw-gift-1b/report.py report --output evidence/hw-gift-1b/RESULTS.md
git add -- evidence/hw-gift-1b/RESULTS.md
git commit --only -m "Report HW-GIFT-1b from four verified checkpoints" -- evidence/hw-gift-1b/RESULTS.md
git push origin HEAD:refs/heads/hw-gift-1b
```

The prediction gates use integer nanoseconds and archive bytes before rounding.
Both gates must pass: the enwik8 L3 / 4 KiB default first-read p50 must be at
least 20 times the 1 MiB value, and every one of the 24 shared-grid archives
must differ from HW-GIFT-1 by at most 1%. A failed prediction is reported as
MISS and does not authorize retuning or rerunning.

Offline synthetic unit checks (no codec execution or real timings):

```sh
python3 -B -m unittest discover -s evidence/hw-gift-1b -p 'test_*.py' -v
```
