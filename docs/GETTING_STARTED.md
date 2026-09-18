# Your first successful run

Use this tool when your application reads small byte ranges from compressed
data and you need to compare density, region latency and decoded work. The
published genome snapshot illustrates a trade-off; it does not choose a codec
for your data or model disk/network I/O. Start with correctness, then measure.

## 1. Prepare Linux and qualify XZ

Linux is the documented platform. Builds need network access, compiler tools
and disk space; first-build time depends on the machine and downloads. This is
not an instant browser demo or a prebuilt binary distribution.

On Ubuntu, install the prerequisites (the only command here requiring sudo):

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake autoconf automake zlib1g-dev git python3
git clone https://github.com/yasha1971-coder/hw-apex-bench.git
cd hw-apex-bench
./run.sh --check codecs/xz.sh
```

Success prints `PASS`, supported axes and a `Receipt:` path. The check builds
pinned XZ/liblzma, compresses small deterministic inputs and checks full and
regional restoration byte-for-byte. It records no performance timing. The log
and receipt live under `.work/adapter-check`; use the printed exact paths.
Qualification is not a claim that XZ beats another codec.

You can now inspect available axes without starting a measurement:

```bash
./run.sh --plan --codec xz --axis ratio --axis region --axis batch
```

The plan needs that successful, current qualification receipt. Unsupported axes
have reasons; a missing or stale receipt is an error, not an unsupported feature.

## 2. Optional small comparison with BGZF

This step **does measure**. It uses an existing deterministic fixture generator,
not a genome download or your private files. The artificial input only checks
the measurement workflow; its ratios/timings are not representative workload results.

```bash
./run.sh --check codecs/bgzip.sh
sample_dir=$(mktemp -d .work/first-run.XXXXXX)
python3 harness/resident_fixture.py "$sample_dir/input.bin"
./run.sh --measure --codec xz --codec bgzip --axis ratio --axis region --input "$sample_dir/input.bin" --output-dir "$sample_dir/comparison"
```

Run these lines in the same shell. The temporary parent exists; the comparison
directory must not exist before the measurement. Read:

- `$sample_dir/comparison/README.md`: the candidate report.
- `$sample_dir/comparison/results.jsonl`: candidate records and provenance.
- `$sample_dir/comparison/manifest.json`: successful completion manifest.

If the command fails, retained files are diagnostics, not a successful result.
Do not compare these timings with the historical host's numbers. Both selected
codecs must use the same input/run; retain configuration and baseline details.
The published root `results.jsonl` is not replaced by this command.

## 3. Bring a real question

Use your own input with `--input` and a new `--output-dir`. Record whether it is
FASTA bytes, sequence-only data, logs or something else. The current region
experiment measures resident byte ranges; it is not automatically an end-to-end
genomic query, object-store test or columnar query benchmark.

For throughput, batch profiles and strict c(g), follow the
[measurement reference](ADAPTERS.md#execute-a-native-subset) and
[method](METHOD.md). Do not infer those axes from the two-axis smoke run.

## If the first check fails

Keep the printed error, command, repository commit (`git rev-parse HEAD`), OS,
adapter name and the last relevant lines of the printed log. Report a
[first-run problem](https://github.com/yasha1971-coder/hw-apex-bench/issues/new?template=first-run.md).
Do not upload private inputs, tokens, environment dumps or complete unrelated logs.
Dependency download failures need their URL/error; do not substitute an unpinned build.
Changed adapters/dependencies require a fresh check; do not edit a receipt to pass.

## Other entry points

- Just exploring? Open the [interactive results](https://yasha1971-coder.github.io/hw-apex-bench/).
- Reviewing evidence? `python3 web/validate_publication.py` checks the committed
  snapshot without building codecs or running measurements.
- Adding a codec? Read [CONTRIBUTING](../CONTRIBUTING.md) and the working
  [XZ adapter](../codecs/xz.sh). Native regions need the declared C/C++ companion.
- Reproducing history? `./run.sh` without arguments starts the historical full
  benchmark. Do not use it as the first-run check.
