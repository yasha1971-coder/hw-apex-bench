# chr1 current ACE region-cost baseline — 2026-09-18

This is the pre-optimization baseline for the **current** ACEAPEX random-access
library path on a full-size archive. It is deliberately not a codec comparison
and not a new granularity sweep.

## Frozen configuration

- corpus: UCSC hg38 chr1 FASTA
- input bytes: **253,935,557**
- input MD5: `9465e0f0df6e2c6eb39729c39cee5465`
- ACEAPEX: `4915321bf118e564ef3883e58927992c7f9d8dc3`
- linked zstd: `f8745da6ff1ad1e7bab384bd1f9d742439278e99`
- `g = 16,384 B`
- request `R = 16,384 B`
- level 2, eight encode threads
- only `ACEAPEX_BS=16384` set; no explicit `LIT_CHUNK`, `FSE_CHUNK`,
  `MIN_MATCH`, or profile override
- archive bytes: **69,122,682**
- ratio: **3.673694**
- full native restore: **bit-perfect**

Archive/context creation, file I/O, output allocation/prefault and 12 warmups
are outside the ordinary per-query timer.

## Baseline table

Primary complete run: GitHub Actions **35361199182**, ARM Neoverse-N2,
Linux 6.17.0-1022-azure aarch64, CPU affinity pinned to CPU 0.

| Layer / diagnostic | Measured baseline |
|---|---:|
| full current `hc_region` p50 | **913.668 µs** |
| full current `hc_region` p99 | **1,274.394 µs** |
| isolated header parse + range locate | **0.0166 µs** |
| isolated full-archive stream-index scan | **0.8911 µs** |
| allocator calls inside `hc_region`, instrumented p50 | **2.176 µs** |
| allocator calls inside `hc_region`, instrumented p99 | **85.832 µs** |
| alloc-like calls / request, p50 | **16** |
| free calls / request, p50 | **16** |
| requested allocation bytes / request, p50 | **1,916,619 B** |
| perf instructions / `hc_region` | **8,796,014** |
| perf cycles / `hc_region` | **2,875,685** |
| adjusted IPC | **3.059** |

The perf values are the median of five 20,000-query hot-loop runs. Each run
uses a zero-query setup control and an ABI-compatible stub loop; the reported
per-query numbers subtract both setup and loop/control work.

The allocator timing is a separate LD_PRELOAD-instrumented run. Its timer is
enabled only around `hc_region()`; a measured back-to-back clock-pair overhead
is removed per allocation call. It is not substituted for the uninstrumented
latency run.

## Full-archive geometry

The 16 KiB chr1 archive contains:

- **15,499 blocks**
- **2,943 literal chunks**
- FSE chunks: offsets **12**, lengths **1**, commands **21**
- default FSE chunk size: **524,288 B**

The explicit linear metadata traversal over those chunk tables costs about
**0.89 µs** on this full archive. So the linear scan concern is real and scales
with archive/chunk count, but on chr1 it is not the dominant source of the
~0.9 ms current request cost.

Likewise, header parsing and block/range lookup are effectively negligible at
this scale. The allocator itself consumes only a few microseconds at the
median, despite the current call path making 16 alloc-like calls and 16 frees
and requesting roughly 1.9 MiB of temporary storage per request. That memory
churn can still create downstream cache/write costs; the 2.176 µs figure is
only time spent inside allocator calls, not the cost of filling or decoding
those temporary buffers.

## What is actually expensive

The current request retires about **8.8 million instructions** and
**2.88 million cycles**. This is consistent with a compute/decode-heavy path,
not a header/index lookup bottleneck.

The current API repeatedly executes the one-shot region path:
stream-range setup, literal/FSE partial decompression, temporary span creation,
block decode and copy. This baseline intentionally does **not** modify or cache
any of that state.

No synthetic additive decomposition is produced. The header, scan and allocator
rows are direct isolated/instrumented measurements that overlap the work inside
the full call. They must not be summed or subtracted to manufacture an
unmeasured “decode remainder”.

The correct use of this table is longitudinal: after each resident-context
change, rerun the same probes and report how much each measured row moved.

## Small-window caution confirmed

A previous matched-g run on thirty 2 MiB windows reported ACE p50 near
0.253 ms at g=R=16 KiB. The full chr1 baseline is much higher.

Because those measurements were taken on different GitHub-hosted machines, the
absolute ratio is not a portable performance factor. But the full-size
experiment confirms the methodological point: **2 MiB archives are too small
to establish the current full-archive region-cost floor**.

A secondary x86 GitHub-hosted run on AMD EPYC 7763 measured full-chr1 p50
**1,134.220 µs** and p99 **1,802.999 µs**. That VM did not expose hardware PMU
cycles/instructions, which is why the primary complete baseline uses the ARM
runner. Absolute times remain declared, machine-specific observations.

## Evidence

Compact baseline:
`evidence/chr1-region-cost-20260918/baseline.json`

Primary artifact:
- Actions run: `35361199182`
- artifact: `10554745486`
- artifact digest:
  `sha256:d84ce5bc5db4527d7b77906e3a68a232ac4caecea424369a48193c1d48681677`

Secondary x86 artifact:
- Actions run: `35360295220`
- artifact: `10554028971`
- artifact digest:
  `sha256:6f239b3236ed5d8b62ab118bea6c442f8961dbfc944a984f6ccb3191bc3f006c`

Protocol and probes:
`review/chr1_region_cost/`
