# B verdict job — protocol v1.1

This section is executable only after the B patch and native correctness CI are
accepted. It does not authorize measurements. The unified Axis 3/4/5 runbook is
A2 and is not fabricated here. No command below has been measured by the patch
producer; native execution is checked on ace-core.

## Retained prerequisites

Use the existing pinned builds and archives, not another machine's throughput.
Rebuild the refrel3 `.so` with `build_refrel3_native.sh` and the BGZF `.so` with
`build_bgzf_axis3.sh`: B adds full sequential decode exports. Existing window-only
libraries are deliberately refused, not replaced by command-per-window execution.
Record new library SHA, compiler, flags and dependencies in build receipts.
Use one stock AGC create; no append chain. Do not change any codec pin.

Prepare a root containing the original FASTA sources, compressed archives, required
references/indexes, and the hash-bound files described in `VERDICT_JOB.md`. Copy
this runbook into that root and bind its SHA in `plan.json`. Freeze the actual
post-application harness commit in `plan.json`, not the author's local commit ID.

## Request preparation (no codec timings)

From the repository root, with INPUT_ROOT set to the retained cohort directory:

```sh
set -euo pipefail
python3 -m tools.verdict_refrel3 prepare --root "$INPUT_ROOT" \
  --manifest cohort.json --out prepared
```

The default optional sweep is W=1,2,4,...,65536, each with 10,000 requests and seed
20261003. `--windows 1,1024,8192,65536` prepares only calibration and verdict points.
Any different diagnostic list is frozen before execution. All formats share the
same list per W. Preparation never opens a compressed archive or times a decoder.
Its output gives the exact file reference for `plan.json`'s `prepared` field.

## One execution command on ace-core

```sh
set -euo pipefail
python3 -m tools.verdict_refrel3 run --root "$INPUT_ROOT" \
  --plan plan.json --out "$EVIDENCE_ROOT/window-law-B"
```

The command verifies source/plan/request/protocol/library hashes, requires a clean
tracked harness at the plan's exact commit, and records a live one-second ace-core
silence gate before the bounded job: load1<0.5, available disk>20,000,000,000 bytes,
no foreign process >=10% CPU. This is a preflight, not a claim of continuous
quiescence. The output directory must not exist. A1's optional native-test SKIP
policy never authorizes skipping an official format: unavailable inputs produce
FAILED with a reason and no valid performance row.

For each format: full sequential decode, 3 warmups + 9 recorded repetitions,
canonical SHA on every repetition outside the timer; then the independent W=1
probe and the frozen W sweep. Only 1024/8192/65536 contribute model-error verdicts.
Wrong SHA at any W is FAILED. Negative c0 is retained and model B is FAIL.
BGZF default/matched-g are two configurations but count as one foreign family;
coverage needs both refrel3 Q values and at least four distinct foreign families.

Duration and peak-memory values need an ace-core run; none are estimated from
synthetic clocks. Required resident memory includes the archives, references,
full-output buffers and codec workspaces. In particular, AGC may materialize full
contig outputs; use the recorded hardware/memory evidence before the official run.

## Verify and retain

```sh
set -euo pipefail
python3 -m tools.verdict_refrel3 verify --root "$EVIDENCE_ROOT/window-law-B"
(cd "$EVIDENCE_ROOT/window-law-B" && sha256sum -c SHA256SUMS)
```

`results.json` uses `schemas/window-law-verdict-v1.schema.json`. `table.md` is
rendered only after raw-log SHA, samples, quantiles, model arithmetic and coverage
are checked. Every caption lists raw-log hashes. Native output bytes and canonical
bytes are separately recorded in each D_Q repetition. Historical runs stay intact.
A nonzero run exit code is not permission to discard failing rows or rerun a
successful point: inspect the saved evidence first. Nothing is published by this job.
