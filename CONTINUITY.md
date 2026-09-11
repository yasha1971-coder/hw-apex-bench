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

## Negative c(g) publication note — 2026-09-11

PR #19 merged into main as 278b04ba8aef62c5e2c147e69b1c0627159047c8.
The owner's requested negative-c(g) note is prepared on docs/negative-cg-note.
It is generated into README through METHOD.md, before the existing license
footer. It reports the reviewed zstd 1 MiB value -0.509942% and the exact file
lengths 78013034 vs 78410855 bytes. The original results remain unchanged.

Local entropy adaptation is identified as a possible mechanism, not a causal
finding: this run did not isolate it, and RFC 8878 section 3.1.1.3 permits
new entropy tables inside a frame already. No claim of literature-wide novelty
or universally costly splitting is made. The empty baseline frame is still
counted. The README digest was refreshed after regeneration; publication
validation and page export passed against the 420 rows currently in main.

No codec or benchmark was run. The full 435-row evidence publication from
PR #16 remains a separate next bounded step; adapter work stays paused.

## Retained PR #16 preparation history

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

## Nine-axis publication integration — 2026-09-11

The owner authorized merging PR #20 and publishing PR #16 on main before any
adapter work. PR #20 merged as 3dab71573fad34a30a01734b85aa48c41359fa98.
This integration joins that main revision with PR #16's reviewed head
1160850bda8385cc18d8960989cad15ecacd8b43. README, METHOD and report generation
retain Apache/CC BY licensing, the negative-c(g) note and both follow-up reviews.
The c(g) renderer now explicitly preserves the empty zstd baseline frame and
states that the pinned ACEAPEX legacy literal path has DNA transform OFF.

All 435 original results remain byte-identical:
cb52b8cb9fac484a6474d976681ea85ae2c052d80d820422b7f57c25ec938100.
Publication validation/export, nine-axis audit, default replay (six rows and
1000 samples), matched-baseline audit and all 48 tests passed locally. Only
reviewed README/curve-report digests were changed; source evidence is untouched.
Full stage1/audit/cg/default/strict-cg workflows are manual-only so this update
cannot launch completed measurements again. Publication CI includes the eleven
focused baseline-review tests. No adapter code is imported from PR #17.

After the PR #16 integration commit passes CI and is merged to main, nine-axis
publication is the completed gate: 3 formats, 4 core configurations, 15 curve
positions with 13 supported geometries, and explicit n/a for unsupported axes.
The next bounded step is reconciling the seven-function adapter interface in
PR #17 with published main. Do not overwrite published reports or licenses with
that older branch's files. No new measurements, xz, CRAM or release are part of
this publication segment. Read current main/PR/Pages status at the next turn.

## Publication completed — authoritative next-step checkpoint

PR #20 is merged: 3dab71573fad34a30a01734b85aa48c41359fa98.
PR #16 is merged into main: 3cb19d2fd3d4fc9ccf3dcb14bda281da7153f538.
Its tested integration head is 42834db372d90946d06e7c457c2dbec57d960adf;
publication CI 34594754058 passed with all 48 tests and read-only audits.
Pages deployment 34594849190 passed on the merge commit. The live homepage
https://yasha1971-coder.github.io/hw-apex-bench/ was fetched successfully and
its embedded results_sha256 matches the reviewed 435-row snapshot:
cb52b8cb9fac484a6474d976681ea85ae2c052d80d820422b7f57c25ec938100.

The first gate is now complete in main: nine axes accounted for on three formats,
including explicit unsupported positions; no new measurements were executed.
Licenses, negative-c(g) note and source/empty-frame qualifications are published.
This final checkpoint changes documentation only, not the tested publication.

Next bounded task: inspect published main and reconcile the seven-function
adapter contract with draft PR #17. Do not blindly merge the draft: its README,
workflow and provenance state precede the publication. Preserve raw result bytes,
license footer and matched-baseline semantics. Do not add xz or CRAM yet. Do not
repeat the completed full benchmarks or alter the three protected repositories.

