| Codec | g | ratio | p50 ms | amplification | break-even N | selection / reason |
|---|---|---:|---:|---:|---:|---|
| bgzip | 4 KiB | n/a | n/a | n/a | n/a | BGZF block size fixed by adapter |
| bgzip | 16 KiB | n/a | n/a | n/a | n/a | BGZF block size fixed by adapter |
| bgzip | ≤64 KiB, 65 280 B | 3.34 | 0.0689 | 5.09 | 3.74e+03 | ★ |
| zstd_seekable | 4 KiB | 2.78 | 0.0315 | 1.25 | 1.21e+04 | ★ |
| zstd_seekable | 16 KiB | 2.93 | 0.0418 | 2 | 7.53e+03 | ★ |
| zstd_seekable | 64 KiB | 3.08 | 0.0569 | 5.04 | 3.96e+03 | ★ |
| xz | 4 KiB | 2.93 | 0.227 | 1.25 | 1.17e+04 | ★ |
| xz | 16 KiB | 3.35 | 0.314 | 2 | 7.27e+03 | ★ |
| xz | 64 KiB | 3.61 | 0.557 | 5.04 | 3.61e+03 | ★ |
