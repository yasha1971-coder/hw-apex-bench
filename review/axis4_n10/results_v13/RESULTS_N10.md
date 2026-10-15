# Axis 4 N10 v1.3 results (ace-core)

Protocol SHA-256 2e5dace0d748e5bb8ef644dde1eff051c756e02ef08e26ac341e7ad88578eb29; prepared-v2 SHA-256 22006f26b783ea74625d512f960630424c8994b7f90e5a7de28bb2ed2f0104e2.
200 requests (20 groups x 10 assemblies); seconds = A6 sum of group times (fetch + upper-case + SHA-256 + coordinate translation), one persistent in-process reader. 3 warm-ups + 9 recorded runs per row.

| format | variant | decoder threads | median s | min s | max s | answers/s (median) | stored bytes | recorded runs | gate retries | leaderboard evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| agc | noref | 1 | 0.131023 | 0.129668 | 0.132759 | 1526.4 | 838558751 | 9 | 0 | `f094e425c762a258` |
| agc | t2t | 1 | 0.134812 | 0.133195 | 0.152258 | 1483.5 | 4005375194 | 9 | 1 | `551a30a1ca2d2a63` |
| bgzf | default | 1 | 0.129335 | 0.128948 | 0.131669 | 1546.4 | 7885365110 | 9 | 0 | `c85619153084e1b0` |
| bgzf | default | 16 | 0.109489 | 0.103920 | 0.120509 | 1826.7 | 7885365110 | 9 | 0 | `58b46f8e383db800` |
| fasta-faidx | plain | 1 | 0.067226 | 0.050056 | 0.069559 | 2975.0 | 30483628250 | 9 | 0 | `f717da19ae92b04b` |
| refrel3 | q16k | 1 | 0.083948 | 0.067828 | 0.086563 | 2382.4 | 3294013072 | 9 | 0 | `f512020b18308033` |
| refrel3 | q4k | 1 | 0.081441 | 0.065867 | 0.084435 | 2455.8 | 3369426921 | 9 | 1 | `7ea4983b99c422c9` |
| zstd-seekable | seekable_compression level 3, frame 16384 B | 1 | 0.105515 | 0.105164 | 0.121789 | 1895.5 | 9312682901 | 9 | 0 | `df99f368ee3fdb7e` |

NOT_SUPPORTED rows (16 decoder threads; A12.1 scalar reader API; no decoder started, no timing):

- agc noref: current pinned native reader exposes only a scalar decoder API
- agc t2t: current pinned native reader exposes only a scalar decoder API
- fasta-faidx plain: current pinned native reader exposes only a scalar decoder API
- refrel3 q16k: current pinned native reader exposes only a scalar decoder API
- refrel3 q4k: current pinned native reader exposes only a scalar decoder API
- zstd-seekable seekable_compression level 3, frame 16384 B: current pinned native reader exposes only a scalar decoder API
