# Resident archive context: correctness proof

This follows the mechanical extraction in PR #21. It is an experimental native
interface exercised on four codecs, not a replacement for the published timing
runner or a completed seven-function shell adapter contract. Historical source
fragments, commands, reports and all 435 result records remain unchanged.

## Derived from the working implementations

| Operation | BGZF | zstd-seekable | ACEAPEX |
|---|---|---|---|
| Open once | RAM-backed fd, BGZF handle, load .gzi | create seekable decoder, initBuff | retain archive pointer and byte length |
| Region | bgzf_useek + bgzf_read | ZSTD_seekable_decompress | aceapex_decompress_region |
| Full decode | seek to start + bgzf_read | decompress from offset zero | aceapex_decompress |
| Close | close BGZF handle | free seekable decoder | free wrapper state |

`harness/resident_context.h` expresses these operations without codec headers.
The caller owns the resident archive buffer until close. An optional sidecar path
belongs to the adapter; the generic runner neither parses it nor knows its suffix.
Expected output size is caller-supplied metadata, not access to original bytes.
The original buffer is held only by the correctness oracle outside the adapter.
Each context has one caller. Different contexts may coexist. A negative return
means failure; output contents after failure are unspecified.

The intended timer encloses the native region callback, including lookup,
decoder work, allocation and copying to the destination. Open/index preparation
and close are outside it. The Python ctypes probe has **no timer**: it checks
correctness and must never be used to publish region latency. Moving timing to
callbacks will require a separate validation of the C timing runner.

ACEAPEX uses published core SHA `1b13df34ac8e839dd3232b59bc59560d689a435a`.
Its API still parses the header on every region call. No table caching or upstream
optimization has been introduced. Source hashes are checked before compilation.
The local HTSlib 1.24 qualification is explicitly distinct from the historical
system HTSlib used for published results; zstd is 1.5.7.

## Capabilities are executable and scoped

Each shell adapter now exposes `codec_supports` and `codec_unavailable` when
sourced, and `supports`/`unavailable` when executed. The generic probe validates
all nine axes: exactly one supported entry or a nonempty n/a reason per axis.
It obtains those reasons from the adapter, not a codec-name table in core.

These capabilities describe the **new context proof path**: decode and region
are available. Timers, storage accounting, counters, block mapping, batch and
controlled curve orchestration have not yet been connected. Their reasons say
so. BGZF c(g) retains its incomparable-baseline reason; BGZF/zstd/xz batch retains
`no batch API`. ACEAPEX batch says its existing callback has not yet been ported.
This does not retract supported axes in the published historical harness.

Legacy shell build/compress/restore dispatch remains intact. The seven-function
public shell contract, generic `./run.sh --check`, capability-driven measurement
scheduling and results generation remain subsequent work.

## Fourth-codec test: XZ

The fourth codec adds `codecs/xz.sh` and `codecs/native/xz.c`. Neither the common
header nor the generic probe contains an XZ branch or a codec-name registry.
Compression uses `--threads=1 -6 --check=crc64 --block-size=g` with XZ environment
overrides cleared. No --block-list or per-block filter change is used.

Open decodes Stream Header/Footer, finds Index using Footer backward_size,
decodes that resident byte range with lzma_index_buffer_decode, and checks stream
size and original size. Region uses lzma_index_iter_locate, decodes intersected
blocks with liblzma, verifies their checks, and assembles the requested slices.
It does not cache decoded blocks. Full decode uses lzma_stream_buffer_decode.

This first adapter supports one Stream without Stream Padding. Concatenated
Streams, padding, invalid footer/index/header and size disagreement are rejected.
The index-memory limit is 64 MiB; per-block output and decoder-memory limits are
256 MiB. These are explicit proof limits, not format limitations. Memory use and
index startup latency are not measured in this segment.

The six unittest methods cover capability reasons, five geometries plus a
one-block baseline, empty/one-byte/exact-block input, corrupt metadata, damaged
block contents, bounds, independent contexts, and resident access after file
removal. They verify the actual block sizes against `xz --robot -lv` and compare
regions inside blocks and across multiple boundaries byte-for-byte. These are
small correctness fixtures, not c(g) measurements.

## Reproduce the XZ proof

Requires Linux, gcc, Python 3, git, xz and the system liblzma.so.5. Header source is
pinned below; the runtime library version is reported, not claimed source-built.

```sh
mkdir -p .work/xz
git -C .work/xz init -q
git -C .work/xz fetch --depth=1 https://github.com/tukaani-project/xz.git 49053c0a649f4c8bd2b8d97ce915f401fbc0f3d9
git -C .work/xz checkout --detach FETCH_HEAD
export HB_XZ="$PWD/.work/xz"
export HB_CONTEXT_LIBRARY="$PWD/.work/xz-context.so"
bash codecs/xz.sh context-build "$HB_CONTEXT_LIBRARY"
python3 -m unittest discover -s harness -p test_resident_xz.py
```

For any already built context and archive, the same name-independent command is:

```sh
python3 harness/resident_probe.py --adapter codecs/xz.sh \
  --library .work/xz-context.so --archive INPUT.xz --original INPUT \
  --granularity 16384
```

BGZF additionally supplies `--sidecar INPUT.bgz.gzi`. Build recipes live in each
shell's `codec_context_build OUTPUT_SO`: set `HB_HTSLIB` to a built static PIC
HTSlib tree, `HB_ZSTD` to a built static PIC zstd tree, and `HB_ACEAPEX` to sources
exported at the published SHA. Preparation of these dependencies is not yet the
generic --check command. The local all-four receipt records actual versions,
input/archive hashes and commands. CI currently builds and runs XZ correctness
and checks capability completeness for all four, not all-four native compilation.

Primary API references:
- https://tukaani.org/xz/liblzma-api/index_8h.html
- https://tukaani.org/xz/liblzma-api/stream__flags_8h.html
- https://tukaani.org/xz/liblzma-api/block_8h.html
- https://tukaani.org/xz/man/xz.1.html
