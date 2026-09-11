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

## Adaptive default follow-up — 2026-09-11

User requested remeasurement at ACEAPEX
`a194893b676a089e5916063d62c45e77483d2c10`, with default beside profiles.
Draft PR #15 (`experiment/default-a194893`) is stacked on draft PR #14
(`experiment/cg-five-point-recovered`); neither has been merged.
Successful measurement commit: `d25d8d16f45a073f167bfb2082f663a909a48ea1`.
Workflow `34574867600` passed, artifact `10189247671`; exact checksums are in
`evidence/default-a194893/receipt.json`. Six complete byte-verified restores,
1000 verified timed region samples; report replays exactly from committed JSONL.
Run `python3 harness/audit_default.py evidence/default-a194893 DEFAULT_RESULTS.md`.

The new default on chr1 has 65536-byte literal chunks, complete-archive ratio
3.7313812953, resident-region p50 2.724145 ms. Explicit LIT_CHUNK=0 has ratio
3.2075509070 and fine-grained region n/a. This matched ratio increase is 16.33%,
not a forced reproduction of the owner's separately reported +17.1%.
All ACEAPEX configurations lose this single-region latency comparison to both
baselines. Text and Silesia remain unmeasured here. No plateau throughput claim.

Attempt `34574475551` failed at interactive restore: this Makefile CLI ignores
--profile and the harness supplied mismatched FSE settings at decode. The harness
was corrected to set explicit matching profile environments for encode and read,
with actual archive geometry checked. This is not a codec failure under matched
settings. The failed artifact is `10189096192`.

Historical curve workflow `34543023595`, source
`d84f38af3b26d830fbc1cc654174f2bd673178ab`, artifact `10178051601` completed.
Its 62.379022 ms observation remains attached to old SHA/configuration; it is
not a full-decode measurement or a new-default row. The independent measurement
exposed the default configuration problem, according to the owner's subsequent
reproduction and correction. Preserve this attribution for Paper 6.
Curve audit / 435-row combined snapshot and deterministic rendering fix remain
in a separate local curve checkout; their upload was interrupted. PR #14's
remote head remains d84f38a at this checkpoint. Its raw artifact was separately
preserved. Do not claim the combined snapshot has been published.

Publication still contains the original verified 420 rows. Next bounded action:
review the complete new default table and audit, then integrate accepted evidence
with the pending curve report and publication validator. No unreviewed merge or
cross-machine speedup claim. No upstream codec repositories were changed.

## Interrupted table upload recovery — 2026-09-11

Live GitHub verification found PR #15 still at
`d25d8d16f45a073f167bfb2082f663a909a48ea1`: the table upload had not arrived.
Recovered the six-file evidence commit `021a0261cbe85100c936d50882328f9136a3f685`
onto that exact remote parent. The artifact ZIP digest matches GitHub, and the
retained JSONL and DEFAULT_RESULTS.md match its bytes exactly. The default audit,
420-row publication validator and homepage build passed without codec execution.

This recovery commit uses `[skip ci]` because the user explicitly prohibited new
measurements. Do not dispatch or rerun benchmark workflows while completing this
handoff. Keep PR #15 draft and stacked on draft PR #14; main remains recovery
merge `e181868f307225bea7c4c3532e0dfb1130d2ae37` at this checkpoint.

PR #14's verified remote head is still
`d84f38af3b26d830fbc1cc654174f2bd673178ab`. Its pending curve evidence exists in
the separate local curve checkout at `419cfbe`; it is not part of this upload.
Next bounded action: show DEFAULT_RESULTS.md for review, then recover and audit
the existing curve report before any integration. Do not repeat measurements.

## Instrument roadmap, first gate — 2026-09-11

The owner supplied a seven-step instrument roadmap. Work is staged as requested;
the current branch `tooling/nine-axis-contract` is the first gate, based on PR #15
head `2a80299c6daba988b449d61ff9cdad3dc59ad98f`. PR #13 is merged; PR #14 and #15
remain drafts. `TOOL_ROADMAP.md` preserves the remaining implementation sequence.

Recovered the audited curve snapshot from local commit
`419cfbe5ea63bdc4db68a9e28149e6deb5d57f93` into this review branch. Its full 435-row
JSONL matches artifact `10178051601` exactly, including the original 420-row byte
prefix. `harness/audit_curve.py` independently checks all 2,600 timed samples.
The original core run already reached all eight encode/full-decode plateaus,
including bgzip and zstd. No new benchmark or codec execution was needed.

