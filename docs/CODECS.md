# Codec configurations

The four-format adapter interface and the four-row historical table are different
scopes: the table contains three CPU formats with two ACEAPEX configurations.
XZ is qualified separately. No full historical XZ timing row is implied.

| Historical row | Granularity | Configuration intent |
|---|---|---|
| bgzip+htslib | variable, at most 64 KiB | Standard BGZF baseline; level 6; required GZI counted. |
| zstd-seekable | 16 KiB frames | Level 3, independently addressable frames. |
| aceapex-interactive | 16 KiB blocks | Level 2; literals 64 KiB; FSE 4 KiB; favor small reads. |
| aceapex-dense | 256 KiB blocks | Level 2; literals 1 MiB; FSE 32 KiB; favor density. |

Encoder threads and decoder/batch workers are separate settings. Full configuration,
backend and actual commands remain in each result and the [full report](RESULTS/FULL_REPORT.md).
Do not substitute the current default configuration for a historical pinned row.

## BGZF

Current adapters build pinned HTSlib with pinned libdeflate and explicit level 6.
The historical system binary and the new backend were reconciled by an untimed
[archive audit](AUDITS/BGZF_BACKEND_REVIEW.md); the earlier zlib run is preserved.
A BGZF block-size ceiling is not a comparable one-block-per-file c(g) baseline.

## zstd-seekable

The historical timing frame and the five-point c(g) sweep are separate experiments.
The c(g) comparison changes frame granularity against one nonempty frame per file.
See [baseline audit](AUDITS/CG_BASELINE_REVIEW.md) for empty-frame accounting.

## ACEAPEX

Interactive and dense profiles hold their own block, literal and entropy settings.
The strict c(g) sweep uses a separate pinned revision/configuration and must not be
assigned to either timing row. Current default behavior has a separate
[refresh report](RESULTS/DEFAULT_RESULTS.md).

## Blocked XZ

[codecs/xz.sh](../codecs/xz.sh) pins XZ, uses `--block-size`, level 6, CRC64 and one
encoder thread. Native regions use liblzma, loading the index before the timer
and locating/decoding blocks inside it. See [context limits](RESIDENT_CONTEXT.md)
for supported streams and memory bounds. Native batch is unavailable with a reason.

The [adapter guide](ADAPTERS.md) is the executable-contract reference.
