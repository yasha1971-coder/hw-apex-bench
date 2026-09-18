# HWB-003: frozen-window resident access

Protocol fixed before timing. No new compression or sampling of sequence windows.
Use all30 retained2MiB inputs:10HOR,10annotation-complement controls and10terminal
contexts. Restore prior ACE/zstd archives at4/16/64/256/1024KiB and fixed BGZF
archives/indexes from accepted bundles; require exact input/archive hashes.

Use native ABI2 contexts and the existing native_measure worker:200 reads of
16KiB after12 warmups, deterministic offsets (seed20260909), same ordered trace
for every archive. Index preparation and resident archive loading are outside
CLOCK_MONOTONIC timing; block lookup and API decoding inside. Output verification
and guard checks outside. One sequential caller, default single-region decoder
policy; no parallel timing jobs. Pin the worker to one allowed CPU and report
hardware, affinity, OS, library pins, build flags and context/worker hashes.

Measure three passes per configuration in seeded shuffled configuration order;
keep every sample/pass, not best-of-three. Main p50/p99 are nearest-rank pooled
samples (600 per window); report per-pass spread. Warm reusable contexts preserve
normal codec caching. Archive-resident does not imply cold decoder state.
Measure counting libraries in a separate untimed pass with the identical trace
and warmup; verify all returned bytes. Counts describe entropy-decoder output
bytes for ACE, zstd block output for zstd, and inflate/libdeflate output for BGZF,
as in the existing amplification instrumentation. They are not memory traffic,
CPU instructions or a distribution of LZ match distances.

Check full restoration with each ordinary native library before accepting its
region samples. Explicit correctness-only boundary probes cover0/end and inside/
across codec boundaries, separately from the common timed random trace. The
16KiB request necessarily spans multiple blocks at4KiB; do not invent within-
block16KiB cases there. Retain actual boundary crossing counts for the trace.

Group p50/p99 pool equally sized window traces; amplification is total counted
bytes/total returned bytes. BGZF is measured once per window, not remeasured as
five fictitious granularity points. Compare relative latencies with BGZF from
this study only. Historical6.216x/83.4x and0.082–0.154ms have different corpus,
codec policy and hosts; they are context, not acceptance targets or baselines.

HWB-002 is a separate untimed parser/decoder inspection: collect accepted-match
distance and length histograms from frozen ACE archives if validated decoding
permits it, verify full output, and record both match-count and matched-byte
weighting. Compare HOR/control at the same g and2MiB baselines. Observed selected
matches are limited by the encoder/search/window: they do not enumerate missed
opportunities. A right shift supports locality sensitivity; it does not isolate
its contribution from entropy coding or prove that every HOR repeat crosses16KiB.
Keep instrumented objects separate from timing and upstream sources unchanged.
