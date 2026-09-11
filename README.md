# hw-apex-bench — Compressed Access Benchmark

Measure access to a region of a compressed file without decoding the rest:
nine measurement axes, with adapters for BGZF, zstd-seekable, ACEAPEX and blocked XZ.

[lzbench](https://github.com/inikep/lzbench) and
[TurboBench](https://github.com/powturbo/TurboBench) cover compression density and bulk speed.
When a genome, column store or cache stays compressed, a request reads only a piece.
hw-apex-bench adds region latency, decoded work and access-pattern measurements
alongside full-file costs, with explicit reproduction and verification evidence.

| Codec | Granularity | Ratio | p50 ms | p99 ms | Amplification |
|---|---:|---:|---:|---:|---:|
| bgzip+htslib | ≤ 64 KiB | 3.383 | 0.102 | 0.212 | 4.82 |
| zstd-seekable | 16 KiB | 3.026 | 0.046 | 0.0594 | 2 |
| aceapex-interactive | 16 KiB | 3.658 | 0.13 | 0.24 | 6.22 |
| aceapex-dense | 256 KiB | 3.781 | 1.33 | 2.52 | 83.4 |

ACEAPEX dense has the highest ratio; zstd-seekable has the lowest p50, p99
and amplification. Both ACEAPEX profiles trade slower regions for greater density.

This is the preserved chr1 CPU snapshot: three formats, four configurations,
200 resident 16 KiB byte reads per configuration; absolute times belong to its host.
BGZF granularity is a ceiling; actual blocks vary. XZ has separate qualification
and small-corpus evidence, not an invented row in this historical comparison.

[All nine axes and full results →](docs/RESULTS/README.md)
[Explore the measurements →](https://yasha1971-coder.github.io/hw-apex-bench/)
[Add your codec →](CONTRIBUTING.md)

## Usage

Run commands from the repository root on Linux.
Prerequisites and pinned builds are in [ADAPTERS.md](docs/ADAPTERS.md).
For the native comparison below, qualify both XZ and BGZF as described there,
and supply the same input file to both; the output directory must be new.

```bash
./run.sh                         # historical full pipeline; expensive
./run.sh --check codecs/xz.sh     # qualify an adapter before measuring
./run.sh --measure --codec xz --codec bgzip --axis region --input input.bin --output-dir .work/region-run
```

The no-argument command is the historical runner, not an all-adapter dispatcher.
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
