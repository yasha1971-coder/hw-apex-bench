# HW-GIFT-1e execution and decision protocol

This resolves details before timing; CALIBRATION.md is unchanged. Its first,
single-file commit is `8b1fba61c325a4020dbad165a058d91848f9f914`.

## Foundations and decision

Read docs/AGENTS.md, HISTORY.md, TOOL_ROADMAP.md, METHOD_PROGNOZ_ZADANIE.md,
1c/1d RESULTS and SOURCE_PATHS, and the supplied 1e assignment. No closed avenue
or competing roadmap item was found. Live main is
`ecc9eb570a3837d81efb11095b8f76e4a43b10fc`, containing merged PR #93. The consumer
is the hw-apex-bench owner preparing a factual zstd issue. The decision is
whether the historical tiny-frame slowdown is reproducible in the old core,
has disappeared in the later core, and merits a bounded search for its change.
The baseline is the upstream seekable writer, whose hint was added for a real
2023 ingestion problem. The supplied P1/P2 and Kill are retained literally.

## Controlled software and operation

Build clean exact tags with the same compiler and flags, outside the timing lock:

- v1.5.4: `945f27758c0fd67b636103a38dbf050266c6b90a`.
- v1.5.7: `f8745da6ff1ad1e7bab384bd1f9d742439278e99`.

Record annotated tag objects, peeled commits, source/library/header/binary hashes,
compiler commands and logs, CLI `zstd -V`, and the actually linked version number
and string. Each core uses its own zstd/common/xxhash headers and static library;
experimental enum numbers or private layouts are never transported between cores.

Freeze the v1.5.4 seekable writer, decoder and seekable header on both libraries.
B is the exact v1.5.4 writer, with no srcSizeHint setter call. A adds the two
assert/setParameter lines from PR #3544. Prove that A exactly matches the tagged
v1.5.7 compression source and that removing those two lines reproduces B.
The header's historical maximum-frame constant differs between tags, but the
frozen header is used throughout and all measured frames are far below either
limit. Thus the paired core comparison has no writer-source drift.

The resident native bridge is the retained 1c API loop. CPU 0 on ace-core, one
thread, RAM input/output. Both variants have identical checksum-bearing seek
tables. New encoder contexts and allocated/prefaulted outer buffers precede each
timer; codec internal lazy allocation remains inside. Exactly one native encode
call is timed per slot. Hashing, file I/O, full restore, index checks and frees
are outside compression time. No decode timing is requested in this study.
Every produced archive must restore bit for bit, including every frame/checksum
and the legitimate terminal empty frame when the writer emits one. Do not force
frame count to ceil(N/G). Preserve actual archive bytes and SHA in private state
and bind them in public receipts. No warmup observations are discarded.
Identical untimed helpers appended to the common bridge verify every seek-table
XXH64 against source slices and separately validate/decode a terminal empty frame.
They execute after the compression intervals; the retained encode loop is unchanged.

## Primary gates, auxiliary grid and order

Primary P1: FULL enwik8 (100,000,000 bytes), L10, G256, v1.5.4.
Use the ratio of the five compression medians, not the median of paired ratios:
P1 HIT iff median(B) >= 5*median(A). Kill triggers iff median(B) < 2*median(A).
At exactly 2x there is no Kill; at exactly 5x P1 is HIT.

Primary P2: the same FULL/L10/G256 pair on v1.5.7. Interpret "differs by less
than 1.2x" symmetrically: 5*max(median(A),median(B)) < 6*min(median(A),median(B)).
Exactly 1.2x is MISS. Also display the directional B/A ratio.

The 12 cells are two versions times two input scopes times three configurations:
{L10/G256, L10/G1024, L3/G256}. Scope is full enwik8 or its exact first
16,777,216 bytes; both bind the full parent SHA. The other ten cells are
auxiliary and never substitute for a primary gate. Full source SHA is
`2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8`.

Order: build/check both versions untimed; v1.5.4 AA method gate; v1.5.4 primary;
evaluate Kill immediately. On Kill, stop all remaining timing, mark remaining
cells NOT RUN: Kill, report machine/input/native-harness differences and make
no "fixed in core" claim. Otherwise run v1.5.7 AA and its primary, then all
remaining cells in version order, full then prefix, configuration order above.
If 2 <= old B/A < 5, finish the fixed grid but do no core search.

