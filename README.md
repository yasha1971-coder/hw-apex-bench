# hw-apex-bench — Compressed Access Benchmark

Three codecs, four configurations. API-only byte regions; implemented axes and review boundary are below.

Run: 2026-09-10T20:29:44.589718+00:00. Benchmark commit: 9cad83e8a5c9a5f3bafb7ef2c70c8d0ead4276fb.

Corpus: chr1 hg38 FASTA, MD5 9465e0f0df6e2c6eb39729c39cee5465.

libzstd: *** Zstandard CLI (64-bit) v1.5.7, by Yann Collet ***; htslib: 1.19; bgzip: bgzip (htslib) 1.19.
C: gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0; C++: g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0.
ACEAPEX: 1b13df34ac8e839dd3232b59bc59560d689a435a; zstd reference implementation: f8745da6ff1ad1e7bab384bd1f9d742439278e99.

Machine: Linux-6.17.0-1022-azure-x86_64-with-glibc2.39; logical CPUs: 4.
Model name:                              Intel(R) Xeon(R) 6973P-C
Hardware details, parameters and commands accompany every measurement in results.jsonl.

| Configuration | Level | Encoder threads | Block/frame bytes | LIT bytes | FSE bytes |
|---|---:|---:|---:|---:|---:|
| bgzip+htslib | 6 | 1 | BGZF variable (<=65536 uncompressed) | n/a | n/a |
| zstd-seekable | 3 | 1 | 16384 | n/a | n/a |
| aceapex-interactive | 2 | 1 | 16384 | 65536 | 4096 |
| aceapex-dense | 2 | 1 | 262144 | 1048576 | 32768 |

| Codec / profile | block (bytes) | Ratio incl. indexes | Region p50 ms | Region p99 ms | Output amplification | GPU |
|---|---:|---:|---:|---:|---:|---|
| bgzip+htslib | 65536 | 3.382558 | 0.102141 | 0.212103 | 4.821094 | n/a |
| zstd-seekable | 16384 | 3.025774 | 0.046046 | 0.059425 | 2.000000 | n/a |
| aceapex-interactive | 16384 | 3.658493 | 0.129720 | 0.240419 | 6.216250 | n/a |
| aceapex-dense | 262144 | 3.780646 | 1.330098 | 2.523226 | 83.431872 | n/a |

Every timed operation reads the same 16,384 original-file bytes. No FASTA parsing is timed.
Amplification A = sum_q(sum of bytes actually expanded by the decoder for query q) / sum_q(requested bytes) = decoded bytes / (200 × 16384).
BGZF counts decompressed blocks, zstd counts reconstructed blocks within frames (including buffered output), and ACEAPEX counts only touched chunks in the literal, offset, length and command streams, not the complete streams. Repeated expansions count each time.
BGZF block=65536 is its size ceiling; actual blocks may be shorter. An unaligned request can cross block and entropy-chunk boundaries. (64 + 3 × 4) / 16 = 4.75 describes exactly one chunk of each kind, not a constant for arbitrary offsets. See [the trace explanation](AMPLIFICATION.md).

| Codec | block (bytes) | Ratio / bgzip >= 0.99 | p50 / bgzip <= 1 | p99 / bgzip <= 1 |
|---|---:|---|---|---|
| bgzip+htslib | 65536 | 1.0000 — PASS | 1.0000 — PASS | 1.0000 — PASS |
| zstd-seekable | 16384 | 0.8945 — FAIL | 0.4508 — PASS | 0.2802 — PASS |
| aceapex-interactive | 16384 | 1.0816 — PASS | 1.2700 — FAIL | 1.1335 — FAIL |
| aceapex-dense | 262144 | 1.1177 — PASS | 13.0222 — FAIL | 11.8962 — FAIL |

| Codec | Decoded bytes (numerator) | Requested bytes (denominator) | LIT / offset / length / command decoded bytes |
|---|---:|---:|---|
| bgzip+htslib | 15797760 | 3276800 | n/a |
| zstd-seekable | 6553600 | 3276800 | n/a |
| aceapex-interactive | 20369408 | 3276800 | [17760256, 933888, 585728, 1089536] |
| aceapex-dense | 273389557 | 3276800 | [251658240, 8028160, 4724725, 8978432] |

## Break-even

Model: independent 16 KiB reads at their measured p50 versus one full library decode.
Smallest integer N with N × p50 > full decode time; full time is the median of five verified decodes after one warmup.
This is a derived intersection, not an observed batch crossover or a plateau-throughput measurement.

