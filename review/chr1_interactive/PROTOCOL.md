# chr1 ACE interactive-profile baseline — control against default

Single assignment: repeat the full-chr1 current-API baseline at the documented
ACEAPEX interactive profile, then stop.

## Frozen configuration

- corpus: UCSC hg38 chr1 FASTA, 253,935,557 B
- uncompressed MD5: `9465e0f0df6e2c6eb39729c39cee5465`
- ACEAPEX source: `4915321bf118e564ef3883e58927992c7f9d8dc3`
- linked zstd: `f8745da6ff1ad1e7bab384bd1f9d742439278e99`
- level 2, eight encoder threads
- g = `ACEAPEX_BS=16384`
- R = 16,384 B
- interactive entropy profile:
  - `LIT_CHUNK=65536`
  - `FSE_CHUNK=4096`
  - `MIN_MATCH` unset
- current public `aceapex_decompress_region` path unchanged
- archive resident before timing
- full native restore must be bit-perfect before any number is accepted

The default baseline is already frozen in
`evidence/chr1-region-cost-20260918/baseline.json`. Its primary structural
reference is 8,796,014 retired instructions/request with default FSE chunks
of 512 KiB.

## Required outputs

Measure on one ARM64 GitHub runner with exposed PMU:

1. current `hc_region` p50/p99, 200 verified 16 KiB requests after 12 warmups;
2. temporary allocation capacity requested per request and alloc/free counts;
3. `perf stat` instructions/cycles using the same 20,000-query + N=0 + ABI-stub
   control method as the default baseline;
4. literal/FSE chunk geometry actually used by the archive/decoder;
5. decoded-byte random-access amplification using the existing ACE counter build
   and the same 200-request trace;
6. complete archive size and ratio;
7. direct instruction delta versus the frozen default baseline.

No new internal timing instrumentation is added. The instruction delta between
default and interactive is the requested coarse cut between the two archive
entropy granularities while keeping block size, request size and public region
API fixed.

## Stop condition

After the table and evidence are committed, stop. Do not integrate rans1_v4,
change the ACE format, or optimize the decoder in this task.
