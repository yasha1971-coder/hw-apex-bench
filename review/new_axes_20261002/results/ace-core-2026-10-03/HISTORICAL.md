# Historical region run — ace-core 2026-10-03

Source commit: `03eb6c735208ec7be380d046a6ccf025a06d5918`.

These rows are retained as historical evidence only. ACEAPEX was pinned to `207bf0042dfd410f908f3b8eeb7bc8701bdbf3ee`; the row previously named `ace-in-process` uses the C99 decoder through the Python ctypes harness. It MUST NOT be relabeled as the C++ `aceapex_decompress_region` path and MUST NOT be overwritten by the newer run.

| corpus | codec | decoder / mode | p50 us | p95 us | p99 us | verified |
|---|---|---|---:|---:|---:|---|
| chr1 | ACEAPEX open 207bf00 | C99 in-process | 99.227 | 188.105 | 194.095 | yes |
| t2t | ACEAPEX open 207bf00 | C99 in-process | 105.015 | 245.285 | 312.029 | yes |
| chr1 | ACEAPEX open 207bf00 | CLI faidx process/request | 1030.119 | 1220.357 | 1289.463 | yes |
| t2t | ACEAPEX open 207bf00 | CLI faidx process/request | 1171.457 | 1378.090 | 1441.618 | yes |
| chr1 | BGZF | htslib in-process | 102.262 | 190.618 | 196.049 | yes |
| t2t | BGZF | htslib in-process | 101.799 | 188.811 | 193.700 | yes |
| chr1 | BGZF | samtools process/request | 1242.572 | 1455.951 | 1531.624 | yes |
| t2t | BGZF | samtools process/request | 1914.593 | 2085.909 | 2223.016 | yes |

The next official ACEAPEX region run uses a newer pin and emits separate C++-library and C99 rows. This historical table is not a current ranking.
