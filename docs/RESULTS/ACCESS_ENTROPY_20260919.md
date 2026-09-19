# Access-entropy sweep — 2026-09-19

This bounded sweep asks two questions only: whether native-batch advantage grows as request starts concentrate, and where ACEAPEX dense batch throughput crosses ACEAPEX interactive.

Scope is unchanged from the existing batch axis: hg38 chr1, 5,000 requests of 16 KiB, one worker, the repository's existing BGZF, zstd-seekable, ACEAPEX interactive and ACEAPEX dense adapters, and the existing `harness/native_batch.c` judge. All points ran on one GitHub-hosted AMD EPYC 9V45 runner pinned to CPU 0.

The published `H_alpha` is the **measured Shannon entropy of request starts on the common 16 KiB grid**, so it is the same workload coordinate for every codec. The finite-Zipf exponent is retained only in evidence. Codec-block entropy is shown separately because BGZF uses variable block boundaries and dense uses 256 KiB blocks.

| workload | measured H_alpha bits | codec | codec-block H_alpha bits | loop ranges/s | native batch ranges/s | batch / loop |
|---|---:|---|---:|---:|---:|---:|
| uniform | 11.994 | bgzip+htslib | 11.286 | 10,040.6 | n/a — no native batch API in current adapter | n/a |
| uniform | 11.994 | zstd-seekable | 11.994 | 27,231.3 | n/a — no native batch API in current adapter | n/a |
| uniform | 11.994 | aceapex-interactive | 11.994 | 9,086.4 | 16,827.1 | 1.86× |
| uniform | 11.994 | aceapex-dense | 9.775 | 973.9 | 20,344.0 | 20.90× |
| zipf-h8 | 7.995 | bgzip+htslib | 6.507 | 11,920.5 | n/a — no native batch API in current adapter | n/a |
| zipf-h8 | 7.995 | zstd-seekable | 7.995 | 28,912.8 | n/a — no native batch API in current adapter | n/a |
| zipf-h8 | 7.995 | aceapex-interactive | 7.995 | 10,417.6 | 47,002.6 | 4.51× |
| zipf-h8 | 7.995 | aceapex-dense | 4.995 | 1,173.2 | 18,664.2 | 15.84× |
| zipf-h4 | 4.002 | bgzip+htslib | 2.418 | 23,317.9 | n/a — no native batch API in current adapter | n/a |
| zipf-h4 | 4.002 | zstd-seekable | 4.002 | 32,183.0 | n/a — no native batch API in current adapter | n/a |
| zipf-h4 | 4.002 | aceapex-interactive | 4.002 | 12,581.4 | 218,119.7 | 17.60× |
| zipf-h4 | 4.002 | aceapex-dense | 1.295 | 1,280.0 | 71,735.2 | 56.19× |
| zipf-h2 | 2.001 | bgzip+htslib | 0.728 | 64,722.7 | n/a — no native batch API in current adapter | n/a |
| zipf-h2 | 2.001 | zstd-seekable | 2.001 | 34,113.3 | n/a — no native batch API in current adapter | n/a |
| zipf-h2 | 2.001 | aceapex-interactive | 2.001 | 13,847.4 | 869,087.9 | 65.39× |
| zipf-h2 | 2.001 | aceapex-dense | 0.206 | 1,357.0 | 467,998.1 | 344.87× |

## Answer

For **ACEAPEX interactive**, batch advantage grows monotonically as access entropy falls: **1.86× → 4.51× → 17.60× → 65.39×** from H=11.994 to H=2.001 bits.

For **ACEAPEX dense**, concentration also produces a much larger endpoint advantage, but not monotonically: **20.90× → 15.84× → 56.19× → 344.87×**. There is an initial dip at H≈8, followed by a very steep rise.

The absolute dense-versus-interactive batch ordering does **not** move the way the hypothesis suggested. Dense is ahead only at the highest-entropy uniform point: **20,344.0 vs 16,827.1 ranges/s at H=11.994**. As starts concentrate, **interactive overtakes dense between H=11.994 and H=7.995**, then stays ahead at every lower measured point: 47,002.6 vs 18,664.2 at H=7.995, 218,119.7 vs 71,735.2 at H=4.002, and 869,087.9 vs 467,998.1 at H=2.001.

So there is **no measured lower-entropy threshold where dense overtakes interactive**. The observed crossover under increasing concentration is the reverse: interactive overtakes dense between roughly 12 and 8 bits of common start entropy.

## Correctness and provenance

Every loop response was compared byte-for-byte with the original outside timing. For ACE native batch, every batch result was also compared with the verified single-call result/source. With three repetitions, each loop row represents **15,000 verified ranges**, and each available batch row represents another **15,000 verified ranges**.

Actions run: **35427975099**. Artifact: **10579228345**, digest `sha256:901eeaf9c01841dca3a213c81d3c816fbd9e7da464f2ca049f2982389e28b081`.

Compact evidence: `evidence/access-entropy-20260919/results.json`. Run receipt: `evidence/access-entropy-20260919/run-receipt.json`. Protocol and deterministic trace generator: `review/access_entropy/`.

Absolute rates belong to this host. The entropy trend and codec ordering statements above are same-run observations. No GPU path, format, axis definition, homepage content or codec implementation was changed.
