| Codec | g | ratio | p50 ms | amplification | break-even N | selection / reason |
|---|---|---:|---:|---:|---:|---|
| bgzip | 4 KiB | n/a | n/a | n/a | n/a | BGZF block size fixed by adapter |
| bgzip | 16 KiB | n/a | n/a | n/a | n/a | BGZF block size fixed by adapter |
| bgzip | ≤64 KiB, 65 280 B | 2.63 | 0.0662 | 4.8 | 1.56e+03 | ★ |
| zstd_seekable | 4 KiB | 2.08 | 0.0236 | 1.25 | 5.06e+03 | ★ |
| zstd_seekable | 16 KiB | 2.33 | 0.03 | 2 | 3.15e+03 | ★ |
| zstd_seekable | 64 KiB | 2.52 | 0.0471 | 4.92 | 1.6e+03 | ★ |
| xz | 4 KiB | 2.13 | 0.3 | 1.25 | 4.88e+03 |  |
| xz | 16 KiB | 2.52 | 0.41 | 2 | 3.04e+03 |  |
| xz | 64 KiB | 2.84 | 0.712 | 4.92 | 1.51e+03 | ★ |
