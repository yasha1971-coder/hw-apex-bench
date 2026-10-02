# Corruption robustness and single-region latency — protocol

Status: protocol / implementation branch. No external publication. No imported ACEAPEX number is a cross-codec result until measured by this common harness.

## Axis 10: corruption robustness

Input: one frozen 16 MiB slice of hg38 chr1 FASTA. The slice coordinates, byte SHA-256 and source chr1 MD5 are part of the receipt.

Each codec compresses the same bytes itself using its declared default configuration. Test both integrity modes where the format supports them:
- zstd: frame checksum on / off;
- lz4 frame: content checksum on / off;
- BGZF: CRC32 is mandatory, therefore checksum-off is n/a;
- ACEAPEX: XXH3 on / off.

Codecs in the first matrix: ACEAPEX CPU, ACEAPEX GPU, zstd, BGZF+htslib, lz4 frame. Every row records exact codec/source version, command/API, CPU/GPU, device/driver when applicable, archive SHA-256, host and seed.

For each codec × integrity mode create 10,000 independent corrupted archive copies from the same clean archive. Publish the PRNG algorithm and fixed seed. Corruption classes are balanced across the run:
1. bit flip;
2. replace 1–16 bytes with PRNG bytes;
3. zero a 16–4096 byte run;
4. truncation;
5. corruption constrained to the first 1024 archive bytes ("header");
6. corruption constrained to bytes after offset 1024 ("payload").

Because 10,000 is not divisible by six, assignment MUST be deterministic and near-balanced (count difference <=1), and the exact per-class counts are written to the receipt. Header/payload are location constraints, not extra hidden severity classes; the harness must record both mutation operator and location for every case so categories cannot overlap ambiguously.

Every case is executed out-of-process behind a 10 s watchdog so crashes/hangs are observable uniformly. Classify exactly one terminal outcome:
- rejected_before_decode;
- caught_during_decode;
- harmless (decoder success and output byte-identical to input);
- silent_error (decoder success and output differs);
- hang;
- process_crash.

"Rejected before decode" requires an explicit validation/open stage exposed by that codec adapter; otherwise n/a/0 must not be inferred from a decoder failure. Exit status alone is insufficient to call a silent error: output bytes must be compared with the frozen input.

Primary result is counts and rates by codec, integrity mode, mutation operator and location, plus totals. Do not rank rows that have different integrity semantics.

Reference-only until replaced by this harness: ACEAPEX private stress on H100/Blackwell reported 0 hangs and 0 silent errors with XXH3; 131 silent errors without hash. Its mutation distribution differs and is not a benchmark row.

## Axis 11: single-region latency

Corpora: hg38 chr1 and T2T-CHM13v2.0, each pinned by URL/checksum and exact uncompressed bytes.

Generate exactly 10,000 random byte regions of length 5,000 from each corpus with one published PRNG algorithm/seed and retain the request list. All codecs consume the identical request list for a corpus. Every returned region is byte-compared with the original FASTA.

Report nearest-rank p50 and p99 in microseconds, plus sample count. Record:
- CPU or GPU;
- resident/in-memory archive state;
- in-process library call or process-per-request;
- threads/workers;
- block/token/literal granularity;
- exact codec version/commit;
- host/device/driver/runtime;
- command/API and warmup policy.

In-process and process-per-request are different scopes and MUST NOT share a ranking/table ordering. GPU resident rows also remain a distinct execution scope unless another codec is measured under the same boundary.

Imported 2026-10-02 ACEAPEX numbers are reference/evidence only until the common request list is run:
- ace-core CPU, one thread, open token chunk 16 KiB at/after 7bb790f: T2T 91.2/160.9 us; chr1 44.3/82.6 us.
- prior 64 KiB: T2T 114.6/242.4 us; chr1 69.2/109.5 us.
- resident GPU: Blackwell 64 KiB 749/2010 us; Blackwell 16 KiB 502/950 us; H100 16 KiB 540/1077 us.
- BGZF/samtools faidx Colab: process/request 1165/1322 us; one invocation about 110 us/region. These are separate modes.
- AGC 3.2.4 HPRC 1–4 assemblies: 15.3–22.8 ms/process; different corpus and process scope, reference only.

## Hardware/full-decode context (not Axis 11 region rows)

Retain as dated external/reference evidence until reproduced under a hw-apex-bench common full-decode protocol:
- H100 80GB HBM3: HPRC 10 assemblies 30.48 GB, 158.8 ms = 192 GB/s, 10/10 bit-perfect; T2T 19.06 ms.
- RTX Pro 6000 Blackwell: T2T 18.5 ms; saturation 176 GB/s at 11 copies.
- ace-core CPU, 16 threads: T2T 17.4 GB/s; chr1 17.4 GB/s.

## ACEAPEX upstream provenance supplied 2026-10-02

- 946591a65b532017cb3fd71ac92d6fc68ef732d1 — merged gpu-hang corruption/hang fixes.
- 7bb790f0152966699ee77740b42f01d8e70eccaf — open profile 16 KiB token chunks by default.
- 207bf0042dfd410f908f3b8eeb7bc8701bdbf3ee — research2/pangenome work.

These commits explain provenance; the axis definitions remain codec-neutral.

## Publication gate

Nothing from this branch is promoted to README/Pages, releases, papers or external posts without an explicit user instruction. Historical evidence is immutable.
