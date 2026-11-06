# Qualified block-size selection

`./run.sh --pick input.bin --output-dir pick-output` uses existing native
adapters after `./run.sh --check codecs/bgzip.sh` (and similarly for
`zstd_seekable.sh` and `xz.sh`). No Python packages are required by pick.
Build prerequisites and source pins are those of the existing harness.
The output directory must not exist. No real corpus is downloaded by pick.

The candidates are 4, 16 and 64 KiB for zstd-seekable and blocked XZ.
BGZF uses only its adapter ceiling of 65 280 B, labelled “≤64 KiB, 65 280 B”;
4/16 KiB are n/a: “BGZF block size fixed by adapter”. Missing qualifications
produce n/a. Invalid/stale receipts or failed adapters stop with nonzero exit.

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
