| Codec | g | ratio | p50 ms | amplification | break-even N | selection / reason |
|---|---|---:|---:|---:|---:|---|
| bgzip | 65 280 B (fixed, not matched to g) | 2.63 | 0.13 | 1.98 | 787 | ★ |
| zstd_seekable | 64 KiB | 2.52 | 0.0912 | 2 | 850 | ★ |
| zstd_seekable | 256 KiB | 2.64 | 0.201 | 4.22 | 416 | ★ |
| zstd_seekable | 1024 KiB | 2.78 | 0.435 | 9.92 | 170 | ★ |
| zstd_seekable | 2048 KiB | 2.8 | 0.713 | 17 | 104 | ★ |
| zstd_seekable | 4096 KiB | 2.81 | 1.58 | 34.7 | 47 |  |
| zstd_seekable | 8192 KiB | 2.81 | 2.89 | 65.7 | 27 |  |
| zstd_seekable | 16384 KiB | 2.81 | 5.29 | 121 | 15 |  |
| xz | 64 KiB | 2.84 | 1.37 | 2 | 761 | ★ |
| xz | 256 KiB | 3.1 | 2.49 | 5.36 | 375 | ★ |
| xz | 1024 KiB | 3.33 | 8.86 | 17 | 94 | ★ |
| xz | 2048 KiB | 3.44 | 16.7 | 32.5 | 47 | ★ |
| xz | 4096 KiB | 3.54 | 31.8 | 64.2 | 24 | ★ |
| xz | 8192 KiB | 3.64 | 66.1 | 128 | 11 | ★ |
| xz | 16384 KiB | 3.72 | 116 | 254 | 6 | ★ |
