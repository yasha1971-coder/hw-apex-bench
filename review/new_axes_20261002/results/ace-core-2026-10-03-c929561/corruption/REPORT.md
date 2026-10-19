# Corruption robustness — common harness

| codec | version | checksum | refused | caught | harmless | SILENT | hang | crash |
|---|---|---|---:|---:|---:|---:|---:|---:|
| aceapex-cpu-open | 091bb1e75aca7691e8b87db7f0fd8505e74739a0 | no-xxh3 | 0 | 9713 | 93 | 194 | 0 | 0 |
| aceapex-cpu-open | 091bb1e75aca7691e8b87db7f0fd8505e74739a0 | xxh3 | 0 | 9918 | 82 | 0 | 0 | 0 |
| bgzip-htslib | bgzip (htslib) 1.13+ds | crc32-mandatory | 0 | 9979 | 20 | 1 | 0 | 0 |
| lz4-frame | *** LZ4 command line interface 64-bits v1.9.3, by Yann Collet *** | content-checksum | 0 | 9997 | 3 | 0 | 0 | 0 |
| lz4-frame | *** LZ4 command line interface 64-bits v1.9.3, by Yann Collet *** | no-content-checksum | 0 | 3779 | 8 | 6213 | 0 | 0 |
| zstd | *** zstd command line interface 64-bits v1.4.8, by Yann Collet *** | check | 0 | 9996 | 4 | 0 | 0 | 0 |
| zstd | *** zstd command line interface 64-bits v1.4.8, by Yann Collet *** | no-check | 0 | 6202 | 3 | 3795 | 0 | 0 |

Each row: 10,000 deterministic mutations; watchdog 10 s; memory limit recorded in summary.json.
