[written by ChatGPT (AI) at the author's request; checked by the author]

# HW-REGION-1

The primary chr1/g=16 KiB measurement selects outcome **(a)**. ACEAPEX p50 is 32.711 µs versus 41.668 µs for zstd-seekable (ratio 0.785039); its p99 is 54.592 versus 47.389 µs (ratio 1.151997). ACE stores 60440764 bytes including indexes, zstd-seekable 83924167, and BGZF 80071563. **P1 MISS; Kill TRIGGERED; P2 NOT TESTED: Kill; P3 MISS.**

These results apply to the measured **ace-core / AMD EPYC 4344P host, one pinned CPU0, and resident archives in RAM**. They do not establish cross-host or historical-version speedups. The input is byte ranges, including the FASTA bytes where present; R=16384 B.

The zero call coefficient is an **NNLS boundary result**, not evidence that real API calls are free. The primary fitted prediction is 42363.199 ns versus measured 32711 ns, an absolute relative error of 29.508%. It fails the local ±20% check. The byte term is model-attributed 129.508% and the residual is -29.508%; these signed additive shares are **not fractions of measured CPU time**. A negative residual denotes overprediction. No refit, tuning, or additional ACE decomposition was used to repair this result.

## Preregistered decisions

| Gate | Exact rule | Result |
|---|---|---|
| P1 | 7/5 ≤ primary ACE p50 / zstd p50 ≤ 11/5 | MISS; 32711/41668 |
| Kill | 10 × ACE p50 < 11 × zstd p50 | TRIGGERED |
| Outcome (a) | ACE p50 / zstd p50 ≤ 11/10 | YES |
| P2 | Every one of 93 chr1/T2T ACE targets within ±20%; references excluded | NOT TESTED: Kill |
| Primary local model check | 5 × abs(predicted − measured) ≤ measured | FAIL |
| P3 | Primary model call term ≥ half measured p50 | MISS; share 0 |

Kill stops decomposition beyond the primary cell. The three-format comparative grid still completes: chr1 and thirty frozen 2 MiB T2T windows at g=4096/16384/65536 B, plus enwik8 and silesia at g=16384 B. This is 95 archive cases and 285 codec rows. P2 remains NOT TESTED when Kill triggers; the failing primary local prediction is reported separately.

## Primary measured tradeoff

| Corpus | g nominal / actual B | Codec | Archive B | Index B | Stored B | Ratio | p50 µs | p99 µs | Amp mean / p50 | Zstd calls/request | Zstd output B/request | Raw |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| chr1 | 16384 / 16384 | ACEAPEX | 60440764 | 0 | 60440764 | 4.201396 | 32.711 | 54.592 | 5.996250 / 4.250000 | 6.582000 | 50970.755 | [cell](cases/chr1-g16384.json) |
| chr1 | 16384 / 16384 | zstd-seekable | 83924167 | 0 | 83924167 | 3.025774 | 41.668 | 47.389 | 2.000000 / 2.000000 | 7.000000 | 32768.000 | [cell](cases/chr1-g16384.json) |
| chr1 | 16384 / 16384 | BGZF | 79823587 | 247976 | 80071563 | 3.171358 | 42.280 | 46.257 | 2.000000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/chr1-g16384.json) |

ACEAPEX has lower p50 and fewer stored bytes in this cell; its p99 and physical amplification are higher than both alternatives. The full grid below is retained without pooling windows into a new forecast HIT.

The primary outcome does not generalize to the window set. For example, the frozen t2t-00/g16384 cell has ACEAPEX p50 25868 ns / stored 112758 B, zstd-seekable p50 11932 ns / stored 102259 B, BGZF p50 10349 ns / stored 99992 B. Every window result remains visible below; no pooled window latency replaces these comparisons.

## Two-constant calibration and the one permitted decomposition

Only four standalone zstd L3 frames from the first chr1 bytes enter the fit. Each uses one persistent ZSTD_DCtx, twelve warmups and 1000 individual frame decodes. Coefficients use deterministic nonnegative exact least squares; no ACE latency enters the fit.

| Decoded frame B | Observed p50 ns | Predicted ns, exact | Residual ns, exact | Raw timing |
|---:|---:|---:|---:|---|
| 4096 | 421 | 11567801/4369 | -9728452/4369 | [raw](raw/constants/frame-4096/zstd/attempt-1/result.json) |
| 16384 | 8265 | 46271204/4369 | -10161419/4369 | [raw](raw/constants/frame-16384/zstd/attempt-1/result.json) |
| 65536 | 43823 | 185084816/4369 | 6377871/4369 | [raw](raw/constants/frame-65536/zstd/attempt-1/result.json) |
| 262144 | 169268 | 740339264/4369 | -807372/4369 | [raw](raw/constants/frame-262144/zstd/attempt-1/result.json) |

`c_call = 0 ns/call`; `c_byte = 11567801/17895424 ns/B`; exact squared residual sum `54755390810/4369 ns²`. The fitted call coefficient lies on its nonnegative boundary.

For each of 1000 primary queries, mᵢ=Kᵢ×c_call+Dᵢ×c_byte using actual zstd invocation/output-byte counters. Sort by (mᵢ,query id) and take rank 500; query **625** is the representative (1 call, 65536 zstd output B). This is the median of joint per-query predictions, not a sum of independent medians. The signed residual is measured p50 minus predicted p50.

| Primary component | Exact ns | Exact signed share | Display share |
|---|---:|---:|---:|
| Calls (model) | 0 | 0 | 0.000% |
| Zstd output bytes (model) | 185084816/4369 | 26440688/20416337 | 129.508% |
| Residual (model overprediction if negative) | -42170457/4369 | -6024351/20416337 | -29.508% |

Exact additive total: 32711 ns and share 1. These values do not isolate causal decoder costs; the primary calibration failure limits such an interpretation.

## Method, admission and correctness

Each timed pass opens one fresh persistent reader handle outside the per-query timer, runs the same twelve warmups and 1000 uniform requests, and checks every returned byte outside the interval. Requests use the frozen per-corpus seeded trace shared across all g values and codecs. p50 and p99 are nearest ranks 500 and 990; all gates compare integer/fraction values before rounding. The separate counter build follows the same trace/cache lifecycle without timing-counter work in the published latency interval.

| AA method gate, chr1/g16384 | First p50 ns | Second p50 ns | abs difference / first | Strict <5% |
|---|---:|---:|---:|---|
| ACEAPEX | 33402 | 32972 | 1.287% | PASS |
| zstd-seekable | 41228 | 41217 | 0.027% | PASS |
| BGZF | 42180 | 42540 | 0.853% | PASS |

The aligned/crossing negative controls use fresh handles and the first usable actual native boundary chosen from archive metadata. Materialized bytes increased as follows:

| Codec | Aligned B | Crossing B |
|---|---:|---:|
| ACEAPEX | 69632 | 135168 |
| zstd-seekable | 16384 | 32768 |
| BGZF | 16384 | 32768 |

Known API controls restore one frame with exactly one DCtx call / 4096 output bytes, one one-shot call / 4096 output bytes, and zero API calls for plain copy. ACE cache-hit work is zero; two distinct misses and invalid-range/corrupt-magic rejection also pass. [Controls](controls.json) · [AA method](method-check.json).

All actual timing units use blocking `flock /run/lock/ovh-bench.lock`, worker CPU0 and T=1. LOADED means load1−1>1 at either boundary or a foreign live process consuming strictly >10% of one CPU at admission, derived from a retained ≥1-second tick delta. Exactly load1=2.00 and foreign CPU=10% pass. Other-core raw CPU accounting is observational. Each logical unit accepts its first CLEAN, retains every LOADED attempt, allows at most three attempts and never retries a worker error or a slow elapsed result.

| Saved trial accounting | Count |
|---|---:|
| Accepted logical timing units (285 cells + 3 AA + 4 constants) | 292 |
| Total attempts | 300 |
| Units retaken due to load | 6 |
| LOADED attempts, excluded from timing results | 8 |
| LOADED admissions before worker start (no benchmark timer) | 8 |
| LOADED attempts after worker start | 0 |
| Accepted per-query timing observations, including both AA passes | 295000 |
| Main-grid untimed counter requests | 285000 |
| Independent GNU dd+cmp observation documents | 1151 |
| Independently compared returned regions, including retained duplicate/control captures | 1146010 |

The final auditor checked every referenced private artifact on the measured host: zero unavailable files. GNU dd extracts the exact source slices and cmp checks captures independently, including every retained LOADED result when present. [Full output proof](audit/outputs-final.json) · [Independent final audit](audit/final.json) (SHA256 `34143d5bd3a5d5559af6046037a3393c5867c68881afc9596676d8a144ec0914`). The audit binds this generator and the numerical run inputs; historical document line references below provide context rather than new numerical evidence.

## Corpus and version provenance

ACEAPEX tag v2.6.5 points to `ce6b6740c7aae8a01720d615ae024c181b7d52b6`. Its actual CLI string is `aceapex 2.6.5-dev (format ACEPX2, libzstd 1.5.7)`, public API header 2.6.5, and literal C99 decoder header **2.6.4**. The linked zstd API is 10507 / 1.5.7. Preserve those distinct identities rather than patching upstream version strings. ACE interactive L2 uses one encoder thread, LIT_CHUNK=65536, FSE_CHUNK=4096; zstd-seekable is L3; BGZF is L6. The timed production readers are unchanged; counters are separate builds.

| Dependency | Exact source commit |
|---|---|
| aceapex | `ce6b6740c7aae8a01720d615ae024c181b7d52b6` |
| zstd | `f8745da6ff1ad1e7bab384bd1f9d742439278e99` |
| htslib | `4b705e4fada8ee2b6b15746f725ee8ac51631803` |
| libdeflate | `dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f` |

Chr1 retains the complete supplied FASTA bytes (MD5 `9465e0f0df6e2c6eb39729c39cee5465`). The thirty windows are the pre-existing 2 MiB manifest selection; their exact bytes were recovered from the verified canonical FASTA, not resampled. Reference corpora are held outside the P2 target grid. All input SHA256 values follow.

