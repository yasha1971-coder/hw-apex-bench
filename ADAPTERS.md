# Current native execution status

All nine axes now have dispatch backends. BGZF c(g) remains unsupported without a
comparable whole-file baseline; BGZF/zstd/XZ have no native batch API. Those reasons
come from adapters. No migration-placeholder n/a is accepted by the nine-axis audit.

```sh
./run.sh --check codecs/aceapex.sh
./run.sh --measure --codec aceapex --axis ratio --axis encode --axis decode --axis region --axis amplification --axis batch --axis h_alpha --axis c_g --axis break_even --plateau --input YOUR_VERIFIED_INPUT --output-dir NEW_RUN_DIRECTORY
```

The profile corpus must be at least 1 MiB + 16 KiB. Defaults are four throughput
scales (1,2,4,8 copies), three encode samples, five decode samples, 200 regions and
five access profiles at 100/600/2000/5000 ranges. `--copies` and `--batch-sizes`
allow explicit smaller smoke subsets. `--plateau` enables the decode curve;
without it decode remains a clearly labelled single-size sample. Encode always
uses the common curve runner. Encoding preserves historical CLI process timing;
all timed decoding is native and resident.

The run writes separate results.jsonl, a generated README.md, manifest.json and raw
samples. It never overwrites the root publication. Each result records its command,
configuration, same-run baseline ratio or explicit reason, and qualification hash.
The sample schema has evolved; historical PR #25 ZIP audit applies to its four-axis
artifacts. Use `python3 review/verify_nine_axes.py RUN/manifest.json` for full axes.

ACEAPEX reader_environment is necessary sideband configuration at pinned 1b13.
In particular full decode uses FSE_CHUNK: omitting the published 4096 value can
silently appear correct below a chunk boundary, then fail on larger inputs.
The correctness fixture now grows to 16 copies to cross that boundary. Environment
parameters are fingerprinted, restored after in-process operations, passed to native
workers and included in reproduction commands. No upstream decoder was changed.

`codec_encode_command` returns JSON argv plus optional stdout_archive/produced
fields, so the generic runner never times shell adapter setup or invents encoder
commands. `codec_counter_library` supplies a separate instrumented context; timed
libraries remain uninstrumented. Counts follow actual decoder work, including zero
work for cached bytes. Counting builds record instrumented source hashes and leave
pinned dependency trees clean.

Optional native extensions are hc_block_id and hc_geometry, hc_count_reset/bytes
on counting libraries, and hc_batch_open/reset/run/valid/close for native batches.
Batch range preparation is untimed; the API call is timed, with one worker and
alternating loop/batch order. H_alpha counts request-start blocks from actual archive
geometry. Strict c(g) verifies every block boundary and accounts for empty frames.
Only granularity varies, with one nonempty whole-file baseline and fixed other
parameters. These profile curves do not replace historical ee5 default curves.

Historical comparison configurations are standalone adapter files:
`bgzip_1_19.sh` pins release 1.19 at 8f7231035d0409d525767c66d9f49f1f967ee1df;
`aceapex_dense.sh` uses the published 256 KiB blocks, 1 MiB literals and 32 KiB FSE.
The regular bgzip adapter remains pinned at 1.24. A matching release does not erase
build-option or hardware differences. Source and binary qualification remains required.

The owner-authorized full comparison is gated behind all small CI matrix checks,
runs once on opening this migration PR, and does not repeat on documentation updates.
Its comparison distinguishes unchanged historical 435 bytes from fresh host timings,
and explicitly excludes GPU declarations/default c(g)/frontier scopes from an
unsupported equality claim. Completing these backends does not itself establish
byte-identical replay of every historical configuration or release readiness.

---

The following sections document earlier extraction/check milestones; where their
execution scope differs, the current status above supersedes it.

# Add and check a codec

`./run.sh --check codecs/xz.sh` builds pinned sources, creates small deterministic
corpora, verifies CLI and native full restoration byte-for-byte, checks native
regions and reports supported axes with explicit n/a reasons. `./run.sh --check`
checks every `codecs/*.sh`. It collects no timings and never writes results.jsonl.

Prerequisites: Linux, Bash, Python 3, git, make, gcc/g++, CMake and zlib development
headers. On Ubuntu: `sudo apt-get install build-essential cmake zlib1g-dev git
python3`. A normal `./run.sh` still invokes the historical full benchmark; use
`--check` for the small correctness gate.

Builds live under `.work/adapter-check`. A lock prevents concurrent writes to one
adapter's build directory. A dirty or wrong-revision cached dependency is rejected;
the checker never resets it. Use `--work NEW_DIRECTORY` for a fresh build. An old
success receipt is removed before a new check and a new receipt is written only
after all checks pass. Subprocess failures and timeouts return nonzero; diagnostic
logs remain beside `check.json`. Timed-out subprocess groups are terminated.

