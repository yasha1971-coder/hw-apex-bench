# hw-apex-bench — Compressed Access Benchmark

Three codecs, four configurations. API-only byte regions; implemented axes and review boundary are below.

Run: 2026-09-10T06:29:06.811389+00:00. Benchmark commit: 1a406213bb4d46b3cfbf26b10f11ce5bd1986be8.

Corpus: chr1 hg38 FASTA, MD5 9465e0f0df6e2c6eb39729c39cee5465.

libzstd: *** Zstandard CLI (64-bit) v1.5.7, by Yann Collet ***; htslib: 1.19; bgzip: bgzip (htslib) 1.19.
C: gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0; C++: g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0.
ACEAPEX: 1b13df34ac8e839dd3232b59bc59560d689a435a; zstd reference implementation: f8745da6ff1ad1e7bab384bd1f9d742439278e99.

Machine: Linux-6.17.0-1022-azure-x86_64-with-glibc2.39; logical CPUs: 4.
Model name:                              INTEL(R) XEON(R) PLATINUM 8573C
Hardware details, parameters and commands accompany every measurement in results.jsonl.

| Configuration | Level | Encoder threads | Block/frame bytes | LIT bytes | FSE bytes |
|---|---:|---:|---:|---:|---:|
| bgzip+htslib | 6 | 1 | BGZF variable (<=65536 uncompressed) | n/a | n/a |
| zstd-seekable | 3 | 1 | 16384 | n/a | n/a |
| aceapex-interactive | 2 | 1 | 16384 | 65536 | 4096 |
| aceapex-dense | 2 | 1 | 262144 | 1048576 | 32768 |

| Codec / profile | block (bytes) | Ratio incl. indexes | Region p50 ms | Region p99 ms | Output amplification | GPU |
|---|---:|---:|---:|---:|---:|---|
| bgzip+htslib | 65536 | 3.382558 | 0.105439 | 0.223233 | 4.821094 | n/a |
| zstd-seekable | 16384 | 3.025774 | 0.053565 | 0.064072 | 2.000000 | n/a |
| aceapex-interactive | 16384 | 3.658493 | 0.150747 | 0.296439 | 6.216250 | n/a |
| aceapex-dense | 262144 | 3.780646 | 1.456867 | 2.720931 | 83.431872 | n/a |

Every timed operation reads the same 16,384 original-file bytes. No FASTA parsing is timed.
Amplification A = sum_q(sum of bytes actually expanded by the decoder for query q) / sum_q(requested bytes) = decoded bytes / (200 × 16384).
BGZF counts decompressed blocks, zstd counts reconstructed blocks within frames (including buffered output), and ACEAPEX counts only touched chunks in the literal, offset, length and command streams, not the complete streams. Repeated expansions count each time.
BGZF block=65536 is its size ceiling; actual blocks may be shorter. An unaligned request can cross block and entropy-chunk boundaries. (64 + 3 × 4) / 16 = 4.75 describes exactly one chunk of each kind, not a constant for arbitrary offsets. See [the trace explanation](AMPLIFICATION.md).

| Codec | block (bytes) | Ratio / bgzip >= 0.99 | p50 / bgzip <= 1 | p99 / bgzip <= 1 |
|---|---:|---|---|---|
| bgzip+htslib | 65536 | 1.0000 — PASS | 1.0000 — PASS | 1.0000 — PASS |
| zstd-seekable | 16384 | 0.8945 — FAIL | 0.5080 — PASS | 0.2870 — PASS |
| aceapex-interactive | 16384 | 1.0816 — PASS | 1.4297 — FAIL | 1.3279 — FAIL |
| aceapex-dense | 262144 | 1.1177 — PASS | 13.8172 — FAIL | 12.1887 — FAIL |

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
| bgzip+htslib | 65536 | 400.811233 | 0.105439 | 3802 | single decoder thread |
| zstd-seekable | 16384 | 422.275401 | 0.053565 | 7884 | single decoder thread |
| aceapex-interactive | 16384 | 228.772285 | 0.150747 | 1518 | 8 reconstruction workers; literal workers up to 8; API has no thread argument |
| aceapex-dense | 262144 | 198.560594 | 1.456867 | 137 | 8 reconstruction workers; literal workers up to 8; API has no thread argument |

