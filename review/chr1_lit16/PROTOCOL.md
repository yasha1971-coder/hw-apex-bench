# chr1 literal-chunk layer control

Purpose: isolate the literal entropy-granularity layer without changing block
size, request size, FSE granularity or the public region API.

## Frozen comparison

Common to both archives:

- hg38 chr1 FASTA, 253,935,557 B
- MD5 `9465e0f0df6e2c6eb39729c39cee5465`
- ACEAPEX source `dbbb8b774bfe4933d40a3f39d357dc9598947a70`
- zstd `f8745da6ff1ad1e7bab384bd1f9d742439278e99`
- `ACEAPEX_BS=16384`
- `FSE_CHUNK=4096`
- `MIN_MATCH` unset
- request R = 16,384 B
- current public `aceapex_decompress_region`
- same ARM64 runner class, same PMU method and controls

Only literal chunk size changes:

- control: `LIT_CHUNK=65536`
- experiment: `LIT_CHUNK=16384`

Current ACE rejects explicit literal chunks below 64 KiB by converting them to
legacy/no-chunk mode. The experiment therefore compiles a **private encoder
copy only** with the environment gate lowered from 64 KiB to 16 KiB. The
production source and the decoder/API are not modified. Both archives are
decoded by the same unmodified resident library.

## Required outputs

For both archives:

- complete archive bytes and ratio
- bit-perfect full restore
- p50/p99 of 200 resident 16 KiB regions
- p50 temporary requested bytes and allocation/free counts
- five-repeat `perf stat` instructions/cycles with N=0 and ABI-stub controls
- literal chunk geometry parsed from the archive

The instruction delta 64 KiB → 16 KiB is the coarse literal-layer cut requested
for this experiment. No additive decomposition is inferred.

## DCtx audit

Record the source-path fact separately: ACE region decode calls one-shot
`ZSTD_decompress()` from both literal and FSE range decoders. In pinned zstd
1.5.7 with default `ZSTD_HEAPMODE=1`, each such call creates a `ZSTD_DCtx`,
decompresses, and frees the context. This is a candidate fixed per-chunk cost,
not changed in this experiment.

## Stop

After the two-row comparison is retained, stop. Do not integrate rANS,
persistent DCtx reuse, or any production codec change in this task.
