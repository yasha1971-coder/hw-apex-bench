# hw-apex-bench: benchmark to tool

## Publication checkpoint

This revision publishes the reviewed nine-axis evidence from PR #16 on main,
with 435 original JSONL records, the recovered default report, generated coverage
and the complete c(g) grid. Licenses, the negative-c(g) note and the baseline
review are preserved. Nine-axis coverage means measured/derived evidence or an
explicit unsupported reason; it does not fabricate unavailable BGZF geometries.
No completed measurement is rerun. Full benchmark workflows are manual-only.

After this revision is merged and publication checks pass, the next bounded step
is the seven-function adapter interface. Reconcile draft PR #17 with this
published baseline; do not merge its old README or measurements over main.
The historical checkpoints below explain how the evidence gate was reached.

## Work order

The owner's order is mandatory:

1. Nine axes on the three existing formats.
2. Extract adapters with the same seven functions.
3. Qualify adapters with `./run.sh --check` and small correctness CI.
4. Add blocked xz through liblzma, without changing the harness.
5. CONTRIBUTING.md and citation metadata (licensing is already merged).
6. Add CRAM with an explicit lossless, alignment-specific operation contract.
7. Release tag and DOI.

Do not add codecs or continue adapter refactoring before reviewing and accepting
the nine-axis evidence. Do not repeat completed measurements. No changes to the
aceapex, glyph-engine or yasha-context repositories are authorized.

## Historical checkpoint: 2026-09-11

Licensing PR #18 was merged into main as
`a5ab7e38bc1d995dc580c8f0e5e1b221f7bca8d7`. Code is Apache-2.0; original
measurements/results are CC BY 4.0. Preserve the README footer through METHOD.md
and regenerate README when merging later branches.

The nine-axis evidence is prepared in draft PR #16, commit
`1160850bda8385cc18d8960989cad15ecacd8b43`; it is not yet published in main.
The existing adapter work in draft PR #17 remains paused and is not a prerequisite
for accepting the measurements.

[Complete nine-axis coverage](https://github.com/yasha1971-coder/hw-apex-bench/blob/1160850bda8385cc18d8960989cad15ecacd8b43/AXES_RESULTS.md)
[Complete five-point table](https://github.com/yasha1971-coder/hw-apex-bench/blob/1160850bda8385cc18d8960989cad15ecacd8b43/CG_CURVE_RESULTS.md)

| Previously questioned item | Retained evidence | Gate status |
|---|---|---|
| bgzip encode / full decode plateau | 29.025 / 711.936 MB/s; one encoder and one decoder worker | Plateau audit passes |
| zstd-seekable encode / full decode plateau | 227.302 / 709.132 MB/s; one encoder and one decoder worker | Plateau audit passes; decode comparison to bgzip is a loss |
| Five-point c(g), zstd and ACEAPEX | Five matched-baseline points each: 4/16/64/256/1024 KiB | Evidence retained; curve review required |
| Five-position BGZF grid | Three measured geometries; 256 KiB and 1 MiB unsupported | Strict c(g): n/a — no comparable single-parameter whole-input baseline |
| Native batch, bgzip and zstd | n/a — no batch API; separately measured loops cover five access profiles | No blank cells or invented native batch rates |
| Other axes | Ratio, region p50/p99, amplification, H_alpha and break-even are in the core-run coverage report | Audit passes |

These figures are descriptive values on the recorded host, not new measurements
or promises across machines. The baseline must come from the same run and operation.
Core evidence has four configurations of three formats. The controlled curve is
from a separate run: ACEAPEX ee5a37e default versus core profiles at 1b13df3. The
adaptive a194893 default refresh is also separate. Never combine these into a
fictitious single configuration with nine measured axes.

The coverage audit reports nine axes, three formats, four core configurations,
15 curve positions and 13 supported geometries. BGZF cannot supply arbitrary
large independent blocks or a strict one-block baseline for this corpus.
Explicitly unsupported positions count as accounted-for coverage, not measurements.

Validation of the retained PR #16 files (no timing or compression):

```sh
./run.sh --audit-axes
python3 -m unittest discover -s harness -p test_axes.py
python3 -m unittest discover -s harness -p test_cg_curve.py
python3 web/validate_publication.py
```

The audit, 31 axis/curve tests and publication validation passed. These files and
results.jsonl were checked byte-identical between PR #16 and the checked local
PR #17 checkout. Retained results SHA-256:
`cb52b8cb9fac484a6474d976681ea85ae2c052d80d820422b7f57c25ec938100`.
The curve receipt records artifact 10178051601 from workflow 34543023595 and
2600 verified regional samples. This checkpoint revalidates retained evidence;
it does not claim to have downloaded the original artifact again or restored
archives again. Main still contains its original 420 records, unchanged.

## Next bounded segment

Review the complete PR #16 curve and coverage table, then prepare the evidence
publication for main with the merged licensing footer and validated manifest.
Do not merge unrelated adapter changes. A merge of PR #16 or scientific acceptance
of the curve is not implied by authorization to merge licensing PR #18.

After that gate, derive the common adapter interface from the working implementation:
`codec_name`, `codec_version`, `codec_build`, `codec_compress`,
`codec_decompress`, `codec_region`, `codec_supports`.
Capabilities must generate explicit n/a reasons. Native library calls, not shell
process startup, belong inside API latency timers. Existing draft implementations
must be reconciled with this contract rather than silently declared complete.

Each bounded segment ends with checks, a saved Git commit/PR, and a CONTINUITY.md
checkpoint containing exact revisions, evidence, remaining issues and one next
action. Do not carry unfinished changes only in conversation memory.

## Focused baseline review

The ten supported c(g) points passed command-level and geometry checks; see
[review/CG_BASELINE_REVIEW.md](review/CG_BASELINE_REVIEW.md). Eleven tests guard
against parameter substitutions. Zstd's baseline has one complete data frame
and an empty terminal frame, both included in the archive size. Do not call it
a file with exactly one physical frame. ACEAPEX has one LZ block; its entropy
stream policies remain unchanged. The review does not rerun measurements or
authorize merging adapter work.
