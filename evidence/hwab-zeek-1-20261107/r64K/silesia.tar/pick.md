| Codec | g | ratio | p50 ms | amplification | break-even N | selection / reason |
|---|---|---:|---:|---:|---:|---|
| bgzip | 65 280 B (fixed, not matched to g) | 3.03 | 0.106 | 2 | 1.7e+03 | ★ |
| zstd_seekable | 64 KiB | 2.88 | 0.0821 | 2 | 1.71e+03 | ★ |
| zstd_seekable | 256 KiB | 3.04 | 0.167 | 4.05 | 891 | ★ |
| zstd_seekable | 1024 KiB | 3.14 | 0.339 | 9.95 | 398 | ★ |
| zstd_seekable | 2048 KiB | 3.16 | 0.601 | 17.8 | 224 | ★ |
| zstd_seekable | 4096 KiB | 3.17 | 1.13 | 31.5 | 118 |  |
| zstd_seekable | 8192 KiB | 3.18 | 2.27 | 61.7 | 62 |  |
| zstd_seekable | 16384 KiB | 3.19 | 4.4 | 118 | 32 |  |
| xz | 64 KiB | 3.5 | 1.11 | 2 | 1.8e+03 | ★ |
| xz | 256 KiB | 3.79 | 2.07 | 5.12 | 865 | ★ |
| xz | 1024 KiB | 4 | 7.34 | 17.1 | 226 | ★ |
| xz | 2048 KiB | 4.08 | 13.6 | 32.8 | 118 | ★ |
| xz | 4096 KiB | 4.16 | 27.7 | 64.2 | 56 | ★ |
| xz | 8192 KiB | 4.22 | 61.5 | 127 | 25 | ★ |
| xz | 16384 KiB | 4.27 | 119 | 251 | 13 | ★ |