| Codec/profile | block bytes | Full decode ms | Region p50 ms | Break-even N | Full decoder threads |
|---|---:|---:|---:|---:|---|
| bgzip+htslib | 65536 | 350.793360 | 0.102141 | 3435 | single decoder thread |
| zstd-seekable | 16384 | 355.400855 | 0.046046 | 7719 | single decoder thread |
| aceapex-interactive | 16384 | 206.622986 | 0.129720 | 1593 | 8 reconstruction workers; literal workers up to 8; API has no thread argument |
| aceapex-dense | 262144 | 176.848186 | 1.330098 | 133 | 8 reconstruction workers; literal workers up to 8; API has no thread argument |

## Batch

Identical raw-byte requests across codecs; every native batch answer matches the single-call result and original bytes.
Three repetitions, median duration; loop/native order alternates. Both loop and batch use one worker (loop1-vs-batch1).
H_alpha counts request-start blocks (actual GZI boundaries for BGZF, declared frame/block boundaries otherwise). H_alpha_16k is also recorded.
bgzip and zstd-seekable native batch: n/a (no native batch API in these adapters); their measured method is loop.
All N=100/600/2000/5000 points are in [BATCH_RESULTS.md](BATCH_RESULTS.md). The fixed N=5000 view follows.

| Codec/profile | block bytes | Access profile | method | N | H_alpha bits | Threads requested | ranges/s | / bgzip loop |
|---|---:|---|---|---:|---:|---:|---:|---|
| bgzip+htslib | 65536 | uniform | loop | 5000 | 11.285997 | 1 | 9341.656 | 1.000 PASS |
| zstd-seekable | 16384 | uniform | loop | 5000 | 11.993736 | 1 | 22378.189 | 2.396 PASS |
| aceapex-interactive | 16384 | uniform | loop | 5000 | 11.993736 | 1 | 6444.580 | 0.690 FAIL |
| aceapex-interactive | 16384 | uniform | batch | 5000 | 11.993736 | 1 | 12312.527 | 1.318 PASS |
| aceapex-dense | 262144 | uniform | loop | 5000 | 9.774765 | 1 | 659.627 | 0.071 FAIL |
| aceapex-dense | 262144 | uniform | batch | 5000 | 9.774765 | 1 | 12369.677 | 1.324 PASS |
| bgzip+htslib | 65536 | sorted | loop | 5000 | 11.285997 | 1 | 16387.479 | 1.000 PASS |
| zstd-seekable | 16384 | sorted | loop | 5000 | 11.993736 | 1 | 24018.968 | 1.466 PASS |
| aceapex-interactive | 16384 | sorted | loop | 5000 | 11.993736 | 1 | 6707.945 | 0.409 FAIL |
| aceapex-interactive | 16384 | sorted | batch | 5000 | 11.993736 | 1 | 11266.210 | 0.687 FAIL |
| aceapex-dense | 262144 | sorted | loop | 5000 | 9.774765 | 1 | 675.669 | 0.041 FAIL |
| aceapex-dense | 262144 | sorted | batch | 5000 | 9.774765 | 1 | 12696.691 | 0.775 FAIL |
| bgzip+htslib | 65536 | clustered | loop | 5000 | 10.387857 | 1 | 9831.154 | 1.000 PASS |
| zstd-seekable | 16384 | clustered | loop | 5000 | 11.574142 | 1 | 22448.874 | 2.283 PASS |
| aceapex-interactive | 16384 | clustered | loop | 5000 | 11.574142 | 1 | 6828.065 | 0.695 FAIL |
| aceapex-interactive | 16384 | clustered | batch | 5000 | 11.574142 | 1 | 22336.887 | 2.272 PASS |
| aceapex-dense | 262144 | clustered | loop | 5000 | 8.688593 | 1 | 673.279 | 0.068 FAIL |
| aceapex-dense | 262144 | clustered | batch | 5000 | 8.688593 | 1 | 17521.561 | 1.782 PASS |
| bgzip+htslib | 65536 | hot-set | loop | 5000 | 6.155796 | 1 | 9128.433 | 1.000 PASS |
| zstd-seekable | 16384 | hot-set | loop | 5000 | 5.987822 | 1 | 22851.094 | 2.503 PASS |
| aceapex-interactive | 16384 | hot-set | loop | 5000 | 5.987822 | 1 | 6954.033 | 0.762 FAIL |
| aceapex-interactive | 16384 | hot-set | batch | 5000 | 5.987822 | 1 | 259708.312 | 28.450 PASS |
| aceapex-dense | 262144 | hot-set | loop | 5000 | 5.951825 | 1 | 722.914 | 0.079 FAIL |
| aceapex-dense | 262144 | hot-set | batch | 5000 | 5.951825 | 1 | 54037.319 | 5.920 PASS |
| bgzip+htslib | 65536 | zipf1.2 | loop | 5000 | 5.244881 | 1 | 11739.432 | 1.000 PASS |
| zstd-seekable | 16384 | zipf1.2 | loop | 5000 | 6.808726 | 1 | 23693.002 | 2.018 PASS |
| aceapex-interactive | 16384 | zipf1.2 | loop | 5000 | 6.808726 | 1 | 7486.212 | 0.638 FAIL |
| aceapex-interactive | 16384 | zipf1.2 | batch | 5000 | 6.808726 | 1 | 44953.027 | 3.829 PASS |
| aceapex-dense | 262144 | zipf1.2 | loop | 5000 | 3.787940 | 1 | 805.252 | 0.069 FAIL |
| aceapex-dense | 262144 | zipf1.2 | batch | 5000 | 3.787940 | 1 | 12701.317 | 1.082 PASS |

