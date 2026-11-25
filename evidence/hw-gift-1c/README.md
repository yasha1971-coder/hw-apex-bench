# HW-GIFT-1c — two seekable writers, one zstd version

The first branch commit, `65baf466eb399f815afff9235e20e94ea7780421`, contains
only the unchanged [protocol](CALIBRATION.md). No new encoding or measurement
preceded it. Main was checked live at
`c1ad9d4b6ff8ed0a576593cb6e101e6c1032faa4` (merged HW-GIFT-1b).
The supplied engineering method is adopted separately in PR #91; its single
file/commit is deliberately not part of this experiment PR.

Foundations checked: `docs/AGENTS.md`, `docs/HISTORY.md`, `docs/METHOD.md`,
`docs/TOOL_ROADMAP.md`, `METHODOLOGY.md`, accepted HW-GIFT-1b inventories,
live main/PR #90 state, and pinned clean zstd source. The project roadmap has no
duplicate HW-GIFT-1c task; this owner-supplied protocol is the current task.
No ACEAPEX code, other projects, existing evidence or public issues are changed.

The decision is whether and when contrib's frame-size policy should change to
match pyzstd's density. Consumers are seekable-zstd writers/readers and the
hw-apex-bench owner. The comparison is the two actual writer paths, with exact
frame hashes and full restored bytes as the oracle. If a method control fails,
stop before comparison. If either minimal frame hash fails, stop before the
one-line patch. Confirmed byte equality leads to the bounded matrix; a mismatch
requires locating the unaccounted bytes before making a cause claim.

## Execution

Use the separate ace-core checkout `/home/ubuntu/hw-apex-bench-hw-gift-1c`.
Existing inputs, pyzstd environment and clean pinned zstd source are read-only
dependencies in the previous checkout. Generated copies and archives stay in
this new checkout's `.work/hw-gift-1c/`. All commands here are correctness or
size checks, without timers; builds stay outside the shared timing lock.

```sh
PYTHON=/home/ubuntu/hw-apex-bench-hw-gift-1b/.work/hw-gift-1b/venv/bin/python
$PYTHON -B evidence/hw-gift-1c/run.py controls
# Commit/push the verified controls before comparison.
$PYTHON -B evidence/hw-gift-1c/run.py inspect
# Commit/push frame inventory, headers and exact minimal proof.
$PYTHON -B evidence/hw-gift-1c/run.py case 0
# Verify and commit/push each case before advancing through case 7.
```

The existing C runner deleted its temporary archive bytes. C archives therefore
must be reconstructed with the unchanged pinned encoder and match the saved
HW-GIFT-1b SHA-256 and byte count before they can be used as references. Existing
pyzstd archives are read directly and likewise checked against saved evidence.
No previous timing series is rerun. Newly added 128/512 KiB points use the same
writer calls and input bytes.

The complete bounded matrix has eight configurations: enwik8 L3 at
64/128/256/512 KiB; enwik8 L19 at 64 KiB; silesia L3 at 64/256 KiB; silesia L19
at 64 KiB. This covers all six anomalous frame points across the four
corpus/level groups, plus both requested boundary points.

`frame_probe.c` isolates source-size hint from feeding schedule. H2 changes
128 KiB feeding to one whole-frame CONTINUE call, keeping the final empty END.
The separate first-call END case is a known-FCS control, not a substitute for
either real writer path. `cparams_from_policy` is the source-derived
`ZSTD_getCParams` policy result, not a claim that requested CCtx parameters are
the already-applied internal state.

Every output/attempt and command stderr/stdout is retained. Existing output
without a complete matching receipt stops for inspection. `cases/*.frames.jsonl.gz`
retains per-frame hashes/geometry; each case validates every native frame decode,
source bytes and table XXH64 when present. Removing checksums and rebuilding the
table must yield the exact pyzstd archive; adding computed checksums must restore
the patched contrib archive byte for byte.

Any optional speed pair requires a separately committed execution description
before timing: CPU 0, one thread, resident input/output, blocking
`flock /run/lock/ovh-bench.lock`, boundary load1 threshold 2.0 and observational
per-core counters. No timer is included in the correctness runner above.

Draft PR #92 stays draft. A facebook/zstd issue, if applicable, is a local draft
only. No external contact or merge is authorized.