| Corpus | Input B | SHA256 |
|---|---:|---|
| chr1 | 253935557 | `04ee6db2e94ccc4daddc168453189d8c17a01454ba67ac0443a73a0401408ee0` |
| t2t-00 | 2097152 | `cd6e23b97a2b8ae81727b2918e20a2abc228862948b00af3b7311fa0c9269887` |
| t2t-01 | 2097152 | `a9b1a67892cc0015ac40428648f8034d2ecc679d8ab7088c00342c2bf94effe4` |
| t2t-02 | 2097152 | `50159e420399de7528f897484f9e319c350e461c8ddd4e2778b595cd77d50ddb` |
| t2t-03 | 2097152 | `8b9c1a5091058576e5c8ebf3d203e11515ba6e8f8e281fb389cb24725d0c34db` |
| t2t-04 | 2097152 | `40367650339d60e93e7acaac2782a7d4138b2c14a481894ffb2f5a0e5321bc6e` |
| t2t-05 | 2097152 | `49caf74dae023ab87674915caa7d8980c852eaa09022c61763968ca9fadd7d7d` |
| t2t-06 | 2097152 | `5141dce04b7f862dddb6512a10be10c4ab3a20feac7bec71a8f6da4b6c4f74f0` |
| t2t-07 | 2097152 | `a57210bad8617538c161fa640de3565cb945db10a60b58b3e334f1cdd9a6207f` |
| t2t-08 | 2097152 | `e7c2736b8c644a8165f2aa5ea9677b27f396bbce72945af5d5e9641060adf78e` |
| t2t-09 | 2097152 | `89143959cdf65e3475af574fea0c580eb67a9bd9dba30887cf80d7fe784087ae` |
| t2t-10 | 2097152 | `97195caebd8ddb853da4b7e3e0a1e1e13fc9c8206b70faffedbb94deed0e9826` |
| t2t-11 | 2097152 | `935e52de423673da74dcea6c6ac09c41ee1bcf3566e5a2c3b69252f37bb97577` |
| t2t-12 | 2097152 | `0c596e36ba77cb9bff63c142a83fa9c9ec8662064e8483da7a9e50bdb6d9d458` |
| t2t-13 | 2097152 | `16b9db5de2a24d143b395bb7e84213bf7426ae912bf6256d13572f44f567acef` |
| t2t-14 | 2097152 | `eb638fe43f638421f3c0f6a23a6e9555700714b34baf6e32d9cc93e26ae997e6` |
| t2t-15 | 2097152 | `9dbad6136e0d5157dc3598112b0668465e2f1185c6f1ef5c550a3471cf5828c9` |
| t2t-16 | 2097152 | `8797f6e8e851e65656bf14d3649a51519d80902b1b00b8f017aa2f3e3bd563fd` |
| t2t-17 | 2097152 | `af8f7a9650c2098b7691e5adb81ce1ce56a18ab081d7d9d0af6b0d61cfe8b509` |
| t2t-18 | 2097152 | `4fbfc4f15396c2f22683b48bca1fd31ae0deb828a89e4a91c6be636e8ae2a093` |
| t2t-19 | 2097152 | `ba6c93ae7bbe51a0fc3d81015a859ee79dd03d90a3a8c5994d13698582471c35` |
| t2t-20 | 2097152 | `01743772ed1db0f86c875debebdbfde535e7d935f1c0d1c2ce7973d373feccbc` |
| t2t-21 | 2097152 | `3e53a33f555899046e348f2f95cbc2ea4e3a0344280adfd63272077009a25930` |
| t2t-22 | 2097152 | `cb36999c1a1deac13278b58c9eac02a6e9f78b858bea13c0a627ada6e32bb503` |
| t2t-23 | 2097152 | `df36fc1dd88af16e03668b8dc81c9d41ee9aba2c9439d67d4f316d12ffbc4478` |
| t2t-24 | 2097152 | `45385e445c55a433c6fc62ebcecd6a4a1b0c2b7e17fe171b9b62a553a548d22e` |
| t2t-25 | 2097152 | `6c9e362351e6e473706f85333fcd57949878adfab37caeb56621a7f693887441` |
| t2t-26 | 2097152 | `dc7fc08aadbcae3d33072e08694c63e8baa3823b067a2746982ddde5134a9c93` |
| t2t-27 | 2097152 | `3a2a161000d6b50ed95ba3ca56d5df26fbeb1cfd10f6547c00cc4446e7376c26` |
| t2t-28 | 2097152 | `c0ef1a2bd81c9cf02eddf68b26c1aedfda7ef8c50ac62a5321b027cbf7674e19` |
| t2t-29 | 2097152 | `8b3db2f0e64c9df8dae8cd7efd30da68185050fc9b51d2da4734b054bc73d72f` |
| enwik8 | 100000000 | `2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8` |
| silesia | 211947520 | `a667bac80089b3d04d5496772149e632f0758974b0579d743cd8d6e5e0d63eb2` |

[Setup and origin coordinates](setup.json) · [Native build](native/build.json) · [Frozen manifest](../t2t-regions-20260916/manifest.json). The prior v2.2.0 adapter remains as `codecs/aceapex_v220.sh`; the active adapter changes only its release pin, label and version.

