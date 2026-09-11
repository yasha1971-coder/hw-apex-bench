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

## Comparison discipline

* Absolute latency and MB/s belong to the recorded machine. Normalize only to a
  baseline from the same run, corpus, request trace and operation. A normalized
  ratio is not guaranteed to remain constant on another architecture. Never mix
  a historical default, an interactive profile and a new-default measurement.
* Display the codec revision, block/frame size, literal/FSE units where applicable,
  encoder workers and decoder workers beside the row. Unequal full-decoder worker
  counts remain explicit and do not establish an equal-thread speed comparison.
* A full-file measurement is not automatically a throughput plateau. Grow the
  workload and recompute stability from the repetitions; otherwise retain
  `data edge` with the reason and do not print a headline rate.
* The 1% ratio comparison tolerance is a declared protocol allowance, not a
  correction applied to file sizes. libzstd and htslib versions remain recorded;
  no fixed version-induced density change is assumed without a matched experiment.
* Keep losses beside wins. Unsupported native batch is generated from the row's
  capability and reason; its measured single-call loop remains a separate method.
  Every missing table cell says `n/a — reason`; it is never blank or zero-filled.
* The retained JSONL is immutable evidence. Render README and the coverage report
  from those records, verify exact reproduction, then update the publication
  manifest only for reviewed data or explicitly explained rendering changes.

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

## Check a codec adapter

Run `./run.sh --check codecs/xz.sh` for a small correctness check, or
`./run.sh --check` for all four adapters. This builds pinned dependencies and
checks byte-exact full and native regional restoration without collecting timings
or modifying published results. See [ADAPTERS.md](ADAPTERS.md) for prerequisites,
the seven-function contract, explicit unsupported axes and current integration limits.

## License

Code: [Apache-2.0](LICENSE). Measurements: [CC BY 4.0](evidence/LICENSE).
Third-party code retains its own licenses; see [NOTICE](NOTICE).
