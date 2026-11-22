| Codec | g | ratio | p50 ms | amplification | break-even N | selection / reason |
|---|---|---:|---:|---:|---:|---|
| bgzip | 65 280 B (fixed, not matched to g) | 2.63 | 0.0658 | 16.4 | 1.54e+03 | ★ |
| zstd_seekable | 1024 KiB | 2.78 | 0.358 | 144 | 201 | ★ |
| zstd_seekable | 16384 KiB | 2.81 | 5.88 | 2.03e+03 | 14 | ★ |
| xz | 1024 KiB | 3.33 | 8.72 | 258 | 94 | ★ |
| xz | 16384 KiB | 3.72 | 115 | 4.07e+03 | 6 | ★ |
