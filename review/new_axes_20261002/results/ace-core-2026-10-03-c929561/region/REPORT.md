# Single-region latency — common 10,000-request lists

| corpus | codec | device | mode | p50 us | p95 us | p99 us | verified |
|---|---|---|---|---:|---:|---:|---|
| chr1 | aceapex-open-c99-decoder | CPU | ace-c99-in-process | 44.573 | 78.217 | 82.554 | True |
| chr1 | aceapex-open-cpp-region | CPU | ace-cpp-in-process | 41.718 | 76.233 | 86.633 | True |
| chr1 | aceapex-open-cli-faidx | CPU | process | 1016.996 | 1185.472 | 1257.116 | True |
| chr1 | bgzip-htslib | CPU | bgzf-in-process | 103.294 | 193.022 | 198.782 | True |
| chr1 | bgzip-samtools | CPU | process | 1245.895 | 1457.281 | 1526.971 | True |
| t2t | aceapex-open-c99-decoder | CPU | ace-c99-in-process | 47.569 | 89.468 | 114.415 | True |
| t2t | aceapex-open-cpp-region | CPU | ace-cpp-in-process | 51.085 | 93.365 | 126.647 | True |
| t2t | aceapex-open-cli-faidx | CPU | process | 1068.694 | 1287.754 | 1357.064 | True |
| t2t | bgzip-htslib | CPU | bgzf-in-process | 102.603 | 189.906 | 195.737 | True |
| t2t | bgzip-samtools | CPU | process | 1892.938 | 2071.453 | 2214.942 | True |

Rows with different modes are separate scopes and are not ranked together. zstd and lz4: no random-access index, therefore no latency row.
