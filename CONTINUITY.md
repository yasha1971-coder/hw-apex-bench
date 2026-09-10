# Continuity checkpoint — publication recovery after PR #12

## Resume from here

This file records work recovered from the ChatGPT thread «Создание репозитория
GitHub». The user's screenshot stopped during recovery of the non-UTF-8
`results.jsonl` after PR #12. That failure was reproduced against the live main
branch and the exact original Actions artifact was recovered.

Recovery PR #13 is merged as `e181868f307225bea7c4c3532e0dfb1130d2ae37`.
Its publication-integrity workflow `34542759441` passed. Pages deployment
`34542832629` passed on that merge. Read
`evidence/stage5-20260910/RECOVERY.md` for artifact provenance.

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
`c8436f656002f20b16ebff9e9c96214533e3e22d` (`cg-tradeoff-five-point`), based on the failed-publication main.
It is now restored on `experiment/cg-five-point-recovered`, based on recovery
merge `e181868f307225bea7c4c3532e0dfb1130d2ae37`.
Its files include `CG_CURVE.md`, `harness/cg_curve.py`, two codec adapters,
`harness/test_cg_curve.py`, and `.github/workflows/cg-curve.yml`.
All 17 tests were rerun successfully after recovery. The existing 420-record
publication and exact report regeneration still pass. This is not evidence of
a measured curve. Check the branch's dedicated workflow and its complete
artifact before citing any new curve numbers or merging the experiment.

Grid: 4, 16, 64, 256 KiB and 1 MiB. Same-container whole-file baselines for
ACEAPEX and seekable zstd. BGZF points beyond its format limit and strict c(g)
are n/a. Each numeric point needs archive accounting and exact restore, plus
common 200-query resident-library p50/p99 measurements.

Next bounded action: run the dedicated workflow and audit its complete curve
before merging it or drawing new conclusions. A successful run creates reviewed
candidates; it must not automatically replace the publication manifest or make
unreviewed numbers live. Preserve the previous 420 rows byte-for-byte.
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
