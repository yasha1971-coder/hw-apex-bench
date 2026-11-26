[written by ChatGPT (AI) at the author's request; checked by the author]

# HW-REGION-1 foundations and source paths

This is source inspection and retained evidence, not a new measurement.
The unchanged preregistration is [CALIBRATION.md](CALIBRATION.md).

## What was already measured

- [README.md:29-45](../../README.md#example-pick-frontier--chrx) links current
  chrX evidence and the separately preserved ACEAPEX snapshots.
- [ACEAPEX_SNAPSHOTS.md:3-19](../../docs/RESULTS/ACEAPEX_SNAPSHOTS.md)
  records the 2026-09-30 refresh: thirty 2 MiB T2T windows, v2.1.0 persistent
  ACEAPEX versus BGZF. Its 16 KiB p50 values are 0.074632/0.065482 ms.
  That refresh contains no zstd-seekable row.
- The same document's historical chr1 table, lines 32-41, reports zstd-seekable
  0.046/0.0594 ms, ACEAPEX interactive 0.13/0.24 ms, and BGZF 0.102/0.212 ms.
  These are older source/host scopes, not predictions for v2.6.5 on ace-core.
- [ACEAPEX_UPGRADE_20260930.md:10-19](../../docs/RESULTS/ACEAPEX_UPGRADE_20260930.md)
  specifies the persistent C99 API and the exact modern matched-g scope.
- [CHR1_LIT16_20260918.md:23-29](../../docs/RESULTS/CHR1_LIT16_20260918.md)
  retains the literal-chunk cut: p50 -14.86%, ratio -3.319%. Its lines 52-61
  audit an older one-shot DCtx path; they do not describe the modern persistent
  C99 handle. The task explicitly closes FSE_CHUNK tuning and retrying the
  previously regressing DCtx change; neither is a lever in this experiment.
- [docs/AGENTS.md:5-15](../../docs/AGENTS.md) protects foreign projects and
  requires three-format CPU comparisons, complete archive/index accounting
  and raw provenance. [TOOL_ROADMAP.md:31-49](../../docs/TOOL_ROADMAP.md)
  requires resident native callbacks; shell startup is not a region timer.

## Live ACEAPEX pin and retained adapter

The official GitHub API resolved annotated tag
[`8fd46ca8c0c907cf352f15fb6de062d5531e6489`](https://api.github.com/repos/yasha1971-coder/aceapex/git/tags/8fd46ca8c0c907cf352f15fb6de062d5531e6489)
to commit [`ce6b6740c7aae8a01720d615ae024c181b7d52b6`](https://github.com/yasha1971-coder/aceapex/commit/ce6b6740c7aae8a01720d615ae024c181b7d52b6),
tagged 2026-11-26. This is the v2.6.5 source used here.

The [public C++ header:9-12](https://github.com/yasha1971-coder/aceapex/blob/ce6b6740c7aae8a01720d615ae024c181b7d52b6/src/aceapex.h#L9-L12)
declares 2.6.5, while the [C99 header:18](https://github.com/yasha1971-coder/aceapex/blob/ce6b6740c7aae8a01720d615ae024c181b7d52b6/c/aceapex_decode.h#L18)
still contains the literal decoder version 2.6.4. Record both, the CLI's actual
build-id string and the source commit. Do not patch an upstream version string.

`codecs/aceapex_v220.sh` preserves the prior adapter script, pinned to
`0a143cd64b35a802835f18c361f981968edf25a1`. The active `aceapex.sh` changes
only ACE_REF, ACE_LABEL and ACE_VERSION. ACE_MODE remains interactive;
the shared adapter's level 2, one thread, LIT_CHUNK=65536 and FSE_CHUNK=4096
contract remains explicit. No codec implementation is changed.

Setup builds fresh, owned dependencies under `.work/hw-region-1/deps`:
ACEAPEX above; zstd `f8745da6ff1ad1e7bab384bd1f9d742439278e99`;
HTSlib `4b705e4fada8ee2b6b15746f725ee8ac51631803`; libdeflate
`dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f`. The last two follow the current
`codecs/bgzip.sh:3-5` pins. Builds and archive creation run on CPU15 outside
the benchmark lock. Existing foreign dependencies are not modified.

## Actual persistent read path and work counters

The [resident wrapper:22-38](../../codecs/native/aceapex_persistent.c)
opens one `aceapex_dec_t` and calls `aceapex_dec_region` per request.
In the pinned C99 source:

- [zdec:46-48](https://github.com/yasha1971-coder/aceapex/blob/ce6b6740c7aae8a01720d615ae024c181b7d52b6/c/aceapex_decode.c#L46-L48)
  calls ZSTD_decompressDCtx, with a one-shot ZSTD_decompress fallback.
- [cur_chunk:209-220](https://github.com/yasha1971-coder/aceapex/blob/ce6b6740c7aae8a01720d615ae024c181b7d52b6/c/aceapex_decode.c#L209-L220)
  reuses a per-cursor DCtx and also supports raw, rANS and open paths.
- [cur_chunk_get:223-231](https://github.com/yasha1971-coder/aceapex/blob/ce6b6740c7aae8a01720d615ae024c181b7d52b6/c/aceapex_decode.c#L223-L231)
  maintains a four-entry chunk cache; [serve_h:393-419](https://github.com/yasha1971-coder/aceapex/blob/ce6b6740c7aae8a01720d615ae024c181b7d52b6/c/aceapex_decode.c#L393-L419)
  retains the last decoded block across region calls.

The v220 counter builder at `review/aceapex_v220/build_counter.py:24-25`
counts final entropy-chunk bytes on cache misses. That is useful physical work,
but it is not an actual count of zstd calls or zstd output bytes: one DNA chunk
can invoke several zstd frames, and some branches invoke none. The model therefore
needs separate counters at the actual zstd call boundary, using successful returned
byte counts. Count on a separate instrumented copy, with the identical trace/cache
lifecycle; leave the timed decoder untouched. Calibrate zstd constants on its
matching persistent-DCtx API, not an older one-shot lifecycle.

The other persistent APIs are `codecs/native/zstd_seekable.c:9-29`
(one ZSTD_seekable) and `codecs/native/bgzip.c:45-54` (one BGZF handle).
`harness/native_measure.c:69-97` shows open, prefault, 12 warmups and byte checks;
its historical 200 requests are not the new protocol's 1000 requests.
Boundary controls use actual archive units and fresh control handles, so cache
hits cannot silently hide the intended extra decoded work.

## Exact corpus recovery

Chr1 is 253935557 bytes, MD5 `9465e0f0df6e2c6eb39729c39cee5465`, SHA256
`04ee6db2e94ccc4daddc168453189d8c17a01454ba67ac0443a73a0401408ee0`.
Setup only reads the supplied foreign path and copies it to owned input state.
Reference enwik8 and silesia inputs are likewise read/copy/hash only.

The thirty T2T windows are the existing manifest coordinates and hashes, never a
fresh selection. The original ZIP is accepted only at 53075428 bytes and SHA256
`78f354a13f70e64ac6790af27e2befa98ac132d582a238a3e804201c24ca9808`.
If unavailable, recover those same bytes from the exact `corpora.json` NCBI gzip:
932696125 compressed bytes / MD5 `9280657210e4161147cbe13b022225b9`,
3156259565 expanded FASTA bytes / MD5 `cd1e52ce400c027ed0b7ab4b9d613f5a`.
Verify gzip CRC and the whole expanded source before accepting any window;
preserve case and remove only FASTA headers/line breaks as in the original
definition. Every recovered window must equal its existing 2097152-byte SHA.
The canonical Git manifest SHA is
`c5bc7014ecd0d6c7855e7ad1b01afbd20b8a7f2e55c93c8e78098fa4c049a763`;
use canonical Git bytes, since a Windows CRLF working copy has another hash.