## Shell contract

An adapter is trusted executable Bash, with these seven functions:

| Function | Contract |
|---|---|
| codec_name | Print the configuration name |
| codec_version | Print the pinned version/SHA; compared with native runtime version |
| codec_build | Build dependencies and the adapter; nonzero on failure |
| codec_compress INPUT OUTPUT GRANULARITY | Write a complete archive and any declared sidecars; preserve input |
| codec_decompress ARCHIVE OUTPUT | Restore the complete input; nonzero on failure |
| codec_region ARCHIVE OFFSET LENGTH OUTPUT | Return exact original-file bytes through a native library; untimed shell convenience |
| codec_supports | Print supported axes separated by spaces |

`codec_unavailable` supplies JSON reasons for every unsupported axis.
`codec_constraints` supplies the smoke granularity and minimum input size, with a
reason for excluded empty input. `codec_artifacts ARCHIVE` lists required files;
`codec_sidecar ARCHIVE` supplies an optional native index path. The common helpers
provide defaults for these, `codec_library`, and the untimed `codec_region` bridge.
A codec supporting native region access also implements resident_context.h ABI 2
in a companion C/C++ file and builds its library. CLI-only adapters need no library.
The native ABI remains experimental until the measurement runner is integrated.

Source `harness/check_common.sh` via `$HB_ROOT` (set by the checker), define the
functions, return when sourced, and use `hb_entry "$@"` when executed. Expose
`supports` and `unavailable` command aliases, as the existing adapters do. Helpers
use `$HB_CHECK_WORK` for outputs and `hb_checkout URL FULL_SHA DIRECTORY` for
immutable dependency preparation. New adapters require no registry or codec-name
branch in the checker. `harness/test_check_adapter.py` demonstrates an external,
CLI-only adapter that is discovered solely by its supplied path.

The existing historical CLI dispatchers are retained separately for commands in
published evidence. The new contract rejects unsupported granularities: BGZF CLI
uses a 65280-byte ceiling; pinned ACEAPEX uses the interactive 16 KiB preset.
XZ uses --block-size; zstd's seekable example accepts a frame size. Moving controlled
c(g) orchestration and the other published configurations remains separate work.

## Native semantics and scope

Open receives resident bytes plus an optional sidecar path. ABI 2 discovers the
original size from archive metadata; it does not need the uncompressed original.
`hc_size` exposes that size. An optional expected size can be checked at open.
ACEAPEX still parses its header inside every region API call; no caching
optimization or upstream source change is included.

Index preparation is outside the future timer. Lookup, decompression and copying
are inside the native region callback. The shell bridge and Python ctypes probe
are strictly correctness tools; never use their process time as region latency.
See RESIDENT_CONTEXT.md for XZ single-Stream/no-padding and memory limits.

The checker exercises mixed binary/DNA data, one byte, empty input, an exact
block and a cross-block fixture. ACEAPEX's pinned CLI excludes empty input with
an explicit reason. Native probes check full decode, shuffled ranges crossing
multiple block boundaries, guards and invalid ranges. Shell-region results are
checked separately, using only archive-derived size. Archive/index hashes must
remain unchanged after reading.

For this new path, decode and region are currently qualified. Reasons for missing
timing, accounting, counters, batch, block mapping and curve integration are
emitted automatically. These do not replace the published historical capabilities.
A passing --check is eligibility for later measurement, not a performance result;
measurement scheduling must consume a successful receipt before adding a row.
That scheduling/result integration is still pending, so no new codec enters the
published table in this segment.

## Dependency scope

- ACEAPEX: 1b13df34ac8e839dd3232b59bc59560d689a435a, interactive preset.
- zstd: f8745da6ff1ad1e7bab384bd1f9d742439278e99 (1.5.7).
- HTSlib: 4b705e4fada8ee2b6b15746f725ee8ac51631803 (1.24), pinned submodules,
  generated minimal zlib-only build configuration. CRAM is not qualified here.
- XZ: 49053c0a649f4c8bd2b8d97ce915f401fbc0f3d9 (5.4.5); CMake builds both CLI
  and static PIC liblzma from this revision for --check. No system liblzma linkage.

These pins establish correctness scope; they do not assert the latest release or
retroactively qualify historical timing results with new dependency versions.
All-four CI starts from a clean Ubuntu runner and retains check.json/check.log
artifacts. Dependency sources remain unmodified; generated build files are allowed.

## Plan axes from a current check

```sh
./run.sh --check codecs/xz.sh
./run.sh --plan --codec xz --axis region --axis batch
```

