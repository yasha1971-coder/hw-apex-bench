| Codec | g | ratio | p50 ms | amplification | break-even N | selection / reason |
|---|---|---:|---:|---:|---:|---|
| bgzip | 65 280 B (fixed, not matched to g) | 3.03 | 0.0567 | 4.92 | 3.22e+03 | ★ |
| zstd_seekable | 4 KiB | 2.34 | 0.022 | 1.25 | 1.02e+04 | ★ |
| zstd_seekable | 16 KiB | 2.67 | 0.0263 | 2 | 6.3e+03 | ★ |
| zstd_seekable | 64 KiB | 2.88 | 0.0417 | 5.08 | 3.44e+03 | ★ |
| xz | 4 KiB | 2.55 | 0.253 | 1.25 | 1.03e+04 |  |
| xz | 16 KiB | 3.08 | 0.336 | 2 | 6.78e+03 | ★ |
| xz | 64 KiB | 3.5 | 0.575 | 5.1 | 3.49e+03 | ★ |
