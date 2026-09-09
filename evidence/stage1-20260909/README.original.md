# hw-apex-bench — Compressed Access Benchmark

Stage 1: first three-codec table, ready for review. Later axes remain deferred.

Run: 2026-09-09T22:37:19.296268+00:00. Benchmark commit: 4f3e3994ce7b10ffbe43ccb7fd1be8b8dd25f2a5.

Corpus: chr1 hg38 FASTA, MD5 9465e0f0df6e2c6eb39729c39cee5465.

libzstd: *** Zstandard CLI (64-bit) v1.5.7, by Yann Collet ***; htslib: 1.19; bgzip: bgzip (htslib) 1.19.
C: gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0; C++: g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0.
ACEAPEX: b1bee4df9c1c0a18d979df2a43947ef1b7adeb57; zstd reference implementation: f8745da6ff1ad1e7bab384bd1f9d742439278e99.

Machine: Linux-6.17.0-1022-azure-x86_64-with-glibc2.39; logical CPUs: 4.
Hardware details, parameters and commands accompany every measurement in results.jsonl.

| Codec | Ratio incl. indexes | Region p50 ms | Region p99 ms | Output amplification | GPU |
|---|---:|---:|---:|---:|---|
| bgzip+htslib | 3.382557 | 0.192881 | 0.321631 | 5.020313 | n/a |
| zstd-seekable | 3.025774 | 0.080781 | 0.096069 | 1.540146 | n/a |
| aceapex | 3.674123 | 0.281506 | 0.438469 | 2.005000 | n/a |

Amplification is reconstructed **FASTA output bytes / requested sequence bytes**.
It excludes intermediate entropy buffers and is not total memory traffic.
BGZF and zstd use decoder-output counters in a separate pass; ACEAPEX uses the exact block span derived from its pinned source and archive header.

| Codec | Ratio / bgzip >= 0.99 | p50 / bgzip <= 1 | p99 / bgzip <= 1 |
|---|---|---|---|
| bgzip+htslib | 1.0000 — PASS | 1.0000 — PASS | 1.0000 — PASS |
| zstd-seekable | 0.8945 — FAIL | 0.4188 — PASS | 0.2987 — PASS |
| aceapex | 1.0862 — PASS | 1.4595 — FAIL | 1.3633 — FAIL |

These are descriptive comparisons against the same-machine baseline, not promises that any codec must win.
A slower codec remains FAIL in this table; correctness failures abort report generation.

## Reproduce

On Linux (Ubuntu/Debian prerequisites):

`sudo apt-get install build-essential git python3 pkg-config libhts-dev tabix zlib1g-dev`

Then run `bash run.sh`. A first run downloads chr1 and the two source dependencies.
ACEAPEX is checked out at an exact 40-character SHA. No existing ACEAPEX,
GLYPH or context working directory is opened or modified.

`run.sh` is the sole benchmark entry point. It builds all three adapters,
verifies the uncompressed UCSC MD5, compresses and fully restores the corpus,
then executes the common library harness. The three-codec table is generated
only when all three codecs pass the full-file and region checks.

The raw query samples and build metadata live under `.work/` and are retained
in the GitHub Actions artifact. Summary records include their SHA-256 digests.
The report can be regenerated with `python3 harness/report.py`.

## Stage-1 contract

* All archives contain the identical original FASTA bytes. Ratio includes
  FAI/GZI sidecars for BGZF. Both archive and index sizes are recorded.
* A query returns 16,384 consecutive chr1 sequence bytes. The zero-based base
  offset is mapped to its FASTA byte span for ACEAPEX/zstd; newline removal
  is included in their timed path, as it is in faidx. This is a genomic
  region workload, not a claim of arbitrary-byte faidx support.
* Every library result is checked byte-for-byte against the original source
  outside the timer. Two boundary probes and ten random warmups precede the
  same 200 deterministic queries per codec. Percentiles use nearest rank.
* Archives are populated before timing: anonymous Linux memfd for htslib and
  heap buffers for ACEAPEX/zstd. FAI/GZI parsing is setup. Initialized decoder
  handles are reused. No process is launched for an individual request.
* Caller-owned buffer allocation, archive loading, initialization, verification
  and serialization are outside the timer. Library-internal allocation remains
  part of its call.
* Uninstrumented latency and instrumented output-byte accounting run separately.
  The output amplification definition excludes intermediate codec streams.
  ACEAPEX's extra entropy work must not be inferred from this number.
* Compression levels are declared: BGZF 6, zstd-seekable 3 with 16 KiB frames,
  ACEAPEX CLI default level, 16 KiB blocks, LIT_CHUNK=65536, FSE_CHUNK=32768,
  MIN_MATCH=0. One encoder thread is requested; ACEAPEX may create additional
  internal entropy workers. The pinned old ACEAPEX decoder needs matching
  FSE_CHUNK environment, so `run.sh` sets it for both encode and decode.
* No encode/full-decode throughput is claimed from a single corpus invocation.
  CLI restore is an untimed correctness check, not a decode benchmark.
* Absolute performance is declared. Same-run relations to BGZF have explicit
  pass/fail predicates in `protocol.json`, including the 1% ratio allowance.
* No GPU code or GPU measurements are present: n/a.

## Review boundary and remaining axes

Stop after this table. Throughput plateau sweeps (or an explicit data-edge
result), independence cost c(g), the five batch profiles, H_alpha and break-even
N are still required for the complete benchmark, and are not implemented or
claimed in stage 1. enwik9, Silesia and FASTQ will receive verified corpus
manifests when their stages are introduced. No URLs or checksums are invented.

`harness/batch.c` and `harness/breakeven.c` will be added after the first table
is reviewed.