`--plan` discovers adapters by basename or supplied file path. Repeat `--codec`
and `--axis` for a subset; omit them to select every adapter and all nine axes.
`--work` selects the same build-root directory as --check. Output defaults to
`.work/axes.plan.json`; an explicit output must end in `.plan.json` to keep plans
separate from measurement JSONL. The command performs no build or measurement.

The plan asks the adapter for its current capabilities. Supported axes receive
`schedule / eligible`; unsupported axes receive `skip / n/a` with exactly the
adapter's reason. There is no codec-name capability table in the planner. Eligible
means correctness-qualified, not measured or ready for publication. A missing
measurement backend is a blocking implementation error, never an invented n/a
reason attributed to the codec.

New --check receipts use protocol `cabench-check-v2`. The checker snapshots state
before and after correctness tests; the planner recomputes it. The binding covers:

- Adapter shell, declared companion sources, and shared correctness code.
- Declared native/CLI binaries and their resolved shared-library hashes.
- Codec name/version, supported axes/reasons, explicit configuration and constraints.
- Dependency commits, clean tracked sources, pinned/clean submodules, architecture
  and the selected loader environment (including PATH).

Adapters declare companion inputs with `codec_inputs` and executable/library
outputs with `codec_build_artifacts`, both JSON path arrays. The native region
library must appear in the latter. `codec_configuration` supplies the configuration
being qualified; the default is the smoke constraints. Authors must declare their
additional helpers/assets: trusted executable adapters cannot be audited for
undeclared arbitrary dependencies by a generic shell checker.

Old receipts remain historical evidence but do not satisfy this stronger gate.
Rerun only the small --check after upgrading; no full benchmark is required.
Receipts are local, unsigned checks of declared inputs, not portable attestations.
A changed source, binary, configuration or loader environment requires rechecking.
Documentation-only changes do not invalidate the protocol fingerprint.

The internal `dispatch_adapter(plan, handlers)` seam revalidates a plan before
calling handlers, never calls a handler for n/a, checks all required backends before
starting, and rejects output if checked state changes during dispatch. A shared
build lock excludes cooperative rebuilds for the complete call sequence. This is
covered with test handlers and the native execution path described below. Plans use their own schema, contain no measured values,
and are never appended to the historical 435-row results file.

Remaining work: connect actual native timing/counter/batch/curve implementations
and validated result serialization to this seam, preserving their methodology and
same-run baseline comparisons. The plan command itself does not finish migration
of the nine axes or make the instrument release-ready.


## Execute the first connected native axes

```sh
./run.sh --check codecs/xz.sh
python3 harness/resident_fixture.py .work/native-input
./run.sh --measure --codec xz --axis ratio --axis region --axis decode --axis break_even --input .work/native-input --output-dir .work/native-xz
```

Repeat `--codec` to measure other qualified adapters in this invocation. Any of
the nine axis names may be selected; unsupported ones yield the adapter's n/a reason
without invoking an encoder or decoder. The output
directory must be new. `manifest.json` is written only after all selected adapters
and verification checks succeed. Raw candidate samples and failure diagnostics
remain in the directory if a worker fails; they are not successful measurements.
This experimental `cabench-native-samples-v1` format is not publication JSONL.

The C worker loads the same ABI-2 context libraries checked by `--check`, without
codec-name branches. Archive loading, index preparation and output allocation are
outside timing. Region timing covers the native context callback, including its
bounds checks and the existing decoder API; it excludes process launch, Python,
verification and serialization. ACEAPEX still parses its header inside each API
call. This callback boundary is recorded explicitly; no claim of instruction-level
identity to the older directly linked timing calls is made.

The region workload retains 12 warmups, seed 20260909, 200 reads of 16 KiB and the
historical LCG sequence. Full decode retains one warmup and five samples. Every
sample is verified outside the timer. Ratio counts all `codec_artifacts`, including
BGZF's mandatory .gzi, and verifies a CLI restoration outside any timer. Break-even
uses the same run's median full decode and region p50, with the historical rule
floor(full_ms / region_p50_ms) + 1. Shared raw samples are reused, not remeasured.

A single-size decode result is explicitly `data_edge`, not a plateau throughput
headline. These small native runs prove executable integration and correctness;
their timings are not performance claims. Capability changes require new small
check receipts. Missing axes remain adapter-owned migration reasons and are not
substituted into the published historical table.

Migration remains incomplete: throughput plateaus/CLI encode timing, decoder
counters, access-profile block mapping, native batch and controlled c(g) still need
backends. Historical dense/default/frontier configurations and declared GPU rows
must also keep their distinct provenance. The 435 published records are immutable:
artifact replay can be byte-identical; fresh timings cannot be expected to be.
The owner authorized a full comparison run after all axes are connected and small
checks pass. It must write a separate artifact before any publication decision.
