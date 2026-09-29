# ACEAPEX v2.1.0 / open-profile refresh

Date: 2026-09-30.

## Pins

- historical control: ACEAPEX `1b13df34ac8e839dd3232b59bc59560d689a435a`
- release: ACEAPEX tag `v2.1.0` = `50723533be48a8d9ed42e4b0f9e1f9106ef169b7`
- current-main snapshot for open: `ec3477877e7ed3f9792885a1a8beb26e48f4b717`
- zstd: `f8745da6ff1ad1e7bab384bd1f9d742439278e99`
- htslib/libdeflate: the existing matched-g benchmark pins

Existing published legacy results are immutable. This refresh creates a new evidence
scope and does not rewrite `results.jsonl` or historical reports.

## Modern adapter lifecycle

Both v2.1.0 interactive and main-open use the standalone C99 persistent decoder:
`aceapex_dec_open / aceapex_dec_region / aceapex_dec_close`. Archive parsing,
chunk tables, per-stream ZSTD_DCtx objects and the four-entry chunk cache are created
outside the per-region timer. This makes their lifecycle comparable to the persistent
BGZF context.

The legacy 1b13df3 control deliberately keeps the benchmark's historical one-shot
`aceapex_decompress_region` wrapper.

## Matched-g

Frozen corpus: the same thirty 2 MiB T2T-CHM13v2.0 windows already retained under
`evidence/t2t-regions-20260916`.

Exact g: 4,096 / 8,192 / 16,384 / 32,768 / 65,280 bytes.

ACE encoders hold `LIT_CHUNK=65,536` and `FSE_CHUNK=4,096` fixed while only
`ACEAPEX_BS=g` changes. main-open additionally sets `AX_PROFILE=open`.
`MIN_MATCH`, `AX_TOK` and `AX_LIT` are unset.

For every codec/window/g archive:
- full byte-exact restore is required before timing;
- resident 16 KiB region trace from `harness/native_measure.c`;
- 12 warmups, then 200 verified queries;
- three passes;
- nearest-rank p50/p99;
- ratio = total input / complete stored representation; BGZF includes .gzi.

All four codecs and five g points run in one GitHub-hosted x86 job so ratios and
latency relations share one machine.

Question: does main-open reduce the approximately constant region overhead relative
to v2.1.0 interactive and narrow the same-run gap to BGZF? The report uses the
five measured deltas; no internal timing axis is added.

## c_file(16 KiB), main-open

Separate full-hg38-chr1 density experiment. Compare:
- `ACEAPEX_BS=16,384`
- `ACEAPEX_BS=input_bytes`

All other open-profile settings stay fixed. Both archives must restore byte-exactly.
Publish complete-file ratio loss:
`c(g) = 100 * (1 - ratio_g / ratio_whole)`.

The historical strict default value 1.632267% at ee5a37e is displayed as an
unchanged historical reference, not recomputed or overwritten.

## GPU import

No GPU job is run here. Measured rows are imported byte-for-byte from the retained
ACEAPEX `results/colab-2026-09-29-*.log` files and `results/gpu-open-table.md`.
Each imported point is labelled `external runner: Colab` and carries GPU, CC,
driver, CUDA, nvCOMP, source ACE commit, corpus identity, archive bytes, bit-perfect
status and source-log provenance. Unsupported/unmeasured region-seek remains n/a.

No external posts are part of this change.