Source foundations: [SOURCE_PATHS.md:56](SOURCE_PATHS.md#actual-persistent-read-path-and-work-counters) documents the persistent decoder/cache and actual API counters. [ACEAPEX_SNAPSHOTS.md:5](../../docs/RESULTS/ACEAPEX_SNAPSHOTS.md#same-run-chr1-refresh--2026-11-26) contains this same-run refresh; [the preserved historical chr1 table, line 50](../../docs/RESULTS/ACEAPEX_SNAPSHOTS.md#historical-chr1-snapshot--2026-09-10-aceapex-before-v210) belongs to its older sources/host and supports no numerical cross-host speedup claim here.

## Foundations and closed directions

- [README.md@e8aa8488:26](https://github.com/yasha1971-coder/hw-apex-bench/blob/e8aa8488310d8cb7d5793f2e49a707c67f80b689/README.md#L26) is the retained chrX pick example, a separate corpus/evidence scope linked to the snapshot collection.
- [ACEAPEX_SNAPSHOTS.md:19](../../docs/RESULTS/ACEAPEX_SNAPSHOTS.md#matched-g-refresh-aceapex-v210--main-open-vs-bgzf--2026-09-30) retains the 2026-09-30 thirty-window v2.1.0 matched-g refresh: at 16 KiB, ACE/BGZF p50 were 0.074632/0.065482 ms; that table has no zstd row. Its values are not pooled with this host or used as a measured old/new speedup.
- [CHR1_LIT16_20260918.md:21,23](../../docs/RESULTS/CHR1_LIT16_20260918.md#result) retains the earlier literal-layer tradeoff (p50 −14.86%, ratio −3.319%). [Its DCtx audit, line 52](../../docs/RESULTS/CHR1_LIT16_20260918.md#dctx-audit) describes an older one-shot path; the present pinned C99 reader already reuses DCtx and caches.
- [PROTOCOL.md:28](PROTOCOL.md#pins-inputs-and-grid) closes persistent-DCtx, literal-chunk and FSE-chunk optimization in this task; [SOURCE_PATHS.md:24](SOURCE_PATHS.md#what-was-already-measured) also records the closed FSE/DCtx retry directions. Those levers were not reopened to rescue the forecasts.

## Complete comparative grid

Ratio is input bytes / (archive + every required index). BGZF at nominal g=65536 B has actual cap **65280 B**; the required `.gzi` bytes are included separately and in stored bytes. Physical amplification is materialized bytes / requested bytes; it includes non-zstd paths and remains separate from actual zstd output bytes. Per-request call and byte columns are means, including legitimate cache-hit/bypass zeros. The CSV keeps exact ns, bytes, totals, fractions, archive/index SHA256 values and raw links; only this Markdown display is rounded. [TABLE.csv](TABLE.csv).

| Corpus | g nominal / actual B | Codec | Archive B | Index B | Stored B | Ratio | p50 µs | p99 µs | Amp mean / p50 | Zstd calls/request | Zstd output B/request | Raw |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| chr1 | 16384 / 16384 | ACEAPEX | 60440764 | 0 | 60440764 | 4.201396 | 32.711 | 54.592 | 5.996250 / 4.250000 | 6.582000 | 50970.755 | [cell](cases/chr1-g16384.json) |
| chr1 | 16384 / 16384 | zstd-seekable | 83924167 | 0 | 83924167 | 3.025774 | 41.668 | 47.389 | 2.000000 / 2.000000 | 7.000000 | 32768.000 | [cell](cases/chr1-g16384.json) |
| chr1 | 16384 / 16384 | BGZF | 79823587 | 247976 | 80071563 | 3.171358 | 42.280 | 46.257 | 2.000000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/chr1-g16384.json) |
| chr1 | 4096 / 4096 | ACEAPEX | 63421483 | 0 | 63421483 | 4.003936 | 27.641 | 54.651 | 5.375314 / 4.250000 | 5.961000 | 46185.937 | [cell](cases/chr1-g4096.json) |
| chr1 | 4096 / 4096 | zstd-seekable | 87184580 | 0 | 87184580 | 2.912620 | 31.808 | 35.615 | 1.250000 / 1.250000 | 16.000000 | 20480.000 | [cell](cases/chr1-g4096.json) |
| chr1 | 4096 / 4096 | BGZF | 83872997 | 991928 | 84864925 | 2.992232 | 33.571 | 36.798 | 1.250000 / 1.250000 | 0.000000 | 0.000 | [cell](cases/chr1-g4096.json) |
| chr1 | 65536 / 65536 | ACEAPEX | 59667955 | 0 | 59667955 | 4.255811 | 47.608 | 80.789 | 8.859565 / 8.250000 | 9.651000 | 72750.635 | [cell](cases/chr1-g65536.json) |
| chr1 | 65536 / 65536 | zstd-seekable | 80693943 | 0 | 80693943 | 3.146897 | 56.344 | 115.213 | 4.956000 / 4.000000 | 4.718000 | 81199.104 | [cell](cases/chr1-g65536.json) |
| chr1 | 65536 / 65280 | BGZF | 75012615 | 62232 | 75074847 | 3.382432 | 69.919 | 143.585 | 5.008359 / 3.984375 | 0.000000 | 0.000 | [cell](cases/chr1-g65536.json) |
| t2t-00 | 4096 / 4096 | ACEAPEX | 142163 | 0 | 142163 | 14.751743 | 25.548 | 54.120 | 3.807150 / 4.140747 | 1.567000 | 58485.148 | [cell](cases/t2t-00-g4096.json) |
| t2t-00 | 4096 / 4096 | zstd-seekable | 211754 | 0 | 211754 | 9.903718 | 16.110 | 19.656 | 1.250000 / 1.250000 | 16.000000 | 20480.000 | [cell](cases/t2t-00-g4096.json) |
| t2t-00 | 4096 / 4096 | BGZF | 198609 | 8184 | 206793 | 10.141310 | 15.138 | 17.222 | 1.249500 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-00-g4096.json) |
| t2t-00 | 16384 / 16384 | ACEAPEX | 112758 | 0 | 112758 | 18.598698 | 25.868 | 60.371 | 3.490145 / 4.250000 | 1.842000 | 40757.576 | [cell](cases/t2t-00-g16384.json) |
| t2t-00 | 16384 / 16384 | zstd-seekable | 102259 | 0 | 102259 | 20.508239 | 11.932 | 16.510 | 1.997000 / 2.000000 | 6.994000 | 32718.848 | [cell](cases/t2t-00-g16384.json) |
| t2t-00 | 16384 / 16384 | BGZF | 97952 | 2040 | 99992 | 20.973198 | 10.349 | 13.004 | 1.993000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-00-g16384.json) |
| t2t-00 | 65536 / 65536 | ACEAPEX | 100517 | 0 | 100517 | 20.863655 | 32.660 | 69.628 | 3.682457 / 4.250000 | 2.357000 | 36126.018 | [cell](cases/t2t-00-g65536.json) |
| t2t-00 | 65536 / 65536 | zstd-seekable | 60149 | 0 | 60149 | 34.865950 | 15.949 | 38.962 | 4.904000 / 4.000000 | 4.688000 | 80347.136 | [cell](cases/t2t-00-g65536.json) |
| t2t-00 | 65536 / 65280 | BGZF | 64811 | 520 | 65331 | 32.100412 | 11.562 | 25.657 | 4.834547 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-00-g65536.json) |
| t2t-01 | 4096 / 4096 | ACEAPEX | 571744 | 0 | 571744 | 3.667991 | 24.826 | 51.395 | 4.689993 / 4.000000 | 2.505000 | 29160.442 | [cell](cases/t2t-01-g4096.json) |
| t2t-01 | 4096 / 4096 | zstd-seekable | 731927 | 0 | 731927 | 2.865247 | 29.765 | 34.804 | 1.249750 / 1.250000 | 15.998000 | 20475.904 | [cell](cases/t2t-01-g4096.json) |
| t2t-01 | 4096 / 4096 | BGZF | 686451 | 8184 | 694635 | 3.019070 | 31.107 | 34.384 | 1.249750 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-01-g4096.json) |
| t2t-01 | 16384 / 16384 | ACEAPEX | 548318 | 0 | 548318 | 3.824700 | 25.618 | 52.427 | 5.334243 / 4.000000 | 2.799000 | 33009.257 | [cell](cases/t2t-01-g16384.json) |
| t2t-01 | 16384 / 16384 | zstd-seekable | 706609 | 0 | 706609 | 2.967910 | 38.962 | 44.041 | 1.998000 / 2.000000 | 6.996000 | 32735.232 | [cell](cases/t2t-01-g16384.json) |
| t2t-01 | 16384 / 16384 | BGZF | 653762 | 2040 | 655802 | 3.197843 | 38.381 | 41.737 | 1.994000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-01-g16384.json) |
| t2t-01 | 65536 / 65536 | ACEAPEX | 541944 | 0 | 541944 | 3.869684 | 48.119 | 77.674 | 7.858488 / 8.000000 | 4.056000 | 48480.080 | [cell](cases/t2t-01-g65536.json) |
| t2t-01 | 65536 / 65536 | zstd-seekable | 679785 | 0 | 679785 | 3.085022 | 51.856 | 108.822 | 4.892000 / 4.000000 | 4.678000 | 80150.528 | [cell](cases/t2t-01-g65536.json) |
| t2t-01 | 65536 / 65280 | BGZF | 623025 | 520 | 623545 | 3.363273 | 61.113 | 124.711 | 4.762328 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-01-g65536.json) |
| t2t-02 | 4096 / 4096 | ACEAPEX | 583917 | 0 | 583917 | 3.591524 | 25.327 | 53.338 | 4.586180 / 4.000000 | 2.385000 | 28369.104 | [cell](cases/t2t-02-g4096.json) |
| t2t-02 | 4096 / 4096 | zstd-seekable | 766341 | 0 | 766341 | 2.736578 | 30.026 | 34.233 | 1.250000 / 1.250000 | 16.000000 | 20480.000 | [cell](cases/t2t-02-g4096.json) |
| t2t-02 | 4096 / 4096 | BGZF | 729640 | 8184 | 737824 | 2.842347 | 31.879 | 34.704 | 1.250000 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-02-g4096.json) |
| t2t-02 | 16384 / 16384 | ACEAPEX | 559058 | 0 | 559058 | 3.751224 | 26.188 | 52.978 | 5.232252 / 4.000000 | 2.673000 | 32261.436 | [cell](cases/t2t-02-g16384.json) |
| t2t-02 | 16384 / 16384 | zstd-seekable | 740705 | 0 | 740705 | 2.831292 | 39.453 | 45.183 | 1.996000 / 2.000000 | 6.992000 | 32702.464 | [cell](cases/t2t-02-g16384.json) |
| t2t-02 | 16384 / 16384 | BGZF | 690301 | 2040 | 692341 | 3.029074 | 39.904 | 42.649 | 1.994000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-02-g16384.json) |
| t2t-02 | 65536 / 65536 | ACEAPEX | 552889 | 0 | 552889 | 3.793080 | 50.503 | 81.390 | 7.892016 / 8.000000 | 4.032000 | 48663.466 | [cell](cases/t2t-02-g65536.json) |
| t2t-02 | 65536 / 65536 | zstd-seekable | 704997 | 0 | 704997 | 2.974696 | 52.938 | 109.402 | 4.916000 / 4.000000 | 4.702000 | 80543.744 | [cell](cases/t2t-02-g65536.json) |
| t2t-02 | 65536 / 65280 | BGZF | 649766 | 520 | 650286 | 3.224969 | 63.107 | 127.877 | 4.887844 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-02-g65536.json) |
| t2t-03 | 4096 / 4096 | ACEAPEX | 79320 | 0 | 79320 | 26.439133 | 9.608 | 22.151 | 3.882824 / 4.000000 | 1.178000 | 63616.193 | [cell](cases/t2t-03-g4096.json) |
| t2t-03 | 4096 / 4096 | zstd-seekable | 229307 | 0 | 229307 | 9.145608 | 15.429 | 19.055 | 1.249750 / 1.250000 | 15.998000 | 20475.904 | [cell](cases/t2t-03-g4096.json) |
| t2t-03 | 4096 / 4096 | BGZF | 211155 | 8184 | 219339 | 9.561236 | 16.641 | 19.396 | 1.249500 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-03-g4096.json) |
| t2t-03 | 16384 / 16384 | ACEAPEX | 43065 | 0 | 43065 | 48.697364 | 8.797 | 19.085 | 2.076656 / 1.997375 | 0.558000 | 34023.931 | [cell](cases/t2t-03-g16384.json) |
| t2t-03 | 16384 / 16384 | zstd-seekable | 77439 | 0 | 77439 | 27.081341 | 9.057 | 12.003 | 1.996000 / 2.000000 | 6.992000 | 32702.464 | [cell](cases/t2t-03-g16384.json) |
| t2t-03 | 16384 / 16384 | BGZF | 77876 | 2040 | 79916 | 26.241954 | 10.129 | 11.551 | 1.990000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-03-g16384.json) |
| t2t-03 | 65536 / 65536 | ACEAPEX | 28283 | 0 | 28283 | 74.148853 | 2.805 | 7.193 | 0.000000 / 0.000000 | 0.000000 | 0.000 | [cell](cases/t2t-03-g65536.json) |
| t2t-03 | 65536 / 65536 | zstd-seekable | 33178 | 0 | 33178 | 63.209114 | 8.656 | 19.947 | 4.896000 / 4.000000 | 4.689000 | 80216.064 | [cell](cases/t2t-03-g65536.json) |
| t2t-03 | 65536 / 65280 | BGZF | 40374 | 520 | 40894 | 51.282633 | 9.738 | 18.955 | 4.847000 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-03-g65536.json) |
| t2t-04 | 4096 / 4096 | ACEAPEX | 555464 | 0 | 555464 | 3.775496 | 24.435 | 57.877 | 4.690718 / 4.000000 | 2.388000 | 32194.504 | [cell](cases/t2t-04-g4096.json) |
| t2t-04 | 4096 / 4096 | zstd-seekable | 731314 | 0 | 731314 | 2.867649 | 30.186 | 34.674 | 1.250000 / 1.250000 | 16.000000 | 20480.000 | [cell](cases/t2t-04-g4096.json) |
| t2t-04 | 4096 / 4096 | BGZF | 687127 | 8184 | 695311 | 3.016135 | 31.168 | 34.364 | 1.250000 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-04-g4096.json) |
| t2t-04 | 16384 / 16384 | ACEAPEX | 531360 | 0 | 531360 | 3.946763 | 26.058 | 58.248 | 5.328449 / 4.000000 | 2.662000 | 36210.707 | [cell](cases/t2t-04-g16384.json) |
| t2t-04 | 16384 / 16384 | zstd-seekable | 702549 | 0 | 702549 | 2.985062 | 38.671 | 43.321 | 1.996000 / 2.000000 | 6.992000 | 32702.464 | [cell](cases/t2t-04-g16384.json) |
| t2t-04 | 16384 / 16384 | BGZF | 651031 | 2040 | 653071 | 3.211216 | 38.141 | 42.398 | 1.989000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-04-g16384.json) |
| t2t-04 | 65536 / 65536 | ACEAPEX | 524154 | 0 | 524154 | 4.001023 | 47.638 | 85.659 | 7.821610 / 8.000000 | 3.886000 | 52978.546 | [cell](cases/t2t-04-g65536.json) |
| t2t-04 | 65536 / 65536 | zstd-seekable | 643227 | 0 | 643227 | 3.260361 | 51.766 | 108.081 | 4.892000 / 4.000000 | 4.680000 | 80150.528 | [cell](cases/t2t-04-g65536.json) |
| t2t-04 | 65536 / 65280 | BGZF | 598462 | 520 | 598982 | 3.501194 | 60.422 | 124.892 | 4.836547 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-04-g65536.json) |
| t2t-05 | 4096 / 4096 | ACEAPEX | 586413 | 0 | 586413 | 3.576237 | 26.570 | 54.641 | 4.605858 / 4.000000 | 2.372000 | 28430.301 | [cell](cases/t2t-05-g4096.json) |
| t2t-05 | 4096 / 4096 | zstd-seekable | 769957 | 0 | 769957 | 2.723726 | 29.875 | 34.173 | 1.249750 / 1.250000 | 15.998000 | 20475.904 | [cell](cases/t2t-05-g4096.json) |
| t2t-05 | 4096 / 4096 | BGZF | 734879 | 8184 | 743063 | 2.822307 | 31.689 | 34.734 | 1.249250 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-05-g4096.json) |
| t2t-05 | 16384 / 16384 | ACEAPEX | 561724 | 0 | 561724 | 3.733421 | 27.471 | 54.581 | 5.302453 / 4.000000 | 2.699000 | 32661.960 | [cell](cases/t2t-05-g16384.json) |
| t2t-05 | 16384 / 16384 | zstd-seekable | 744527 | 0 | 744527 | 2.816757 | 39.143 | 43.741 | 1.998000 / 2.000000 | 6.996000 | 32735.232 | [cell](cases/t2t-05-g16384.json) |
| t2t-05 | 16384 / 16384 | BGZF | 693756 | 2040 | 695796 | 3.014033 | 39.854 | 43.301 | 1.993000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-05-g16384.json) |
| t2t-05 | 65536 / 65536 | ACEAPEX | 555309 | 0 | 555309 | 3.776550 | 52.758 | 83.885 | 7.693624 / 8.000000 | 3.924000 | 47416.422 | [cell](cases/t2t-05-g65536.json) |
| t2t-05 | 65536 / 65536 | zstd-seekable | 710998 | 0 | 710998 | 2.949589 | 53.088 | 109.894 | 4.860000 / 4.000000 | 4.663000 | 79626.240 | [cell](cases/t2t-05-g65536.json) |
| t2t-05 | 65536 / 65280 | BGZF | 655966 | 520 | 656486 | 3.194511 | 63.849 | 129.270 | 4.734938 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-05-g65536.json) |
| t2t-06 | 4096 / 4096 | ACEAPEX | 108009 | 0 | 108009 | 19.416456 | 16.882 | 36.628 | 4.170444 / 4.000000 | 1.376000 | 68328.558 | [cell](cases/t2t-06-g4096.json) |
| t2t-06 | 4096 / 4096 | zstd-seekable | 240589 | 0 | 240589 | 8.716741 | 16.660 | 19.997 | 1.249750 / 1.250000 | 15.998000 | 20475.904 | [cell](cases/t2t-06-g4096.json) |
| t2t-06 | 4096 / 4096 | BGZF | 230018 | 8184 | 238202 | 8.804091 | 16.160 | 18.314 | 1.249500 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-06-g4096.json) |
| t2t-06 | 16384 / 16384 | ACEAPEX | 79383 | 0 | 79383 | 26.418150 | 19.035 | 43.260 | 3.403254 / 4.000000 | 1.222000 | 55758.912 | [cell](cases/t2t-06-g16384.json) |
| t2t-06 | 16384 / 16384 | zstd-seekable | 90115 | 0 | 90115 | 23.271953 | 10.159 | 15.298 | 1.995000 / 2.000000 | 6.990000 | 32686.080 | [cell](cases/t2t-06-g16384.json) |
| t2t-06 | 16384 / 16384 | BGZF | 92224 | 2040 | 94264 | 22.247645 | 10.118 | 12.353 | 1.993000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-06-g16384.json) |
| t2t-06 | 65536 / 65536 | ACEAPEX | 62381 | 0 | 62381 | 33.618442 | 21.470 | 54.391 | 2.840257 / 4.000000 | 1.120000 | 46534.776 | [cell](cases/t2t-06-g65536.json) |
| t2t-06 | 65536 / 65536 | zstd-seekable | 44726 | 0 | 44726 | 46.888879 | 11.701 | 27.561 | 4.952000 / 4.000000 | 4.733000 | 81133.568 | [cell](cases/t2t-06-g65536.json) |
| t2t-06 | 65536 / 65280 | BGZF | 51094 | 520 | 51614 | 40.631457 | 10.319 | 21.140 | 4.838031 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-06-g65536.json) |
| t2t-07 | 4096 / 4096 | ACEAPEX | 581288 | 0 | 581288 | 3.607768 | 24.726 | 50.955 | 4.422070 / 4.000000 | 2.302000 | 27339.277 | [cell](cases/t2t-07-g4096.json) |
| t2t-07 | 4096 / 4096 | zstd-seekable | 760463 | 0 | 760463 | 2.757730 | 30.196 | 34.554 | 1.250000 / 1.250000 | 16.000000 | 20480.000 | [cell](cases/t2t-07-g4096.json) |
| t2t-07 | 4096 / 4096 | BGZF | 724622 | 8184 | 732806 | 2.861811 | 31.889 | 34.544 | 1.250000 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-07-g4096.json) |
| t2t-07 | 16384 / 16384 | ACEAPEX | 556429 | 0 | 556429 | 3.768948 | 25.267 | 50.684 | 5.139484 / 4.000000 | 2.624000 | 31663.711 | [cell](cases/t2t-07-g16384.json) |
| t2t-07 | 16384 / 16384 | zstd-seekable | 732585 | 0 | 732585 | 2.862674 | 39.673 | 44.783 | 1.998000 / 2.000000 | 6.996000 | 32735.232 | [cell](cases/t2t-07-g16384.json) |
| t2t-07 | 16384 / 16384 | BGZF | 683141 | 2040 | 685181 | 3.060727 | 39.634 | 42.720 | 1.994000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-07-g16384.json) |
| t2t-07 | 65536 / 65536 | ACEAPEX | 550749 | 0 | 550749 | 3.807818 | 48.631 | 78.686 | 7.908911 / 8.000000 | 4.042000 | 48748.393 | [cell](cases/t2t-07-g65536.json) |
| t2t-07 | 65536 / 65536 | zstd-seekable | 699559 | 0 | 699559 | 2.997820 | 53.379 | 110.576 | 4.908000 / 4.000000 | 4.694000 | 80412.672 | [cell](cases/t2t-07-g65536.json) |
| t2t-07 | 65536 / 65280 | BGZF | 642904 | 520 | 643424 | 3.259362 | 62.566 | 127.186 | 4.866922 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-07-g65536.json) |
| t2t-08 | 4096 / 4096 | ACEAPEX | 583453 | 0 | 583453 | 3.594380 | 25.187 | 52.287 | 4.668848 / 4.000000 | 2.412000 | 28840.193 | [cell](cases/t2t-08-g4096.json) |
| t2t-08 | 4096 / 4096 | zstd-seekable | 766268 | 0 | 766268 | 2.736839 | 30.346 | 35.135 | 1.249750 / 1.250000 | 15.998000 | 20475.904 | [cell](cases/t2t-08-g4096.json) |
| t2t-08 | 4096 / 4096 | BGZF | 728894 | 8184 | 737078 | 2.845224 | 31.909 | 34.705 | 1.249750 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-08-g4096.json) |
| t2t-08 | 16384 / 16384 | ACEAPEX | 558941 | 0 | 558941 | 3.752010 | 26.560 | 53.860 | 5.307641 / 4.000000 | 2.685000 | 32667.470 | [cell](cases/t2t-08-g16384.json) |
| t2t-08 | 16384 / 16384 | zstd-seekable | 739455 | 0 | 739455 | 2.836078 | 39.513 | 44.493 | 1.994000 / 2.000000 | 6.988000 | 32669.696 | [cell](cases/t2t-08-g16384.json) |
| t2t-08 | 16384 / 16384 | BGZF | 689848 | 2040 | 691888 | 3.031057 | 40.144 | 43.491 | 1.990000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-08-g16384.json) |
| t2t-08 | 65536 / 65536 | ACEAPEX | 552423 | 0 | 552423 | 3.796279 | 50.244 | 81.552 | 7.919724 / 8.000000 | 4.032000 | 48795.518 | [cell](cases/t2t-08-g65536.json) |
| t2t-08 | 65536 / 65536 | zstd-seekable | 706906 | 0 | 706906 | 2.966663 | 54.531 | 112.198 | 4.964000 / 4.000000 | 4.743000 | 81330.176 | [cell](cases/t2t-08-g65536.json) |
| t2t-08 | 65536 / 65280 | BGZF | 651133 | 520 | 651653 | 3.218204 | 62.967 | 129.581 | 4.877875 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-08-g65536.json) |
| t2t-09 | 4096 / 4096 | ACEAPEX | 81368 | 0 | 81368 | 25.773670 | 9.097 | 20.418 | 4.514410 / 4.000000 | 1.306000 | 73964.099 | [cell](cases/t2t-09-g4096.json) |
| t2t-09 | 4096 / 4096 | zstd-seekable | 302940 | 0 | 302940 | 6.922665 | 18.885 | 21.430 | 1.249500 / 1.250000 | 15.996000 | 20471.808 | [cell](cases/t2t-09-g4096.json) |
| t2t-09 | 4096 / 4096 | BGZF | 290997 | 8184 | 299181 | 7.009643 | 17.172 | 19.476 | 1.249500 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-09-g4096.json) |
| t2t-09 | 16384 / 16384 | ACEAPEX | 55256 | 0 | 55256 | 37.953381 | 9.357 | 21.330 | 4.187269 / 4.000000 | 1.132000 | 68604.208 | [cell](cases/t2t-09-g16384.json) |
| t2t-09 | 16384 / 16384 | zstd-seekable | 95692 | 0 | 95692 | 21.915646 | 9.949 | 12.754 | 1.993000 / 2.000000 | 6.986000 | 32653.312 | [cell](cases/t2t-09-g16384.json) |
| t2t-09 | 16384 / 16384 | BGZF | 102176 | 2040 | 104216 | 20.123129 | 10.700 | 12.273 | 1.992000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-09-g16384.json) |
| t2t-09 | 65536 / 65536 | ACEAPEX | 40214 | 0 | 40214 | 52.149799 | 10.410 | 26.991 | 3.735969 / 4.000000 | 0.936000 | 61210.116 | [cell](cases/t2t-09-g65536.json) |
| t2t-09 | 65536 / 65536 | zstd-seekable | 36149 | 0 | 36149 | 58.014108 | 9.147 | 18.876 | 4.880000 / 4.000000 | 4.678000 | 79953.920 | [cell](cases/t2t-09-g65536.json) |
| t2t-09 | 65536 / 65280 | BGZF | 48241 | 520 | 48761 | 43.008798 | 9.888 | 19.436 | 4.790719 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-09-g65536.json) |
| t2t-10 | 4096 / 4096 | ACEAPEX | 568951 | 0 | 568951 | 3.685998 | 23.484 | 50.193 | 4.447565 / 4.000000 | 2.369000 | 27626.601 | [cell](cases/t2t-10-g4096.json) |
| t2t-10 | 4096 / 4096 | zstd-seekable | 727458 | 0 | 727458 | 2.882850 | 29.605 | 34.063 | 1.249250 / 1.250000 | 15.994000 | 20467.712 | [cell](cases/t2t-10-g4096.json) |
| t2t-10 | 4096 / 4096 | BGZF | 686201 | 8184 | 694385 | 3.020157 | 30.767 | 33.732 | 1.249250 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-10-g4096.json) |
| t2t-10 | 16384 / 16384 | ACEAPEX | 543906 | 0 | 543906 | 3.855725 | 24.987 | 51.115 | 5.170146 / 4.000000 | 2.698000 | 31974.252 | [cell](cases/t2t-10-g16384.json) |
| t2t-10 | 16384 / 16384 | zstd-seekable | 698009 | 0 | 698009 | 3.004477 | 38.501 | 44.072 | 1.994000 / 2.000000 | 6.988000 | 32669.696 | [cell](cases/t2t-10-g16384.json) |
| t2t-10 | 16384 / 16384 | BGZF | 647270 | 2040 | 649310 | 3.229816 | 37.349 | 41.417 | 1.990000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-10-g16384.json) |
| t2t-10 | 65536 / 65536 | ACEAPEX | 537731 | 0 | 537731 | 3.900002 | 45.685 | 80.069 | 7.798951 / 8.000000 | 4.067000 | 48204.356 | [cell](cases/t2t-10-g65536.json) |
| t2t-10 | 65536 / 65536 | zstd-seekable | 666396 | 0 | 666396 | 3.147006 | 68.006 | 140.131 | 4.832000 / 4.000000 | 4.639000 | 79167.488 | [cell](cases/t2t-10-g65536.json) |
| t2t-10 | 65536 / 65280 | BGZF | 613254 | 520 | 613774 | 3.416815 | 60.292 | 125.603 | 4.734938 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-10-g65536.json) |
| t2t-11 | 4096 / 4096 | ACEAPEX | 585975 | 0 | 585975 | 3.578910 | 26.029 | 53.419 | 4.622396 / 4.000000 | 2.369000 | 28519.209 | [cell](cases/t2t-11-g4096.json) |
| t2t-11 | 4096 / 4096 | zstd-seekable | 768188 | 0 | 768188 | 2.729998 | 30.046 | 34.434 | 1.249750 / 1.250000 | 15.998000 | 20475.904 | [cell](cases/t2t-11-g4096.json) |
| t2t-11 | 4096 / 4096 | BGZF | 732636 | 8184 | 740820 | 2.830852 | 31.840 | 34.534 | 1.249750 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-11-g4096.json) |
| t2t-11 | 16384 / 16384 | ACEAPEX | 561465 | 0 | 561465 | 3.735143 | 26.820 | 54.191 | 5.357763 / 4.000000 | 2.713000 | 32988.234 | [cell](cases/t2t-11-g16384.json) |
| t2t-11 | 16384 / 16384 | zstd-seekable | 742323 | 0 | 742323 | 2.825121 | 39.533 | 44.353 | 1.995000 / 2.000000 | 6.990000 | 32686.080 | [cell](cases/t2t-11-g16384.json) |
| t2t-11 | 16384 / 16384 | BGZF | 694047 | 2040 | 696087 | 3.012773 | 39.954 | 45.966 | 1.994000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-11-g16384.json) |
| t2t-11 | 65536 / 65536 | ACEAPEX | 554955 | 0 | 554955 | 3.778959 | 51.826 | 83.305 | 7.967816 / 8.000000 | 4.050000 | 49082.956 | [cell](cases/t2t-11-g65536.json) |
| t2t-11 | 65536 / 65536 | zstd-seekable | 709619 | 0 | 709619 | 2.955321 | 56.655 | 116.838 | 4.896000 / 4.000000 | 4.688000 | 80216.064 | [cell](cases/t2t-11-g65536.json) |
| t2t-11 | 65536 / 65280 | BGZF | 654620 | 520 | 655140 | 3.201075 | 63.708 | 128.709 | 4.846500 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-11-g65536.json) |
| t2t-12 | 4096 / 4096 | ACEAPEX | 88451 | 0 | 88451 | 23.709760 | 11.090 | 29.816 | 4.455841 / 4.000000 | 1.277000 | 73004.507 | [cell](cases/t2t-12-g4096.json) |
| t2t-12 | 4096 / 4096 | zstd-seekable | 275175 | 0 | 275175 | 7.621157 | 17.934 | 21.771 | 1.250000 / 1.250000 | 16.000000 | 20480.000 | [cell](cases/t2t-12-g4096.json) |
| t2t-12 | 4096 / 4096 | BGZF | 263356 | 8184 | 271540 | 7.723179 | 17.492 | 19.426 | 1.250000 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-12-g4096.json) |
| t2t-12 | 16384 / 16384 | ACEAPEX | 58752 | 0 | 58752 | 35.694989 | 9.528 | 37.089 | 3.643293 / 4.000000 | 1.085000 | 59691.720 | [cell](cases/t2t-12-g16384.json) |
| t2t-12 | 16384 / 16384 | zstd-seekable | 91092 | 0 | 91092 | 23.022351 | 9.498 | 14.146 | 1.995000 / 2.000000 | 6.990000 | 32686.080 | [cell](cases/t2t-12-g16384.json) |
| t2t-12 | 16384 / 16384 | BGZF | 97354 | 2040 | 99394 | 21.099382 | 10.519 | 12.333 | 1.991000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-12-g16384.json) |
| t2t-12 | 65536 / 65536 | ACEAPEX | 44329 | 0 | 44329 | 47.308805 | 8.456 | 39.674 | 2.309914 / 0.000000 | 0.591000 | 37845.636 | [cell](cases/t2t-12-g65536.json) |
| t2t-12 | 65536 / 65536 | zstd-seekable | 40190 | 0 | 40190 | 52.180941 | 9.748 | 26.439 | 4.892000 / 4.000000 | 4.683000 | 80150.528 | [cell](cases/t2t-12-g65536.json) |
| t2t-12 | 65536 / 65280 | BGZF | 51398 | 520 | 51918 | 40.393544 | 10.530 | 23.284 | 4.859453 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-12-g65536.json) |
| t2t-13 | 4096 / 4096 | ACEAPEX | 560190 | 0 | 560190 | 3.743644 | 22.361 | 48.450 | 4.575064 / 4.000000 | 2.426000 | 28387.052 | [cell](cases/t2t-13-g4096.json) |
| t2t-13 | 4096 / 4096 | zstd-seekable | 719549 | 0 | 719549 | 2.914537 | 29.565 | 33.853 | 1.249750 / 1.250000 | 15.998000 | 20475.904 | [cell](cases/t2t-13-g4096.json) |
| t2t-13 | 4096 / 4096 | BGZF | 667382 | 8184 | 675566 | 3.104289 | 30.267 | 33.352 | 1.249750 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-13-g4096.json) |
| t2t-13 | 16384 / 16384 | ACEAPEX | 535939 | 0 | 535939 | 3.913042 | 23.303 | 47.098 | 5.226748 / 4.000000 | 2.698000 | 32267.577 | [cell](cases/t2t-13-g16384.json) |
| t2t-13 | 16384 / 16384 | zstd-seekable | 691631 | 0 | 691631 | 3.032183 | 37.901 | 43.010 | 1.999000 / 2.000000 | 6.998000 | 32751.616 | [cell](cases/t2t-13-g16384.json) |
| t2t-13 | 16384 / 16384 | BGZF | 635028 | 2040 | 637068 | 3.291881 | 36.568 | 40.796 | 1.998000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-13-g16384.json) |
| t2t-13 | 65536 / 65536 | ACEAPEX | 529233 | 0 | 529233 | 3.962625 | 44.072 | 72.936 | 7.683655 / 8.000000 | 3.918000 | 47333.751 | [cell](cases/t2t-13-g65536.json) |
| t2t-13 | 65536 / 65536 | zstd-seekable | 660429 | 0 | 660429 | 3.175439 | 51.466 | 107.981 | 4.872000 / 4.000000 | 4.670000 | 79822.848 | [cell](cases/t2t-13-g65536.json) |
| t2t-13 | 65536 / 65280 | BGZF | 606430 | 520 | 606950 | 3.455230 | 58.609 | 123.630 | 4.855469 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-13-g65536.json) |
| t2t-14 | 4096 / 4096 | ACEAPEX | 580362 | 0 | 580362 | 3.613524 | 24.766 | 51.506 | 4.523125 / 4.000000 | 2.340000 | 27943.958 | [cell](cases/t2t-14-g4096.json) |
| t2t-14 | 4096 / 4096 | zstd-seekable | 760601 | 0 | 760601 | 2.757230 | 29.986 | 34.735 | 1.249750 / 1.250000 | 15.998000 | 20475.904 | [cell](cases/t2t-14-g4096.json) |
| t2t-14 | 4096 / 4096 | BGZF | 731156 | 8184 | 739340 | 2.836519 | 31.749 | 34.525 | 1.249750 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-14-g4096.json) |
| t2t-14 | 16384 / 16384 | ACEAPEX | 555724 | 0 | 555724 | 3.773729 | 25.758 | 52.137 | 5.178386 / 4.000000 | 2.635000 | 31904.695 | [cell](cases/t2t-14-g16384.json) |
| t2t-14 | 16384 / 16384 | zstd-seekable | 727202 | 0 | 727202 | 2.883864 | 39.343 | 44.673 | 1.995000 / 2.000000 | 6.990000 | 32686.080 | [cell](cases/t2t-14-g16384.json) |
| t2t-14 | 16384 / 16384 | BGZF | 679548 | 2040 | 681588 | 3.076862 | 39.183 | 42.439 | 1.990000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-14-g16384.json) |
| t2t-14 | 65536 / 65536 | ACEAPEX | 549366 | 0 | 549366 | 3.817404 | 49.292 | 80.620 | 7.744081 / 8.000000 | 3.943000 | 47716.196 | [cell](cases/t2t-14-g65536.json) |
| t2t-14 | 65536 / 65536 | zstd-seekable | 691107 | 0 | 691107 | 3.034482 | 53.610 | 109.874 | 4.872000 / 4.000000 | 4.667000 | 79822.848 | [cell](cases/t2t-14-g65536.json) |
| t2t-14 | 65536 / 65280 | BGZF | 634994 | 520 | 635514 | 3.299930 | 61.925 | 126.386 | 4.691609 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-14-g65536.json) |
| t2t-15 | 4096 / 4096 | ACEAPEX | 88342 | 0 | 88342 | 23.739014 | 11.652 | 30.977 | 4.101125 / 4.000000 | 1.224000 | 67192.827 | [cell](cases/t2t-15-g4096.json) |
| t2t-15 | 4096 / 4096 | zstd-seekable | 240338 | 0 | 240338 | 8.725844 | 15.779 | 20.208 | 1.250000 / 1.250000 | 16.000000 | 20480.000 | [cell](cases/t2t-15-g4096.json) |
| t2t-15 | 4096 / 4096 | BGZF | 223066 | 8184 | 231250 | 9.068765 | 16.521 | 18.866 | 1.250000 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-15-g4096.json) |
| t2t-15 | 16384 / 16384 | ACEAPEX | 57722 | 0 | 57722 | 36.331936 | 10.379 | 34.875 | 2.763685 / 4.000000 | 0.866000 | 45280.215 | [cell](cases/t2t-15-g16384.json) |
| t2t-15 | 16384 / 16384 | zstd-seekable | 87660 | 0 | 87660 | 23.923705 | 9.658 | 14.226 | 1.995000 / 2.000000 | 6.990000 | 32686.080 | [cell](cases/t2t-15-g16384.json) |
| t2t-15 | 16384 / 16384 | BGZF | 88122 | 2040 | 90162 | 23.259821 | 10.229 | 12.573 | 1.994000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-15-g16384.json) |
| t2t-15 | 65536 / 65536 | ACEAPEX | 43025 | 0 | 43025 | 48.742638 | 4.097 | 38.903 | 0.723176 / 0.000000 | 0.246000 | 11848.517 | [cell](cases/t2t-15-g65536.json) |
| t2t-15 | 65536 / 65536 | zstd-seekable | 40341 | 0 | 40341 | 51.985623 | 10.670 | 28.162 | 4.940000 / 4.000000 | 4.722000 | 80936.960 | [cell](cases/t2t-15-g65536.json) |
| t2t-15 | 65536 / 65280 | BGZF | 49122 | 520 | 49642 | 42.245518 | 10.359 | 21.891 | 4.899797 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-15-g65536.json) |
| t2t-16 | 4096 / 4096 | ACEAPEX | 570131 | 0 | 570131 | 3.678369 | 23.023 | 47.950 | 4.618940 / 4.000000 | 2.479000 | 28695.693 | [cell](cases/t2t-16-g4096.json) |
| t2t-16 | 4096 / 4096 | zstd-seekable | 730351 | 0 | 730351 | 2.871430 | 29.716 | 34.535 | 1.249750 / 1.250000 | 15.998000 | 20475.904 | [cell](cases/t2t-16-g4096.json) |
| t2t-16 | 4096 / 4096 | BGZF | 685643 | 8184 | 693827 | 3.022586 | 30.938 | 34.324 | 1.249250 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-16-g4096.json) |
| t2t-16 | 16384 / 16384 | ACEAPEX | 545525 | 0 | 545525 | 3.844282 | 24.456 | 49.252 | 5.238391 / 4.000000 | 2.763000 | 32434.255 | [cell](cases/t2t-16-g16384.json) |
| t2t-16 | 16384 / 16384 | zstd-seekable | 700981 | 0 | 700981 | 2.991739 | 38.391 | 43.391 | 1.998000 / 2.000000 | 6.996000 | 32735.232 | [cell](cases/t2t-16-g16384.json) |
| t2t-16 | 16384 / 16384 | BGZF | 647987 | 2040 | 650027 | 3.226254 | 37.721 | 41.728 | 1.990000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-16-g16384.json) |
| t2t-16 | 65536 / 65536 | ACEAPEX | 539288 | 0 | 539288 | 3.888742 | 45.324 | 74.949 | 7.965974 / 8.000000 | 4.121000 | 49187.698 | [cell](cases/t2t-16-g65536.json) |
| t2t-16 | 65536 / 65536 | zstd-seekable | 669885 | 0 | 669885 | 3.130615 | 52.077 | 108.022 | 4.952000 / 4.000000 | 4.721000 | 81133.568 | [cell](cases/t2t-16-g65536.json) |
| t2t-16 | 65536 / 65280 | BGZF | 615028 | 520 | 615548 | 3.406967 | 59.651 | 122.709 | 4.822594 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-16-g65536.json) |
| t2t-17 | 4096 / 4096 | ACEAPEX | 583760 | 0 | 583760 | 3.592490 | 24.486 | 50.354 | 4.639372 / 4.000000 | 2.398000 | 28664.692 | [cell](cases/t2t-17-g4096.json) |
| t2t-17 | 4096 / 4096 | zstd-seekable | 765668 | 0 | 765668 | 2.738983 | 30.066 | 34.455 | 1.249250 / 1.250000 | 15.994000 | 20467.712 | [cell](cases/t2t-17-g4096.json) |
| t2t-17 | 4096 / 4096 | BGZF | 735077 | 8184 | 743261 | 2.821555 | 31.950 | 34.915 | 1.249250 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-17-g4096.json) |
| t2t-17 | 16384 / 16384 | ACEAPEX | 558879 | 0 | 558879 | 3.752426 | 25.338 | 51.486 | 5.296140 / 4.000000 | 2.687000 | 32612.678 | [cell](cases/t2t-17-g16384.json) |
| t2t-17 | 16384 / 16384 | zstd-seekable | 734959 | 0 | 734959 | 2.853427 | 39.684 | 45.625 | 1.997000 / 2.000000 | 6.994000 | 32718.848 | [cell](cases/t2t-17-g16384.json) |
| t2t-17 | 16384 / 16384 | BGZF | 685700 | 2040 | 687740 | 3.049338 | 39.464 | 42.640 | 1.992000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-17-g16384.json) |
| t2t-17 | 65536 / 65536 | ACEAPEX | 552839 | 0 | 552839 | 3.793423 | 48.401 | 78.767 | 7.747518 / 8.000000 | 3.941000 | 47729.593 | [cell](cases/t2t-17-g65536.json) |
| t2t-17 | 65536 / 65536 | zstd-seekable | 699065 | 0 | 699065 | 2.999938 | 54.672 | 112.370 | 4.868000 / 4.000000 | 4.661000 | 79757.312 | [cell](cases/t2t-17-g65536.json) |
| t2t-17 | 65536 / 65280 | BGZF | 642206 | 520 | 642726 | 3.262902 | 61.495 | 124.683 | 4.775281 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-17-g65536.json) |
| t2t-18 | 4096 / 4096 | ACEAPEX | 70411 | 0 | 70411 | 29.784437 | 7.624 | 18.464 | 3.227843 / 4.000000 | 0.912000 | 52884.976 | [cell](cases/t2t-18-g4096.json) |
| t2t-18 | 4096 / 4096 | zstd-seekable | 163908 | 0 | 163908 | 12.794690 | 12.964 | 16.040 | 1.249750 / 1.250000 | 15.998000 | 20475.904 | [cell](cases/t2t-18-g4096.json) |
| t2t-18 | 4096 / 4096 | BGZF | 158231 | 8184 | 166415 | 12.601941 | 15.810 | 17.613 | 1.249750 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-18-g4096.json) |
| t2t-18 | 16384 / 16384 | ACEAPEX | 33371 | 0 | 33371 | 62.843547 | 1.703 | 11.952 | 0.302954 / 0.000000 | 0.101000 | 4963.604 | [cell](cases/t2t-18-g16384.json) |
| t2t-18 | 16384 / 16384 | zstd-seekable | 56918 | 0 | 56918 | 36.845146 | 7.584 | 10.419 | 1.995000 / 2.000000 | 6.990000 | 32686.080 | [cell](cases/t2t-18-g16384.json) |
| t2t-18 | 16384 / 16384 | BGZF | 60566 | 2040 | 62606 | 33.497620 | 9.438 | 11.261 | 1.991000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-18-g16384.json) |
| t2t-18 | 65536 / 65536 | ACEAPEX | 21046 | 0 | 21046 | 99.646109 | 2.315 | 5.650 | 0.000026 / 0.000000 | 0.001000 | 0.420 | [cell](cases/t2t-18-g65536.json) |
| t2t-18 | 65536 / 65536 | zstd-seekable | 25782 | 0 | 25782 | 81.341711 | 7.915 | 16.541 | 4.996000 / 4.000000 | 4.759000 | 81854.464 | [cell](cases/t2t-18-g65536.json) |
| t2t-18 | 65536 / 65280 | BGZF | 33426 | 520 | 33946 | 61.779061 | 9.548 | 17.884 | 4.922203 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-18-g65536.json) |
| t2t-19 | 4096 / 4096 | ACEAPEX | 561432 | 0 | 561432 | 3.735362 | 23.414 | 49.913 | 4.680332 / 4.000000 | 2.478000 | 29063.600 | [cell](cases/t2t-19-g4096.json) |
| t2t-19 | 4096 / 4096 | zstd-seekable | 720099 | 0 | 720099 | 2.912311 | 29.475 | 33.803 | 1.250000 / 1.250000 | 16.000000 | 20480.000 | [cell](cases/t2t-19-g4096.json) |
| t2t-19 | 4096 / 4096 | BGZF | 674547 | 8184 | 682731 | 3.071711 | 30.457 | 33.352 | 1.249750 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-19-g4096.json) |
| t2t-19 | 16384 / 16384 | ACEAPEX | 537220 | 0 | 537220 | 3.903712 | 25.367 | 51.005 | 5.368986 / 4.000000 | 2.791000 | 33191.872 | [cell](cases/t2t-19-g16384.json) |
| t2t-19 | 16384 / 16384 | zstd-seekable | 690375 | 0 | 690375 | 3.037700 | 38.131 | 43.190 | 1.997000 / 2.000000 | 6.994000 | 32718.848 | [cell](cases/t2t-19-g16384.json) |
| t2t-19 | 16384 / 16384 | BGZF | 636184 | 2040 | 638224 | 3.285918 | 37.399 | 41.217 | 1.993000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-19-g16384.json) |
| t2t-19 | 65536 / 65536 | ACEAPEX | 531403 | 0 | 531403 | 3.946444 | 44.654 | 73.818 | 7.848066 / 8.000000 | 4.055000 | 48461.211 | [cell](cases/t2t-19-g65536.json) |
| t2t-19 | 65536 / 65536 | zstd-seekable | 657925 | 0 | 657925 | 3.187524 | 52.177 | 108.212 | 4.912000 / 4.000000 | 4.699000 | 80478.208 | [cell](cases/t2t-19-g65536.json) |
| t2t-19 | 65536 / 65280 | BGZF | 604196 | 520 | 604716 | 3.467995 | 58.409 | 120.445 | 4.885344 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-19-g65536.json) |
| t2t-20 | 4096 / 4096 | ACEAPEX | 585233 | 0 | 585233 | 3.583448 | 25.788 | 52.508 | 4.535917 / 4.000000 | 2.346000 | 28028.829 | [cell](cases/t2t-20-g4096.json) |
| t2t-20 | 4096 / 4096 | zstd-seekable | 768529 | 0 | 768529 | 2.728787 | 30.267 | 34.765 | 1.249750 / 1.250000 | 15.998000 | 20475.904 | [cell](cases/t2t-20-g4096.json) |
| t2t-20 | 4096 / 4096 | BGZF | 734225 | 8184 | 742409 | 2.824793 | 31.900 | 34.183 | 1.249250 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-20-g4096.json) |
| t2t-20 | 16384 / 16384 | ACEAPEX | 560666 | 0 | 560666 | 3.740466 | 26.740 | 53.640 | 5.273381 / 4.000000 | 2.681000 | 32483.342 | [cell](cases/t2t-20-g16384.json) |
| t2t-20 | 16384 / 16384 | zstd-seekable | 742386 | 0 | 742386 | 2.824881 | 39.464 | 44.493 | 1.999000 / 2.000000 | 6.998000 | 32751.616 | [cell](cases/t2t-20-g16384.json) |
| t2t-20 | 16384 / 16384 | BGZF | 692579 | 2040 | 694619 | 3.019140 | 39.775 | 42.910 | 1.993000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-20-g16384.json) |
| t2t-20 | 65536 / 65536 | ACEAPEX | 554291 | 0 | 554291 | 3.783486 | 51.106 | 82.754 | 7.383758 / 8.000000 | 3.774000 | 45532.941 | [cell](cases/t2t-20-g65536.json) |
| t2t-20 | 65536 / 65536 | zstd-seekable | 708120 | 0 | 708120 | 2.961577 | 52.869 | 109.214 | 4.888000 / 4.000000 | 4.680000 | 80084.992 | [cell](cases/t2t-20-g65536.json) |
| t2t-20 | 65536 / 65280 | BGZF | 652682 | 520 | 653202 | 3.210572 | 63.408 | 127.989 | 4.746391 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-20-g65536.json) |
| t2t-21 | 4096 / 4096 | ACEAPEX | 115745 | 0 | 115745 | 18.118727 | 19.506 | 40.897 | 3.800590 / 4.000000 | 1.396000 | 62268.864 | [cell](cases/t2t-21-g4096.json) |
| t2t-21 | 4096 / 4096 | zstd-seekable | 226099 | 0 | 226099 | 9.275371 | 16.140 | 19.056 | 1.249250 / 1.250000 | 15.994000 | 20467.712 | [cell](cases/t2t-21-g4096.json) |
| t2t-21 | 4096 / 4096 | BGZF | 209294 | 8184 | 217478 | 9.643054 | 15.860 | 17.863 | 1.249250 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-21-g4096.json) |
| t2t-21 | 16384 / 16384 | ACEAPEX | 81509 | 0 | 81509 | 25.729085 | 19.998 | 47.148 | 2.484578 / 4.000000 | 1.422000 | 28542.206 | [cell](cases/t2t-21-g16384.json) |
| t2t-21 | 16384 / 16384 | zstd-seekable | 96283 | 0 | 96283 | 21.781124 | 11.061 | 13.926 | 1.991000 / 2.000000 | 6.982000 | 32620.544 | [cell](cases/t2t-21-g16384.json) |
| t2t-21 | 16384 / 16384 | BGZF | 93523 | 2040 | 95563 | 21.945230 | 10.329 | 11.701 | 1.988000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-21-g16384.json) |
| t2t-21 | 65536 / 65536 | ACEAPEX | 60657 | 0 | 60657 | 34.573949 | 9.017 | 41.998 | 0.776756 / 0.000000 | 0.831000 | 5840.857 | [cell](cases/t2t-21-g65536.json) |
| t2t-21 | 65536 / 65536 | zstd-seekable | 50100 | 0 | 50100 | 41.859321 | 12.744 | 28.003 | 4.916000 / 4.000000 | 4.707000 | 80543.744 | [cell](cases/t2t-21-g65536.json) |
| t2t-21 | 65536 / 65280 | BGZF | 56903 | 520 | 57423 | 36.521115 | 11.010 | 22.251 | 4.842016 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-21-g65536.json) |
| t2t-22 | 4096 / 4096 | ACEAPEX | 551137 | 0 | 551137 | 3.805137 | 23.063 | 48.601 | 4.609273 / 4.000000 | 2.482000 | 28724.445 | [cell](cases/t2t-22-g4096.json) |
| t2t-22 | 4096 / 4096 | zstd-seekable | 704120 | 0 | 704120 | 2.978401 | 29.805 | 34.565 | 1.249500 / 1.250000 | 15.996000 | 20471.808 | [cell](cases/t2t-22-g4096.json) |
| t2t-22 | 4096 / 4096 | BGZF | 657661 | 8184 | 665845 | 3.149610 | 30.166 | 33.152 | 1.249500 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-22-g4096.json) |
| t2t-22 | 16384 / 16384 | ACEAPEX | 526835 | 0 | 526835 | 3.980662 | 24.647 | 49.482 | 5.268066 / 4.000000 | 2.750000 | 32614.407 | [cell](cases/t2t-22-g16384.json) |
| t2t-22 | 16384 / 16384 | zstd-seekable | 672492 | 0 | 672492 | 3.118479 | 37.500 | 42.710 | 1.991000 / 2.000000 | 6.982000 | 32620.544 | [cell](cases/t2t-22-g16384.json) |
| t2t-22 | 16384 / 16384 | BGZF | 618688 | 2040 | 620728 | 3.378536 | 36.528 | 40.435 | 1.988000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-22-g16384.json) |
| t2t-22 | 65536 / 65536 | ACEAPEX | 519123 | 0 | 519123 | 4.039798 | 45.515 | 73.978 | 7.856395 / 8.000000 | 4.099000 | 48601.415 | [cell](cases/t2t-22-g65536.json) |
| t2t-22 | 65536 / 65536 | zstd-seekable | 640960 | 0 | 640960 | 3.271892 | 51.276 | 105.788 | 4.884000 / 4.000000 | 4.677000 | 80019.456 | [cell](cases/t2t-22-g65536.json) |
| t2t-22 | 65536 / 65280 | BGZF | 589348 | 520 | 589868 | 3.555290 | 58.049 | 119.544 | 4.823094 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-22-g65536.json) |
| t2t-23 | 4096 / 4096 | ACEAPEX | 584926 | 0 | 584926 | 3.585329 | 25.758 | 53.640 | 4.754151 / 4.000000 | 2.458000 | 29377.507 | [cell](cases/t2t-23-g4096.json) |
| t2t-23 | 4096 / 4096 | zstd-seekable | 768309 | 0 | 768309 | 2.729568 | 30.116 | 34.504 | 1.250000 / 1.250000 | 16.000000 | 20480.000 | [cell](cases/t2t-23-g4096.json) |
| t2t-23 | 4096 / 4096 | BGZF | 731197 | 8184 | 739381 | 2.836362 | 31.849 | 34.464 | 1.249750 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-23-g4096.json) |
| t2t-23 | 16384 / 16384 | ACEAPEX | 560157 | 0 | 560157 | 3.743865 | 26.580 | 53.670 | 5.250151 / 4.000000 | 2.645000 | 32293.483 | [cell](cases/t2t-23-g16384.json) |
| t2t-23 | 16384 / 16384 | zstd-seekable | 742290 | 0 | 742290 | 2.825246 | 39.895 | 45.044 | 1.997000 / 2.000000 | 6.994000 | 32718.848 | [cell](cases/t2t-23-g16384.json) |
| t2t-23 | 16384 / 16384 | BGZF | 692709 | 2040 | 694749 | 3.018575 | 39.884 | 42.830 | 1.993000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-23-g16384.json) |
| t2t-23 | 65536 / 65536 | ACEAPEX | 553776 | 0 | 553776 | 3.787004 | 50.645 | 81.111 | 7.339086 / 8.000000 | 3.734000 | 45212.373 | [cell](cases/t2t-23-g65536.json) |
| t2t-23 | 65536 / 65536 | zstd-seekable | 707673 | 0 | 707673 | 2.963448 | 53.270 | 109.575 | 4.964000 / 4.000000 | 4.736000 | 81330.176 | [cell](cases/t2t-23-g65536.json) |
| t2t-23 | 65536 / 65280 | BGZF | 652778 | 520 | 653298 | 3.210100 | 63.508 | 128.259 | 4.846500 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-23-g65536.json) |
| t2t-24 | 4096 / 4096 | ACEAPEX | 121697 | 0 | 121697 | 17.232569 | 20.448 | 42.319 | 3.998738 / 4.000000 | 1.481000 | 63467.330 | [cell](cases/t2t-24-g4096.json) |
| t2t-24 | 4096 / 4096 | zstd-seekable | 215626 | 0 | 215626 | 9.725877 | 15.770 | 18.294 | 1.250000 / 1.250000 | 16.000000 | 20480.000 | [cell](cases/t2t-24-g4096.json) |
| t2t-24 | 4096 / 4096 | BGZF | 197924 | 8184 | 206108 | 10.175015 | 15.279 | 17.283 | 1.250000 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-24-g4096.json) |
| t2t-24 | 16384 / 16384 | ACEAPEX | 91663 | 0 | 91663 | 22.878937 | 21.200 | 45.154 | 3.148529 / 4.000000 | 1.606000 | 38109.654 | [cell](cases/t2t-24-g16384.json) |
| t2t-24 | 16384 / 16384 | zstd-seekable | 87387 | 0 | 87387 | 23.998444 | 10.349 | 13.355 | 1.995000 / 2.000000 | 6.990000 | 32686.080 | [cell](cases/t2t-24-g16384.json) |
| t2t-24 | 16384 / 16384 | BGZF | 83513 | 2040 | 85553 | 24.512898 | 9.718 | 11.782 | 1.993000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-24-g16384.json) |
| t2t-24 | 65536 / 65536 | ACEAPEX | 77852 | 0 | 77852 | 26.937677 | 23.253 | 53.901 | 3.124784 / 4.000000 | 1.929000 | 26374.694 | [cell](cases/t2t-24-g65536.json) |
| t2t-24 | 65536 / 65536 | zstd-seekable | 45380 | 0 | 45380 | 46.213134 | 11.903 | 26.319 | 4.848000 / 4.000000 | 4.660000 | 79429.632 | [cell](cases/t2t-24-g65536.json) |
| t2t-24 | 65536 / 65280 | BGZF | 49129 | 520 | 49649 | 42.239562 | 9.989 | 19.336 | 4.852969 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-24-g65536.json) |
| t2t-25 | 4096 / 4096 | ACEAPEX | 576312 | 0 | 576312 | 3.638918 | 24.536 | 51.176 | 4.640634 / 4.000000 | 2.419000 | 28697.350 | [cell](cases/t2t-25-g4096.json) |
| t2t-25 | 4096 / 4096 | zstd-seekable | 746466 | 0 | 746466 | 2.809441 | 30.147 | 34.644 | 1.249750 / 1.250000 | 15.998000 | 20475.904 | [cell](cases/t2t-25-g4096.json) |
| t2t-25 | 4096 / 4096 | BGZF | 714652 | 8184 | 722836 | 2.901283 | 31.328 | 34.144 | 1.249500 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-25-g4096.json) |
| t2t-25 | 16384 / 16384 | ACEAPEX | 553816 | 0 | 553816 | 3.786731 | 25.437 | 50.064 | 5.319825 / 4.000000 | 2.720000 | 32788.358 | [cell](cases/t2t-25-g16384.json) |
| t2t-25 | 16384 / 16384 | zstd-seekable | 711054 | 0 | 711054 | 2.949357 | 38.993 | 43.621 | 1.998000 / 2.000000 | 6.996000 | 32735.232 | [cell](cases/t2t-25-g16384.json) |
| t2t-25 | 16384 / 16384 | BGZF | 663666 | 2040 | 665706 | 3.150268 | 38.171 | 41.568 | 1.994000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-25-g16384.json) |
| t2t-25 | 65536 / 65536 | ACEAPEX | 546266 | 0 | 546266 | 3.839067 | 45.645 | 78.146 | 7.959095 / 8.000000 | 4.050000 | 49023.541 | [cell](cases/t2t-25-g65536.json) |
| t2t-25 | 65536 / 65536 | zstd-seekable | 676632 | 0 | 676632 | 3.099398 | 53.310 | 110.046 | 4.968000 / 4.000000 | 4.744000 | 81395.712 | [cell](cases/t2t-25-g65536.json) |
| t2t-25 | 65536 / 65280 | BGZF | 621823 | 520 | 622343 | 3.369769 | 60.463 | 127.589 | 4.881859 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-25-g65536.json) |
| t2t-26 | 4096 / 4096 | ACEAPEX | 582394 | 0 | 582394 | 3.600916 | 24.886 | 51.656 | 4.511336 / 4.000000 | 2.340000 | 27886.369 | [cell](cases/t2t-26-g4096.json) |
| t2t-26 | 4096 / 4096 | zstd-seekable | 764154 | 0 | 764154 | 2.744410 | 30.026 | 34.986 | 1.250000 / 1.250000 | 16.000000 | 20480.000 | [cell](cases/t2t-26-g4096.json) |
| t2t-26 | 4096 / 4096 | BGZF | 728922 | 8184 | 737106 | 2.845116 | 31.799 | 34.454 | 1.249500 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-26-g4096.json) |
| t2t-26 | 16384 / 16384 | ACEAPEX | 557860 | 0 | 557860 | 3.759280 | 25.668 | 52.127 | 5.154719 / 4.000000 | 2.629000 | 31767.292 | [cell](cases/t2t-26-g16384.json) |
| t2t-26 | 16384 / 16384 | zstd-seekable | 735944 | 0 | 735944 | 2.849608 | 39.574 | 45.435 | 1.997000 / 2.000000 | 6.994000 | 32718.848 | [cell](cases/t2t-26-g16384.json) |
| t2t-26 | 16384 / 16384 | BGZF | 685851 | 2040 | 687891 | 3.048669 | 39.363 | 42.910 | 1.993000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-26-g16384.json) |
| t2t-26 | 65536 / 65536 | ACEAPEX | 551640 | 0 | 551640 | 3.801668 | 48.491 | 86.111 | 7.178178 / 8.000000 | 3.674000 | 44267.712 | [cell](cases/t2t-26-g65536.json) |
| t2t-26 | 65536 / 65536 | zstd-seekable | 701735 | 0 | 701735 | 2.988524 | 53.450 | 112.029 | 4.840000 / 4.000000 | 4.647000 | 79298.560 | [cell](cases/t2t-26-g65536.json) |
| t2t-26 | 65536 / 65280 | BGZF | 644910 | 520 | 645430 | 3.249232 | 62.487 | 126.576 | 4.788734 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-26-g65536.json) |
| t2t-27 | 4096 / 4096 | ACEAPEX | 127720 | 0 | 127720 | 16.419919 | 21.640 | 48.251 | 3.023643 / 4.000000 | 1.867000 | 25536.803 | [cell](cases/t2t-27-g4096.json) |
| t2t-27 | 4096 / 4096 | zstd-seekable | 173208 | 0 | 173208 | 12.107709 | 14.617 | 18.715 | 1.250000 / 1.250000 | 16.000000 | 20480.000 | [cell](cases/t2t-27-g4096.json) |
| t2t-27 | 4096 / 4096 | BGZF | 159110 | 8184 | 167294 | 12.535728 | 14.096 | 16.681 | 1.249750 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-27-g4096.json) |
| t2t-27 | 16384 / 16384 | ACEAPEX | 87266 | 0 | 87266 | 24.031719 | 8.276 | 46.437 | 1.768469 / 0.250000 | 1.488000 | 13942.276 | [cell](cases/t2t-27-g16384.json) |
| t2t-27 | 16384 / 16384 | zstd-seekable | 87382 | 0 | 87382 | 23.999817 | 11.221 | 15.248 | 1.998000 / 2.000000 | 6.996000 | 32735.232 | [cell](cases/t2t-27-g16384.json) |
| t2t-27 | 16384 / 16384 | BGZF | 78554 | 2040 | 80594 | 26.021193 | 9.217 | 11.632 | 1.990000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-27-g16384.json) |
| t2t-27 | 65536 / 65536 | ACEAPEX | 75499 | 0 | 75499 | 27.777216 | 11.872 | 53.641 | 1.150385 / 0.250000 | 1.240000 | 8976.549 | [cell](cases/t2t-27-g65536.json) |
| t2t-27 | 65536 / 65536 | zstd-seekable | 58067 | 0 | 58067 | 36.116073 | 16.180 | 36.368 | 4.988000 / 4.000000 | 4.749000 | 81723.392 | [cell](cases/t2t-27-g65536.json) |
| t2t-27 | 65536 / 65280 | BGZF | 54218 | 520 | 54738 | 38.312543 | 10.650 | 22.292 | 4.926688 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-27-g65536.json) |
| t2t-28 | 4096 / 4096 | ACEAPEX | 575151 | 0 | 575151 | 3.646263 | 24.806 | 51.576 | 4.654662 / 4.000000 | 2.422000 | 28775.586 | [cell](cases/t2t-28-g4096.json) |
| t2t-28 | 4096 / 4096 | zstd-seekable | 747550 | 0 | 747550 | 2.805367 | 30.236 | 34.615 | 1.249750 / 1.250000 | 15.998000 | 20475.904 | [cell](cases/t2t-28-g4096.json) |
| t2t-28 | 4096 / 4096 | BGZF | 719536 | 8184 | 727720 | 2.881812 | 31.368 | 34.274 | 1.249750 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-28-g4096.json) |
| t2t-28 | 16384 / 16384 | ACEAPEX | 549766 | 0 | 549766 | 3.814627 | 25.978 | 52.758 | 5.267720 / 4.000000 | 2.692000 | 32465.443 | [cell](cases/t2t-28-g16384.json) |
| t2t-28 | 16384 / 16384 | zstd-seekable | 710074 | 0 | 710074 | 2.953427 | 39.744 | 46.096 | 1.995000 / 2.000000 | 6.990000 | 32686.080 | [cell](cases/t2t-28-g16384.json) |
| t2t-28 | 16384 / 16384 | BGZF | 664108 | 2040 | 666148 | 3.148177 | 38.192 | 41.378 | 1.994000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-28-g16384.json) |
| t2t-28 | 65536 / 65536 | ACEAPEX | 543875 | 0 | 543875 | 3.855945 | 48.631 | 80.040 | 7.861344 / 8.000000 | 4.001000 | 48425.028 | [cell](cases/t2t-28-g65536.json) |
| t2t-28 | 65536 / 65536 | zstd-seekable | 673624 | 0 | 673624 | 3.113238 | 53.571 | 111.178 | 4.944000 / 4.000000 | 4.727000 | 81002.496 | [cell](cases/t2t-28-g65536.json) |
| t2t-28 | 65536 / 65280 | BGZF | 617711 | 520 | 618231 | 3.392182 | 59.552 | 123.181 | 4.877375 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-28-g65536.json) |
| t2t-29 | 4096 / 4096 | ACEAPEX | 559286 | 0 | 559286 | 3.749695 | 24.866 | 52.297 | 4.630245 / 4.000000 | 2.387000 | 28592.960 | [cell](cases/t2t-29-g4096.json) |
| t2t-29 | 4096 / 4096 | zstd-seekable | 730338 | 0 | 730338 | 2.871481 | 29.545 | 34.074 | 1.250000 / 1.250000 | 16.000000 | 20480.000 | [cell](cases/t2t-29-g4096.json) |
| t2t-29 | 4096 / 4096 | BGZF | 704830 | 8184 | 713014 | 2.941249 | 30.758 | 33.873 | 1.249500 / 1.250000 | 0.000000 | 0.000 | [cell](cases/t2t-29-g4096.json) |
| t2t-29 | 16384 / 16384 | ACEAPEX | 535170 | 0 | 535170 | 3.918665 | 26.650 | 53.220 | 5.249159 / 4.000000 | 2.649000 | 32295.320 | [cell](cases/t2t-29-g16384.json) |
| t2t-29 | 16384 / 16384 | zstd-seekable | 684226 | 0 | 684226 | 3.064999 | 38.542 | 43.541 | 1.998000 / 2.000000 | 6.996000 | 32735.232 | [cell](cases/t2t-29-g16384.json) |
| t2t-29 | 16384 / 16384 | BGZF | 638922 | 2040 | 640962 | 3.271882 | 36.278 | 40.235 | 1.991000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/t2t-29-g16384.json) |
| t2t-29 | 65536 / 65536 | ACEAPEX | 528663 | 0 | 528663 | 3.966898 | 49.613 | 80.261 | 7.834680 / 8.000000 | 3.971000 | 48237.012 | [cell](cases/t2t-29-g65536.json) |
| t2t-29 | 65536 / 65536 | zstd-seekable | 642029 | 0 | 642029 | 3.266444 | 53.420 | 109.625 | 4.916000 / 4.000000 | 4.704000 | 80543.744 | [cell](cases/t2t-29-g65536.json) |
| t2t-29 | 65536 / 65280 | BGZF | 592130 | 520 | 592650 | 3.538601 | 57.117 | 119.363 | 4.885344 / 3.984375 | 0.000000 | 0.000 | [cell](cases/t2t-29-g65536.json) |
| enwik8 | 16384 / 16384 | ACEAPEX | 41649923 | 0 | 41649923 | 2.400965 | 72.476 | 122.189 | 6.134294 / 5.000000 | 4.787000 | 100504.267 | [cell](cases/enwik8-g16384.json) |
| enwik8 | 16384 / 16384 | zstd-seekable | 42939459 | 0 | 42939459 | 2.328860 | 29.585 | 33.813 | 1.999000 / 2.000000 | 6.998000 | 32751.616 | [cell](cases/enwik8-g16384.json) |
| enwik8 | 16384 / 16384 | BGZF | 41418060 | 97656 | 41515716 | 2.408726 | 42.199 | 47.218 | 1.999000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/enwik8-g16384.json) |
| silesia | 16384 / 16384 | ACEAPEX | 76265370 | 0 | 76265370 | 2.779079 | 75.321 | 134.371 | 5.821495 / 5.000000 | 4.761000 | 95379.371 | [cell](cases/silesia-g16384.json) |
| silesia | 16384 / 16384 | zstd-seekable | 79417442 | 0 | 79417442 | 2.668778 | 26.690 | 35.156 | 2.000000 / 2.000000 | 7.000000 | 32768.000 | [cell](cases/silesia-g16384.json) |
| silesia | 16384 / 16384 | BGZF | 76441540 | 206984 | 76648524 | 2.765187 | 34.535 | 61.384 | 2.000000 / 2.000000 | 0.000000 | 0.000 | [cell](cases/silesia-g16384.json) |

[Unchanged calibration](CALIBRATION.md) · [Execution protocol](PROTOCOL.md) · [Exact decision](decision.json) · [Exact fit](model/fit.json) · [Only primary decomposition](model/cases/chr1-g16384.json).
