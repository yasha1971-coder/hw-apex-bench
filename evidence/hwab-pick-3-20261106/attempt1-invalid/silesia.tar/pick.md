| Codec | g | ratio | p50 ms | amplification | break-even N | selection / reason |
|---|---|---:|---:|---:|---:|---|
| bgzip | 4 KiB | n/a | n/a | n/a | n/a | BGZF block size fixed by adapter |
| bgzip | 16 KiB | n/a | n/a | n/a | n/a | BGZF block size fixed by adapter |
| bgzip | ≤64 KiB, 65 280 B | 3.03 | 0.0552 | 4.92 | 3.22e+03 | ★ |
| zstd_seekable | 4 KiB | 2.34 | 0.0253 | 1.25 | 8.7e+03 | ★ |
| zstd_seekable | 16 KiB | 2.67 | 0.0266 | 2 | 6.4e+03 | ★ |
| zstd_seekable | 64 KiB | 2.88 | 0.0431 | 5.08 | 3.28e+03 | ★ |
| xz | 4 KiB | 2.55 | 0.25 | 1.25 | 1.03e+04 |  |
| xz | 16 KiB | 3.08 | 0.33 | 2 | 6.8e+03 | ★ |
| xz | 64 KiB | 3.5 | 0.588 | 5.1 | 3.37e+03 | ★ |
