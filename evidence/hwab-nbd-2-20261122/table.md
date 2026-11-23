| image | file B | ratio | A p50 cold ms | A p99 ms | C p50 warm ms | C p99 ms | peak RSS MiB | A p50 per repeat ms |
|---|---|---|---|---|---|---|---|---|
| qcow2 zstd (64 KiB clusters) | 669450240 | 8.020 | 0.0407 | 0.1172 | 0.0344 | 0.1027 | 9.3 | 0.0361, 0.0408, 0.0430, 0.0377, 0.0407 |
| qcow2 zlib (64 KiB clusters) | 659816448 | 8.137 | 0.1597 | 0.2369 | 0.1533 | 0.2264 | 9.0 | 0.1559, 0.1606, 0.1591, 0.1597, 0.1737 |
| nbdkit file on raw (NBD overhead) | 5368709120 | 1.000 | 0.0139 | 0.0235 | 0.0139 | 0.0208 | 4.7 | 0.0140, 0.0139, 0.0137, 0.0138, 0.0140 |

Median of 5 repeats (1 000 A + 1 000 C reads each); peak RSS = maximum over the repeats (qemu-nbd / nbdkit process).