## Batch

Identical raw-byte requests across codecs; every native batch answer matches the single-call result and original bytes.
Three repetitions, median duration; loop/native order alternates. Both loop and batch use one worker (loop1-vs-batch1).
H_alpha counts request-start blocks (actual GZI boundaries for BGZF, declared frame/block boundaries otherwise). H_alpha_16k is also recorded.
bgzip and zstd-seekable native batch: n/a (no native batch API in these adapters); their measured method is loop.
All N=100/600/2000/5000 points are in [BATCH_RESULTS.md](BATCH_RESULTS.md). The fixed N=5000 view follows.

| Codec/profile | block bytes | Access profile | method | N | H_alpha bits | Threads requested | ranges/s | / bgzip loop |
|---|---:|---|---|---:|---:|---:|---:|---|
| bgzip+htslib | 65536 | uniform | loop | 5000 | 11.285997 | 1 | 7949.367 | 1.000 PASS |
| zstd-seekable | 16384 | uniform | loop | 5000 | 11.993736 | 1 | 18961.544 | 2.385 PASS |
| aceapex-interactive | 16384 | uniform | loop | 5000 | 11.993736 | 1 | 5919.569 | 0.745 FAIL |
| aceapex-interactive | 16384 | uniform | batch | 5000 | 11.993736 | 1 | 10526.068 | 1.324 PASS |
| aceapex-dense | 262144 | uniform | loop | 5000 | 9.774765 | 1 | 592.718 | 0.075 FAIL |
| aceapex-dense | 262144 | uniform | batch | 5000 | 9.774765 | 1 | 11221.386 | 1.412 PASS |
| bgzip+htslib | 65536 | sorted | loop | 5000 | 11.285997 | 1 | 13947.708 | 1.000 PASS |
| zstd-seekable | 16384 | sorted | loop | 5000 | 11.993736 | 1 | 19851.140 | 1.423 PASS |
| aceapex-interactive | 16384 | sorted | loop | 5000 | 11.993736 | 1 | 6064.093 | 0.435 FAIL |
| aceapex-interactive | 16384 | sorted | batch | 5000 | 11.993736 | 1 | 10496.713 | 0.753 FAIL |
| aceapex-dense | 262144 | sorted | loop | 5000 | 9.774765 | 1 | 600.296 | 0.043 FAIL |
| aceapex-dense | 262144 | sorted | batch | 5000 | 9.774765 | 1 | 11102.342 | 0.796 FAIL |
| bgzip+htslib | 65536 | clustered | loop | 5000 | 10.387857 | 1 | 8454.044 | 1.000 PASS |
| zstd-seekable | 16384 | clustered | loop | 5000 | 11.574142 | 1 | 18878.867 | 2.233 PASS |
| aceapex-interactive | 16384 | clustered | loop | 5000 | 11.574142 | 1 | 5876.384 | 0.695 FAIL |
| aceapex-interactive | 16384 | clustered | batch | 5000 | 11.574142 | 1 | 19572.762 | 2.315 PASS |
| aceapex-dense | 262144 | clustered | loop | 5000 | 8.688593 | 1 | 595.297 | 0.070 FAIL |
| aceapex-dense | 262144 | clustered | batch | 5000 | 8.688593 | 1 | 15806.575 | 1.870 PASS |
| bgzip+htslib | 65536 | hot-set | loop | 5000 | 6.155796 | 1 | 7883.483 | 1.000 PASS |
| zstd-seekable | 16384 | hot-set | loop | 5000 | 5.987822 | 1 | 19849.953 | 2.518 PASS |
| aceapex-interactive | 16384 | hot-set | loop | 5000 | 5.987822 | 1 | 5990.699 | 0.760 FAIL |
| aceapex-interactive | 16384 | hot-set | batch | 5000 | 5.987822 | 1 | 271266.964 | 34.410 PASS |
| aceapex-dense | 262144 | hot-set | loop | 5000 | 5.951825 | 1 | 653.958 | 0.083 FAIL |
| aceapex-dense | 262144 | hot-set | batch | 5000 | 5.951825 | 1 | 50391.835 | 6.392 PASS |
| bgzip+htslib | 65536 | zipf1.2 | loop | 5000 | 5.244881 | 1 | 10369.135 | 1.000 PASS |
| zstd-seekable | 16384 | zipf1.2 | loop | 5000 | 6.808726 | 1 | 20346.021 | 1.962 PASS |
| aceapex-interactive | 16384 | zipf1.2 | loop | 5000 | 6.808726 | 1 | 6716.782 | 0.648 FAIL |
| aceapex-interactive | 16384 | zipf1.2 | batch | 5000 | 6.808726 | 1 | 40504.666 | 3.906 PASS |
| aceapex-dense | 262144 | zipf1.2 | loop | 5000 | 3.787940 | 1 | 720.827 | 0.070 FAIL |
| aceapex-dense | 262144 | zipf1.2 | batch | 5000 | 3.787940 | 1 | 12470.876 | 1.203 PASS |

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
| ACEAPEX default @ 7216280 (ace-core, declared) | 16384 | 3.141615 | 3.193722 | — | 1.631528 | 8 |