Five A/B rounds per cell. Cell index is version_index*6 + scope_index*3 +
configuration_index (versions old/new; scopes full/prefix). Reverse starting
variant by parity of (cell_index + repeat_index), so A/B and B/A alternate.
Store both slots separately. Report median and minimum integer ns and complete
archive bytes for each variant; compare all predicates before display rounding.

## Method gates and exclusion policy

Before main timing on a version: version/CLI and clean-source pins must pass;
same-input deterministic positive controls, changed-input distinction, corrupt
magic rejection, and byte/checksum restores must pass. v1.5.7 prefix archives
must reproduce the corresponding saved 1d A/nohint archive SHA; B has no setter
but a fresh default context has the same byte policy as 1d's zero-valued setter.
This known answer is a byte check, not reuse of 1d timing observations.

Per-version AA gate: full/L10/G256, A twice per round, five new pairs. Require
20*abs(median(second)-median(first)) < median(first), strictly. A is deliberately
the specified same-writer control; its observations are not pooled with A/B.
A failed timing-stability gate stops, rather than retrying until it passes.
Test load decisions with known 1.00/2.00 CLEAN and 2.01 LOADED examples and
other-core deltas with known counters. These controls read no timing clock.

Every timed round is launched through blocking external
`flock /run/lock/ovh-bench.lock`. Wait if occupied. Record literal date -u,
cat /proc/loadavg and nproc at both boundaries, CPU/kernel/governor/core, other
processes and raw /proc/stat. Attach other-core counter deltas to both boundaries
as observations only. The sole successful-round exclusion is load1 > 2.0 at
either boundary. Retake that round alone immediately with identical input/order,
at most three attempts total; retain all attempts. Three LOADED attempts stop
BLOCKED: load and retain the required ps top eight. Worker/byte/source errors
are fatal even if loaded. No decision to exclude depends on elapsed time.

Replay completed CLEAN rounds without timing. Interrupted/error state needs
inspection. Save and push method/cell checkpoints before the next stage; delivery
retries never retake measurements. Retain N retaken / M logical rounds and all
attempts. Build and correctness work never hold the shared benchmark lock.

## Conditional core search

Only primary P1 HIT AND P2 HIT admit step 4. Record a separate search protocol
before any search-stage timing or candidate build. Freeze the B writer and all
non-core sources. The search cell is prefix16MiB/L10/G256; full-input effects
cannot be assumed to separate this cell's endpoint versions.

The search protocol must verify a fresh interleaved B-old/B-new prefix bracket,
require at least 2x endpoint separation or stop NO BRACKET, freeze its classifier
before candidates, and compare each candidate against fixed B-v1.5.7 in five
interleaved rounds. No timing-based retakes. A geometric midpoint classifier
with an explicit indeterminate band may stop with a range rather than force a
classification. All observations remain in evidence.

Conservative build budget: at most 12 distinct core builds TOTAL, including the
two mandatory endpoint builds (at most 10 additional candidates). Failed builds
count; cached verified builds do not get rebuilt. A failed or incompatible build
is never FAST. Verify ancestry first; freeze the actual search path, midpoint
algorithm and handling of merges/skips in the separate protocol. A first-parent
transition is labelled as such; without a monotonicity proof it is not a global
first-fast claim. If endpoints are not adjacent or the budget runs out, report
the remaining slow-to-fast commit range and titles. Do not attribute a merge's
effect to an unmeasured individual commit in its side branch.

## Deliverables and interpretation

One version/scope/configuration table, original P1/P2/Kill outcomes, all size/time
losses, and search boundary/range if admitted. A separate controller rebuilds a
correctness oracle, recalculates raw hashes/medians/load admission and checks the
unsent draft. Old 1c/1d evidence stays unchanged.

The new issue draft starts with PR #3544's reason and whether it reproduces in
these versions, then derives the 1d price of hinting by level from saved data
(correcting approximate ranges or scope if needed), and ends with ONE question
to maintainers. Historical M1 numbers belong to the PR description; L10/256 B
settings are confirmed in the later reproducer, not the original issue comment.
Use explicit host/RAM/version/input scopes; no universal or original-Pijul-app
claim follows automatically. Draft PR only; no external issue/comment or merge.
