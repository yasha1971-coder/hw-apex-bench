# Corruption robustness — common harness

| codec | version | checksum | refused | caught | harmless | SILENT | hang | crash |
|---|---|---|---:|---:|---:|---:|---:|---:|
| aceapex-cpu-open | 091bb1e75aca7691e8b87db7f0fd8505e74739a0 | no-xxh3 | 0 | 9120 | 106 | 774 | 0 | 0 |
| aceapex-cpu-open | 091bb1e75aca7691e8b87db7f0fd8505e74739a0 | xxh3 | 0 | 9905 | 95 | 0 | 0 | 0 |
| bgzip-htslib | bgzip (htslib) 1.13+ds | crc32-mandatory | 0 | 9981 | 19 | 0 | 0 | 0 |
| lz4-frame | *** LZ4 command line interface 64-bits v1.9.3, by Yann Collet *** | content-checksum | 0 | 9998 | 2 | 0 | 0 | 0 |
| lz4-frame | *** LZ4 command line interface 64-bits v1.9.3, by Yann Collet *** | no-content-checksum | 0 | 3646 | 0 | 6354 | 0 | 0 |
| zstd | *** zstd command line interface 64-bits v1.4.8, by Yann Collet *** | check | 0 | 9995 | 5 | 0 | 0 | 0 |
| zstd | *** zstd command line interface 64-bits v1.4.8, by Yann Collet *** | no-check | 0 | 6034 | 4 | 3962 | 0 | 0 |

Each row: 10,000 deterministic mutations; watchdog 10 s; memory limit recorded in summary.json.