bgzip+htslib: n/a: gzip and bgzip use different encoder implementations; no same-encoder block-size-only baseline measured.

aceapex-interactive: n/a for this profile/SHA: the strict supplied pair uses the default configuration at 7216280, not `--profile interactive` at 1b13df3.

aceapex-dense: n/a for this profile/SHA: no block-size-only dense pair has been supplied.

ACEAPEX default @ 7216280 uses supplied ace-core file sizes: 80829622 bytes at 16 KiB and 79510864 bytes for one whole-input block. It is marked declared because compiler/libzstd versions, archive hashes and a byte-equal restore receipt were not supplied. The defect is fixed at `ee5a37e`; an independent strict rerun of that new SHA is defined in [the strict reproduction contract](STRICT_CG.md).

Address table component: 15499 blocks × 64 bytes = **991936 bytes**, or
**1.227%** of the complete 80829622-byte 16 KiB archive. This is shown
separately from payload compression and is included in archive c(g).

zstd bases are explicitly zstd 1.5.7 level -3, one continuous frame versus independent 16384-byte frames. The user-reported historical version is 1.4.8 with 6.68%; version change is a hypothesis for the difference, not an attribution established by a matched rerun.
The historical 0.410% is payload-only: it excludes the AET header and 64-byte `BlockOffsets` entry per block. The cross-codec archive ratio includes both. Neither 0.410% nor 6.68% is an acceptance target.

Whole-file means one continuous member/frame/output block, not an unlimited match window. gzip retains its 32 KiB backward-distance limit; this does not make its blocks independent. bgzip adds independent member boundaries, index/headers and implementation differences.
ACEAPEX uses the same pinned binary on both sides. ACEAPEX_BS changes from 16384 or 262144 to 253935557. MIN_MATCH was cleared and defaults to 0. LIT_CHUNK/FSE_CHUNK remain 65536/4096 (interactive) or 1048576/32768 (dense).
Important source-layout correction: at 7216280 the guarded root `aceapex_depth.cpp` is not the source compiled by `make`; the Makefile builds `src/aceapex_main.cpp`, whose corresponding read lacks the `local_pos < ORIGIN_CAP` guard. At 1b13df3 the measured profile pairs use the guarded source. The two revisions and configurations are not interchangeable.

The defect is closed upstream at `ee5a37eda18b81c1300a1ee44a7e06b6be925bd2`.
New benchmark builds use a compiler trace: every actually compiled translation
unit is hashed and checked against the source named by claim provenance before
measurements run. System bgzip/htslib is explicitly `n/a` for source matching,
with the installed binary hash and version recorded instead.
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

Stop for review before plateau throughput and the three-machine experiment.


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
`./run.sh` also measures independence cost c(g); `--stage 2` stops before it.
The next review stop precedes encode/full-decode plateau throughput and the
subsequent three-machine experiment. Those remain deferred.
The previous controlled audit is reproduced at benchmark commit
`baede64fd37bd087eecf9a94333d8fbf33e23c33`; its script depends on that historical
harness and original ACEAPEX pin.
