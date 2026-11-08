| Codec | g | ratio | p50 ms | amplification | break-even N | selection / reason |
|---|---|---:|---:|---:|---:|---|
| bgzip | 65 280 B (fixed, not matched to g) | 3.03 | 0.0541 | 4.92 | 3.37e+03 | ★ |
| zstd_seekable | 4 KiB | 2.34 | 0.0221 | 1.25 | 1.02e+04 | ★ |
| zstd_seekable | 16 KiB | 2.67 | 0.0267 | 2 | 6.34e+03 | ★ |
| zstd_seekable | 64 KiB | 2.88 | 0.043 | 5.08 | 3.24e+03 | ★ |
| xz | 4 KiB | 2.55 | 0.253 | 1.25 | 1.03e+04 |  |
| xz | 16 KiB | 3.08 | 0.325 | 2 | 6.96e+03 | ★ |
| xz | 64 KiB | 3.5 | 0.568 | 5.1 | 3.48e+03 | ★ |
