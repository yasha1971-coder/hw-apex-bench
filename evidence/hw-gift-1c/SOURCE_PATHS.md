# HW-GIFT-1c: pinned writer paths

This is source inspection, not a measurement or a byte-identity result. The
candidate below remains unproved until the preregistered method controls and
frame comparisons pass. No encoding or timing was performed for this document.

## Versions and provenance

The existing HW-GIFT-1b environment uses CPython 3.12.16, pyzstd 0.20.0,
backports.zstd 1.8.0, and linked libzstd 1.5.7. CPython imports the compiled
`backports/zstd/_zstd.cpython-312-x86_64-linux-gnu.so`, not the CFFI implementation.
The installation pins and payload hashes are retained in
[the existing installation receipt](../hw-gift-1b/environment/install-receipt.json)
and [wheel manifest](../hw-gift-1b/environment/wheel-manifest.json).

| Release | Immutable source anchor |
|---|---|
| pyzstd 0.20.0 | tag `0.20.0`, commit [`f6c6cb109290b74cb7289bba8252514222d4a6ab`](https://github.com/Rogdham/pyzstd/tree/f6c6cb109290b74cb7289bba8252514222d4a6ab) |
| backports.zstd 1.8.0 | tag `v1.8.0`, commit [`2372ea098b7b87430293c8344888e01ad3d1d04d`](https://github.com/Rogdham/backports.zstd/tree/2372ea098b7b87430293c8344888e01ad3d1d04d) |
| zstd 1.5.7 | existing checkout HEAD [`f8745da6ff1ad1e7bab384bd1f9d742439278e99`](https://github.com/facebook/zstd/tree/f8745da6ff1ad1e7bab384bd1f9d742439278e99) |

The exact package artifacts are:

| Artifact | SHA-256 |
|---|---|
| `pyzstd-0.20.0-py3-none-any.whl` | `9c6aff5aa9b12bb14d51f724915f176db9b187214d66d93d990c75ff054483c6` |
| `backports_zstd-1.8.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl` | `f9e9aa28a44db1897fb637f037175566f3b75890d4bae6cae7ba34f1df1e0804` |
| [`backports_zstd-1.8.0.tar.gz`](https://files.pythonhosted.org/packages/ff/9c/13569626440e88f09d16f43ec1c2aa0d10a523be2811414580d1cfb7c9f3/backports_zstd-1.8.0.tar.gz) | `9dae4f4c481716e3db473d667457b4f508ff7459c0931b567a5c9677fb3db316` |

The sdist was read in memory and checked against its
[exact-version PyPI metadata](https://pypi.org/pypi/backports-zstd/1.8.0/json).
Its `src/c/compression_zstd/compressor.c` bytes match the pinned GitHub commit.
The installed pyzstd `__init__.py` and `_seekable_zstdfile.py`, and the installed
backports.zstd `__init__.py`, also match their pinned GitHub source bytes.
Matching release source does not assert a reproducible build of the wheel's
native extension; its installed binary hash is recorded separately below.

## pyzstd writer to native backend

1. On CPython below 3.14, [pyzstd `src/pyzstd/__init__.py:18-21`](https://github.com/Rogdham/pyzstd/blob/f6c6cb109290b74cb7289bba8252514222d4a6ab/src/pyzstd/__init__.py#L18-L21)
   selects `backports.zstd`. Its [loader:36-40](https://github.com/Rogdham/backports.zstd/blob/2372ea098b7b87430293c8344888e01ad3d1d04d/src/python/backports/zstd/__init__.py#L36-L40)
   imports the compressor from `_zstd`.
2. [Seekable writer constructor:594-602](https://github.com/Rogdham/pyzstd/blob/f6c6cb109290b74cb7289bba8252514222d4a6ab/src/pyzstd/_seekable_zstdfile.py#L594-L602)
   stores `max_frame_content_size` and creates `ZstdCompressor` with the supplied
   level/dictionary. [Frame reset:673-676](https://github.com/Rogdham/pyzstd/blob/f6c6cb109290b74cb7289bba8252514222d4a6ab/src/pyzstd/_seekable_zstdfile.py#L673-L676)
   resets byte counters, not a pledged source size.
3. [Writer:735-759](https://github.com/Rogdham/pyzstd/blob/f6c6cb109290b74cb7289bba8252514222d4a6ab/src/pyzstd/_seekable_zstdfile.py#L735-L759)
   slices each `.write()` input at the remaining frame capacity and calls
   `compress(data)` without a mode argument. The [wrapper:225-235](https://github.com/Rogdham/pyzstd/blob/f6c6cb109290b74cb7289bba8252514222d4a6ab/src/pyzstd/__init__.py#L225-L235)
   defaults that call to `CONTINUE`.
4. At a frame boundary, [writer:786-801](https://github.com/Rogdham/pyzstd/blob/f6c6cb109290b74cb7289bba8252514222d4a6ab/src/pyzstd/_seekable_zstdfile.py#L786-L801)
   calls `flush(FLUSH_FRAME)` and logs the completed frame. [Close:706-708](https://github.com/Rogdham/pyzstd/blob/f6c6cb109290b74cb7289bba8252514222d4a6ab/src/pyzstd/_seekable_zstdfile.py#L706-L708)
   also closes the final frame before writing the seek table.
5. The native [compressor constructor:364-376](https://github.com/Rogdham/backports.zstd/blob/2372ea098b7b87430293c8344888e01ad3d1d04d/src/c/compression_zstd/compressor.c#L364-L376)
   creates a `ZSTD_CCtx`. The integer level reaches
   [`ZSTD_CCtx_setParameter(..., ZSTD_c_compressionLevel, level)`:114-116](https://github.com/Rogdham/backports.zstd/blob/2372ea098b7b87430293c8344888e01ad3d1d04d/src/c/compression_zstd/compressor.c#L114-L116).
   [Native input setup:465-475](https://github.com/Rogdham/backports.zstd/blob/2372ea098b7b87430293c8344888e01ad3d1d04d/src/c/compression_zstd/compressor.c#L465-L475)
   passes the complete supplied buffer, or an empty input for flush.
   [`compressor.c:493`](https://github.com/Rogdham/backports.zstd/blob/2372ea098b7b87430293c8344888e01ad3d1d04d/src/c/compression_zstd/compressor.c#L493)
   calls `ZSTD_compressStream2` with the requested directive;
   [flush:688](https://github.com/Rogdham/backports.zstd/blob/2372ea098b7b87430293c8344888e01ad3d1d04d/src/c/compression_zstd/compressor.c#L688)
   calls that path with a null input buffer and `ZSTD_e_end`.

An explicit pledge API exists: [pyzstd wrapper:248-261](https://github.com/Rogdham/pyzstd/blob/f6c6cb109290b74cb7289bba8252514222d4a6ab/src/pyzstd/__init__.py#L248-L261)
delegates to [native `ZSTD_CCtx_setPledgedSrcSize`:744-745](https://github.com/Rogdham/backports.zstd/blob/2372ea098b7b87430293c8344888e01ad3d1d04d/src/c/compression_zstd/compressor.c#L744-L745).
The inspected `SeekableZstdFile` write path does not invoke it and does not set
`ZSTD_c_srcSizeHint`.

## contrib writer and source-size hint

The example's [input allocation:67](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/contrib/seekable_format/examples/seekable_compression.c#L67)
uses `ZSTD_CStreamInSize()`, and its [read/feed loop:77-85](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/contrib/seekable_format/examples/seekable_compression.c#L77-L85)
uses the seekable stream's next-input hint, capped by that allocation.

The seekable initializer [calls `ZSTD_initCStream`:164](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/contrib/seekable_format/zstdseek_compress.c#L164).
In zstd 1.5.7, [`ZSTD_initCStream`:6077-6083](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/compress/zstd_compress.c#L6077-L6083)
resets the session and sets the compression level.

The additional choice is at
[`contrib/seekable_format/zstdseek_compress.c:234`](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/contrib/seekable_format/zstdseek_compress.c#L234):

```c
ZSTD_CCtx_setParameter(zcs->cstream, ZSTD_c_srcSizeHint, (int)zcs->maxFrameSize);
```

The following [lines:235-242](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/contrib/seekable_format/zstdseek_compress.c#L235-L242)
limit the input to the remaining frame capacity and call `ZSTD_compressStream`.
That [legacy API:6301-6304](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/compress/zstd_compress.c#L6301-L6304)
delegates to `ZSTD_compressStream2(..., ZSTD_e_continue)`.
The seekable [end-frame path:197-223](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/contrib/seekable_format/zstdseek_compress.c#L197-L223)
calls `ZSTD_endStream`, logs the frame, and resets the session. The
[end-stream API:7654-7657](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/compress/zstd_compress.c#L7654-L7657)
supplies empty input with `ZSTD_e_end`.

## H1/H2 distinction and candidate experiment

`srcSizeHint` is a parameter-selection hint, not a pledge of frame content
size. [Its declaration:2075-2079](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/zstd.h#L2075-L2079)
defines zero as an invalid/absent hint. When the pledged source size is unknown,
[`ZSTD_getCParamsFromCCtxParams`:1641-1650](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/compress/zstd_compress.c#L1641-L1650)
uses a positive hint for parameter selection. The
[tier selector:7761-7772](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/compress/zstd_compress.c#L7761-L7772)
has boundaries at 16, 128 and 256 KiB. For example, the source tables have
different level-3 rows for [unknown/large sources:31](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/compress/clevels.h#L31)
and [sources up to 256 KiB:57](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/compress/clevels.h#L57).
These are table entries; actual resolved parameters and frame headers must be
checked by the experiment.

Consequently, the inspected paths suggest a source-size-tier mechanism without
an explicit pledge in either writer. A hint need not create an FCS field. This
is narrower than H1's proposed pledge/single-END mechanism; the header dump and
parameter comparison must decide which parts of H1 survive.

For the minimal C comparison, use a fresh CCtx, the same level, no dictionary,
no pledge, `CONTINUE` input calls, then an empty-input `END` drained to completion.
Vary only `srcSizeHint` between zero and the frame limit while holding input
chunking and output-buffer handling constant. The source-only one-line candidate
for a copy of contrib is:

```c
ZSTD_CCtx_setParameter(zcs->cstream, ZSTD_c_srcSizeHint, 0);
```

This candidate is not a claimed fix, a recommendation, or evidence of a size or
speed benefit until the required byte-hash and decode checks pass.

For H2, hold the hint, level, output-buffer handling and end directive constant;
vary only the input split between `ZSTD_CStreamInSize()` chunks and the full
frame. The original example's chunking is the reference condition, so a hint
test must not change it simultaneously. Calling `END` with the whole input is
not an isolated chunking test: at the first stream initialization,
[`zstd_compress.c:6366`](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/compress/zstd_compress.c#L6366)
automatically pledges that input size. Such a call is useful as a separate known
FCS/header-decoder control.

## Seek-table accounting is separate

The contrib example [enables seek-table checksums:74](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/contrib/seekable_format/examples/seekable_compression.c#L74).
Contrib's [entry-size calculation:270-273](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/contrib/seekable_format/zstdseek_compress.c#L270-L273)
uses 12 bytes per entry when enabled. Its [end-frame code:211-215](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/contrib/seekable_format/zstdseek_compress.c#L211-L215)
records the low 32 bits of XXH64 for that entry.
Pyzstd's [writer:293-305](https://github.com/Rogdham/pyzstd/blob/f6c6cb109290b74cb7289bba8252514222d4a6ab/src/pyzstd/_seekable_zstdfile.py#L293-L305)
allocates `17 + 8 * frame_count` bytes and writes only compressed/decompressed
sizes. At equal frame count, this structural difference is exactly four bytes
per seek-table entry. It is not a data-frame checksum or a compressed-payload
difference. Any additional archive-size difference needs separate frame/header
comparison.

## Source and installed-payload hashes

The hashes below were read without modifying source files. Paths use the
repository layout at the pinned source commits; installed Python modules omit
the `src/` prefix.

| Source/payload | SHA-256 |
|---|---|
| pyzstd `src/pyzstd/__init__.py` | `9ae8acf623c257d392001efa11c776ab9b03ae2e9e3c23825f5fc369fe55e1de` |
| pyzstd `src/pyzstd/_seekable_zstdfile.py` | `6b28a9ba31397d2aeeec0e31a2ec09566a6a5c3bedece770e5ffb6bd5b9769d6` |
| backports.zstd `src/python/backports/zstd/__init__.py` | `47cdd7c51b1c95138c51b308df07e85c4ba1d34e7ca3f42b2a96b35539330755` |
| backports.zstd `src/c/compression_zstd/compressor.c` | `dc66416125901d89d1873986f2a425052bd2bad9215a1a0a1ed05768bf4834f6` |
| backports.zstd `src/c/compression_zstd/clinic/compressor.c.h` | `dc931eee5f85ee1e1f3abffafe75594894fbc0e4c8fa2e2212c96b2f22bf5a6b` |
| installed `backports/zstd/_zstd.cpython-312-x86_64-linux-gnu.so` | `dafddc5ce29d0f891c4f0c7605bb8e0c6c2fc529fd9d10e13a31537e3c1c6698` |
| zstd `contrib/seekable_format/examples/seekable_compression.c` | `fc0dfdb04e639bb2844c672261252068572c29ed2272adcdb8bcb0314290e705` |
| zstd `contrib/seekable_format/zstdseek_compress.c` | `3aefdd381ba8989857392037ada029441030a00f5af0b6dfbfbf817dbbeba4de` |
| zstd `lib/compress/zstd_compress.c` | `10c315ae609d49b2fc431521aa95908086e69fd917991c5ed9a875af3d1208e8` |
| zstd `lib/compress/clevels.h` | `d764daa89b7a636d26fe96ff3536c5075e9867fb5dddbf8c9d57023a8ff4a155` |
| zstd `lib/zstd.h` | `9b4bc8245565c98ccfc61c07749928b57e7c0f6fddb0530c4f6aa1971893d88b` |