The generated README now defines nine axes; `AXES_RESULTS.md` and
`./run.sh --audit-axes` validate their coverage. Reports generate native-batch
unavailability from retained capability/reason fields. Blank/unexplained table
cells fail publication. Plateau checks recompute sample CV, rates and summary
evidence; same-run ratios reject mixed hardware or a fabricated PASS.

The old zstd CLI-versus-seekable 7.180634% is still retained in raw JSONL and the
operational comparison column, but no longer displayed as strict same-container
c(g). The recovered matched series gives 6.569397% at 16 KiB. All raw values are
unchanged. Historical ee5a37e default, 1b13df3 profiles and a194893 refresh remain
separate; do not combine their axes into a fictitious configuration.

Validation commands (no measurements):
`python3 -m unittest discover -s harness -p test_axes.py`,
`python3 -m unittest discover -s harness -p test_cg_curve.py`,
`python3 -m unittest discover -s web -p test_publication.py`,
`./run.sh --audit-axes`,
`python3 harness/audit_default.py evidence/default-a194893 DEFAULT_RESULTS.md`,
`python3 web/validate_publication.py`,
`python3 web/build.py /tmp/cabench-pages/index.html`.

Next bounded action: implement the adapter/native-callback contract and `--check`
for the existing three formats, then replace automatic full PR benchmarks with
small correctness CI. Shell process invocation cannot be the timed region path.
No xz or CRAM adapter, licensing change, v0.1 tag or DOI has been claimed here.
CRAM needs an alignment-specific lossless/operation contract; default quality
quantization is not assumed. Same-run normalization is not machine invariance.
Keep this first-gate report in draft for curve review; use `[skip ci]` on its
evidence upload so existing full benchmark workflows are not re-executed.

Delivery checkpoint: draft PR #16
`https://github.com/yasha1971-coder/hw-apex-bench/pull/16` contains the first-gate
implementation at `14f052409066f072fe84546620b6bc4a76cb6c54` (validated Git tree
`2bdc1d6b857f0bae7e8c86c059bacd5bc20f0983`), stacked on PR #15. All 37 local tests
passed; executable homepage JavaScript syntax also passed. The small final
handoff commit only adds this delivery checkpoint. PR #14's remote head remained
`d84f38af3b26d830fbc1cc654174f2bd673178ab`; the recovered curve is delivered in
PR #16, not falsely attributed to an update of PR #14. Adapter extraction is the
next stage, not a completed feature.

## Adapter qualification checkpoint — 2026-09-11

Branch `tooling/adapter-contract` is based on PR #16 commit
`1160850bda8385cc18d8960989cad15ecacd8b43`. It adds a single-file shell adapter
contract plus a versioned native callback ABI and `./run.sh --check PATH`.
Three existing codecs passed byte-exact qualification: BGZF and zstd each have
five cases/1040 regional checks; ACEAPEX has four cases/832 regional checks and
native batch checks. Qualification receipts are in `evidence/adapter-qualification`.
An external renamed zstd adapter in `/tmp/external-adapter.sh` also passed without
core edits. BGZF passed again from the initially empty `/tmp/cabench-clean-adapter`
build directory, downloading all pinned dependencies and the MD5-checked corpus.
Eight adapter tests and all previous 37 publication/curve/axes tests passed.
README was regenerated from unchanged results.jsonl and METHOD.md; publication
validation and site export passed. The measurement SHA256 remains
`cb52b8cb9fac484a6474d976681ea85ae2c052d80d820422b7f57c25ec938100`.

Runtime diagnosis `python3 harness/probe_aceapex_geometry.py` confirms that the
pinned a194893 one-shot encoder puts block_size=1048576 into the header while
ACEAPEX_BS=16384 creates 17 blocks for 262400 bytes. The adapter uses the original
CLI only for untimed archive preparation; native encode has an explicit n/a reason.
Empty input is explicitly unsupported by this upstream path. Native amplification
counters remain unported and unavailable in all new adapters. Full ACEAPEX decode
uses eight internal workers, native batch requests one; no equal-thread speed
claim is made. HTSlib 1.24 is a new qualification dependency, not a replacement for
historical measured versions. No upstream tracked sources were changed.

Automatic full stage1, audit, curve and default-refresh PR triggers were removed.
Only small adapter correctness and publication checks are automatic; no full
measurements were dispatched. Keep changes in a draft PR stacked on PR #16.
The next bounded action is integrating measurement scheduling and normalization
with the native ABI while preserving plateau, instrumentation and thread-policy
gates. Historical measurement scheduling still contains codec-specific logic;
therefore the full benchmark is not yet universally extensible. Do not add xz or
CRAM before that integration, and do not describe qualification as measured axes.
See ADAPTERS.md and TOOL_ROADMAP.md for explicit scope and limitations.
