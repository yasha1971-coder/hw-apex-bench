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
