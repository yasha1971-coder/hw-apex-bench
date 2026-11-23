# hw-apex-bench — Compressed Access Benchmark

Measure random access into compressed data: density, region latency and decoded work, alongside full-file and batch costs.

[lzbench](https://github.com/inikep/lzbench) and [TurboBench](https://github.com/powturbo/TurboBench) rank compressors by density and bulk throughput; [SeqBench](https://dl.acm.org/doi/10.1145/3698587.3701386) covers sequence compression; per-format seekable readers exist for gzip ([rapidgzip](https://pypi.org/project/rapidgzip/)), zstd ([zstdra](https://github.com/derijkp/zstdra), [seekable-zstd](https://github.com/3leaps/seekable-zstd)) and BGZF ([htslib bgzip](https://www.htslib.org/doc/bgzip.html)). None of them compares the cost of reading one region across formats at matched block sizes. That is what this measures.

## Quick start

From the repository root on Ubuntu, this prints the Pareto frontier of ratio/p50 across codecs and block sizes g; see [pick options](docs/PICK.md).

```bash
sudo apt-get update -qq && sudo apt-get install -y -qq build-essential autoconf automake cmake zlib1g-dev && python3 harness/quickstart.py download
for codec in bgzip zstd_seekable xz; do ./run.sh --check "codecs/$codec.sh" || exit; done
./run.sh --pick enwik8 --output-dir .work/quickstart-pick
```

## Limitations

- One host per run; absolute times are declared for that host.
- pick supports CPU measurements only.
- BGZF g ≤ 65 280 B in the current pick adapter.
- Four development corpora; results do not establish general workload coverage.
- No concurrent workload is measured.
- ACEAPEX is developed by the author of this benchmark.

## Example pick frontier — chrX

Retained PR #79 evidence (accepted attempt 2), CPU, 16 KiB reads; not a new benchmark.
★ marks nondominated rows across all codecs: higher ratio and lower p50. It is not a universal winner.

| Codec | g | ratio | p50 ms | amplification | break-even N | selection / reason |
|---|---|---:|---:|---:|---:|---|
| bgzip | ≤64 KiB, 65 280 B | 3.17 | 0.0711 | 5.09 | 2.35e+03 | ★ |
| zstd_seekable | 4 KiB | 2.69 | 0.0317 | 1.25 | 7.62e+03 | ★ |
| zstd_seekable | 16 KiB | 2.8 | 0.0417 | 2 | 4.78e+03 | ★ |
| zstd_seekable | 64 KiB | 2.94 | 0.0568 | 4.96 | 2.52e+03 | ★ |
| xz | 4 KiB | 2.81 | 0.222 | 1.25 | 7.68e+03 | dominated |
| xz | 16 KiB | 3.18 | 0.314 | 2 | 4.8e+03 | ★ |
| xz | 64 KiB | 3.41 | 0.564 | 4.96 | 2.32e+03 | ★ |

[Source table](evidence/hwab-pick-3-20261106/t2t_chrX.fa/pick.md) · [Raw values](evidence/hwab-pick-3-20261106/t2t_chrX.fa/pick.json)

[Results](docs/RESULTS/README.md) · [ACEAPEX snapshots](docs/RESULTS/ACEAPEX_SNAPSHOTS.md) · [Explore the measurements](https://yasha1971-coder.github.io/hw-apex-bench/)

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
Current open-profile GPU rows are measured external Colab evidence with retained logs; older owner-declared GPU observations remain historical.

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
 