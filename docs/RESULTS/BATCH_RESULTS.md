# Batch results

Generated from results.jsonl. All repetitions and trace hashes are retained in evidence.

| Codec/profile | block bytes | Access profile | method | N | H_alpha bits | Threads requested | ranges/s | / bgzip loop |
|---|---:|---|---|---:|---:|---:|---:|---|
| bgzip+htslib | 65536 | uniform | loop | 100 | 6.643856 | 1 | 7657.962 | 1.000 PASS |
| bgzip+htslib | 65536 | uniform | batch | 100 | 6.643856 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | uniform | loop | 100 | 6.643856 | 1 | 22115.977 | 2.888 PASS |
| zstd-seekable | 16384 | uniform | batch | 100 | 6.643856 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | uniform | loop | 100 | 6.643856 | 1 | 6577.835 | 0.859 FAIL |
| aceapex-interactive | 16384 | uniform | batch | 100 | 6.643856 | 1 | 6513.246 | 0.851 FAIL |
| aceapex-dense | 262144 | uniform | loop | 100 | 6.583856 | 1 | 685.671 | 0.090 FAIL |
| aceapex-dense | 262144 | uniform | batch | 100 | 6.583856 | 1 | 745.813 | 0.097 FAIL |
| bgzip+htslib | 65536 | uniform | loop | 600 | 9.086302 | 1 | 9329.266 | 1.000 PASS |
| bgzip+htslib | 65536 | uniform | batch | 600 | 9.086302 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | uniform | loop | 600 | 9.174227 | 1 | 22415.494 | 2.403 PASS |
| zstd-seekable | 16384 | uniform | batch | 600 | 9.174227 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | uniform | loop | 600 | 9.174227 | 1 | 6618.261 | 0.709 FAIL |
| aceapex-interactive | 16384 | uniform | batch | 600 | 9.174227 | 1 | 7549.154 | 0.809 FAIL |
| aceapex-dense | 262144 | uniform | loop | 600 | 8.695731 | 1 | 666.629 | 0.071 FAIL |
| aceapex-dense | 262144 | uniform | batch | 600 | 8.695731 | 1 | 1416.961 | 0.152 FAIL |
| bgzip+htslib | 65536 | uniform | loop | 2000 | 10.536799 | 1 | 9437.920 | 1.000 PASS |
| bgzip+htslib | 65536 | uniform | batch | 2000 | 10.536799 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | uniform | loop | 2000 | 10.846275 | 1 | 22697.981 | 2.405 PASS |
| zstd-seekable | 16384 | uniform | batch | 2000 | 10.846275 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | uniform | loop | 2000 | 10.846275 | 1 | 6938.207 | 0.735 FAIL |
| aceapex-interactive | 16384 | uniform | batch | 2000 | 10.846275 | 1 | 8723.796 | 0.924 FAIL |
| aceapex-dense | 262144 | uniform | loop | 2000 | 9.536387 | 1 | 665.289 | 0.070 FAIL |
| aceapex-dense | 262144 | uniform | batch | 2000 | 9.536387 | 1 | 4545.376 | 0.482 FAIL |
| bgzip+htslib | 65536 | uniform | loop | 5000 | 11.285997 | 1 | 9341.656 | 1.000 PASS |
| bgzip+htslib | 65536 | uniform | batch | 5000 | 11.285997 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | uniform | loop | 5000 | 11.993736 | 1 | 22378.189 | 2.396 PASS |
| zstd-seekable | 16384 | uniform | batch | 5000 | 11.993736 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | uniform | loop | 5000 | 11.993736 | 1 | 6444.580 | 0.690 FAIL |
| aceapex-interactive | 16384 | uniform | batch | 5000 | 11.993736 | 1 | 12312.527 | 1.318 PASS |
| aceapex-dense | 262144 | uniform | loop | 5000 | 9.774765 | 1 | 659.627 | 0.071 FAIL |
| aceapex-dense | 262144 | uniform | batch | 5000 | 9.774765 | 1 | 12369.677 | 1.324 PASS |
| bgzip+htslib | 65536 | sorted | loop | 100 | 6.643856 | 1 | 8838.945 | 1.000 PASS |
| bgzip+htslib | 65536 | sorted | batch | 100 | 6.643856 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | sorted | loop | 100 | 6.643856 | 1 | 21544.875 | 2.437 PASS |
| zstd-seekable | 16384 | sorted | batch | 100 | 6.643856 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | sorted | loop | 100 | 6.643856 | 1 | 6587.294 | 0.745 FAIL |
| aceapex-interactive | 16384 | sorted | batch | 100 | 6.643856 | 1 | 6530.290 | 0.739 FAIL |
| aceapex-dense | 262144 | sorted | loop | 100 | 6.583856 | 1 | 688.009 | 0.078 FAIL |
| aceapex-dense | 262144 | sorted | batch | 100 | 6.583856 | 1 | 746.176 | 0.084 FAIL |
| bgzip+htslib | 65536 | sorted | loop | 600 | 9.086302 | 1 | 10059.818 | 1.000 PASS |
| bgzip+htslib | 65536 | sorted | batch | 600 | 9.086302 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | sorted | loop | 600 | 9.174227 | 1 | 22354.305 | 2.222 PASS |
| zstd-seekable | 16384 | sorted | batch | 600 | 9.174227 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | sorted | loop | 600 | 9.174227 | 1 | 6668.639 | 0.663 FAIL |
| aceapex-interactive | 16384 | sorted | batch | 600 | 9.174227 | 1 | 7424.198 | 0.738 FAIL |
| aceapex-dense | 262144 | sorted | loop | 600 | 8.695731 | 1 | 633.929 | 0.063 FAIL |
| aceapex-dense | 262144 | sorted | batch | 600 | 8.695731 | 1 | 1414.419 | 0.141 FAIL |
| bgzip+htslib | 65536 | sorted | loop | 2000 | 10.536799 | 1 | 12232.566 | 1.000 PASS |
| bgzip+htslib | 65536 | sorted | batch | 2000 | 10.536799 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | sorted | loop | 2000 | 10.846275 | 1 | 23165.126 | 1.894 PASS |
| zstd-seekable | 16384 | sorted | batch | 2000 | 10.846275 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | sorted | loop | 2000 | 10.846275 | 1 | 6941.176 | 0.567 FAIL |
| aceapex-interactive | 16384 | sorted | batch | 2000 | 10.846275 | 1 | 8786.032 | 0.718 FAIL |
| aceapex-dense | 262144 | sorted | loop | 2000 | 9.536387 | 1 | 658.075 | 0.054 FAIL |
| aceapex-dense | 262144 | sorted | batch | 2000 | 9.536387 | 1 | 4596.055 | 0.376 FAIL |
| bgzip+htslib | 65536 | sorted | loop | 5000 | 11.285997 | 1 | 16387.479 | 1.000 PASS |
| bgzip+htslib | 65536 | sorted | batch | 5000 | 11.285997 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | sorted | loop | 5000 | 11.993736 | 1 | 24018.968 | 1.466 PASS |
| zstd-seekable | 16384 | sorted | batch | 5000 | 11.993736 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | sorted | loop | 5000 | 11.993736 | 1 | 6707.945 | 0.409 FAIL |
| aceapex-interactive | 16384 | sorted | batch | 5000 | 11.993736 | 1 | 11266.210 | 0.687 FAIL |
| aceapex-dense | 262144 | sorted | loop | 5000 | 9.774765 | 1 | 675.669 | 0.041 FAIL |
| aceapex-dense | 262144 | sorted | batch | 5000 | 9.774765 | 1 | 12696.691 | 0.775 FAIL |
| bgzip+htslib | 65536 | clustered | loop | 100 | 5.344722 | 1 | 7990.335 | 1.000 PASS |
| bgzip+htslib | 65536 | clustered | batch | 100 | 5.344722 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | clustered | loop | 100 | 6.248758 | 1 | 21212.597 | 2.655 PASS |
| zstd-seekable | 16384 | clustered | batch | 100 | 6.248758 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | clustered | loop | 100 | 6.248758 | 1 | 6923.342 | 0.866 FAIL |
| aceapex-interactive | 16384 | clustered | batch | 100 | 6.248758 | 1 | 15084.986 | 1.888 PASS |
| aceapex-dense | 262144 | clustered | loop | 100 | 3.762446 | 1 | 686.541 | 0.086 FAIL |
| aceapex-dense | 262144 | clustered | batch | 100 | 3.762446 | 1 | 9044.818 | 1.132 PASS |
| bgzip+htslib | 65536 | clustered | loop | 600 | 7.822019 | 1 | 9461.960 | 1.000 PASS |
| bgzip+htslib | 65536 | clustered | batch | 600 | 7.822019 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | clustered | loop | 600 | 8.800388 | 1 | 21540.418 | 2.277 PASS |
| zstd-seekable | 16384 | clustered | batch | 600 | 8.800388 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | clustered | loop | 600 | 8.800388 | 1 | 6694.686 | 0.708 FAIL |
| aceapex-interactive | 16384 | clustered | batch | 600 | 8.800388 | 1 | 16357.497 | 1.729 PASS |
| aceapex-dense | 262144 | clustered | loop | 600 | 6.180524 | 1 | 661.411 | 0.070 FAIL |
| aceapex-dense | 262144 | clustered | batch | 600 | 6.180524 | 1 | 11234.586 | 1.187 PASS |
| bgzip+htslib | 65536 | clustered | loop | 2000 | 9.394449 | 1 | 9833.061 | 1.000 PASS |
| bgzip+htslib | 65536 | clustered | batch | 2000 | 9.394449 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | clustered | loop | 2000 | 10.439641 | 1 | 22877.290 | 2.327 PASS |
| zstd-seekable | 16384 | clustered | batch | 2000 | 10.439641 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | clustered | loop | 2000 | 10.439641 | 1 | 6974.263 | 0.709 FAIL |
| aceapex-interactive | 16384 | clustered | batch | 2000 | 10.439641 | 1 | 18603.185 | 1.892 PASS |
| aceapex-dense | 262144 | clustered | loop | 2000 | 7.779615 | 1 | 673.118 | 0.068 FAIL |
| aceapex-dense | 262144 | clustered | batch | 2000 | 7.779615 | 1 | 12973.183 | 1.319 PASS |
| bgzip+htslib | 65536 | clustered | loop | 5000 | 10.387857 | 1 | 9831.154 | 1.000 PASS |
| bgzip+htslib | 65536 | clustered | batch | 5000 | 10.387857 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | clustered | loop | 5000 | 11.574142 | 1 | 22448.874 | 2.283 PASS |
| zstd-seekable | 16384 | clustered | batch | 5000 | 11.574142 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | clustered | loop | 5000 | 11.574142 | 1 | 6828.065 | 0.695 FAIL |
| aceapex-interactive | 16384 | clustered | batch | 5000 | 11.574142 | 1 | 22336.887 | 2.272 PASS |
| aceapex-dense | 262144 | clustered | loop | 5000 | 8.688593 | 1 | 673.279 | 0.068 FAIL |
| aceapex-dense | 262144 | clustered | batch | 5000 | 8.688593 | 1 | 17521.561 | 1.782 PASS |
| bgzip+htslib | 65536 | hot-set | loop | 100 | 5.472271 | 1 | 9304.861 | 1.000 PASS |
| bgzip+htslib | 65536 | hot-set | batch | 100 | 5.472271 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | hot-set | loop | 100 | 5.416175 | 1 | 24585.338 | 2.642 PASS |
| zstd-seekable | 16384 | hot-set | batch | 100 | 5.416175 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | hot-set | loop | 100 | 5.416175 | 1 | 6526.380 | 0.701 FAIL |
| aceapex-interactive | 16384 | hot-set | batch | 100 | 5.416175 | 1 | 12886.354 | 1.385 PASS |
| aceapex-dense | 262144 | hot-set | loop | 100 | 5.416175 | 1 | 759.385 | 0.082 FAIL |
| aceapex-dense | 262144 | hot-set | batch | 100 | 5.416175 | 1 | 1542.681 | 0.166 FAIL |
| bgzip+htslib | 65536 | hot-set | loop | 600 | 6.123543 | 1 | 9164.527 | 1.000 PASS |
| bgzip+htslib | 65536 | hot-set | batch | 600 | 6.123543 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | hot-set | loop | 600 | 5.928246 | 1 | 23849.638 | 2.602 PASS |
| zstd-seekable | 16384 | hot-set | batch | 600 | 5.928246 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | hot-set | loop | 600 | 5.928246 | 1 | 6660.288 | 0.727 FAIL |
| aceapex-interactive | 16384 | hot-set | batch | 600 | 5.928246 | 1 | 56845.113 | 6.203 PASS |
| aceapex-dense | 262144 | hot-set | loop | 600 | 5.901579 | 1 | 751.365 | 0.082 FAIL |
| aceapex-dense | 262144 | hot-set | batch | 600 | 5.901579 | 1 | 7283.839 | 0.795 FAIL |
| bgzip+htslib | 65536 | hot-set | loop | 2000 | 6.142347 | 1 | 9206.379 | 1.000 PASS |
| bgzip+htslib | 65536 | hot-set | batch | 2000 | 6.142347 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | hot-set | loop | 2000 | 5.974815 | 1 | 23509.189 | 2.554 PASS |
| zstd-seekable | 16384 | hot-set | batch | 2000 | 5.974815 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | hot-set | loop | 2000 | 5.974815 | 1 | 6600.630 | 0.717 FAIL |
| aceapex-interactive | 16384 | hot-set | batch | 2000 | 5.974815 | 1 | 152027.345 | 16.513 PASS |
| aceapex-dense | 262144 | hot-set | loop | 2000 | 5.935685 | 1 | 747.903 | 0.081 FAIL |
| aceapex-dense | 262144 | hot-set | batch | 2000 | 5.935685 | 1 | 23419.053 | 2.544 PASS |
| bgzip+htslib | 65536 | hot-set | loop | 5000 | 6.155796 | 1 | 9128.433 | 1.000 PASS |
| bgzip+htslib | 65536 | hot-set | batch | 5000 | 6.155796 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | hot-set | loop | 5000 | 5.987822 | 1 | 22851.094 | 2.503 PASS |
| zstd-seekable | 16384 | hot-set | batch | 5000 | 5.987822 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | hot-set | loop | 5000 | 5.987822 | 1 | 6954.033 | 0.762 FAIL |
| aceapex-interactive | 16384 | hot-set | batch | 5000 | 5.987822 | 1 | 259708.312 | 28.450 PASS |
| aceapex-dense | 262144 | hot-set | loop | 5000 | 5.951825 | 1 | 722.914 | 0.079 FAIL |
| aceapex-dense | 262144 | hot-set | batch | 5000 | 5.951825 | 1 | 54037.319 | 5.920 PASS |
| bgzip+htslib | 65536 | zipf1.2 | loop | 100 | 4.265106 | 1 | 11785.564 | 1.000 PASS |
| bgzip+htslib | 65536 | zipf1.2 | batch | 100 | 4.265106 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | zipf1.2 | loop | 100 | 5.282666 | 1 | 24588.584 | 2.086 PASS |
| zstd-seekable | 16384 | zipf1.2 | batch | 100 | 5.282666 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | zipf1.2 | loop | 100 | 5.282666 | 1 | 7908.123 | 0.671 FAIL |
| aceapex-interactive | 16384 | zipf1.2 | batch | 100 | 5.282666 | 1 | 17000.402 | 1.442 PASS |
| aceapex-dense | 262144 | zipf1.2 | loop | 100 | 3.122792 | 1 | 763.125 | 0.065 FAIL |
| aceapex-dense | 262144 | zipf1.2 | batch | 100 | 3.122792 | 1 | 2859.484 | 0.243 FAIL |
| bgzip+htslib | 65536 | zipf1.2 | loop | 600 | 4.835831 | 1 | 12267.131 | 1.000 PASS |
| bgzip+htslib | 65536 | zipf1.2 | batch | 600 | 4.835831 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | zipf1.2 | loop | 600 | 6.150155 | 1 | 21102.375 | 1.720 PASS |
| zstd-seekable | 16384 | zipf1.2 | batch | 600 | 6.150155 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | zipf1.2 | loop | 600 | 6.150155 | 1 | 6819.878 | 0.556 FAIL |
| aceapex-interactive | 16384 | zipf1.2 | batch | 600 | 6.150155 | 1 | 24925.681 | 2.032 PASS |
| aceapex-dense | 262144 | zipf1.2 | loop | 600 | 3.546787 | 1 | 793.734 | 0.065 FAIL |
| aceapex-dense | 262144 | zipf1.2 | batch | 600 | 3.546787 | 1 | 5465.186 | 0.446 FAIL |
| bgzip+htslib | 65536 | zipf1.2 | loop | 2000 | 5.135643 | 1 | 12216.698 | 1.000 PASS |
| bgzip+htslib | 65536 | zipf1.2 | batch | 2000 | 5.135643 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | zipf1.2 | loop | 2000 | 6.550518 | 1 | 23686.076 | 1.939 PASS |
| zstd-seekable | 16384 | zipf1.2 | batch | 2000 | 6.550518 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | zipf1.2 | loop | 2000 | 6.550518 | 1 | 7872.142 | 0.644 FAIL |
| aceapex-interactive | 16384 | zipf1.2 | batch | 2000 | 6.550518 | 1 | 34490.010 | 2.823 PASS |
| aceapex-dense | 262144 | zipf1.2 | loop | 2000 | 3.754888 | 1 | 805.388 | 0.066 FAIL |
| aceapex-dense | 262144 | zipf1.2 | batch | 2000 | 3.754888 | 1 | 8246.130 | 0.675 FAIL |
| bgzip+htslib | 65536 | zipf1.2 | loop | 5000 | 5.244881 | 1 | 11739.432 | 1.000 PASS |
| bgzip+htslib | 65536 | zipf1.2 | batch | 5000 | 5.244881 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| zstd-seekable | 16384 | zipf1.2 | loop | 5000 | 6.808726 | 1 | 23693.002 | 2.018 PASS |
| zstd-seekable | 16384 | zipf1.2 | batch | 5000 | 6.808726 | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter | n/a — no native batch API in this adapter |
| aceapex-interactive | 16384 | zipf1.2 | loop | 5000 | 6.808726 | 1 | 7486.212 | 0.638 FAIL |
| aceapex-interactive | 16384 | zipf1.2 | batch | 5000 | 6.808726 | 1 | 44953.027 | 3.829 PASS |
| aceapex-dense | 262144 | zipf1.2 | loop | 5000 | 3.787940 | 1 | 805.252 | 0.069 FAIL |
| aceapex-dense | 262144 | zipf1.2 | batch | 5000 | 3.787940 | 1 | 12701.317 | 1.082 PASS |
