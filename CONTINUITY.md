# Continuity checkpoint — publication recovery after PR #12

## Resume from here

This file records work recovered from the ChatGPT thread «Создание репозитория
GitHub». The user's screenshot stopped during recovery of the non-UTF-8
`results.jsonl` after PR #12. That failure was reproduced against the live main
branch and the exact original Actions artifact was recovered.

Read `evidence/stage5-20260910/RECOVERY.md`, then check current GitHub PRs and
workflow runs before deciding whether the recovery has already merged/deployed.

## Repository identity and scope

- Actual repository: `yasha1971-coder/hw-apex-bench`.
- Existing public homepage: `https://yasha1971-coder.github.io/hw-apex-bench/`.
- Original/current introductory brief names `yasha1971-coder/cabench`. The
  connected GitHub API returned 404 for that name during recovery. No rename or
  new repository has been performed. Naming remains an explicit unresolved
  mismatch; do not silently claim that `cabench` exists or restart the experiment.
- Protected scope: no changes to `aceapex`, `glyph-engine`, `yasha-context`.
- Scientific aim: independently reproduce the measured density/access tradeoff.
  No universal law, predetermined winner, fitted slope, or historical target.

## Confirmed merged work

| PR | Completed scope |
|---|---|
| #5 | Five access profiles, H_alpha, equal-worker loop/batch and break-even |
| #6–#8 | Independence measurements and stricter causal/baseline definitions |
| #9–#10 | Actual compiled-source provenance; fixed-SHA strict c(g) reproduction |
| #11 | CPU encode/full-decode load curves with plateau qualification |
| #12 | zstd frame-size frontier; separately declared GPU observations |

Main at the failed publication:
`5c43e8633d00c520d46bf7e3460f7a4c4881c2e7`.
PR #12 head: `3a6f5077d7c636087db4093a0c2658e26ae50ad8`.
Thus the old first-table audit boundary was already passed in the prior thread;
do not discard the subsequent approved work or rerun stages 1–5 to fix encoding.

## Exact recovered evidence

- Corpus: chr1 hg38 FASTA, 253935557 bytes, MD5
  `9465e0f0df6e2c6eb39729c39cee5465`.
- Successful measured source: `9cad83e8a5c9a5f3bafb7ef2c70c8d0ead4276fb`.
- Run: `2026-09-10T20:29:44.589718+00:00`, workflow `34526588649`.
- Results: 420 rows; SHA-256
  `4123976f7c546208c92d344a5fc27f21760b14eb84741d51415c8c5b7e97be3e`.
- Original ZIP, including raw samples/logs/traces, is retained separately for the
  owner as `cabench-stage5-source-artifact.zip`. Automatic approval review rejected
  public upload of the complete raw payload; it is excluded from the Git tree.
  The public recovery record retains its Actions artifact ID and exact digest.
- `evidence/published-results.json` verifies exact results/reports and records the
  original ZIP's independently checked GitHub digest.
- Local recovery: all six publication regression tests passed; README and
  BATCH_RESULTS regenerate exactly; homepage generation succeeds.
- These checks validate recovery/publication; they are not a fresh codec run.

## Claims that must keep their scope

- Archive ratio includes complete file/index bytes. Historical 0.410% ACEAPEX
  loss is payload-only. It must not substitute for strict complete-archive c(g).
- The owner's 1.631528% point at `7216280` is a separate declared observation.
  Inspect `STRICT_CG.md` and later measured fixed-SHA evidence before citing it.
- An earlier source review examined the root `aceapex_depth.cpp`, while Makefile
  built `src/aceapex_main.cpp`. Do not lose the actual translation-unit distinction.
  The fixed strict-sweep dependency is `ee5a37eda18b81c1300a1ee44a7e06b6be925bd2`.
- bgzip/gzip is not a same-encoder whole-block causal baseline. Strict bgzip c(g)
  remains n/a when such a baseline cannot be represented.
- All measured absolute CPU values are `declared` by protocol; comparisons on
  the same machine carry pass/fail. This differs from owner-supplied GPU evidence,
  whose `gpu-declared` group was not measured by the CPU runner.
- GPU rows retain hardware, driver, CUDA, block size and missing-log caveats.
  RTX composition 0.87x remains FAIL; reported block counts differ from ceil
  geometry by one. No raw logs have closed that discrepancy.

## Saved next experiment

The previous thread committed a five-point curve implementation locally as
`c8436f6` (`cg-tradeoff-five-point`), based on the failed-publication main.
Its files include `CG_CURVE.md`, `harness/cg_curve.py`, two codec adapters,
`harness/test_cg_curve.py`, and `.github/workflows/cg-curve.yml`.
The screenshot reported 17 passing tests. That is not evidence of a measured
curve. Remote publication and CI status must be checked separately.

Grid: 4, 16, 64, 256 KiB and 1 MiB. Same-container whole-file baselines for
ACEAPEX and seekable zstd. BGZF points beyond its format limit and strict c(g)
are n/a. Each numeric point needs archive accounting and exact restore, plus
common 200-query resident-library p50/p99 measurements.