The full matrix keeps native batch and loop visible separately; a failed speed relation remains FAIL.
The prior EPYC 9V74 4.78× result remains unchanged in [historical evidence](evidence/audit-20260909/FAILS.md).

| Historical machine | Reported batch/loop | Evidence status |
|---|---:|---|
| EPYC 9V74 | 4.78× | measured, preserved original log; below its upstream 5× predicate |
| EPYC 4344P | 13.3× | declared by user; matching command/configuration/receipt unavailable here |

These historical points use another protocol and are not inputs to current pass/fail.
The old parse checks without numpy are interpreted as skipped (missing dependency); the original FAIL text is preserved.

Batch review is complete; measured c(g) follows below.
See [batch protocol and upstream attribution](BATCH_METHOD.md).


## Independence cost c(g): strict baseline contract

Only the independent block size may change. Corpus bytes, encoder revision, level, effective search/entropy parameters and threads must otherwise be fixed. Deterministic encoder behavior caused by the changed boundary is part of the treatment.
`c(g) = 100 × (1 − ratio_g / ratio_whole)`. Every ratio uses input bytes divided by complete output-file bytes. Historical JSONL metric independence_cost_percent means the operational comparison; strict claims are explicit rows with their own provenance.

| Codec/profile | block bytes | ratio g | ratio whole | Operational loss % | Strict c(g) | Encoder threads requested |
|---|---:|---:|---:|---:|---|---:|
| bgzip+htslib | 65536 | 3.382558 | 3.395854 | 0.391536 | n/a | 1 |
| zstd-seekable | 16384 | 3.025774 | 3.259852 | 7.180634 | 7.180634 | 1 |
| aceapex-interactive | 16384 | 3.658493 | 3.722310 | 1.714456 | n/a | 1 |
| aceapex-dense | 262144 | 3.780646 | 3.793413 | 0.336554 | n/a | 1 |
| ACEAPEX default @ ee5a37e (reproduced) | 16384 | 3.159784 | 3.212216 | — | 1.632267 | 8 |

bgzip+htslib: n/a: gzip and bgzip use different encoder implementations; no same-encoder block-size-only baseline measured.

aceapex-interactive: n/a for this profile/SHA: the strict reproduced pair uses the default configuration at ee5a37e, not --profile interactive at 1b13df3.

aceapex-dense: n/a for this profile/SHA: no block-size-only dense pair has been supplied.

ACEAPEX default @ ee5a37e was reproduced by GitHub Actions run 34488734677: 80364845 bytes at 16 KiB and 79053076 bytes for one whole-input block, both exact restores passing. GCC 13.3.0, libzstd 1.5.5. The compiled source `src/aceapex_main.cpp` was observed in the compiler trace and hashed. The result differs from the ace-core 1.631528% by 0.000740 percentage point.

