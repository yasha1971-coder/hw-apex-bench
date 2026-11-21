| Codec | g | ratio | p50 ms | amplification | break-even N | selection / reason |
|---|---|---:|---:|---:|---:|---|
| bgzip | 65 280 B (fixed, not matched to g) | 3.03 | 0.0523 | 16.7 | 3.53e+03 | ★ |
| zstd_seekable | 1024 KiB | 3.14 | 0.312 | 144 | 433 | ★ |
| zstd_seekable | 16384 KiB | 3.19 | 4.75 | 1.96e+03 | 30 | ★ |
| xz | 1024 KiB | 4 | 6.89 | 256 | 240 | ★ |
| xz | 16384 KiB | 4.27 | 119 | 3.96e+03 | 13 | ★ |
