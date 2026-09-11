# Nine-axis evidence coverage

Generated from results.jsonl; this audit does not execute compression or timing.

## Nine-axis measurement contract

| Axis | Unit | Definition and procedure |
|---|---|---|
| ratio | dimensionless | Input bytes / complete archive file bytes plus all required sidecar/index bytes; stat the files and verify full byte-exact restore. |
| encode | MB/s | Input bytes / encoder wall seconds / 10^6; report encoder threads and only promote a rate after the documented load-growth plateau. |
| full decode | MB/s | Input bytes / full library-decode wall seconds / 10^6; resident archive, prefaulted output, explicit decoder workers, verified plateau. |
| region p50/p99 | ms | Nearest-rank percentiles of 200 identical 16 KiB reads; resident archive and reusable handle, timer around the library API only, byte verification outside timing. |
| amplification | decoded bytes / returned bytes | Sum actual bytes expanded by the decoder / sum bytes returned; count repeated expansions in a separate instrumented pass. |
| c(g) | % | 100 × (ratio_whole − ratio_g) / ratio_whole; same corpus, codec, settings and container, changing only independent block size; test 4/16/64/256/1024 KiB. |
| batch | ranges/s | N / median wall seconds for uniform, sorted, clustered, hot-set and Zipf(1.2); same trace and workers; show loop and native batch separately. |
| H_alpha | bits | Shannon entropy −Σ p_b log2(p_b) of request-start blocks for each batch trace; use actual index boundaries, and retain the common 16 KiB-grid entropy. |
| break-even N | requests | Intersection N* = median full-decode ms / region p50 ms; report floor(N*)+1 as the first integer where independent seeks cost more than full decode. |

The disk-size denominator means file lengths, not allocator blocks or the sum of compressed streams. Required indexes always count.
`H_alpha` is this protocol's historical name for Shannon entropy; alpha is not a fitted Rényi-entropy parameter.
A native batch API can be unavailable while a measured single-call loop remains valid. Missing values require a reason in the same cell.
A configuration-specific unsupported result does not transfer measurements from another profile or revision.

## Existing core run

Run `2026-09-10T20:29:44.589718+00:00`; four configurations, three formats. See README for values, versions, complete configurations and same-run comparisons.

| Configuration | Ratio + regions + amplification | Encode + full-decode plateau | Five-profile loop + H_alpha | Native batch | Break-even |
|---|---|---|---|---|---|
| bgzip+htslib | byte-verified evidence | verified plateau / verified plateau | 20 verified workloads, one worker | n/a — no native batch API in this adapter | derived, same run |
| zstd-seekable | byte-verified evidence | verified plateau / verified plateau | 20 verified workloads, one worker | n/a — no native batch API in this adapter | derived, same run |
| aceapex-interactive | byte-verified evidence | verified plateau / verified plateau | 20 verified workloads, one worker | 20 verified workloads, one worker | derived, same run |
| aceapex-dense | byte-verified evidence | verified plateau / verified plateau | 20 verified workloads, one worker | 20 verified workloads, one worker | derived, same run |

## Separate controlled c(g) run

Run `2026-09-10T23:38:56.105858+00:00`; exact configurations and complete 15-position table: [docs/CG_CURVE_RESULTS.md](CG_CURVE_RESULTS.md).

| Configuration | Grid coverage | Strict c(g) availability |
|---|---|---|
| bgzip-cg | 3 measured geometries; 2 explicitly unsupported positions | n/a — BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported |
| zstd-seekable-cg | 5 measured geometries; 0 explicitly unsupported positions | 5 measured matched-baseline points |
| aceapex-cg-default | 5 measured geometries; 0 explicitly unsupported positions | 5 measured matched-baseline points |

The curve uses ACEAPEX ee5a37e default; core profiles use 1b13df3. Neither is relabeled as adaptive default a194893.
The separate a194893 refresh retains its six byte-verified rows in docs/DEFAULT_RESULTS.md; it supplies no unmeasured amplification, batch or plateau values.

## Interpretation

All nine axes are accounted for as measured/derived evidence or an explicit unsupported result. This is coverage, not a claim that every configuration supports every axis.
Absolute CPU performance is declared. A ratio to bgzip is computed only within its own run, corpus and operation; its predicate retains PASS and FAIL. Normalization does not establish machine invariance.
The original 420 rows are preserved byte-for-byte, followed by 15 original curve records. No benchmark was rerun to construct this report.
Recheck: `./run.sh --audit-axes`.