zstd bases are explicitly zstd 1.5.7 level -3, one continuous frame versus independent 16384-byte frames. The user-reported historical version is 1.4.8 with 6.68%; version change is a hypothesis for the difference, not an attribution established by a matched rerun.
The historical 0.410% is payload-only: it excludes the AET header and 64-byte BlockOffsets entry per block. The cross-codec archive ratio includes both. Neither 0.410% nor 6.68% is an acceptance target.

Whole-file means one continuous member/frame/output block, not an unlimited match window. gzip retains its 32 KiB backward-distance limit; this does not make its blocks independent. bgzip adds independent member boundaries, index/headers and implementation differences.
ACEAPEX uses the same pinned binary on both sides. ACEAPEX_BS changes from 16384 or 262144 to 253935557. MIN_MATCH was cleared and defaults to 0. LIT_CHUNK/FSE_CHUNK remain 65536/4096 (interactive) or 1048576/32768 (dense).
Important correction: flattening is not disabled for the entire large block. The actual guard is local_pos < (1u<<20), with c_off <= local_pos. Eligible non-rep matches in its first MiB may be flattened; later matches are not. Each small block resets local_pos. The separate size impact of this difference is unmeasured; isolated c(g) is n/a for these ACEAPEX pairs.
The old JSONL baseline caveat used the inaccurate shorthand “skips chain flattening above 1 MiB”. Raw historical evidence is preserved; this report and INDEPENDENCE_AUDIT.md correct that interpretation. No observed archive size or ratio has changed.

### Both compression commands for every row

Commands below are the recorded commands, with the runner checkout prefix replaced by `.` for local replay. Each compression command is paired with its own ratio and archive size. Codec wrappers are part of the pinned benchmark source. Before replay, clear overrides exactly as run.sh does:

```bash
unset ACEAPEX_BS LIT_CHUNK FSE_CHUNK MIN_MATCH LIT_LEVEL LIT_LANES NO_REP DIRECT8 FORCED_BIN ACEAPEX_DUMP LD_PRELOAD
```

#### bgzip+htslib

Blocked: ratio **3.382558276489**, archive + required index **75072042 bytes**.

```bash
bash codecs/bgzip.sh compress ./.work/chr1.fa ./.work/chr1.fa.gz
```

Continuous baseline: ratio **3.395854265262**, archive **74778108 bytes**.

```bash
gzip -n -6 -c ./.work/chr1.fa > ./.work/whole-bgzip-htslib.archive
```

#### zstd-seekable

Blocked: ratio **3.025773934700**, archive + required index **83924167 bytes**.

```bash
bash codecs/zstd_seekable.sh compress ./.work ./.work/chr1.fa
```

Continuous baseline: ratio **3.259851962595**, archive **77897880 bytes**.

```bash
./.work/zstd/programs/zstd -3 -T1 --no-check -f ./.work/chr1.fa -o ./.work/whole-zstd-seekable.archive
```

#### aceapex-interactive

Blocked: ratio **3.658493060599**, archive + required index **69409878 bytes**.

```bash
bash codecs/aceapex.sh compress ./.work ./.work/chr1.fa ./.work/chr1-interactive.aet interactive
```

Continuous baseline: ratio **3.722310445126**, archive **68219876 bytes**.

```bash
env ACEAPEX_BS=253935557 ./.work/aceapex-cli c --in ./.work/chr1.fa --out ./.work/whole-aceapex-interactive.archive --threads 1 --level 2 --profile interactive
```

#### aceapex-dense

Blocked: ratio **3.780646221619**, archive + required index **67167236 bytes**.

```bash
bash codecs/aceapex.sh compress ./.work ./.work/chr1.fa ./.work/chr1-dense.aet dense
```

Continuous baseline: ratio **3.793413104059**, archive **66941182 bytes**.

```bash
env ACEAPEX_BS=253935557 ./.work/aceapex-cli c --in ./.work/chr1.fa --out ./.work/whole-aceapex-dense.archive --threads 1 --level 2 --profile dense
```

[Expanded CLI commands, environment and flattening audit](INDEPENDENCE_AUDIT.md). Expected historical percentages are not acceptance thresholds.

Plateau throughput follows below.


## Encode and full decode on the plateau

Input is byte-concatenated chr1. A plateau requires the latest three scale medians to remain within 5%, with sample CV at every scale no greater than 5%. If this is not reached by the available data edge, no headline rate is printed.

