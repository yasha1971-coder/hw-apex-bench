# Single-region latency — common 10,000-request lists

| corpus | codec | device | mode | p50 us | p95 us | p99 us | verified |
|---|---|---|---|---:|---:|---:|---|
| chr1 | aceapex-open-c99-decoder | CPU | ace-c99-in-process | 44.053 | 77.376 | 81.383 | True |
| chr1 | aceapex-open-cpp-region | CPU | ace-cpp-in-process | 40.396 | 70.092 | 76.303 | True |
| chr1 | aceapex-open-cli-faidx | CPU | process | 1018.795 | 1187.091 | 1262.162 | True |
| chr1 | bgzip-htslib | CPU | bgzf-in-process | 100.849 | 188.865 | 194.486 | True |
| chr1 | bgzip-samtools | CPU | process | 1242.765 | 1459.262 | 1542.509 | True |
| t2t | aceapex-open-c99-decoder | CPU | ace-c99-in-process | 47.359 | 88.948 | 113.653 | True |
| t2t | aceapex-open-cpp-region | CPU | ace-cpp-in-process | 64.712 | 101.702 | 130.976 | True |
| t2t | aceapex-open-cli-faidx | CPU | process | 1063.539 | 1286.106 | 1361.017 | True |
| t2t | bgzip-htslib | CPU | bgzf-in-process | 102.703 | 190.568 | 196.088 | True |
| t2t | bgzip-samtools | CPU | process | 1899.568 | 2071.733 | 2205.233 | True |

Rows with different modes are separate scopes and are not ranked together. zstd and lz4: no random-access index, therefore no latency row.
