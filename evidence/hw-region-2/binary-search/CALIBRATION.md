[written by ChatGPT (AI) at the author's request; checked by the author]

# HW-REGION-2: separate chr1 binary-search reader experiment

Owner-authorized addition, 2026-11-26, after complete casefix head
`d8a77912bade66ce03d665e3afc5cd76465dcbb5`. This file is committed alone before
any new measurement. The original CALIBRATION, its P1-P3, thresholds and verdicts
remain unchanged; they use the original casefix row only.

Consumer and decision: Yakov / hw-apex-bench needs to distinguish the cost of
lib2bit's mask-table lookup from the .2bit representation before interpreting
chr1 versus short T2T windows. Add one explicitly non-upstream reader row for
chr1; do not replace the registered comparison or tune the other readers.

Known before this experiment: chr1 casefix/storeMasked=1 p50=88965 ns;
original/storeMasked=0 p50=6823 ns, returning case-folded, non-equivalent bytes.
Saved metadata has 331893 mask runs on chr1; the 30 T2T windows have median
8509.5, minimum34 and maximum15137. The pinned softMask loop starts at index0
and skips ended runs until it reaches the query; the exact number visited
depends on query position. Counts alone do not prove its timing contribution.

Hypothesis B1 (80%): keeping the same archive and case-preserving output, a
lower_bound search for the first mask block whose exclusive end exceeds start
removes the dominant chr1 scan cost. Forecast: new chr1 p50 <= 0.25 times the
saved casefix p50 (4 * new_p50_ns <= 88965), judged on integer nanoseconds.
This is a separate forecast, not P1, P2 or P3. If false, record MISS and retain
the clean result; never retry or revise the threshold because of elapsed time.

Change only softMask's initial lookup relative to the authorized one-line
casefix, at the same lib2bit commit58e20daa898a6fc338eae82e5d2ef7108d4fc07f.
All subsequent clipping/lowercasing, allocation, N restoration and public API
remain unchanged. Validate sorted, disjoint, positive mask intervals outside
the timer; compute search ends in uint64_t. Leave the known EOF limitation
unpatched and keep every frozen chr1 start.

Before any timer: commit patch and execution sources, qualify actual C search
against the linear casefix on synthetic boundary/N/n/range cases, then require
byte equality against FASTA at every frozen chr1 12+1000 start and the retained
lowercase-n witness, plus the previous synthetic boundary control. Any required
failure or byte mismatch is Kill: stop, retain it, publish no new timing row.

Same host ace-core EPYC4344P, CPU0, one timed thread, archive/index warm in RAM;
reuse unchanged worker/native wrapper, compiler flags, archive, reference and
trace. Builds/correctness use CPU15. Two fresh-process A/A passes of the new
reader must satisfy strict abs(B-A)/A < 0.05. The unchanged synthetic mask
boundary control must satisfy crossing median > aligned median. A clean method
failure stops this extension without a time-based retry. Then measure one
new main chr1 cell (12 warmups +1000 requests, persistent handle), same query,
open and whole-process RSS scope. No old CLEAN cell or T2T timing is repeated.

Only timing holds blocking flock /run/lock/ovh-bench.lock. Retain date -u,
/proc/loadavg, nproc, CPU, kernel, governor, pin and other-core /proc/stat delta
at boundaries. LOADED if load1-1 >1.0 at either boundary or a surviving foreign
process exceeds10% of one CPU in the one-second pre-start observation. Inspect
all live processes; inspection errors are errors. While inadmissible, wait
at least300s before another poll. A passing poll is consumed once, then the
unchanged lock helper rechecks. A LOADED unit alone gets the same seed/offsets,
at most3 actual attempts; all are retained and excluded. After LOADED wait300s;
after CLEAN proceed to the next unit. Three LOADED => BLOCKED: load, retain
ps top8 and stop for the owner. Never stop another session's processes.

PASS => explain the bounded reader mechanism using saved mask counts and the
new isolated reader row. MISS => report its measured size and timing, limit the
causal claim. Keep PR97 draft; checkpoint sources/evidence in this repository,
no upstream text, merge or modification of the standalone casefix adapter.
