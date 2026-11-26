[written by ChatGPT (AI) at the author's request; checked by the author]

# HW-REGION-2: binary-search reader addition

This stage implements the owner's 2026-11-26 correction. Its separate
[calibration](CALIBRATION.md) was the sole file in first commit
`633badf83a934cbbfe063a8455ffe348114e2f36`, before any new measurement.
The original completed 31-corpus/186-row experiment at
`d8a77912bade66ce03d665e3afc5cd76465dcbb5` and P1-P3 are frozen.

Foundations checked: docs/METHOD_PROGNOZ_ZADANIE.md, docs/EXTERNAL_TEXTS.md,
docs/AGENTS.md and HISTORY; original casefix protocol, execution clarification,
resume amendment, complete report and saved audit; the pinned 2bit.c on ace-core;
the original writer metadata and trace; live local/remote branch and draft PR97.
There is no separate genome binary-search task in the discovered roadmap.
The current comparison remains ACEAPEX, zstd-seekable, BGZF and equivalent .2bit;
no previous row is dropped or measured again.

## Change and attribution

Apply lib2bit-binary-search.patch to the existing casefix source, from the same
upstream pin `58e20daa898a6fc338eae82e5d2ef7108d4fc07f`. Inside softMask only,
lower_bound searches the first exclusive mask end greater than query start;
the old loop resumes at that index. Search uses an overflow-safe midpoint and
uint64_t end sum. Sorted non-overlapping positive mask runs ending within the
sequence are required and checked from the actual retained archive metadata.
All remaining source bytes, compiler flags, archive/index bytes and native query
wrapper are unchanged. Build in a separate owned directory; do not modify or
relax the qualified standalone casefix adapter.

The report label is exactly:
`lib2bit-casefix + binary search (reader change, not upstream)`.
Machine profile is `twobit_casefix_binary_mask1`, exact case-preserving semantics.
This is a reader development experiment after seeing the original results,
not an upstream release or a replacement for the registered P1-P3 row.

## Checks and fixed sequence

1. Build the new library/DSO with the same flags. Reuse the exact old worker
   binary, native.c and coordinate.h. Bind their source and binary hashes, the
   patch, the original source cohort, and the new stage source commit.
2. Untimed actual-C checks compare the linear casefix and binary-search softMask
   on deterministic mask/N/n/boundary/no-overlap cases, valid random disjoint
   runs, empty cases and uint32 limits, with guard bytes. Wrong length/content
   or invalid geometry stops the stage.
3. Untimed native worker: all frozen chr1 warmups and 1000 requests, original
   lowercase-n witness, and the unchanged synthetic mask-boundary input/trace.
   Every returned byte must equal the case-preserved FASTA. Any required error
   or difference is Kill, including on a LOADED attempt. Retain captures.
4. A/A: two independent fresh-process passes of this new reader on the unchanged
   chr1 trace. Evaluate `20 * abs(B_p50_ns - A_p50_ns) < A_p50_ns` once.
5. Boundary: reuse the existing synthetic mask control with 12 warmup pairs and
   1000 alternating AB/BA pairs, fresh handles. Crossing p50 must exceed aligned
   p50. Do not select or change control coordinates after observing time.
6. Main: one fresh process, persistent handle, unchanged chr1 archive, 12 warmups
   and 1000 requests, R=16384 case-preserved bases. Same malloc-returning native
   API inside timer; validation/capture/free outside. Open is separate n=1;
   RSS remains whole-process, not library-only. Judge only separate B1 here.

No additional T2T timing or old CLEAN run is authorized. The 30 saved T2T window
metadata and timings supply the explanatory comparison only. Count mask runs
from all windows; define typical as the exact median of their 30 counts and
also report their range. Any metadata-based loop-count replay is an operation
count, not a measured decomposition of elapsed time.

## Load admission and retention

Use the same ace-core EPYC4344P, CPU0, T=1, warm RAM/page-cache archives and
original OVH helper/thresholds. New compilation and correctness run on CPU15
without the timing lock. Blocking flock covers each actual timed pass only.
The unchanged helper binds the old casefix protocol/calibration in its receipts;
the new unit identity additionally binds this stage's calibration/protocol,
patch, sources and build. Both bindings must validate.

Admission polling and attempts use a stage-specific immutable ledger. After an
inadmissible poll or an actual LOADED attempt, wait at least 300 seconds before
polling again. Waiting polls consume no attempt. Consume a fresh passing poll
once; recheck under the shared lock. After CLEAN the next unit may poll at once.
LOADED means load1-1 > 1.0 at either boundary or surviving foreign CPU >10% in
the one-second pre-start observation. Equality passes. Inspection failure is
ERROR. Capture date -u, loadavg, nproc, CPU/kernel/governor/pin and observational
other-core /proc/stat deltas at both boundaries. Three actual LOADED attempts
per logical pass stop the stage with BLOCKED: load and foreign process names.
All attempts/polls remain saved; do not repeat a CLEAN slow result or restart
a failed clean method gate. Stop no foreign process.

Persist untimed admission, then method evidence, then the single main cell in
checkpoints. Independently audit raw byte captures, exact quantiles, source
closure and all attempt selections from saved evidence. Report the original
P1 HIT / P2 MISS / P3 HIT (30/30) unchanged beside separate B1. Keep PR97 draft;
no upstream message or merge. If README/snapshots gain numbers, use a dated
numerical row and an adjacent T2T-window row; retain every old snapshot.
