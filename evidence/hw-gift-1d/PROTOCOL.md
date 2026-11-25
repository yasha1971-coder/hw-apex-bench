# HW-GIFT-1d execution and decision protocol

This resolves execution details before timing; CALIBRATION.md is unchanged.
Its first, single-file commit is `2d02a8b466ab1d1a07a4c604e17775bb60d7162d`.

## Foundations and decision

Read: docs/AGENTS.md, docs/HISTORY.md, docs/TOOL_ROADMAP.md,
docs/METHOD_PROGNOZ_ZADANIE.md, HW-GIFT-1c RESULTS.md, SOURCE_PATHS.md,
TIMING_PROTOCOL.md and native instrument. No closed avenue forbids this task;
the historical roadmap has no competing tiny-frame experiment. Live main is
`52018a3951b0815713eb0bc291c800bca6629d80`, after merged PRs #91 and #92.
The consumer is the hw-apex-bench owner preparing a factual, unsent zstd issue;
the decision is whether a simple frame-size condition preserves tiny-frame
ingestion speed and avoids larger-frame size loss. The alternative is the
existing unconditional hint, introduced for tiny-frame speed in zstd PR #3544.
The model and its numeric P1/P2/P3/Kill predictions are the unchanged calibration.

## Frozen experimental scope

zstd is the same clean pinned 1.5.7 source and static library as HW-GIFT-1c.
Two private writer copies differ only at the srcSizeHint argument: frame size
versus zero. Both retain seek-table checksums, so complete archive sizes compare
the same format. Shared instrumentation accessors, if any, are identical.
Native resident input/output, one thread on ace-core CPU 0. Fresh contexts are
created and initialized before each timed native encode. Buffers are allocated
and prefaulted before timing; codec internal lazy allocation remains inside.
Hashing, full byte restore, disk access and context telemetry stay outside.
No warmups. Five original/nohint pairs per cell, in A B A B order. The starting
variant reverses on alternating cells (A B / B A), fixed by cell index, never
chosen from outcomes. Report each variant's median and minimum compression ns.
One full-decode observation per variant/cell, on pair 0, has no ranking claim.
Every produced archive, including each timed repetition, restores bit for bit.
Archives remain in the experiment's .work directory; committed manifests bind
their exact SHA, size, source SHA and checks. Raw attempts/receipts are committed.

Grid order is level 3, 10, 19, each frame ascending 256, 1024, 4096, 16384,
65536, 262144, 524288 bytes. The two smallest frames use exactly the first
16,777,216 bytes; other cells use the full named corpus. This mixed input scope
is explicit in every table and is not treated as a size-independent curve.

## Method checks and mechanical exclusions

Before the main grid: reproduce both complete enwik8 L3/256 KiB C archive SHA
values from 1c; repeat a deterministic positive encoding; distinguish changed
input and reject corrupt magic; verify all restorations. Check the load gate
with known synthetic boundary cases 1.00, 2.00 (CLEAN) and 2.01 (LOADED), and
test observational CPU deltas without using them for admission. Then five
same-writer A/A timed pairs at enwik8 L3/256 KiB: abs(median(second)/median(first)
- 1) must be strictly below 0.05. This is a declared method gate, not a reason
to discard slow grid results. Failure stops before the main grid; no selective
retry based on timing. All method attempts are retained.

Each timed pair uses the existing blocking external
`flock /run/lock/ovh-bench.lock` helper. Record literal date -u, /proc/loadavg,
nproc, CPU/kernel/governor/affinity, other processes and raw /proc/stat at both
boundaries; attach other-core counter deltas to both boundaries as observations.
Only load1 > 2.0 at either boundary makes a successful pair LOADED. Retake that
pair alone immediately, same input/order, at most three attempts; retain all.
Three LOADED attempts stop BLOCKED: load with ps top eight. Byte/worker failures
are ERROR and stop, even if loaded. CLEAN observations are never retimed for
outliers. Resume verifies saved hashes and reuses finished pairs. Build outside
the lock. Push a checkpoint per cell, and method/selection stages separately.

## Training, development freeze and confirmation

First collect only enwik8's 21 cells. Do not inspect silesia timing/size results
before committing the choice. Candidate X values are 1024, 4096, 16384, 65536
bytes, the measured possibilities in P3's preregistered interval. Select the
smallest candidate for which every measured enwik8 level and G >= X has
median(nohint ns)/median(original ns) <= 1.10. This maximizes the no-hint region
under the declared speed constraint. If none passes, record NO SUPPORTED X;
do not invent a threshold outside the interval or silently drop level 19.
For P3 the conditional archive at G >= X must equal nohint byte for byte,
which is stronger than its <=0.05% size allowance. Below X it must equal the
original byte for byte. No claim that nohint is always worse below X is implied.

Record chosen X, its training facts, a new numeric prediction for the conditional
implementation, and the one-line patch in a separate development commit before
building/timing it or opening silesia results. Confirm P3 on all 21 silesia cells
without adjusting X. Verify the actual conditional writer on all enwik8 cells in five interleaved
original/conditional pairs after the freeze. On silesia collect five interleaved
original/nohint/conditional triples per cell, rotating the starting variant by
repeat index. This compares conditional directly against original under the same
conditions. Require conditional/original median <=1.10 in every cell, exact
conditional archive equality with the selected original/nohint archive and a
bit-perfect restore. Report development A/B, post-freeze enwik8 A/C and holdout
A/B/C phases separately, including min and one decode per variant/cell/phase;
never pool their repetitions. No silesia measurements precede the X freeze.
If no X is supported, skip conditional development as inapplicable and report
the honest trade-off; do not fabricate a conditional pass.

## Literal verdicts

Compare integer ns and byte counts before display rounding (ratio of medians, not median of pair ratios). P1 is ratio >=3
at the specified prefix/cell. P2 is checked at every corpus, L3/L10, G >=65536:
0.90 <= median(nohint)/median(original) <=1.10 and nohint bytes <=original.
P3 needs a selected X, all training/holdout speed bounds, actual conditional
byte equality and its separate implementation check. Missing cells mean
INCOMPLETE, not PASS. Kill is literal: enwik8 G65536 L3 nohint/original >=1.10;
a trigger on either corpus counts. If triggered, frame the issue as a trade-off
even if another threshold looks attractive. Report P1/P2/P3 HIT/MISS separately;
do not rewrite predictions after seeing data. A failure on holdout cannot be
repaired by selecting another X in this experiment.

The evidence supports only this measured host, pinned core, library/input paths
and RAM-resident operation. A second corpus is confirmation, not a second
machine or a universal law. An independent controller recalculates raw receipts,
hash bindings, medians, gate decisions and threshold selection before the final
issue draft. PR stays draft. Nothing is sent to zstd; no merge is performed.
