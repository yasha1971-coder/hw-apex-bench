| Codec | g | ratio | p50 ms | amplification | break-even N | selection / reason |
|---|---|---:|---:|---:|---:|---|
| bgzip | 4 KiB | n/a | n/a | n/a | n/a | BGZF block size fixed by adapter |
| bgzip | 16 KiB | n/a | n/a | n/a | n/a | BGZF block size fixed by adapter |
| bgzip | ≤64 KiB, 65 280 B | 3.17 | 0.0711 | 5.09 | 2.35e+03 | ★ |
| zstd_seekable | 4 KiB | 2.69 | 0.0317 | 1.25 | 7.62e+03 | ★ |
| zstd_seekable | 16 KiB | 2.8 | 0.0417 | 2 | 4.78e+03 | ★ |
| zstd_seekable | 64 KiB | 2.94 | 0.0568 | 4.96 | 2.52e+03 | ★ |
| xz | 4 KiB | 2.81 | 0.222 | 1.25 | 7.68e+03 |  |
| xz | 16 KiB | 3.18 | 0.314 | 2 | 4.8e+03 | ★ |
| xz | 64 KiB | 3.41 | 0.564 | 4.96 | 2.32e+03 | ★ |
