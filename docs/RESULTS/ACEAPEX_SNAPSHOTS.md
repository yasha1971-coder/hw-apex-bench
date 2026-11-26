ACEAPEX is developed by the author of this benchmark.

## Matched-g refresh: ACEAPEX v2.1.0 / main open vs BGZF — 2026-09-30

Measured on thirty frozen 2 MiB T2T-CHM13v2.0 windows, not the chr1 snapshot below; ratios are not comparable between the two tables. ACEAPEX is written by the author of this benchmark. Its density advantage and its latency penalty are both reported below; the harness, corpora and raw samples are in the repository.

Each cell is **ratio · p50 / p99 ms**.

| exact g | BGZF | ACE 1b13df3 legacy | ACE v2.1.0 interactive | ACE main open |
|---:|---:|---:|---:|---:|
| 4 KiB | 3.794020 · 0.052949 / 0.067827 | 4.682708 · 0.136184 / 0.269816 | 4.682708 · 0.068290 / 0.135201 | 4.455378 · 0.211221 / 0.458329 |
| 8 KiB | 4.139526 · 0.054550 / 0.071012 | 5.010591 · 0.141694 / 0.263842 | 5.010591 · 0.067162 / 0.139417 | 4.879676 · 0.153141 / 0.467160 |
| 16 KiB | 4.406650 · 0.065482 / 0.083762 | 5.219838 · 0.143850 / 0.272584 | 5.219838 · 0.074632 / 0.149201 | 5.148826 · 0.176257 / 0.482423 |
| 32 KiB | 4.643726 · 0.062581 / 0.142081 | 5.344308 · 0.156778 / 0.303165 | 5.344308 · 0.083464 / 0.180311 | 5.307601 · 0.216979 / 0.529897 |
| 65,280 B | 4.810834 · 0.108651 / 0.244448 | 5.412621 · 0.210062 / 0.438012 | 5.412621 · 0.124668 / 0.277486 | 5.395254 · 0.271045 / 0.757243 |

The modern rows use a persistent C99 decoder handle; the legacy row retains the historical one-shot path as a same-run control. v2.1.0 interactive cuts legacy p50 by 40.7–52.6% and leaves only a 9.2–20.9 µs p50 gap to BGZF. Main open does **not** remove that remainder: it is slower than v2.1.0 interactive at all 5 points and is also less dense at all 5 points.