## Native extraction first — 2026-09-11

The owner requires extracting working code before fixing the adapter contract.
Branch refactor/native-codec-extraction starts at published main
0e8246f8b14b74191b3bf8cc6f14b71be85779ce. Existing three codecs/*.sh already
contain CLI operations and are unchanged. Sixteen native sections are copied
from region_latency.c, codec_io.h and batch.c into three harness/native/*.inc
files. This is a transitional mechanical layout, not an invented plugin ABI.

The extraction verifier reconstructs all three original source files exactly
and verifies all 435 result records unchanged. Five rejection/equivalence tests
pass. Five before/after GCC -O3 assembly outputs are byte-identical, including
COUNT_DECODER; no executable or performance measurement was run. See
CODEC_EXTRACTION.md, the section manifest and assembly receipt for scope and
header versions. Generated README/reports, licenses and manifest remain exact.
Publication CI now checks the mechanical move against the pinned base commit.

Next bounded action: review the moved implementations side by side and derive
capabilities from existing n/a evidence; then choose the actual native interface.
Dispatch, counter selection and shared state are still in core, so adapter
extraction is not declared complete. Do not merge old PR #17 over published main,
do not add xz before the real interface/check gate, and do not rerun full timings.

## Resident context / fourth-codec proof — 2026-09-11

User changed the next-stage order: derive operations/capabilities from the three
working codecs, exercise xz immediately, then generic --check. This supersedes
the earlier prohibition on xz before --check. PR #21 remains draft/unmerged at
c82c96fcd9e9d60717ad601c991ec6f2251eff85; live main remains 0e8246f8b14b74191b3bf8cc6f14b71be85779ce.
New branch tooling/resident-context-proof is based on that exact PR #21 head.

Common experimental C operations: open resident archive, region, full decode,
close, ABI/version. No codec headers or name switches in the shared header/probe.
Three existing API calls are wrapped in codecs/native/*.c; ACE retains per-call
header parsing and the published 1b13 source. The old three shell CLI dispatchers
and all historical measurement sources remain unchanged. codec_supports and
codec_unavailable describe the NEW context proof path only; decode/region are
implemented, all remaining axes carry explicit reasons. They do not replace the
historical published capability/results state. See RESIDENT_CONTEXT.md.

Fourth codec xz uses --block-size, a Footer-located resident Index, native block
lookup/decode and cross-block assembly. One Stream/no padding is the initial
supported scope; concatenation/padding are explicitly rejected. It required no
codec-specific branch in the shared interface or generic probe. No ACE table
caching, full timing runs, new c(g) values, CRAM, tag or main merge occurred.

Local qualification: four byte-exact full restores, 1248 valid region queries,
12 invalid ranges rejected, destination guards intact. Six additional unittest
methods cover five XZ geometries plus one-block baseline, empty/one-byte/exact
block data, corrupt metadata/blocks, resident lifetime and two independent
contexts. An initial test parsed xz robot column 8 (ratio) instead of 7 (raw size);
fixed against actual robot output; the complete suite then passed. All existing
53 tests also pass; the 16-section reconstruction and 435-record byte comparison
pass. Publication validator and Pages export pass. Proof receipt with commands,
versions and hashes: review/resident-context-proof.json. XZ links system liblzma
5.4.5 with pinned 5.4.5 API headers; HTSlib is 1.24, explicitly not a historical
measurement-library qualification. New CI only tests XZ native correctness and
all-four capability reasons; it does NOT claim an all-four clean dependency build.

Next bounded action after reviewing this proof: finish the common shell build/
compress/decompress/region contract and generic --check with pinned dependency
preparation and all-four CI. Then connect capability-driven measurement planning,
batch/counters/block mapping and results output. The Python ctypes probe must
never be used as a performance timer. The final timing ABI is not frozen yet.
Do not merge PR #17 or overwrite measured evidence; do not optimize ACE parsing.

Resident-context proof saved as draft PR #22:
https://github.com/yasha1971-coder/hw-apex-bench/pull/22
Base refactor/native-codec-extraction (PR #21); code head
6074adf7763794a75689f5a3c79ad682963c3762.
GitHub CI completed successfully on that head: publication integrity
34602915976; resident XZ correctness 34602916028. The latter ran all six new
unittest methods on ubuntu-24.04 after fetching pinned API headers. This final
checkpoint only records those live outcomes; it changes no tested code/data.
Neither PR #21 nor PR #22 has been merged. Preserve the stacked review order.

## Runnable seven-function contract and --check — 2026-09-11

Branch tooling/adapter-check starts at PR #22 checkpoint
c7e2bafa88185baee19e50290e9cf8b64323e38b. PR #21/#22 remain draft/unmerged;
main was checked live and remains 0e8246f8b14b74191b3bf8cc6f14b71be85779ce.

Four shell adapters implement name/version/build/compress/decompress/region/
supports, plus adapter-owned unavailable reasons and constraints. The generic
./run.sh --check [codecs/NAME.sh] builds pinned sources and checks small fixtures;
without the adapter argument it discovers all codecs/*.sh. Native ABI 2 derives
size from the archive; optional expected size is a validation input, not required
for region access. ACEAPEX retains its original per-call API/header parsing.
XZ CLI and static PIC liblzma now come from one pinned 5.4.5 source build in --check.
No protected upstream repository was changed. Local CMake 3.31.6 was installed
only into scratch build tools; user/CI prerequisites are documented in ADAPTERS.md.

Local fresh builds passed: BGZF five restores/422 native regions; zstd five/614;
ACEAPEX four/613 plus explicit empty-input exclusion; XZ five/614. Total 19
full restores and 2263 valid native ranges, plus guarded out-of-bounds cases and
shell native-region verification. Five checker tests cover an external CLI-only
adapter without a native library, bad restoration, missing function, empty n/a
reason and overlapping checks. Six XZ tests and the 53 existing tests also pass.
The generic core contains no codec-name dispatch/dependency recipe. A check never
writes results.jsonl or starts timing. Failed checks cannot leave a stale success
receipt; a directory lock and subprocess-group timeout handle interrupted runs.

README's short --check entry was generated from METHOD.md; only its corresponding
publication digest was updated. All 435 records and other generated reports are
byte-identical. Publication validation/export and original source reconstruction
pass; the license remains the final generated README section. New matrix CI
builds all four adapters on separate clean runners and retains receipts/logs.

Next bounded action: verify matrix CI on the saved PR, then integrate successful
check receipts and codec_supports into measurement scheduling/result formatting.
Do not claim that seven shell functions finish migration of the nine axes: batch,
counters, block mapping, controlled c(g), other ACE configurations and the C timing
runner are not connected to the new contract yet. Existing historical CLI paths
are retained. No new performance numbers, main merges, CRAM or release in this step.

PR #23 saved: https://github.com/yasha1971-coder/hw-apex-bench/pull/23
Base tooling/resident-context-proof (#22); code head
b6dfdaaccfc16617809a433f4d6cee2eacbb0d89. All GitHub CI passed on this head:
34604937509 (four clean codec builds), 34604937464 (publication integrity),
34604937426 (native XZ correctness). Downloaded all four matrix artifacts and
verified their ZIP SHA-256 against GitHub metadata, then inspected each check.json.
Live receipts confirm the same 19 restores / 2263 regions and actual versions:
HTSlib 1.24, zstd 1.5.7, ACEAPEX 1b13, XZ 5.4.5. Persistent receipt summaries and
artifact digests are in review/adapter-check-ci.json. Artifact IDs:
10265269430 bgzip; 10265784165 zstd; 10265714129 ACE; 10265654129 XZ.
This final checkpoint changes only documentation/receipt summaries, not tested
code or publication. PR #21/#22/#23 are still draft; no merge was performed.
The check gate is complete for these four adapters. Next is measurement planning
and output integration, with no rerun of the completed published measurements.

## Capability planning and current-check eligibility — 2026-09-11

Branch tooling/axis-planner starts at PR #23 checkpoint
216f9ad47556c903227c9b1cff3b3e6ba2db1ea1. PR #23 was checked live: draft,
unmerged; main remains 0e8246f8b14b74191b3bf8cc6f14b71be85779ce.

New ./run.sh --plan [--codec NAME_OR_PATH] [--axis AXIS] produces a separate
*.plan.json, never measurements. All selection/capability decisions come from
the supplied adapter; no codec-name table in the planner. Current real four-codec
plan has 36 positions: eight eligible decode/region tasks and 28 n/a tasks with
adapter-owned reasons. These are new-path migration limits, not retractions of
historical nine-axis results. No native performance backend is connected here.
Internal dispatch_adapter revalidates the plan, preflights all handlers, skips
unsupported axes, holds the build lock and rejects results if checked state changes.
Missing backend is a blocking implementation error, never codec n/a.

--check now writes protocol cabench-check-v2: snapshots of adapter/declared
companion/shared correctness code, CLI/native binaries, resolved shared libraries,
dependency commits/cleanliness, name/version/capabilities/configuration, constraints,
architecture and selected loader environment. It compares before/after tests.
Planning rejects missing, old, failed, stale or incomplete receipts. Adapters now
provide codec_inputs, codec_build_artifacts and codec_configuration. Old CI receipts
remain historical evidence and are not upgraded by editing them. This is local
unsigned verification of declared inputs, not a portable attestation.

Refreshed all four small checks locally (no performance timings); again 19 full
restores and 2263 valid native regions. Planning against those real receipts passed.
Fourteen new planner tests cover n/a provenance, handler dispatch, stale adapter,
helper, binary or configuration, old/failed/incomplete receipts, tampered plans,
active checks, unknown axes, missing backends and mutation during dispatch.
Existing checker five tests, XZ six tests, native extraction five tests and
publication validation/export pass; original 435 records and published documents
are unchanged. Matrix CI now also creates plans from each freshly built receipt.

Next bounded action: verify this PR's CI and plan artifacts, then connect actual
native measurement implementations and validated output to the dispatch seam.
Do not describe the planner/test handlers as a completed measurement migration.
Do not rerun full benchmarks, alter ACE header parsing, merge drafts without the
owner's authorization, or add CRAM/release work to this segment.

PR #24 saved: https://github.com/yasha1971-coder/hw-apex-bench/pull/24
Base tooling/adapter-check (#23); code head c36b79dfab7879e5f56bdf85b9bea137f2c9aa6b.
All CI passed: 34610793725 all-four check/plan matrix, 34610793549 publication
integrity, 34610793562 native XZ. Downloaded and verified all four ZIP digests and
cross-checked plan receipt hashes, qualification fingerprints and every n/a reason
against the embedded check.json. Artifacts: 10269055027 zstd, 10269040019 ACE,
10268965174 XZ, 10268940301 BGZF. Persistent summary: review/axis-planner-ci.json.
Thirty-six plan positions verified (eight eligible, twenty-eight explicit n/a).
This checkpoint only records CI evidence; tested source and publication are unchanged.
PRs #21/#22/#23/#24 remain draft, unmerged. Next step is actual native backend
integration; no claim that dispatch tests are real measurements or release readiness.

## Native execution first connected axes — 2026-09-11

Branch tooling/native-axis-execution starts at PR #24 checkpoint
cd8ffe070d80860872edbca1daa5536c0b76d21a. PR #24 checked live: draft, unmerged.
The latest owner instruction authorizes a full comparison run AFTER all nine axes
are connected and small checks pass. This supersedes the older no-full-run rule
only at that gate. Do not launch the historical workflow as a substitute: it
rewrites results.jsonl and cannot prove the new dispatch path works.

Implemented --measure with a codec-independent dlopen C worker. Region keeps the
historical 12 warmups, LCG/seed, 200 x 16 KiB queries; decode one warmup/five samples.
Archive/index setup, I/O, process startup, Python, verification and serialization
are outside timing. ABI-2 callbacks retain per-call ACE header parsing. Callback
bounds/dispatch overhead is included and explicitly distinguished from the older
directly linked worker. No upstream source or existing native extraction changed.

Connected ratio (archive plus every mandatory artifact, CLI byte-exact restore),
native region/full-decode samples, and break-even (same-run cached samples,
floor(full median / region p50)+1). Each adapter now advertises these four axes.
One input size is data_edge, never a plateau headline. --measure requires a new
output directory, a current check receipt, and writes manifest.json only after
all selected handlers, bytes, hashes and state validate. Failed candidates retain
logs without a success manifest. Timeouts/interruption kill the process group.
The cabench-native-samples-v1 artifact is explicitly unpublished, not results.jsonl.

All four fresh local --checks passed: 19 restores / 2263 native regions. A separate
349571-byte native integration run passed four codecs x four connected axes:
800 timed regions, 20 timed full decodes, four verified ratios; break-even reuses
the same raw samples. These are small integration timings, not performance claims.
Five new tests cover an independently compiled identity native codec, exact query
sequence, corrupted bytes/guards, incomplete samples, repeat validation, and an
external CLI-only ratio codec whose mandatory index is included without a library.
Checker/planner tests and publication integrity/extraction checks pass. The existing
435 rows remain byte-identical with SHA256
cb52b8cb9fac484a6474d976681ea85ae2c052d80d820422b7f57c25ec938100.
CI now exercises this small real dispatcher after clean builds of all four codecs,
retaining manifest/raw samples/logs; it does not run the full performance suite.

NOT COMPLETE: remaining throughput plateau/CLI encode backend, decoder counters,
block mapping/H_alpha, native batch, controlled c(g), additional historical
configurations and final publication serialization/same-run baseline comparison.
The published 435 are 409 main-run rows +15 c(g) +11 owner-declared GPU rows across
separate scopes. Core ACE is 1b13 interactive/dense; strict c(g) uses ee5 default;
current check HTSlib1.24 differs from the historical build. Fresh timing bytes
cannot equal old wall-clock values. Require exact historical artifact replay and
matched-method/configuration comparison, without copying old values into a new run.
Next bounded action: check this native integration CI/artifacts, then connect the
plateau runner while preserving published encode CLI wall-clock boundaries (do not
substitute the ACE compression API, whose old geometry differs from the CLI).

PR #25 saved: https://github.com/yasha1971-coder/hw-apex-bench/pull/25
Base tooling/axis-planner (#24). Final tested code:
a612d132b5b558ca66a64b345df7a736d6565631 (tree
f1369e35d3809786f847a87ae4b950d2b735e032).
All CI passed: 34614784390 all-four clean builds/checks/native dispatch,
34614784393 publication integrity, 34614784397 native XZ correctness.
Downloaded all four ZIPs, verified GitHub SHA-256, manifest-to-check receipt links,
raw sample digests/workload/counts/percentiles, ratio accounting and break-even
reuse. IDs: 10269363204 BGZF, 10269248394 zstd, 10269738189 ACE, 10269983119 XZ.
Receipt summaries: review/native-dispatch-ci.json; repeatable ZIP audit:
review/verify_native_artifact.py ZIP EXPECTED_SHA256.
The final code accepts all nine axis names: unsupported selections emit exactly
the adapter reason without archive creation; tested with BGZF batch as well as an
external fixture. This is not a claim that all nine have measurement backends.

Live inspection of the actual published row confirms htslib/bgzip 1.19, versus
current correctness adapter 1.24. This must be reconciled before a matched-version
full comparison. Do not silently treat those configurations as byte-identical.
No full benchmark, publication rewrite or draft merge occurred. This checkpoint
adds only evidence/audit documentation; it does not change tested measurement code.