| Codec/profile | block bytes | Encoder threads | Encode MB/s | vs bgzip | Full decoder threads | Full decode MB/s | vs bgzip | Largest input |
|---|---:|---:|---|---|---|---|---|---:|
| bgzip+htslib | 65536 | 1 | 29.025 | 1.000 PASS | single decoder thread | 711.936 | 1.000 PASS | 2031484456 |
| zstd-seekable | 16384 | 1 | 227.302 | 7.831 PASS | single decoder thread | 709.132 | 0.996 FAIL | 2031484456 |
| aceapex-interactive | 16384 | 1 | 49.953 | 1.721 PASS | 8 reconstruction workers; literal workers up to 8; API has no thread argument; runner exposed 4 logical CPUs | 1301.365 | 1.828 PASS | 2031484456 |
| aceapex-dense | 262144 | 1 | 49.059 | 1.690 PASS | 8 reconstruction workers; literal workers up to 8; API has no thread argument; runner exposed 4 logical CPUs | 1523.325 | 2.140 PASS | 2031484456 |

Encode is process wall clock around the encoder. Full decode is timed only around the library call, with archive resident and output allocated and prefaulted. All decoded bytes are compared with the concatenated input outside the timer.
The declared resource edge is eight copies (2,031,484,456 input bytes). Every curve point, repetition, command, archive hash, machine and library version is retained in `results.jsonl` and `.work/throughput-raw.json`.

The ACEAPEX full-decode API has no thread-count argument. Its pinned implementation creates 8 reconstruction workers and up to 8 literal workers; the exact runner CPU count is printed in each row. Therefore its reported full-decode rate is not a one-thread result.

GPU remains a separate path and is not inferred from these CPU measurements.

GPU evidence follows as a separate provenance group. Stop for review before merge or the three-machine experiment.

## zstd-seekable frame-size frontier

Only frame size changes: zstd 1.5.7, level 3, one encoder thread, the same chr1 bytes and the same 16 KiB API requests. Region timers reuse one resident `ZSTD_seekable` handle. Full-decode speed is published only if the standard plateau rule is reached.

| frame bytes | Ratio incl. seek table | Region p50 ms | Region p99 ms | Amplification | Plateau full decode MB/s |
|---:|---:|---:|---:|---:|---|
| 16384 | 3.025774 | 0.045859 | 0.063288 | 2.000000 | 709.307 |
| 65536 | 3.146897 | 0.060676 | 0.129817 | 5.040000 | 1021.890 |
| 262144 | 3.099202 | 0.136185 | 0.380864 | 12.240000 | 966.701 |
| 2097152 | 3.258310 | 0.995506 | 2.380872 | 71.275000 | 1094.171 |

This is a measured tradeoff curve, not a single ‘zstd versus ACEAPEX’ point: larger frames may improve density or sequential decode while increasing the amount of work touched by a 16 KiB request. The table prints the observed result even when that expectation does not hold.

## GPU — separately declared device-resident path

These points are owner-supplied declarations, not measurements made by this runner. They use ACEAPEX `606f6fc`, G=16, chr1 MD5 `9465e0f0df6e2c6eb39729c39cee5465`, driver 580.178.04 and CUDA 12.4.131; every published point names its block size and reports `MATCHES OK`. Exact raw pod logs were not supplied, so no row is promoted to `measured`.

| Codec | GPU | VRAM | block bytes | reported / ceil blocks | Full decode GB/s | wall ms | streams.bin MD5 | status |
|---|---|---:|---:|---:|---:|---:|---|---|
| ACEAPEX | RTX PRO 4000 Blackwell | 24 GB | 8192 | 30997 / 30998 | 112.8 | 2.25 | n/a: per-point stream hash not supplied | declared |
| ACEAPEX | RTX PRO 4000 Blackwell | 24 GB | 16384 | 15498 / 15499 | 99.2 | 2.56 | 07d7cb1e946d9e0637de976640383c31 | declared |
| ACEAPEX | H100 80GB HBM3 | 80 GB | 4096 | 61995 / 61996 | 179.8 | n/a | n/a: per-point stream hash not supplied | declared |
| ACEAPEX | H100 80GB HBM3 | 80 GB | 8192 | 30997 / 30998 | 160.7 | n/a | n/a: per-point stream hash not supplied | declared |
| ACEAPEX | H100 80GB HBM3 | 80 GB | 16384 | 15498 / 15499 | 128.0 | n/a | 07d7cb1e946d9e0637de976640383c31 | declared |
| bgzip+htslib | n/a | n/a | n/a | n/a | n/a | n/a | n/a | no GPU decoder in benchmark adapter |
| zstd-seekable | n/a | n/a | n/a | n/a | n/a | n/a | n/a | no GPU decoder in benchmark adapter |

