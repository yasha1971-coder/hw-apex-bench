| Codec | g | ratio | p50 ms | amplification | break-even N | selection / reason |
|---|---|---:|---:|---:|---:|---|
| bgzip | 4 KiB | n/a | n/a | n/a | n/a | BGZF block size fixed by adapter |
| bgzip | 16 KiB | n/a | n/a | n/a | n/a | BGZF block size fixed by adapter |
| bgzip | ≤64 KiB, 65 280 B | 3.17 | 0.0694 | 5.09 | 2.43e+03 | ★ |
| zstd_seekable | 4 KiB | 2.69 | 0.0308 | 1.25 | 7.84e+03 | ★ |
| zstd_seekable | 16 KiB | 2.8 | 0.0419 | 2 | 4.85e+03 | ★ |
| zstd_seekable | 64 KiB | 2.94 | 0.0574 | 4.96 | 2.52e+03 | ★ |
| xz | 4 KiB | 2.81 | 0.222 | 1.25 | 7.66e+03 |  |
| xz | 16 KiB | 3.18 | 0.314 | 2 | 4.69e+03 | ★ |
| xz | 64 KiB | 3.41 | 0.555 | 4.96 | 2.32e+03 | ★ |
