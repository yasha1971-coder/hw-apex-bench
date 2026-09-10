# Batch, access entropy and break-even

Run `./run.sh` for the complete currently implemented stage, or `./run.sh --stage 1`
for the four-row region table only. All results in one report come from the same
invocation and machine. Later axes stop at the review boundary.

## Source attribution

The unchanged source snapshots in `harness/upstream/` are from ACEAPEX commit
`1b13df34ac8e839dd3232b59bc59560d689a435a`:

| Source | Git blob |
|---|---|
| scripts/batch_test_ci.c | 5d6b8f86821d8d5eb431a1f9a8aab2e891de14da |
| scripts/breakeven.c | 32402bd688bd45b5f0caed8f1ee5752f82953ea4 |

The batch snapshot has `H_a` and the corrected once-per-run hot-set. Both snapshots
are checked by git blob hash before measurement. Adaptations live only in this
repository; upstream dependency checkouts are unchanged.

## Shared traces

`harness/access_profiles.py` generates exact 16,384-byte original-file requests
using a fixed 64-bit integer generator and seed 20260910. All codecs use the same
trace for a given profile and N; generation, file loading and allocation are
outside timing. Sizes are 100, 600, 2000 and 5000. Traces and their SHA-256 hashes
are retained, allowing replay independent of Python versions.

* Uniform: uniformly sampled valid starting byte offsets.
* Sorted: the exact uniform multiset for that N, sorted by offset.
* Clustered: one shared 1 MiB window for each group of 32 requests, then a new
  window; offsets within a window are random. Unlike the upstream generator,
  a fresh center is not chosen independently for every request.
* Hot-set: 64 distinct canonical 16 KiB blocks selected once for the whole run.
  Requests choose a hot block and jitter within its valid start positions.
  The hot set is preserved across all N and codecs. The original snapshot chose
  positions; this adaptation explicitly chooses distinct blocks.
* Zipf(1.2): exact finite probability weights proportional to rank^-1.2 over
  canonical 16 KiB blocks, sampled through a normalized CDF and binary search.
  This replaces the upstream power approximation and avoids its zero-input cast.

H_alpha is Shannon entropy of request-start blocks, `-sum(p * log2(p))`. Each row
uses its declared `block` size for fixed-size units. BGZF uses actual GZI-indexed
block boundaries because 65536 is only its ceiling. The GZI hash and raw
uncompressed block starts are retained with the trace evidence. H_alpha_16k is also retained to compare the same
access distribution at a fixed scale. A 64-block hot set on the canonical grid
may map to fewer dense blocks. Conversely, jitter within a canonical cell can
cross a real BGZF boundary, so those 64 canonical cells can visit more than
64 actual BGZF blocks. Per-codec entropy is not forced to six bits.
H_alpha describes the starting-block distribution, not all intersected blocks.

## Batch operation and timing

The library handles and compressed archives remain resident. Caller buffers,
query arrays and native range descriptors are allocated and prefaulted before
timing. There are two checked boundary probes plus ten checked single-call warmups;
ACEAPEX additionally gets a checked native warmup with ten ranges.

All codecs measure `method=loop`: a C loop over single-region library calls.
ACEAPEX additionally measures `method=batch`: one `aceapex_decompress_ranges`
call. The loop wall clock necessarily includes loop/dispatch overhead; neither
method times FASTA processing, trace generation, validation or serialization.
All native answers must equal the single-call answers, and every single-call
answer must equal the original bytes. Return checks are outside the measured
loop; adapter error propagation stays inside the call.

Three repetitions are retained. Loop/native execution order alternates; codec
order rotates across workloads. Published ranges/s uses N divided by median wall
time, with no best-run selection. ACEAPEX batch/loop speedup is the median of the
three paired duration ratios. The two statistics need not be ratios of medians.

Loop requests one calling thread. Native batch explicitly requests min(4, logical
CPUs); upstream uses one worker below 512 ranges, otherwise caps workers by the
number of groups. Thread policies are recorded alongside every measurement.
The absence of a native batch API for other adapters is `n/a` with a reason;
it does not create zero-valued throughput rows. Cross-codec ratios always retain
method labels, and failed ratios remain fail.

## Break-even

`harness/breakeven.c` measures one full library decode after resident setup,
using one checked warmup and five checked full decodes. Whole-output buffers are
preallocated and prefaulted. BGZF includes its seek-to-zero and full read; zstd
uses its seekable library at offset zero; ACEAPEX uses `aceapex_decompress`.
Every full result is compared directly with the original file.

`N = floor(median_full_decode_ms / region_p50_ms) + 1` is the smallest integer
satisfying the strict inequality N*p50 > full decode. Region p50 comes from the
same run's 200-query measurement. The unrounded intersection is also recorded.
This is a two-line cost model for independent reads at a constant median cost;
it does not account for batch reuse, distributions of total time, or full-decode
output reuse. Its status is derived, and absolute durations are declared.

ACEAPEX's full API has no thread argument: this source uses eight reconstruction
workers and up to eight literal workers. BGZF/zstd full adapters use one thread.
Those policies are explicit; no equal-thread full-decode speed claim is implied.
These durations support break-even only. Encode/full-decode MB/s or GB/s require
the later plateau experiment and are not published here.

## Review boundary

Stop after batch, H_alpha and break-even. c(g) needs a separate reviewed PR;
plateau throughput follows separately. Only then run the complete protocol on
ace-core EPYC 4344P and WSL. No claim that cross-codec ratios are machine-invariant
is accepted without those measurements.