[ACEAPEX v2.1.0 / open refresh report →](ACEAPEX_UPGRADE_20260930.md)  
[GitHub Actions run 36641590388 →](https://github.com/yasha1971-coder/hw-apex-bench/actions/runs/36641590388) · [historical 2026-09-18 matched-g report →](MATCHED_G_INTERACTIVE_20260918.md)

**Independence cost at 16 KiB (separate full-chr1 `c_file(g)` scopes):** historical ACEAPEX default @ ee5a37e is **1.632%**; current main-open @ ec347787 is **1.735%**; matched zstd-seekable is **6.569%**. BGZF is **n/a** because no same-encoder whole-input baseline exists. These ACE values use different revisions/profiles and are shown as separate measured scopes, not as a one-variable profile delta. [Current refresh →](ACEAPEX_UPGRADE_20260930.md) · [Scope definitions →](../CG_SCOPES.md)

**Batch sweep scope (2026-09-19):** hg38 chr1, N=5000, 16 KiB ranges, workers=1, Actions run 35427975099.

A native batch API is what makes the dense profile usable at all for region reads: it moves from 659.6 to 12,369.7 ranges/s under uniform access. But dense leads interactive only under uniform access. Once requests concentrate, interactive overtakes it somewhere between 12 and 8 bits of access entropy and keeps the lead: at Hα ≈ 2 bits, interactive reaches 869,088 ranges/s against 467,998 for dense. For batch-heavy workloads with any locality, interactive is the profile to pick.

Concentration helps BGZF more than it helps ACEAPEX in the single-request path. Under uniform access bgzip runs 10,040.6 ranges/s against ACEAPEX interactive at 9,086.4, a 1.1× gap. At Hα ≈ 2 bits bgzip reaches 64,722.7 against 13,847.4, a 4.7× gap. The batch API is where ACEAPEX answers locality; the loop path is not.

[Access-entropy sweep →](ACCESS_ENTROPY_20260919.md)

[written by ChatGPT (AI) at the author's request; checked by the author]

## Same-run chr1 refresh — 2026-11-26

Full hg38 chr1 FASTA (253,935,557 bytes), R=16 KiB, archive in RAM; ratio = input / stored bytes including required indexes. Each date has its own host, source, configuration and request sample.

2026-09-10: Intel Xeon 6973P-C, 200 requests per configuration; ACEAPEX 1b13df3 uses the one-shot `aceapex_decompress_region` API. BGZF g is a 64 KiB ceiling; ACE dense uses g=256 KiB.

2026-11-26 (HW-REGION-1): one pinned core on ace-core (AMD EPYC 4344P), 1,000 uniform requests per format, persistent library handles, g=16 KiB for all three formats; ACE interactive LIT=65,536 B, FSE=4,096 B.

| Date / scope | Codec / source version | g | Stored bytes incl. indexes | Ratio | p50 / p99 ms | Mean amplification |
|---|---|---:|---:|---:|---:|---:|
| 2026-09-10 · historical | ACEAPEX 1b13df3 interactive (L2) | 16 KiB | 69,409,878 | 3.658493 | 0.129720 / 0.240419 | 6.216250 |
| 2026-11-26 · HW-REGION-1 | ACEAPEX tag v2.6.5 / ce6b674 interactive (L2) | 16 KiB | 60,440,764 | 4.201396 | 0.032711 / 0.054592 | 5.996250 |
| 2026-09-10 · historical | zstd-seekable 1.5.7 (L3) | 16 KiB | 83,924,167 | 3.025774 | 0.046046 / 0.059425 | 2.000000 |
| 2026-11-26 · HW-REGION-1 | zstd-seekable 1.5.7 (L3) | 16 KiB | 83,924,167 | 3.025774 | 0.041668 / 0.047389 | 2.000000 |
| 2026-09-10 · historical | BGZF / HTSlib 1.19 (L6) | ≤ 64 KiB | 75,072,042 | 3.382558 | 0.102141 / 0.212103 | 4.821094 |
| 2026-11-26 · HW-REGION-1 | BGZF / HTSlib 1.24 (L6) | 16 KiB | 80,071,563 | 3.171358 | 0.042280 / 0.046257 | 2.000000 |
| 2026-09-10 · historical | ACEAPEX 1b13df3 dense (L2) | 256 KiB | 67,167,236 | 3.780646 | 1.330098 / 2.523226 | 83.431872 |

Same-run non-genome, g=16 KiB, ACEAPEX / zstd: [enwik8](../../evidence/hw-region-1/cases/enwik8-g16384.json) p50 = 2.45, stored bytes = 41,649,923 / 42,939,459; [silesia](../../evidence/hw-region-1/cases/silesia-g16384.json) p50 = 2.82, stored bytes = 76,265,370 / 79,417,442.

Within 2026-11-26, ACEAPEX / zstd: p50 = 0.785039; p99 = 1.151997; stored bytes = 0.720183; amplification = 2.998125.

[Historical rows](../../results.jsonl) · [Run report](../../evidence/hw-region-1/RESULTS.md) · [Saved primary cell](../../evidence/hw-region-1/cases/chr1-g16384.json) · [Pinned versions, CLI/header strings and build metadata](../../evidence/hw-region-1/setup.json). Historical rows below retain their original sources and hosts.

[written by ChatGPT (AI) at the author's request; checked by the author]

## Historical chr1 snapshot — 2026-09-10 (ACEAPEX before v2.1.0)

| Codec | Granularity | Ratio | p50 ms | p99 ms | Amplification |
|---|---:|---:|---:|---:|---:|
| bgzip+htslib | ≤ 64 KiB | 3.383 | 0.102 | 0.212 | 4.82 |
| zstd-seekable | 16 KiB | 3.026 | 0.046 | 0.0594 | 2 |
| aceapex-interactive | 16 KiB | 3.658 | 0.13 | 0.24 | 6.22 |
| aceapex-dense | 256 KiB | 3.781 | 1.33 | 2.52 | 83.4 |

ACEAPEX dense has the highest ratio; zstd-seekable has the lowest p50, p99 and amplification. Both ACEAPEX profiles trade slower regions for greater density.

This is the preserved chr1 CPU snapshot: three formats, four configurations, 200 resident 16 KiB byte reads per configuration; absolute times belong to its host. BGZF granularity is a ceiling; actual blocks vary. XZ has separate qualification and small-corpus evidence, not an invented row in this historical comparison.

