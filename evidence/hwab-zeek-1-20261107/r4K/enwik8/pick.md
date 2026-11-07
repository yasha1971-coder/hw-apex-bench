| Codec | g | ratio | p50 ms | amplification | break-even N | selection / reason |
|---|---|---:|---:|---:|---:|---|
| bgzip | 65 280 B (fixed, not matched to g) | 2.63 | 0.0649 | 16.4 | 1.56e+03 | ★ |
| zstd_seekable | 64 KiB | 2.52 | 0.0447 | 17.2 | 1.71e+03 | ★ |
| zstd_seekable | 256 KiB | 2.64 | 0.189 | 50.7 | 431 | ★ |
| zstd_seekable | 1024 KiB | 2.78 | 0.355 | 144 | 199 | ★ |
| zstd_seekable | 2048 KiB | 2.8 | 0.736 | 272 | 100 |  |
| zstd_seekable | 4096 KiB | 2.81 | 1.47 | 536 | 52 |  |
| zstd_seekable | 8192 KiB | 2.81 | 2.84 | 1.01e+03 | 27 |  |
| zstd_seekable | 16384 KiB | 2.81 | 5.88 | 2.03e+03 | 14 |  |
| xz | 64 KiB | 2.84 | 0.689 | 17.2 | 1.51e+03 | ★ |
| xz | 256 KiB | 3.1 | 2.41 | 66.2 | 381 | ★ |
| xz | 1024 KiB | 3.33 | 8.63 | 258 | 95 | ★ |
| xz | 2048 KiB | 3.44 | 16.3 | 511 | 48 | ★ |
| xz | 4096 KiB | 3.54 | 31.2 | 1.02e+03 | 24 | ★ |
| xz | 8192 KiB | 3.64 | 65.7 | 2.04e+03 | 11 | ★ |
| xz | 16384 KiB | 3.72 | 115 | 4.07e+03 | 6 | ★ |
