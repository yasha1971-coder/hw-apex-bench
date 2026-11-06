| Codec | g | ratio | p50 ms | amplification | break-even N | selection / reason |
|---|---|---:|---:|---:|---:|---|
| bgzip | 4 KiB | n/a | n/a | n/a | n/a | BGZF block size fixed by adapter |
| bgzip | 16 KiB | n/a | n/a | n/a | n/a | BGZF block size fixed by adapter |
| bgzip | ≤64 KiB, 65 280 B | 2.63 | 0.0666 | 4.8 | 1.55e+03 | ★ |
| zstd_seekable | 4 KiB | 2.08 | 0.0238 | 1.25 | 5.02e+03 | ★ |
| zstd_seekable | 16 KiB | 2.33 | 0.03 | 2 | 3.14e+03 | ★ |
| zstd_seekable | 64 KiB | 2.52 | 0.046 | 4.92 | 1.61e+03 | ★ |
| xz | 4 KiB | 2.13 | 0.303 | 1.25 | 4.83e+03 |  |
| xz | 16 KiB | 2.52 | 0.412 | 2 | 3.01e+03 |  |
| xz | 64 KiB | 2.84 | 0.706 | 4.92 | 1.5e+03 | ★ |
