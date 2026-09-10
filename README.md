# hw-apex-bench — Compressed Access Benchmark

Three codecs, four configurations. API-only byte regions; implemented axes and review boundary are below.

Run: 2026-09-10T01:04:32.803016+00:00. Benchmark commit: bc8e5a99fe6878e3a7e0f70cc432cb12e193f9e0.

Corpus: chr1 hg38 FASTA, MD5 9465e0f0df6e2c6eb39729c39cee5465.

libzstd: *** Zstandard CLI (64-bit) v1.5.7, by Yann Collet ***; htslib: 1.19; bgzip: bgzip (htslib) 1.19.
C: gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0; C++: g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0.
ACEAPEX: 1b13df34ac8e839dd3232b59bc59560d689a435a; zstd reference implementation: f8745da6ff1ad1e7bab384bd1f9d742439278e99.

Machine: Linux-6.17.0-1022-azure-x86_64-with-glibc2.39; logical CPUs: 4.
Model name:                              AMD EPYC 7763 64-Core Processor
Hardware details, parameters and commands accompany every measurement in results.jsonl.

| Configuration | Level | Encoder threads | Block/frame bytes | LIT bytes | FSE bytes |
|---|---:|---:|---:|---:|---:|
| bgzip+htslib | 6 | 1 | BGZF variable (<=65536 uncompressed) | n/a | n/a |
| zstd-seekable | 3 | 1 | 16384 | n/a | n/a |
| aceapex-interactive | 2 | 1 | 16384 | 65536 | 4096 |
| aceapex-dense | 2 | 1 | 262144 | 1048576 | 32768 |

| Codec / profile | block (bytes) | Ratio incl. indexes | Region p50 ms | Region p99 ms | Output amplification | GPU |
|---|---:|---:|---:|---:|---:|---|
| bgzip+htslib | 65536 | 3.382558 | 0.117187 | 0.244023 | 4.821094 | n/a |
| zstd-seekable | 16384 | 3.025774 | 0.070370 | 0.104574 | 2.000000 | n/a |
| aceapex-interactive | 16384 | 3.658493 | 0.158624 | 0.289628 | 6.216250 | n/a |
| aceapex-dense | 262144 | 3.780646 | 1.353232 | 2.535737 | 83.431872 | n/a |

Every timed operation reads the same 16,384 original-file bytes. No FASTA parsing is timed.
Amplification is **actual decoded chunk bytes / requested bytes** in a separate counted pass.
BGZF counts decompressed blocks, zstd counts reconstructed blocks within frames (including buffered output), and ACEAPEX counts the decoded chunks of all four streams. Raw per-stream totals are retained.
BGZF block=65536 is its size ceiling; actual blocks may be shorter. Different block limits are explicit, not normalized away.

| Codec | block (bytes) | Ratio / bgzip >= 0.99 | p50 / bgzip <= 1 | p99 / bgzip <= 1 |
|---|---:|---|---|---|
| bgzip+htslib | 65536 | 1.0000 — PASS | 1.0000 — PASS | 1.0000 — PASS |
| zstd-seekable | 16384 | 0.8945 — FAIL | 0.6005 — PASS | 0.4285 — PASS |
| aceapex-interactive | 16384 | 1.0816 — PASS | 1.3536 — FAIL | 1.1869 — FAIL |
| aceapex-dense | 262144 | 1.1177 — PASS | 11.5476 — FAIL | 10.3914 — FAIL |

## Break-even

Model: independent 16 KiB reads at their measured p50 versus one full library decode.
Smallest integer N with N × p50 > full decode time; full time is the median of five verified decodes after one warmup.
This is a derived intersection, not an observed batch crossover or a plateau-throughput measurement.

| Codec/profile | block bytes | Full decode ms | Region p50 ms | Break-even N | Full decoder threads |
|---|---:|---:|---:|---:|---|
| bgzip+htslib | 65536 | 433.359050 | 0.117187 | 3699 | single decoder thread |
| zstd-seekable | 16384 | 523.952488 | 0.070370 | 7446 | single decoder thread |
| aceapex-interactive | 16384 | 219.723264 | 0.158624 | 1386 | 8 reconstruction workers; literal workers up to 8; API has no thread argument |
| aceapex-dense | 262144 | 176.135476 | 1.353232 | 131 | 8 reconstruction workers; literal workers up to 8; API has no thread argument |

## Batch

Identical raw-byte requests across codecs; every native batch answer matches the single-call result and original bytes.
Three repetitions, median duration; loop/native order alternates. Native batch threads are requested explicitly.
H_alpha counts request-start blocks (actual GZI boundaries for BGZF, declared frame/block boundaries otherwise). H_alpha_16k is also recorded.
bgzip and zstd-seekable native batch: n/a (no native batch API in these adapters); their measured method is loop.
All N=100/600/2000/5000 points are in [BATCH_RESULTS.md](BATCH_RESULTS.md). The fixed N=5000 view follows.