The supplied full-decode block counts are one below `ceil(253935557 / block_bytes)` at all three block sizes. They are printed as reported, beside the derived geometry, and remain declared pending the raw log. Full-decode commands omit start/count so the documented CLI selects the complete archive.

The same GPU and corpus change materially with block size: H100 reports 179.8 GB/s at 4 KiB and 128.0 GB/s at 16 KiB; RTX reports 112.8 GB/s at 8 KiB and 99.2 GB/s at 16 KiB. These are supplied observations, not a universal optimum claim.

| GPU | block bytes | start block | count | seek observation | statistic |
|---|---:|---:|---:|---|---|
| RTX PRO 4000 Blackwell | 16384 | 5000 | 1 | 575–783 us (spread 36%) | single supplied observation; not p50/p99 |
| RTX PRO 4000 Blackwell | 16384 | 5000 | 100 | 670 us | single supplied observation; not p50/p99 |

No p50/p99 is inferred from the supplied seek range.

| GPU | block bytes | blocks | composition scan / sequential | verdict |
|---|---:|---:|---:|---|
| RTX PRO 4000 Blackwell | 16384 | 15499 | 0.87× | FAIL |
| H100 80GB HBM3 | 16384 | 15499 | 1.81× | PASS |

The RTX 0.87× result is retained as FAIL: composition scan lost. H100 won at the matched 15,499-block point.

The CPU table now supports a precise statement: ACEAPEX dense is the densest configuration, while ACEAPEX interactive has the fastest plateau-qualified full decode. Both ACEAPEX profiles lose encode throughput to zstd-seekable and lose the single-region p50 comparison. GPU rows are separate and do not establish a cross-codec GPU ranking.

Not published as headline rows: the old 172 GB/s and 0.36 ms values; the FASTQ result without corpus URL/MD5; plateau samples without their concatenation commands; composition/capacity points without an unambiguous block/input mapping.

Stop for review before merge.

These are descriptive comparisons against the same-machine baseline, not promises that any codec must win.
A slower codec remains FAIL in this table; correctness failures abort report generation.

## Reproduce

On Linux, install `build-essential git python3 pkg-config libhts-dev tabix zlib1g-dev`,
then run `./run.sh`. The script downloads chr1, checks its uncompressed MD5, and
checks out ACEAPEX at `1b13df34ac8e839dd3232b59bc59560d689a435a` plus zstd v1.5.7.
Only dependency clones inside this benchmark are used.

`run.sh` builds three codec adapters, compresses four configurations, verifies
all four full restores by MD5 and direct byte comparison, then measures and
verifies every region, followed by batch/H_alpha and break-even by default.
Use `./run.sh --stage 1` to stop after regions. `results.jsonl` has one row per measurement or relation,
with configuration, commands, library/compiler versions, hardware, archive SHA-256
and corpus provenance. `python3 harness/report.py` regenerates this README.
Raw latency and amplification samples are retained separately with SHA-256 hashes.

## API-only contract (api-bytes-v3)

* All archives contain identical original FASTA bytes. Every request is exactly
  16,384 original-file bytes at the same zero-based byte offset for all four rows.
  No FASTA parsing, base-coordinate mapping or newline removal occurs in a timer.
* BGZF uses htslib `bgzf_useek` followed by `bgzf_read`; both calls are timed
  together, including any decompression performed by the seek. It uses the
  required GZI index, which is included in ratio. FAI is not needed by this raw-byte
  API. This replaces the earlier faidx sequence operation, which processed FASTA.
* zstd uses `ZSTD_seekable_decompress`; ACEAPEX uses `aceapex_decompress_region`.
  Return-code checks, byte validation and output serialization follow the timer.
  Caller buffers, handles and archive loading are prepared before measurement;
  allocation performed internally by a library is part of its API cost.
* Archives remain resident: anonymous Linux memfd for BGZF and malloc buffers for
  zstd/ACEAPEX. One BGZF handle/index and one zstd seekable handle are reused.
  The ACEAPEX API takes the resident buffer directly. No per-query process or open.
* Two untimed boundary checks plus ten random warmups precede 200 timed queries.
  Every result, including warmup and boundary results, is byte-verified. All rows
  use seed 20260909 and the same trace. Quantiles use nearest rank (indices 99/197).
