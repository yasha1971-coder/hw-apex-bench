[written by ChatGPT (AI) at the author's request; checked by the author]

# TB-LVL-0 execution and reporting protocol

The owner asked for TurboBench level ladders on one golden Silesia tar and
row candidates for CROWN-3. The [calibration](CALIBRATION.md) was committed
alone in fa8a9cf801b2dcf62356b5d9c00c23c680836d21 before any timer. Predictions,
comparison predicates and exclusions are fixed there. A level-name reply must
be recorded before method timing; source inspection/builds continue meanwhile.

## Build and exact source identity

GitHub Actions builds only: no compression or decompression benchmark on the
Actions host. TurboBench4aa97c8c37311e399ea3e7782c18c652c5bdb69f; ACE override
c53f3a04f3dbac8590e46a1f86c5fded1e69e065. Other selected gitlinks remain the
upstream tree's exact pins. Use the committed build script, Go1.27.4, GCC/G++14,
TurboBench's normal optimization recipes and x86-64-v3/generic target flags.
Disallow host-native ISA assumptions. All selected source trees and index
gitlinks must validate; an explicit sparse selection of uninitialised unused
gitlinks is separately recorded. No algorithm source patches are permitted.

The artifact includes the binary, full build.json, source/configuration/command
receipts, module hashes and static proof. Require PASS, exact binary SHA,
no ELF INTERP/NEEDED and enabled machine selectors/levels for the grid. Retain
failed build artifacts separately; never substitute another release binary.
Source versions, registry literals and actual module versions are distinct
(notably minlz's Go module versus the registry's version text).

## Native roundtrip semantics

Use only /home/aeterna/golden/mixed/silesia.ref.tar, size211947520,
SHA256 a667bac80089b3d04d5496772149e632f0758974b0579d743cd8d6e5e0d63eb2.
Verify once at admission and check immutable file identity on subsequent cells;
input changes stop the run. No corpus conversion, padding or alternate tar.

One external round is one fresh TurboBench process in its own initially empty
directory. Invoke one codec/level, whole-file block target1073741824B and exact
input limit211947520B, `-i0,0`, full byte checking `-C3`, and the runner's
committed metadata/output flags. At this pin, -i0,0 means one compressor and one
decompressor call rather than an internal minimum over calibrated repetitions.
The input is loaded and buffers prepared before native codec timers. Report
these in-memory whole-file C/D measurements, not random-access latency.

The native full byte comparison, exit code and absence of error markers are
mandatory for every method/main round. The first method-only fast1 call must
produce130490328B; failure stops before the grid. Save this call separately
and do not count it among the three main rounds. Keep any failure output.

Do not pass -p7 to a benchmark: it is an existing-result printing mode. Do not
reuse a .tbb file: the default path can merge earlier minimum times. Do not
use -K as a deadline: at this source it is a ranking mode. Keep every raw .tbb,
stdout and stderr. Native .tbb ctime/dtime are seconds with six decimals; CSV
fields bearing those names instead display rounded MB/s. Parse original .tbb,
and derive rates as input_bytes / seconds /1000000. No rounded CSV comparison.

Three external main rounds, each a full sweep of the frozen canonical grid:
canonical order, reverse order, then rotate canonical by floor(N/2). Save
each roundtrip immediately; resume only missing/LOADED units. No clean retime,
time-selected exclusion or extra repeat to improve a median. Report median of
three sizes and of three C/D rates independently; show size variation if any.

## Host, lock, admission and hard release

ace-core AMD EPYC4344P; timed process pinned CPU0, one CPU. Controller, hashing
and correctness use CPU15. Record CPU/kernel/governor/affinity and host CPU
count. Preserve actual nproc output (affinity may make it1). Only measurement
holds blocking flock /run/lock/ovh-bench.lock. Never hold it for a build, source
copy or checksum. Leave every other session and its lock/processes alone.

At start/end save date -u, /proc/loadavg and nproc, plus /proc/stat observations.
Apply the calibrated admission from CALIBRATION: load1-1 <=1.0 and no surviving
foreign process >10% of one CPU during the one-second pre-start observation;
exact equality passes. A live inspection error is ERROR. Recheck under the
lock even after a passing poll. A passing observation is consumed once.
After a rejected poll or LOADED attempt wait at least300 seconds before the
next observation. Waiting does not consume an actual attempt. At most3 actual
LOADED attempts per unit; then BLOCKED: load, saved ps top8, stop for Yakov.
Actual decoder/byte/command errors stop even if the environment is loaded.

Hard host release is 2026-11-28T05:30:00Z (06:30 Berlin). Refuse a new attempt
from05:25Z, including a newly acquired lock after that point. Own process-group
supervision covers the waiting flock and worker children; prevent orphaned
waiters after connection/controller loss. TERM by05:29:40Z, KILL if needed by
05:29:50Z, reap/release before05:30Z. Partial/terminated attempts stay retained
and cannot enter medians. Do not start another attempt after release. A pending
cell or forecast is INCOMPLETE/NOT TESTED, never a fabricated failure/zero.

## Computation, frontier and neighbours

All decisions use exact integers/rationals from the saved native decimals.
Archive percentage is100*compressed/input (lower is denser), not input/archive.
Main D dominance is strictly smaller AND strictly faster D. Report the complete
finite-grid D-front and each fixed5pp band's local D-front separately; include
empty bands and >100% overflow. Do not call this a universal codec frontier.
P1 uses only its eleven zstd/brotli/lzma neighbours. P2 uses the compression
axis, requiring a witness for each of the six mapped fast API13-18 rows.

For misa77 levels0-5, choose among all registered ACE default/fast rows by
minimum absolute stored-byte difference. Exact ties: higher D, smaller archive,
canonical identifier. Show both signed percentage points of input and signed
percent of misa77's bytes, alongside ACE/misa D, D difference and D percentage.
This selection is based on density first and is fixed before timing.

Write RESULTS.md and machine-readable summary from retained evidence, then
independently audit source/build/input identity, roundtrip and attempt closure,
admission/deadline, exact medians and all frontier/witness/nearest decisions.
Keep every excluded attempt and every completed checkpoint. Retain the old
repository measurements byte-for-byte. Draft PR98 is inside this repository;
no upstream text, release, merge or message outside the repo is authorized.
