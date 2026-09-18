# ACEAPEX vs BGZF — exact matched-g legal corridor (2026-09-18)

This result closes the earlier apples-to-oranges comparison. ACEAPEX and BGZF
were measured on the same frozen T2T corpus, at the same uncompressed
granularity \(g\), with the same 16 KiB resident region trace.

Primary corpus: all thirty frozen 2 MiB T2T-CHM13v2.0 windows from
\`evidence/t2t-regions-20260916/manifest.json\` (60 MiB total per codec):
10 centromeric HOR, 10 telomere-context, 10 annotation-complement.

## Result

Density is complete input bytes / complete stored bytes. ACEAPEX counts the
whole archive. BGZF counts the whole archive plus its \`.gzi\` index.
p50 is nearest-rank over 18,000 verified resident 16 KiB requests per codec
per point: 30 windows × 3 deterministic passes × 200 requests.

| exact g (B) | ACE ratio | BGZF ratio | ACE p50 (ms) | BGZF p50 (ms) | ACE density gain | ACE latency penalty | command |
|---:|---:|---:|---:|---:|---:|---:|---|
| 4,096 | 4.746234 | 3.794020 | 0.274156 | 0.053571 | +25.10% | +411.76% | \`python3 review/matched_g/run_point.py --g 4096 ...\` |
| 8,192 | 5.056374 | 4.139526 | 0.259729 | 0.054012 | +22.15% | +380.87% | \`python3 review/matched_g/run_point.py --g 8192 ...\` |
| 16,384 | 5.254574 | 4.406650 | 0.252896 | 0.063419 | +19.24% | +298.77% | \`python3 review/matched_g/run_point.py --g 16384 ...\` |
| 32,768 | 5.372721 | 4.643726 | 0.266261 | 0.059041 | +15.70% | +350.98% | \`python3 review/matched_g/run_point.py --g 32768 ...\` |
| 65,280 | 5.438417 | 4.810834 | 0.314202 | 0.100369 | +13.05% | +213.05% | \`python3 review/matched_g/run_point.py --g 65280 ...\` |

The GitHub Actions execution was run 35356858787. All five point jobs and the
curve job completed successfully. Each point has its own checkpoint artifact;
IDs, artifact digests, result hashes, binary hashes, CPU and codec pins are in
\`evidence/matched-g-20260918/run-receipt.json\`.

## Closed BGZF boundary

No matched-g point above **65,280 uncompressed bytes** is valid in this study
and none is to be measured.

Compatible BGZF virtual offsets reserve 16 low bits for the uncompressed
offset within a BGZF block. A complete BGZF member is itself limited to
65,536 bytes. With the pinned htslib implementation, the ordinary maximum
uncompressed payload used by BGZF is 65,280 bytes. Therefore 65,280 B is the
top exact common point for this benchmark. ACEAPEX is also set to 65,280 B at
the top point; the previous 65,536-vs-65,280 approximation is not used here.

The protocol and writer reject a BGZF g above 65,280 B.

## Correctness gate

Every one of the **300 generated codec/window/g archive configurations**
completed a full native decode and matched its frozen 2 MiB input byte-for-byte
before timing. The timed worker also verifies every returned 16 KiB region and
destination guards.

Total timed requests: **180,000**.

The T2T source was re-downloaded and verified before extraction:

- compressed MD5: \`9280657210e4161147cbe13b022225b9\`
- expanded MD5: \`cd1e52ce400c027ed0b7ab4b9d613f5a\`
- expanded bytes: \`3156259565\`

## Timing boundary: what is inside the p50

Both codecs are timed **in-process through resident shared libraries by the same
\`harness/native_measure.c\` worker**. No codec CLI, subprocess startup, archive
file I/O, dynamic-library load, archive open, index load, output allocation or
output-buffer prefault is inside the region timer.

For every configuration the worker first reads the archive and original input,
\`dlopen()\`s the codec wrapper, creates one resident context with \`hc_open()\`,
allocates and prefaults the guarded 16 KiB destination, and then performs 12
warmups. The timer surrounds only one call to \`hc_region()\`.

The two codec wrappers nevertheless expose different internal lifecycle
semantics:

- ACEAPEX \`hc_region()\` calls the public one-shot
  \`aceapex_decompress_region()\` on every query. That API reparses and validates
  the archive header on each call, derives the relevant stream ranges, creates
  temporary range/span buffers, decodes the touched blocks, copies the requested
  bytes, and releases those temporaries.
- BGZF \`hc_open()\` creates a persistent \`BGZF *\` once and loads the \`.gzi\`
  index before timing. Each timed \`hc_region()\` then performs
  \`bgzf_useek()\` + \`bgzf_read()\` on that already-open context.

Therefore the matched-g p50 is a fair comparison of the **current resident
library operations exposed by the two implementations**, but it is not a
format-only lower bound. In particular, ACE's ~0.25 ms contains reusable
implementation work that is independent of the chosen g as well as the
g-dependent decode span. It is consequently a real optimization target for a
persistent ACE region context; it must not be attributed to block size alone.

A future ACE resident-context experiment may cache validated header/table
state and reusable scratch buffers, but it must be published as a new
implementation result rather than rewriting this measurement.

## Historical latency comparisons are not directly comparable

Earlier Paper 5 checks did not use this symmetric resident-library harness.
ACE latency was measured through an in-process library helper, while the BGZF
reference was timed by launching \`samtools faidx\` as a subprocess for each
request. The old script explicitly describes that value as a "bgzip process
read" and notes about 15x on EPYC and 11x on a laptop.

Those ratios include process/CLI overhead on the BGZF side and must not be used
as a baseline for the present resident-library ratio. In the exact matched-g
run, the direct ratio \`ACE p50 / BGZF p50\` ranges from about **3.13x to 5.12x**.
(For example, +213% latency penalty means 3.13x total latency, not 2.13x.)

The GitHub Actions host is also a shared Azure VM. CPU affinity was pinned to
CPU 0, which fixes scheduling affinity but does not guarantee invariant clock
frequency, steal time, cache interference or identical host placement. Absolute
latencies are therefore **declared machine-specific observations only**. The
portable result of this run is the same-run curve and same-run codec ratios;
no absolute latency threshold is inferred from the GitHub runner.

## What the slopes say

ACEAPEX is denser at every legal g, but slower at every legal g.

The relative density advantage decreases monotonically as g grows:
**+25.10% → +22.15% → +19.24% → +15.70% → +13.05%**.

The relative p50 latency penalty is not monotonic:
**+411.76% → +380.87% → +298.77% → +350.98% → +213.05%**.
ACE's own absolute p50 is lowest at 16 KiB (0.252896 ms), exactly the request
length. BGZF does **not** have the same minimum: its lowest measured p50 is at
4 KiB (0.053571 ms), with 8 KiB nearly identical. Its 65,280 B point rises to
0.100369 ms, about 1.87x the 4 KiB value.

The matched-g run did not collect amplification counters, so amplification is
not reported as a measured axis here. Geometry nevertheless explains why the
largest BGZF block is disadvantaged for a 16 KiB request: a random request
usually requires substantially more than 16 KiB of block output, and a
separate earlier counter run reported 4.821x BGZF decoded-byte amplification
for 65,280-byte blocks. That historical counter is context, not a substituted
measurement for this curve.

The useful generalization is therefore not "optimal g always equals request
size." The data support a narrower rule: **search g on the scale of the
application's typical region, including values below it**, because larger g
increases overdecode while smaller g increases per-block overhead and density
cost. ACE's present implementation bottoms near R=16 KiB; BGZF's present
implementation prefers the smaller tested blocks. The optimum is a property of
workload + decoder implementation + format geometry, not of codec identity
alone.

There is no dimensionally universal statement that a percentage density gain
"covers" a percentage latency loss without a workload utility function. If,
only as a diagnostic, the two relative percentages are assigned equal weight,
\`density_gain_pct - latency_penalty_pct\` is negative at all five points:

| g (B) | equal-% diagnostic margin |
|---:|---:|
| 4,096 | -386.66 pp |
| 8,192 | -358.72 pp |
| 16,384 | -279.53 pp |
| 32,768 | -335.28 pp |
| 65,280 | -200.00 pp |

So under that explicit equal-percentage convention there is **no crossing
inside the interoperable BGZF corridor**. This is a statement about that
normalization, not a universal application preference.

In Pareto terms, neither **current implementation path** dominates the other on
these two measured objectives: ACEAPEX always provides higher density; BGZF
always provides lower resident-library p50. This is intentionally phrased as
an implementation result, not a claim that the encoded formats impose those
absolute latencies.

## Reproduction and provenance

Protocol: \`review/matched_g/PROTOCOL.md\`.

Workflow: \`.github/workflows/matched-g.yml\`.

Exact-g BGZF writer: \`review/matched_g/bgzf_encode_g.c\`.

Point runner: \`review/matched_g/run_point.py\`.

Curve generator: \`review/matched_g/curve.py\`.

Pinned codec sources:

- ACEAPEX \`4915321bf118e564ef3883e58927992c7f9d8dc3\`
- zstd \`f8745da6ff1ad1e7bab384bd1f9d742439278e99\`
- htslib \`8f7231035d0409d525767c66d9f49f1f967ee1df\`
- libdeflate \`dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f\`

Timing host: AMD EPYC 7763 64-Core Processor, Linux
6.17.0-1022-azure x86_64, runner affinity pinned to CPU 0.

Raw per-request samples are retained in the five GitHub Actions checkpoint
artifacts identified by the run receipt. The compact committed curve is
\`evidence/matched-g-20260918/curve.json\`.
