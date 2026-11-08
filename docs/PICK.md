# Qualified block-size selection

`./run.sh --pick input.bin --output-dir pick-output` uses existing native
adapters after `./run.sh --check codecs/bgzip.sh` (and similarly for
`zstd_seekable.sh` and `xz.sh`). No Python packages are required by pick.
Build prerequisites and source pins are those of the existing harness.
The output directory must not exist. No real corpus is downloaded by pick.

Without `--g`, zstd-seekable and blocked XZ use 4, 16 and 64 KiB.
`--g` accepts a comma-separated ordered list of positive byte counts, optionally
with uppercase K (KiB) or M (MiB). Example:

```bash
./run.sh --pick input.bin --g 64K,256K,1M,2M,4M,8M,16M --output-dir pick-large
```

BGZF always contributes exactly one row at 65 280 B, labelled
“fixed, not matched to g”; it is independent of the requested grid.
The default thus contains seven rows, without the former two BGZF n/a rows.
Missing qualifications still produce n/a for the applicable configurations.
Invalid syntax, zero/negative sizes, equivalent duplicates (e.g. 1M,1024K),
and sizes outside 1..1 073 741 824 bytes fail before any measurement.
The common upper limit comes from `ZSTD_SEEKABLE_MAX_FRAME_DECOMPRESSED_SIZE`
in [the pinned zstd header](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/contrib/seekable_format/zstd_seekable.h);
XZ accepts this range too. No powers-of-two restriction is imposed.
`pick.json` records requested byte sizes in run-level `g_set`, preserving order.
Invalid/stale receipts or failed adapters stop with nonzero exit.

The default stars the Pareto frontier across all measured rows of this corpus,
including all codecs and block sizes together. A row is on the frontier exactly
when no other measured row has ratio >= and p50 <= with at least one strict
inequality. Ratios use absolute units without normalization. Rows equal on both
metrics are both on the frontier; n/a rows are excluded.
This follows HW-APEX-BENCH/CALIBRATION.md at yasha-context commit b648b6c.

Every JSON row includes `on_front` (bool), `dominated_by` (zero-based indices into
this JSON's rows array, or []), and `p99_ms` (harness region p99 in ms, or null).
An n/a row has on_front=false and dominated_by=[]. The constraint flags retain
their existing per-codec selection; selected/★ may then differ from on_front.
 `--max-p50 X` selects the largest ratio with p50 at most X ms;
`--min-ratio R` selects the smallest p50 with input/archive ratio at least R.
These options are mutually exclusive; an unsatisfied constraint fails.
There is no single universal best block size.

`pick.json` retains unrounded measurements and per-codec wall times;
`pick.md` formats values with three significant digits. NativeExecution supplies
ratio, 200 resident region samples of 16 KiB, amplification, and break-even N.
Decode measurements describe this input, not a demonstrated throughput plateau.
Per-codec pick time includes compression, verification and measurement, and is
not encode/decode throughput. All timings are machine-dependent.

The source SHA is frozen before the run and checked afterwards. Each region's
SHA is compared with the corresponding source slice, not with the whole-file
SHA (which cannot authenticate an individual slice). Archives and sidecars are
pinned by size and SHA. A raw input.bin has no format-level truncation oracle;
truncation before the initial hash requires an externally supplied expected SHA.

## Synthetic CI acceptance

`python3 harness/pick_acceptance.py .work/pick-acceptance` creates exactly
100 000 000 synthetic bytes, requires all seven supported codec/g pairs,
compares JSON with the rendered table and runs positive native read controls.
It then makes 1000 seeded bit/byte/truncation mutations of archives created by
pick. Every case must be refused by pick's pinned-archive SHA guard. This tests
the checked-access boundary; it does not claim native codec corruption detection
or measure the native codec's silent-error rate. A separate unit test injects a
wrong decoded response and requires the region SHA oracle to reject it.

The CI artifact retains input identity, pick.json, pick.md, native evidence,
per-case corruption records and before/after full unittest suite logs.
Qualifications are rebuilt in the acceptance job because their receipts bind
absolute paths and build artifacts; copying receipts between runners is unsafe.
README publication tables and committed results are not updated by this command.

## Getting started and entry points

Choose a codec and block size for small reads; compare density, latency and decoded work.
Start with the [copy-and-run guide](GETTING_STARTED.md): prerequisites,
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
The documented corpus URLs and checksums are in [corpora.json](../corpora.json).

## Region size

`--region-size SIZE` accepts positive bytes or uppercase binary K/M units.
The default is 16 KiB; the default seven configurations and table format stay
unchanged. Reads may cross any number of blocks, including when the requested
region is larger than g. A region larger than the input is rejected before
measurement. The native worker compares every answer with the source; pick
independently checks SHA256 of each complete answer outside the timer.

```bash
./run.sh --pick input.bin --g 256K,2M --region-size 4K
```

`pick.json` records `region_size_bytes` and `zstd_level` at run level. The latter
comes from the qualified adapter configuration (currently 3, matching its
compression command); it is null if zstd was not qualified/measured. There is
no `--codec-opt` override. Row fields are unchanged. Amplification divides
counted decoded bytes by the actual total requested bytes. Latency, counters
and break-even use the same requested region size and query schedule.
