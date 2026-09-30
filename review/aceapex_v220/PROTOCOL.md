# ACEAPEX v2.2.0 refresh protocol — 2026-09-30

## Frozen revisions

- ACEAPEX v2.2.0: `0a143cd64b35a802835f18c361f981968edf25a1`
- zstd reference: `f8745da6ff1ad1e7bab384bd1f9d742439278e99` (1.5.7)
- htslib: `8f7231035d0409d525767c66d9f49f1f967ee1df`
- libdeflate: `dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f`
- ACEAPEX v2.2.0 DOI: 10.5281/zenodo.23061934

ACEAPEX must be built through its upstream `make` target. The exact built binary
SHA-256 and libzstd version are retained in every ACEAPEX result row.

Historical v2.1.0 and earlier measurements remain immutable evidence. No v2.1
number is copied into a v2.2 measurement.

## Matched-g CPU scope

Corpus: the existing thirty frozen T2T-CHM13v2.0 windows, each 2 MiB.

Exact common granularity:
`4096 / 8192 / 16384 / 32768 / 65280 B`.

Rows at every g:

1. ACEAPEX v2.2.0 interactive, DNA default l1 encoder,
   `LIT_CHUNK=65536 FSE_CHUNK=4096`.
2. ACEAPEX v2.2.0 open, same l1 encoder plus `AX_PROFILE=open`.
3. BGZF + htslib.
4. zstd-seekable reference implementation, level 3.

Request: 16 KiB resident byte region. Archive/context setup and output allocation
are outside the timer. Timer wraps only the resident library API. Every returned
range is byte-compared with its original window.

Per codec/g:
- region: 30 windows × 3 passes × 200 requests;
- amplification: 30 × 200 verified requests, separate instrumented libraries;
- full decode for break-even: 30 windows × 3 timed full-decode repeats after warmup.

Ratio is input bytes / archive-file bytes as requested in this refresh. The BGZF
`.gzi` sidecar size is retained in provenance but excluded from this ratio column.

Break-even uses the median full-decode time of the 2 MiB windows divided by the
same-run region p50, then `floor(x)+1`. It is a cost model for this window scope,
not an observed N-request batch crossover.

## Amplification instrumentation

Latency libraries are unmodified. BGZF and zstd use the existing separate counter
builds. ACEAPEX uses an instrumented copy of the v2.2.0 C99 decoder. It increments
decoded-byte work only when a stream chunk is actually materialized on a persistent
cache miss. The upstream source hash, instrumented source hash and counter-library
hash are retained.

## Strict c_file(g)

Separate full hg38 chr1 scope, MD5
`9465e0f0df6e2c6eb39729c39cee5465`.

Compare `g=16384` against one whole-input block while holding
`LIT_CHUNK=65536`, `FSE_CHUNK=4096`, level 2 and threads fixed.

Two encoder rows:
- DNA default l1;
- `AX_ENC=chain` (the 2.1-era matcher).

Both archives on both sides must restore byte-exactly. Report archive bytes,
ratios and strict `c_file(g)=100*(1-ratio_g/ratio_whole)`.

## GPU evidence

Do not execute a GPU in hw-apex-bench. Import the v2.2.0 Blackwell measurements
at ACE commit `27b61b1430715e47848cea6d54a333b2f1642334` as
`measured, external runner: Colab`.

The v2.2.0 release/CHANGELOG state: RTX PRO 6000 Blackwell Server Edition,
16 KiB blocks, 64 KiB literal chunks, median of 3, every row bit-perfect,
libzstd 1.5.5.

The raw Blackwell 2026-09-30 log is not committed in the v2.2.0 Git snapshot;
the upstream `results/limits-2026-09-30.md` explicitly says those logs were in
the conversation. This absence must appear under "not reproduced"; no raw-log
path is invented.

## Publication

Output:
- one table per axis: ratio, region p50/p99, amplification, break-even, c(g);
- provenance per row;
- GPU table in its own external-runner scope;
- explicit "not reproduced" section;
- report in `docs/RESULTS`, evidence under `evidence/`, separate PR.

First-screen promotion follows the existing >=3-point rule. No external posts.
