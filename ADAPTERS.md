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
