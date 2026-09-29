# hw-apex-bench — Compressed Access Benchmark

Measure access to a region of a compressed file without decoding the rest: nine measurement axes, with adapters for BGZF, zstd-seekable, ACEAPEX and blocked XZ.

When a genome, column store or cache stays compressed, a request reads only a piece. hw-apex-bench adds region latency, decoded work and access-pattern measurements alongside full-file costs, with explicit reproduction and verification evidence.

[lzbench](https://github.com/inikep/lzbench) and [TurboBench](https://github.com/powturbo/TurboBench) rank compressors by density and bulk throughput; [SeqBench](https://dl.acm.org/doi/10.1145/3698587.3701386) covers sequence compression; per-format seekable readers exist for gzip ([rapidgzip](https://pypi.org/project/rapidgzip/)), zstd ([zstdra](https://github.com/derijkp/zstdra), [seekable-zstd](https://github.com/3leaps/seekable-zstd)) and BGZF ([htslib bgzip](https://www.htslib.org/doc/bgzip.html)). None of them compares the cost of reading one region across formats at matched block sizes. That is what this measures.

## Matched-g refresh: ACEAPEX v2.1.0 / main open vs BGZF — 2026-09-30

Measured on thirty frozen 2 MiB T2T-CHM13v2.0 windows, not the chr1 snapshot below; ratios are not comparable between the two tables.

ACEAPEX is written by the author of this benchmark. Its density advantage and its latency penalty are both reported below; the harness, corpora and raw samples are in the repository.

Each cell is **ratio · p50 / p99 ms**.

| exact g | BGZF | ACE 1b13df3 legacy | ACE v2.1.0 interactive | ACE main open |
|---:|---:|---:|---:|---:|
| 4 KiB | 3.794020 · 0.052949 / 0.067827 | 4.682708 · 0.136184 / 0.269816 | 4.682708 · 0.068290 / 0.135201 | 4.455378 · 0.211221 / 0.458329 |
| 8 KiB | 4.139526 · 0.054550 / 0.071012 | 5.010591 · 0.141694 / 0.263842 | 5.010591 · 0.067162 / 0.139417 | 4.879676 · 0.153141 / 0.467160 |
| 16 KiB | 4.406650 · 0.065482 / 0.083762 | 5.219838 · 0.143850 / 0.272584 | 5.219838 · 0.074632 / 0.149201 | 5.148826 · 0.176257 / 0.482423 |
| 32 KiB | 4.643726 · 0.062581 / 0.142081 | 5.344308 · 0.156778 / 0.303165 | 5.344308 · 0.083464 / 0.180311 | 5.307601 · 0.216979 / 0.529897 |
| 65,280 B | 4.810834 · 0.108651 / 0.244448 | 5.412621 · 0.210062 / 0.438012 | 5.412621 · 0.124668 / 0.277486 | 5.395254 · 0.271045 / 0.757243 |

The modern rows use a persistent C99 decoder handle; the legacy row retains the historical one-shot path as a same-run control. v2.1.0 interactive cuts legacy p50 by 40.7–52.6% and leaves only a 9.2–20.9 µs p50 gap to BGZF. Main open does **not** remove that remainder: it is slower than v2.1.0 interactive at all 5 points and is also less dense at all 5 points.

[ACEAPEX v2.1.0 / open refresh report →](docs/RESULTS/ACEAPEX_UPGRADE_20260930.md)  
[GitHub Actions run 36641590388 →](https://github.com/yasha1971-coder/hw-apex-bench/actions/runs/36641590388) · [historical 2026-09-18 matched-g report →](docs/RESULTS/MATCHED_G_INTERACTIVE_20260918.md)

**Independence cost at 16 KiB (separate full-chr1 `c_file(g)` scopes):** historical ACEAPEX default @ ee5a37e is **1.632%**; current main-open @ ec347787 is **1.735%**; matched zstd-seekable is **6.569%**. BGZF is **n/a** because no same-encoder whole-input baseline exists. These ACE values use different revisions/profiles and are shown as separate measured scopes, not as a one-variable profile delta. [Current refresh →](docs/RESULTS/ACEAPEX_UPGRADE_20260930.md) · [Scope definitions →](docs/CG_SCOPES.md)

**Batch sweep scope (2026-09-19):** hg38 chr1, N=5000, 16 KiB ranges, workers=1, Actions run 35427975099.

A native batch API is what makes the dense profile usable at all for region reads: it moves from 659.6 to 12,369.7 ranges/s under uniform access. But dense leads interactive only under uniform access. Once requests concentrate, interactive overtakes it somewhere between 12 and 8 bits of access entropy and keeps the lead: at Hα ≈ 2 bits, interactive reaches 869,088 ranges/s against 467,998 for dense. For batch-heavy workloads with any locality, interactive is the profile to pick.

Concentration helps BGZF more than it helps ACEAPEX in the single-request path. Under uniform access bgzip runs 10,040.6 ranges/s against ACEAPEX interactive at 9,086.4, a 1.1× gap. At Hα ≈ 2 bits bgzip reaches 64,722.7 against 13,847.4, a 4.7× gap. The batch API is where ACEAPEX answers locality; the loop path is not.

[Access-entropy sweep →](docs/RESULTS/ACCESS_ENTROPY_20260919.md)

| Codec | Granularity | Ratio | p50 ms | p99 ms | Amplification |
|---|---:|---:|---:|---:|---:|
| bgzip+htslib | ≤ 64 KiB | 3.383 | 0.102 | 0.212 | 4.82 |
| zstd-seekable | 16 KiB | 3.026 | 0.046 | 0.0594 | 2 |
| aceapex-interactive | 16 KiB | 3.658 | 0.13 | 0.24 | 6.22 |
| aceapex-dense | 256 KiB | 3.781 | 1.33 | 2.52 | 83.4 |

ACEAPEX dense has the highest ratio; zstd-seekable has the lowest p50, p99 and amplification. Both ACEAPEX profiles trade slower regions for greater density.

This is the preserved chr1 CPU snapshot: three formats, four configurations, 200 resident 16 KiB byte reads per configuration; absolute times belong to its host. BGZF granularity is a ceiling; actual blocks vary. XZ has separate qualification and small-corpus evidence, not an invented row in this historical comparison.

[All nine axes and full results →](docs/RESULTS/README.md)
[Explore the measurements →](https://yasha1971-coder.github.io/hw-apex-bench/)
[Add your codec →](CONTRIBUTING.md)

## Try it

Choose a codec and block size for small reads; compare density, latency and decoded work.
Start with the [copy-and-run guide](docs/GETTING_STARTED.md): prerequisites,
a small generated input, expected outputs and troubleshooting. Linux required.
The correctness check builds pinned dependencies; it does not collect timings.

```bash
git clone https://github.com/yasha1971-coder/hw-apex-bench.git
cd hw-apex-bench
./run.sh --check codecs/xz.sh     # first success: byte-exact correctness, not speed
```

The no-argument `./run.sh` starts the expensive historical runner; it is not the quick start.
Native subsets use `--measure`; bare `--codec` is not a supported entry point.
Use `--plan` to inspect capability decisions without starting measurements.
The documented corpus URLs and checksums are in [corpora.json](corpora.json).

## Nine axes

| Axis | Unit | Meaning |
|---|---|---|
| Ratio | input / stored bytes | Density including the complete archive and required indexes. |
| Encode | MB/s | Encoder wall-clock throughput, promoted only after a plateau. |
| Full decode | MB/s | Library wall-clock throughput, promoted only after a plateau. |
| Region p50/p99 | ms | Median and tail latency of 200 resident 16 KiB API reads. |
| Amplification | decoded / returned bytes | Work expanded by the decoder for the requested output. |
| c(g) | fraction or labelled % | Ratio loss against one block per file, changing only granularity. |
| Batch | ranges/s | Five access profiles at equal worker counts; native API availability is explicit. |
| H_alpha | bits | Entropy of request-start frequencies across blocks. |
| Break-even N | queries | First integer where repeated p50 reads exceed one full decode. |

[Definitions and procedures →](docs/METHOD.md)
[New to compressed random access? →](docs/AXES.md)

Amplification can reach one when decoded work matches the requested bytes.
Break-even is a cost model, not a promise about batched or overlapping requests.
[File c_file(g) and window c_window(g)](docs/CG_SCOPES.md) use different baseline inputs; corpus, scale and codec version differ, so their percentages are not directly comparable.
A negative c(g) is valid: local coding statistics can outweigh lost long matches.
Access entropy and block size describe the workload; neither is a quality score.

## Add a codec

Start with one adapter file in `codecs/`; keep codec dispatch out of the harness.
The seven core operations are complemented by capability, artifact and native hooks.
Use [the working XZ adapter](codecs/xz.sh) and [the full contract](docs/ADAPTERS.md).
`--check` must pass before a current adapter can enter a measured comparison.
Follow [CONTRIBUTING.md](CONTRIBUTING.md) for native companions and provenance.

## Measurement discipline

- Absolute timings belong to the host; compare against a baseline in the same run.
- Throughput needs a plateau; otherwise show `data edge` instead of a headline.
- Configuration is part of the row identity, including threads and library backend.
- Every unsupported axis has `n/a` with a reason supplied by the adapter.
- Measurements require a passing qualification receipt for the current adapter.
- Losses appear beside wins, under the same workload and comparison boundary.

## Read the evidence

The overview is generated from [results.jsonl](results.jsonl), never edited by hand.
The published 435 records retain their original bytes and separate evidence scopes.
No rounded display value replaces the underlying record.

[PROVENANCE.md](docs/PROVENANCE.md) explains row identities, commands and hashes.
[CODECS.md](docs/CODECS.md) explains configuration choices and backend differences.
[AUDITS](docs/AUDITS/README.md) collects the checks behind the claims.
[HISTORY.md](docs/HISTORY.md) preserves decisions, corrections and review boundaries.

The full migration comparison and untimed BGZF closure remain distinct receipts.
Their deterministic checks do not assert byte-identical timing on different hosts.
The strict c(g) run uses its own baseline and configuration; do not splice it
into the interactive/dense CPU rows as though it were the same experiment.
GPU observations remain separately labelled owner-declared evidence.

The Pages explorer selects only measured profile points, without interpolation.
Unavailable comparisons stay visible with their reasons.
Its tables provide the same values as the graph for keyboard and screen-reader users.
The detailed result pages retain commands and scope for reviewing each conclusion.

## Reproduce the presentation

`python3 harness/report.py` regenerates the overview and full CPU report.
`python3 web/validate_publication.py` checks data, digests and generated reports.
`python3 web/build.py /tmp/hw-apex-bench/index.html` exports the explorer.
These commands render or audit existing evidence; they do not benchmark codecs.

[Documentation index →](docs/README.md)
[Report an issue →](https://github.com/yasha1971-coder/hw-apex-bench/issues)

## License and citation

Code: [Apache-2.0](LICENSE). Measurements: [CC BY 4.0](evidence/LICENSE).
Third-party components retain their licenses; see [NOTICE](NOTICE).
Cite version 0.1 using [CITATION.cff](CITATION.cff), and identify the measured run.
DOI: [10.5281/zenodo.22713364](https://doi.org/10.5281/zenodo.22713364).
