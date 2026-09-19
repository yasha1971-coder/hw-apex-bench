# Access-entropy sweep v1

Question: does native-batch advantage increase as request starts concentrate, and at
what measured access entropy does ACEAPEX dense exceed ACEAPEX interactive?

This is a bounded follow-up to the existing batch axis, not a new axis.

## Frozen scope

- corpus: hg38 chr1 FASTA, 253,935,557 bytes,
  MD5 `9465e0f0df6e2c6eb39729c39cee5465`
- request length: 16,384 bytes
- requests per point: 5,000
- workers: 1
- one GitHub-hosted Ubuntu 24.04 x86_64 runner for all timing points
- current repository adapters, unchanged:
  - `codecs/bgzip.sh`
  - `codecs/zstd_seekable.sh`
  - `codecs/aceapex.sh` (interactive)
  - `codecs/aceapex_dense.sh` (dense)
- same `harness/native_batch.c` judge and timing boundary
- three repetitions per available method; ranges/s uses N / median wall time
- every returned range is compared byte-for-byte with the original outside timing
- ACE native batch uses one requested worker
- BGZF and zstd-seekable batch stay `n/a`: their current adapters expose no
  native batch API

## Access distributions

The common workload entropy is Shannon entropy of request-start counts on the
shared 16 KiB grid, so the x-coordinate is identical across codecs.

Four deterministic traces are used:

- uniform: the existing shared uniform N=5000 trace
- finite Zipf traces with retained exponents chosen only to place the *measured*
  common-grid entropy near 8, 4 and 2 bits

The report publishes measured `H_alpha`, not the requested Zipf exponent.
The exponent remains in provenance only to reproduce the exact trace.

Target guard bands are ±0.15 bit around 12 / 8 / 4 / 2.

Codec-block entropy is also retained as provenance because BGZF has variable block
boundaries and ACE dense uses 256 KiB blocks. It is not used as the common x-axis.

## Output

One table only:

`workload, measured H_alpha, codec, codec-block H_alpha, loop ranges/s,
native-batch ranges/s, batch/loop`.

The report then answers only:

1. whether measured batch/loop speedup increases as common H_alpha falls;
2. the first measured H_alpha at which dense batch ranges/s exceeds interactive
   batch ranges/s, or the bracket/no-crossing if applicable.

No format changes, GPU work, new benchmark axes, homepage changes, or unrelated
measurements are part of this PR.
