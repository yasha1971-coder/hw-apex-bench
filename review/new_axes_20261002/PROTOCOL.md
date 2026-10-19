# Corruption robustness and single-region latency — protocol

Status: common CPU harness measured on ace-core; final evidence commit `7bd8e0091d0b54895abc5ad9b354ad7d5f7d5883`. No external publication. GPU remains a later stage.

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

The earlier ACEAPEX private stress is superseded for this axis by the common CPU harness. Final ace-core results (10,000 cases per row, seed 20261002, input chr1 [104857600,121634816), SHA-256 `29a01276c5d4f40d15e6deab7841853d04e55459a3ebe68c77113336ae76fea1`):

| codec | integrity | refused | caught | harmless | SILENT | hang | crash |
|---|---|---:|---:|---:|---:|---:|---:|
| ACEAPEX CPU open 091bb1e | XXH3 | 0 | 9918 | 82 | 0 | 0 | 0 |
| ACEAPEX CPU open 091bb1e | no XXH3 | 0 | 9713 | 93 | 194 | 0 | 0 |
| BGZF / htslib 1.13 | CRC32 mandatory | 0 | 9979 | 20 | 1 | 0 | 0 |
| LZ4 1.9.3 | content checksum | 0 | 9997 | 3 | 0 | 0 | 0 |
| LZ4 1.9.3 | no content checksum | 0 | 3779 | 8 | 6213 | 0 | 0 |
| zstd 1.4.8 | frame checksum | 0 | 9996 | 4 | 0 | 0 | 0 |
| zstd 1.4.8 | no checksum | 0 | 6202 | 3 | 3795 | 0 | 0 |

The single BGZF SILENT case is case 867: truncation exactly at a BGZF block boundary; `bgzip -d` warns that the EOF marker is absent but exits 0 with shorter output, therefore it is SILENT under the common harness definition.

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

Final common-harness CPU results are from evidence commit `7bd8e0091d0b54895abc5ad9b354ad7d5f7d5883`. Every row contains 10,000 identical frozen requests and all returned regions passed their per-region SHA-256.

**In-process scope**

| corpus | codec / decoder | p50 us | p95 us | p99 us |
|---|---|---:|---:|---:|
| chr1 | ACEAPEX 091bb1e C++ `aceapex_decompress_region` | 41.718 | 76.233 | 86.633 |
| chr1 | ACEAPEX 091bb1e C99 decoder | 44.573 | 78.217 | 82.554 |
| chr1 | BGZF htslib | 103.294 | 193.022 | 198.782 |
| T2T | ACEAPEX 091bb1e C++ `aceapex_decompress_region` | 51.085 | 93.365 | 126.647 |
| T2T | ACEAPEX 091bb1e C99 decoder | 47.569 | 89.468 | 114.415 |
| T2T | BGZF htslib | 102.603 | 189.906 | 195.737 |

**Process-per-request scope**

| corpus | codec | p50 us | p95 us | p99 us |
|---|---|---:|---:|---:|
| chr1 | ACEAPEX 091bb1e CLI faidx | 1016.996 | 1185.472 | 1257.116 |
| chr1 | BGZF samtools faidx | 1245.895 | 1457.281 | 1526.971 |
| T2T | ACEAPEX 091bb1e CLI faidx | 1068.694 | 1287.754 | 1357.064 |
| T2T | BGZF samtools faidx | 1892.938 | 2071.453 | 2214.942 |

zstd and lz4 have no random-access index in this axis and therefore have no region latency row. GPU measurements and AGC measurements remain contextual/reference evidence because they were not produced by this common CPU harness.

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