* Amplification counts decoded chunk bytes / requested bytes. BGZF counts the
  bytes expanded by inflate/libdeflate. zstd counts actual block reconstruction,
  including output still buffered inside the library. ACEAPEX counts every decoded
  chunk in the literal, offset, length and command streams, with per-stream totals.
  A separate counting executable is built from generated dependency copies, with
  original/generated source hashes retained; latency uses untouched source objects.
* `block` is the independent access unit in bytes. BGZF reports its 65536-byte
  ceiling (actual blocks may be shorter); zstd reports the configured frame size;
  ACEAPEX reports the profile block size. Rows with unequal block sizes are explicit.

## ACEAPEX configurations

The encoder is the unchanged `aceapex_depth.cpp` from the pinned commit, built
with g++ `-O3 -std=c++17 -pthread`. The API uses unchanged `src/aceapex_api.cpp`
with the same flags; no architecture-specific optimization is added.
Both link the pinned static libzstd. The CLI's printed historical profile figures
are labels from upstream source, not observations; only measured values enter
this report. Ratio always uses complete archive bytes, including headers/tables.

Compression explicitly uses `--profile interactive` or `--profile dense`,
`--level 2 --threads 1`. Codec override environment variables are cleared before
encoding because upstream environment takes precedence over `--profile`.
The script checks preset values against the pinned source before running.

| Profile | ACEAPEX_BS | LIT_CHUNK | FSE_CHUNK | MIN_MATCH |
|---|---:|---:|---:|---:|
| interactive | 16384 | 65536 | 4096 | 0 |
| dense | 262144 | 1048576 | 32768 | 0 |

Untimed CLI restore uses the same profile flag. The C region API has no profile
argument, so its child process receives the matching environment above. Each
measurement records that environment and the command; no profile is inherited
from another measurement. Thread count is the encoder request; internal entropy
workers may differ. No throughput claim is made from these correctness runs.

The two ACEAPEX rows expose its measured size/access tradeoff alongside BGZF
level 6 and zstd-seekable level 3 (16 KiB frames). They do not establish a global
Pareto frontier or imply other codecs have no tunable parameters.

Absolute timings are declared. Same-run relations to BGZF have explicit pass/fail
predicates in protocol.json, including a 1% ratio allowance. A slower row retains
FAIL; byte mismatches abort publication. GPU is a separate measured path and is
never inferred from CPU rows.

## Review boundary and history

This is a new raw-byte operation contract. Do not compare its latency directly
with historical faidx/sequence timings or the 0.082 ms declared reference on
another machine. The former results and matched-harness investigation remain in
[AUDIT.md](AUDIT.md) and [historical evidence](evidence/).
[Exact FAIL output from EPYC 9V74](evidence/audit-20260909/FAILS.md) is preserved.

Batch, H_alpha and break-even are implemented as specified in [BATCH_METHOD.md](BATCH_METHOD.md).
`./run.sh` also measures independence cost c(g) and CPU plateau throughput;
`--stage 2` stops before c(g), and `--stage 3` stops before throughput. The
plateau contract is in [THROUGHPUT.md](THROUGHPUT.md). The next review stop
precedes the three-machine experiment and separate GPU publication.
The previous controlled audit is reproduced at benchmark commit
`baede64fd37bd087eecf9a94333d8fbf33e23c33`; its script depends on that historical
harness and original ACEAPEX pin.

## Negative c(g)

**Splitting can improve compression:** the [reviewed zstd-seekable 1 MiB point](review/CG_BASELINE_REVIEW.md)
has `c(g) = -0.509942%`: 78,013,034 bytes versus 78,410,855 bytes for the whole-input
baseline, including container overhead. A negative sign is a valid outcome, not
by itself an error. Local entropy adaptation can in principle outweigh lost
cross-boundary matches and added framing costs; this run does not isolate that
mechanism. Zstd already permits new entropy tables within a frame
([RFC 8878, section 3.1.1.3](https://www.rfc-editor.org/rfc/rfc8878.html#section-3.1.1.3)),
so the result does not establish that frame splitting alone enabled local adaptation.
The baseline's empty terminal frame remains included; see the linked review.

## License

Code: [Apache-2.0](LICENSE). Measurements: [CC BY 4.0](evidence/LICENSE).
Third-party code retains its own licenses; see [NOTICE](NOTICE).

