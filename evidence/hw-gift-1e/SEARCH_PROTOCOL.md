# HW-GIFT-1e: bounded core attribution

This stage is admitted only after the complete twelve-cell tag grid and its
independent saved-data audit pass. The unchanged primary predicates have passed:
v1.5.4 full enwik8/L10/256 B B/A = 65207374880/2090112729 (P1 HIT);
v1.5.7 A/B = 2087706392/1916454131 (P2 HIT under the symmetric <1.2 rule).
Kill did not trigger. These observations admit this search; they do not identify
a cause. The endpoint gate references and source hashes are frozen in a committed
admission receipt before any search-stage build or timing.

The consumer is a zstd maintainer deciding whether the reason for PR #3544 still
needs a seekable-writer workaround. The strongest baseline is B on pinned v1.5.7,
paired with every tested core. The search measures enwik8's first 16,777,216 bytes,
L10, 256 B frames. It cannot replace the full-input primary predictions.

Source-informed forecast S1: the first-parent pair e2965edd -> 9420bce8 changes
from SLOW to FAST under the classifier below. This is a new attribution forecast,
not a rewrite of P1/P2. Failure leaves the original tag results intact.

## Sources, controls and endpoint gate

Freeze the literal v1.5.4 B writer without a hint setter, v1.5.4 seekable header
and decoder, and the already tested native bridge plus untimed checksum helpers.
Only the zstd core, its matching public/common headers, and its static library
change. Preserve the compiler, flags, linkage, CPU0, host and RAM input. Verify
the version from the candidate CLI and linked library, clean Git sources, all
source/binary hashes, deterministic C,C encodings, complete byte restoration,
seek-table extents and every per-frame XXH64, including the empty terminal frame.
All correctness encodings and builds occur outside the benchmark lock on CPU15.
No candidate may be timed if these controls fail. The tag AA gates remain the
method-stability evidence and are not pooled with search observations.

First collect five fresh paired B-v1.5.4/B-v1.5.7 rounds at this prefix cell.
Require median(old) >= 2*median(new), using integer ns. Otherwise stop NO BRACKET
without candidate builds. Publish the endpoint summary and commit a classifier
receipt before the first candidate build. Do not alter the endpoint admission:
create a separate committed candidate admission that refers to it and the fixed
classifier. A delivered checkpoint is replayed without new timings.

Let S and F be these fixed old/new endpoint medians, and C and R the candidate
and paired fixed B-v1.5.7 medians. Define q=C/R and midpoint sqrt(S/F). Classify:

- FAST iff 100*C*C*F < 81*R*R*S (q < 0.9*midpoint).
- SLOW iff 100*C*C*F > 121*R*R*S (q > 1.1*midpoint).
- Otherwise INDETERMINATE, including either equality: stop with the current range.

All classification uses integer arithmetic before display rounding. The paired
reference reduces sensitivity to host drift; it is not an elapsed-time exclusion
rule. No classification is forced if endpoint separation or controls fail.

## Candidate path and finite budget

At most twelve distinct core builds TOTAL, including both already built tags.
Reserve a candidate's slot before checkout/build. Failed and incompatible builds
consume a slot, are retained, are not retried, and stop with the existing range.
Cached verified builds are reused. A separate exclusive search-state lock
serializes reservations, replay and timing; it is not the OVH benchmark lock.

Verify ancestry in the full upstream Git history. Test these source-informed
candidates in order, stopping on an observed adjacent first-parent SLOW/FAST pair:

1. e2965edd107acd0123294e23848cdc00af906468, parent of 9420bce8.
2. 9420bce8a491e21821c4b372f837bf4bd47e5870, "Add init once memory (#3528) (#3529)".
3. 91f4c23e634a1d260f290f00b6d870a56cd59ab6, "Add salt into row hash (#3528 part 2) (#3533)";
   its first parent is 9420bce8, so that shared parent is not rebuilt or retimed.

If no adjacent transition is found, choose the shortest ancestry path between
any tested SLOW ancestor and tested FAST descendant; tie-break by slow then fast
full SHA. Construct each path backwards from FAST: at each commit take the first
parent, in Git's recorded parent order, that has SLOW as an ancestor. Reverse the
result. Record the full path and titles before building its interior midpoint at
index floor((len(path)-1)/2), then recompute the closest tested bracket. Stop on
budget exhaustion, INDETERMINATE, build/control failure, no usable bracket, or an
adjacent edge. A merge edge through a non-first parent remains a qualified range;
do not attribute the merge to an unmeasured individual side-branch patch.

Publish every attempted build, full SHA/title/parents, selected paths, raw rounds,
classification and the final bracket. The result is an observed local boundary
or narrowed range, not a global first-fast claim: monotonicity across the whole
1068-commit DAG has not been established. Do not spend unused budget after an
adjacent transition merely to collect more timings.

## Rounds, load and delivery

Each endpoint/candidate has five C/R pairs: CR, RC, CR, RC, CR. C is the tested
core's B writer; R is the fixed B-v1.5.7 writer. Only encode is timed. Allocation,
initialization, prefault, full restoration, CRC/hash checks and artifact writes
are outside the clock. The native encode loop is unchanged from the tag study.

Every timed pair uses blocking `flock /run/lock/ovh-bench.lock`, pinned CPU0.
Record date -u, /proc/loadavg, nproc, CPU/kernel/governor/core, other processes,
raw /proc/stat and other-core deltas at both boundaries. LOADED iff load1 >2.0
at either boundary. Retake that logical pair alone, same input/order, at most
three attempts, retaining every attempt. Three LOADED attempts stop BLOCKED:
load with ps top eight. Worker/source/byte failures are fatal even when loaded.
An orphan or interrupted attempt is inspected and never silently retimed.
No exclusion or retry is based on elapsed time. Build work never holds OVH lock.

Push each completed endpoint/candidate checkpoint before continuing. An
independent controller checks receipts, source closure, exact classifier,
ancestry and budget. A separately rebuilt decoder checks all retained archives
without benchmark encodings or clocks. Report S1 HIT/MISS, all attempts and
medians/minima; retain the original P1/P2 outcomes. Update only the unsent draft
issue in this repository; PR #94 stays draft. No upstream issue/comment or merge.
