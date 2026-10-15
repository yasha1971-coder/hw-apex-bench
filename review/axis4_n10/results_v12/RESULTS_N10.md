# Axis 4 N10 v1.2 results (ace-core)

Protocol SHA-256 45a3862f0162a6bf0f5913468ee46071fa94de1379c4c61fb9e50961f6c07603; prepared-v2 SHA-256 22006f26b783ea74625d512f960630424c8994b7f90e5a7de28bb2ed2f0104e2.
200 requests (20 groups x 10 assemblies); seconds = A6 sum of group times (fetch + upper-case + SHA-256 + coordinate translation), one persistent in-process reader. 3 warm-ups + 9 recorded runs per row.

| format | variant | decoder threads | median s | min s | max s | answers/s (median) | stored bytes | recorded runs | gate retries | leaderboard evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| agc | noref | 1 | 0.132307 | 0.131315 | 0.150246 | 1511.6 | 838558751 | 9 | 0 | `0c263bc79d5ab92c` |
| agc | t2t | 1 | 0.134055 | 0.132796 | 0.150030 | 1491.9 | 4005375194 | 9 | 0 | `9bf40998fbaede25` |
| bgzf | default | 1 | 0.128769 | 0.128519 | 0.131441 | 1553.2 | 7885365110 | 9 | 1 | `e7f2202e27efdb91` |
| bgzf | default | 16 | 0.116691 | 0.106745 | 0.121602 | 1713.9 | 7885365110 | 9 | 1 | `6914caced29d92f2` |
| fasta-faidx | plain | 1 | 0.064559 | 0.051206 | 0.066194 | 3097.9 | 30483628250 | 9 | 0 | `e2edddd6dbe75dee` |
| refrel3 | q16k | 1 | 0.082428 | 0.068365 | 0.082762 | 2426.4 | 3294013072 | 9 | 0 | `ed9ba12640c1b83e` |
| refrel3 | q4k | 1 | 0.079299 | 0.065025 | 0.081747 | 2522.1 | 3369426921 | 9 | 1 | `7201a6646c77d633` |
| zstd-seekable | seekable_compression level 3, frame 16384 B | 1 | 0.108113 | 0.106197 | 0.124059 | 1849.9 | 9312682901 | 9 | 0 | `cf1a3e6a1737b3f7` |

NOT_SUPPORTED rows (16 decoder threads; A12.1 scalar reader API; no decoder started, no timing):

- agc noref: current pinned native reader exposes only a scalar decoder API
- agc t2t: current pinned native reader exposes only a scalar decoder API
- fasta-faidx plain: current pinned native reader exposes only a scalar decoder API
- refrel3 q16k: current pinned native reader exposes only a scalar decoder API
- refrel3 q4k: current pinned native reader exposes only a scalar decoder API
- zstd-seekable seekable_compression level 3, frame 16384 B: current pinned native reader exposes only a scalar decoder API
