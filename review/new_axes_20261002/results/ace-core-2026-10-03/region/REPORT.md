# Single-region latency — common 10,000-request lists

| corpus | codec | device | mode | p50 us | p95 us | p99 us | verified |
|---|---|---|---|---:|---:|---:|---|
| chr1 | aceapex-open | CPU | ace-in-process | 99.227 | 188.105 | 194.095 | True |
| chr1 | aceapex-open | CPU | process | 1030.119 | 1220.357 | 1289.463 | True |
| chr1 | bgzip-htslib | CPU | bgzf-in-process | 102.262 | 190.618 | 196.049 | True |
| chr1 | bgzip-samtools | CPU | process | 1242.572 | 1455.951 | 1531.624 | True |
| t2t | aceapex-open | CPU | ace-in-process | 105.015 | 245.285 | 312.029 | True |
| t2t | aceapex-open | CPU | process | 1171.457 | 1378.090 | 1441.618 | True |
| t2t | bgzip-htslib | CPU | bgzf-in-process | 101.799 | 188.811 | 193.700 | True |
| t2t | bgzip-samtools | CPU | process | 1914.593 | 2085.909 | 2223.016 | True |

Rows with different modes are separate scopes and are not ranked together. zstd and lz4: no random-access index, therefore no latency row.