| Codec/profile | block bytes | Access profile | method | N | H_alpha bits | Threads requested | ranges/s | / bgzip loop |
|---|---:|---|---|---:|---:|---:|---:|---|
| bgzip+htslib | 65536 | uniform | loop | 5000 | 11.285997 | 1 | 7274.140 | 1.000 PASS |
| zstd-seekable | 16384 | uniform | loop | 5000 | 11.993736 | 1 | 14913.914 | 2.050 PASS |
| aceapex-interactive | 16384 | uniform | loop | 5000 | 11.993736 | 1 | 5785.304 | 0.795 FAIL |
| aceapex-interactive | 16384 | uniform | batch | 5000 | 11.993736 | 4 | 26950.322 | 3.705 PASS |
| aceapex-dense | 262144 | uniform | loop | 5000 | 9.774765 | 1 | 628.045 | 0.086 FAIL |
| aceapex-dense | 262144 | uniform | batch | 5000 | 9.774765 | 4 | 32190.077 | 4.425 PASS |
| bgzip+htslib | 65536 | sorted | loop | 5000 | 11.285997 | 1 | 12858.892 | 1.000 PASS |
| zstd-seekable | 16384 | sorted | loop | 5000 | 11.993736 | 1 | 15980.975 | 1.243 PASS |
| aceapex-interactive | 16384 | sorted | loop | 5000 | 11.993736 | 1 | 6102.199 | 0.475 FAIL |
| aceapex-interactive | 16384 | sorted | batch | 5000 | 11.993736 | 4 | 27111.508 | 2.108 PASS |
| aceapex-dense | 262144 | sorted | loop | 5000 | 9.774765 | 1 | 634.640 | 0.049 FAIL |
| aceapex-dense | 262144 | sorted | batch | 5000 | 9.774765 | 4 | 31989.789 | 2.488 PASS |
| bgzip+htslib | 65536 | clustered | loop | 5000 | 10.387857 | 1 | 7610.407 | 1.000 PASS |
| zstd-seekable | 16384 | clustered | loop | 5000 | 11.574142 | 1 | 14718.325 | 1.934 PASS |
| aceapex-interactive | 16384 | clustered | loop | 5000 | 11.574142 | 1 | 6065.674 | 0.797 FAIL |
| aceapex-interactive | 16384 | clustered | batch | 5000 | 11.574142 | 4 | 50999.866 | 6.701 PASS |
| aceapex-dense | 262144 | clustered | loop | 5000 | 8.688593 | 1 | 630.455 | 0.083 FAIL |
| aceapex-dense | 262144 | clustered | batch | 5000 | 8.688593 | 4 | 44265.070 | 5.816 PASS |
| bgzip+htslib | 65536 | hot-set | loop | 5000 | 6.155796 | 1 | 7030.084 | 1.000 PASS |
| zstd-seekable | 16384 | hot-set | loop | 5000 | 5.987822 | 1 | 15468.923 | 2.200 PASS |
| aceapex-interactive | 16384 | hot-set | loop | 5000 | 5.987822 | 1 | 6063.478 | 0.863 FAIL |
| aceapex-interactive | 16384 | hot-set | batch | 5000 | 5.987822 | 4 | 545627.023 | 77.613 PASS |
| aceapex-dense | 262144 | hot-set | loop | 5000 | 5.951825 | 1 | 692.639 | 0.099 FAIL |
| aceapex-dense | 262144 | hot-set | batch | 5000 | 5.951825 | 4 | 124686.858 | 17.736 PASS |
| bgzip+htslib | 65536 | zipf1.2 | loop | 5000 | 5.244881 | 1 | 9091.640 | 1.000 PASS |
| zstd-seekable | 16384 | zipf1.2 | loop | 5000 | 6.808726 | 1 | 15954.848 | 1.755 PASS |
| aceapex-interactive | 16384 | zipf1.2 | loop | 5000 | 6.808726 | 1 | 6768.610 | 0.744 FAIL |
| aceapex-interactive | 16384 | zipf1.2 | batch | 5000 | 6.808726 | 4 | 103419.838 | 11.375 PASS |
| aceapex-dense | 262144 | zipf1.2 | loop | 5000 | 3.787940 | 1 | 756.903 | 0.083 FAIL |
| aceapex-dense | 262144 | zipf1.2 | batch | 5000 | 3.787940 | 4 | 33727.583 | 3.710 PASS |

The full matrix keeps native batch and loop visible separately; a failed speed relation remains FAIL.
The prior EPYC 9V74 4.78× result remains unchanged in [historical evidence](evidence/audit-20260909/FAILS.md).

| Historical machine | Reported batch/loop | Evidence status |
|---|---:|---|
| EPYC 9V74 | 4.78× | measured, preserved original log; below its upstream 5× predicate |
| EPYC 4344P | 13.3× | declared by user; matching command/configuration/receipt unavailable here |

These historical points use another protocol and are not inputs to current pass/fail.
The old parse checks without numpy are interpreted as skipped (missing dependency); the original FAIL text is preserved.

Stop for review here. c(g), plateau throughput and the subsequent three-machine run remain deferred.
See [batch protocol and upstream attribution](BATCH_METHOD.md).


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
FAIL; byte mismatches abort publication. GPU is n/a for all current adapters.

## Review boundary and history

This is a new raw-byte operation contract. Do not compare its latency directly
with historical faidx/sequence timings or the 0.082 ms declared reference on
another machine. The former results and matched-harness investigation remain in
[AUDIT.md](AUDIT.md) and [historical evidence](evidence/).
[Exact FAIL output from EPYC 9V74](evidence/audit-20260909/FAILS.md) is preserved.

Batch, H_alpha and break-even are implemented as specified in [BATCH_METHOD.md](BATCH_METHOD.md).
The review stop now precedes independence cost c(g), encode/full-decode plateau
throughput, and the subsequent three-machine experiment. Those remain deferred.
The previous controlled audit is reproduced at benchmark commit
`baede64fd37bd087eecf9a94333d8fbf33e23c33`; its script depends on that historical
harness and original ACEAPEX pin.