Next bounded action: preserve that commit remotely, base the experiment on the
publication repair, audit its harness, run the dedicated workflow, and show the
complete curve for review before merging it or drawing new conclusions.
Three-machine generalization and Paper 6 conclusions remain subsequent work.
No Paper 6 manuscript was recovered as a committed deliverable in this step.

## Transition commands

```sh
git status --short --branch
git log -5 --oneline
python3 web/validate_publication.py
python3 web/build.py /tmp/cabench-pages/index.html
```

Record subsequent PR/run URLs and update this checkpoint whenever an open item
changes. A SHA and preserved artifact are stronger continuity than chat memory.

## Licensing priority — 2026-09-11

The user's current priority supersedes adapter/codec work: publish project code
under Apache-2.0 and original measurements under CC BY 4.0 first.
Branch `licensing/code-and-measurements` is based directly on main commit
`e181868f307225bea7c4c3532e0dfb1130d2ae37`, so this change can merge independently
of draft PRs #14–#17. It adds LICENSE, evidence/LICENSE and NOTICE. LICENSE contains
the complete canonical Apache 2.0 text, preceded by the requested copyright.
NOTICE distinguishes the two vendored ACEAPEX test snapshots (MIT) from fetched
or system dependencies, names htslib MIT with its cram/ BSD exception, and selects
zstd BSD-3-Clause. Third-party source/corpus terms are preserved.

The README license footer is generated from METHOD.md. Only its reviewed digest
was updated in the publication manifest. Publication validation and page export
passed against all 420 records on main; measurement bytes and upstream snapshots
are unchanged. No builds, benchmark runs or upstream repository changes occurred.
This branch deliberately does not import the extra recovered records or adapter
changes from the draft branches. On subsequent merges, regenerate README from the
merged METHOD.md/results.jsonl and update its manifest digest, retaining this
license footer. Finish the licensing PR before resuming any adapter work.

## Owner's ordering restored — 2026-09-11

Licensing PR #18 is merged: main commit
`a5ab7e38bc1d995dc580c8f0e5e1b221f7bca8d7`.
The authoritative next order is in BENCH_TO_TOOL.md:
nine-axis acceptance, adapters, check, xz, CONTRIBUTING/citation, CRAM, tag/DOI.
Do not continue adapter work in PR #17 or add codecs ahead of the evidence gate.

The nine-axis audit of retained PR #16 content at
`1160850bda8385cc18d8960989cad15ecacd8b43` passes: 9 axes, 3 formats,
4 core configurations, 15 curve positions, 13 supported geometries.
The 31 axis/curve tests and publication validation pass. The checked files and
results are identical to those in the local PR #17 checkout; no measurements
were rerun. BGZF/zstd plateaus already exist, native batch has explicit n/a,
and BGZF's strict c(g) limitation is not fabricated into five measured points.
Main still has 420 records; the prepared 435-record publication is in PR #16.

Next bounded action: review/prepare PR #16's complete table for evidence acceptance
and main integration, preserving the license footer and regeneration integrity.
PR #18 merge authorization does not authorize merging PR #16 or PR #17. This
checkpoint is documentation only and does not publish new measurements.

## Focused c(g) baseline audit — 2026-09-11

Documentation work continues in PR #19, branch docs/nine-axis-gate, from
7499d65dfdfb54a220d4cce76132c2f1fafd43e7. The additional read-only audit and eleven
tests verify all ten supported points' commands and whole-input geometry.
ACEAPEX baseline: one LZ block covering 253935557 bytes. Zstd baseline: one
nonempty whole-input frame PLUS an empty terminal frame, not literally one
physical frame; both are included in the baseline file length. BGZF has no
strict baseline. Source hashes matched retained compiler provenance.

See review/CG_BASELINE_REVIEW.md and review/cg-baseline-check.json for the
exact scope and commands. No archive was reopened or recompressed in this
segment; existing restore receipts remain existing evidence. No changes to
raw results, codec source, README or adapter code. Next bounded action remains
preparing the reviewed PR #16 evidence for main with the license footer and
publication validation. Do not erase the zstd empty-frame qualification.

## Frame symmetry and LIT_CHUNK follow-up — 2026-09-11

PR #19 follow-up to ee3dd40c6e0a46586558f5b20d3ec12b971a5666 verifies zstd
indexed frame counts 61996/15499/3875/969/243 at 4/16/64/256/1024 KiB;
all have zero empty data frames. Baseline: two indexed frames, one empty.
Each file also has one seek-table skippable frame. Counts are retained parser
evidence, not a new zstd -l run; original archives are absent locally.
All ACEAPEX baseline/point commands unset LIT_CHUNK. In pinned ee5a37e this
selects the legacy four-part zstd level-3 path, with DNA transform OFF for
all six configurations; FSE policy remains 512 KiB. Newer changes do not
apply retroactively. Source hash matches retained compiler provenance.
Do not publish 6.57–7.18% as a c(g) interval: 6.569397% is matched seekable
c(g), while 7.180634% is the historical CLI-versus-seekable comparison.
See review/CG_BASELINE_REVIEW.md. No raw result bytes changed. Next: prepare
PR #16 publication on licensed main, keeping these distinctions.
