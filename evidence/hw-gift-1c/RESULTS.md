# HW-GIFT-1c: source-size hint changes the writer policy

**STATUS: COMPLETE.** The exact cause is contrib’s unconditional [`ZSTD_c_srcSizeHint = maxFrameSize`, zstdseek_compress.c:234](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/contrib/seekable_format/zstdseek_compress.c#L234). pyzstd’s writer leaves that hint unset. The hint selects small-source compression parameters and a smaller window while pledged size remains unknown. Disabling the hint in a private copy makes every tested data frame byte-identical to pyzstd. Full archives retain an exactly explained optional seek-table checksum difference.

[Original preregistration](CALIBRATION.md) · [Pinned source paths](SOURCE_PATHS.md) · [One-line patch](zstdseek_compress.patch) · [Minimal C program](frame_probe.c) · [Independent audit](audit/independent-audit.json)

## Preregistered calibration

|hypothesis|forecast / observed fact|verdict|
|---|---|---|
|H1|The source-size-tier/window part is supported, but the stated single-END/pledged-size mechanism is false: both actual writers stream with unknown pledged size; contrib supplies a hint. FCS is absent in both. At 512 KiB the size gap vanishes, but a window-descriptor byte still differs.|Literal **MISS**; corrected hint mechanism recorded separately.|
|H2|Holding hint and final empty END fixed, replacing two 128 KiB CONTINUE feeds with one whole-frame CONTINUE changes neither writer’s frame SHA.|**Rejected / MISS**: declared kill-H2 condition met.|

The declared kill-H1 predicate (identical headers and effective parameters) is not met: windows differ and the source-derived parameter policies differ. That does not convert the incorrect pledge premise into a HIT. No hypothesis or criterion was rewritten after inspection. The result establishes the pinned code cause on these inputs; it does not claim a general speed law or novelty.

## Method controls and references

All three required controls passed before comparison: identical 256 KiB input/call produced identical bytes twice; level 3 vs 4 differed and the comparator reported byte 6; a separate first-call END frame decoded to known FCS 262144. Corrupted frame magic also raised a native error. [Raw method checks](method-check.json).

The old C runner deleted its temporary archives. This investigation reconstructed C references with the unchanged encoder and required exact HW-GIFT-1b SHA/size equality for the six existing points. Existing pyzstd archives were read directly and likewise checked. The two new 128/512 KiB points use the same writer paths. No historical timing series was rerun.

## Main anomaly: enwik8 L3, 256 KiB

[Per-frame CSV](frame-comparison.csv): 382 frames, including 381 full frames; all 381 full frames have different compressed lengths. pyzstd is smaller in 381 of 382 total frames; full frame 272 is one byte larger (75675 → 75676 B). This local loss remains in the CSV.

Both header descriptors are `0x00`: no FCS, no frame-content checksum, no dictionary ID. The window byte differs:

|writer|frame-0 header hex|window descriptor|window B|FCS|
|---|---|---|---:|---|
|contrib|`28b52ffd0040`|`0x40`|262144|absent|
|pyzstd|`28b52ffd0058`|`0x58`|2097152|absent|

Parameter policy returned by pinned `ZSTD_getCParams(level, hint-or-UNKNOWN, 0)`:
|policy|windowLog|chainLog|hashLog|searchLog|minMatch|targetLength|strategy|
|---|---:|---:|---:|---:|---:|---:|---|
|hint=262144|18|16|16|1|4|0|2 (dfast)|
|hint=0 / UNKNOWN|21|16|17|1|5|0|2 (dfast)|

These are source-derived policy values, not requested-zero CCtx getters presented as internal-state measurements. The source fallback using the hint is [zstd_compress.c:1641–1645](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/compress/zstd_compress.c#L1641); size-tier selection is [line 7762](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/compress/zstd_compress.c#L7762). The applied window is checked independently in actual headers. The experiment changes the hint as a whole and does not isolate the contribution of each internal parameter.

## Exact minimal reproduction

Take bytes `[0,262144)` of the hash-verified enwik8 input. Use a fresh CCtx, no pledged-size call, CONTINUE input and a final empty END. The only policy difference is hint 262144 versus zero.

```sh
cc -std=c11 -O2 -Wall -Wextra -Werror -I"$ZSTD/lib" frame_probe.c "$ZSTD/lib/libzstd.a" -pthread -o frame_probe
head -c 262144 enwik8 > slice.bin
./frame_probe slice.bin contrib.zst 3 262144 131072 empty
./frame_probe slice.bin pyzstd.zst 3 0 262144 empty
sha256sum contrib.zst pyzstd.zst
```

|frame|bytes|SHA-256, exactly equal to frame 0 in the complete reference archive|
|---|---:|---|
|contrib|93113|`3cab61b1c4cec5296d5ff271d162bbbd3ef730604c00a8833a4dac211db461e6`|
|pyzstd policy|91459|`bf72723ed208c90b32be0400bb1a611201f32555ca98d6f6261395614f2ec2c2`|

Both outputs restore the original slice exactly. The independent controller rebuilt the C probe and reproduced both hashes again. [Minimal proof and H2 controls](minimal-proof.json). The first-call END used for known-FCS validation is kept separate from this real streaming path.

## One-line private-copy change

```diff
- ZSTD_CCtx_setParameter(zcs->cstream, ZSTD_c_srcSizeHint, (int)zcs->maxFrameSize);
+ ZSTD_CCtx_setParameter(zcs->cstream, ZSTD_c_srcSizeHint, 0);
```

The original pinned source stays clean. No other writer policy is changed. Patched contrib keeps seek-table checksums enabled.

## Complete size effect

|corpus/level|frame KiB|N frames|original contrib B|hint=0 contrib B|pyzstd B|change B|change %|remaining B|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|[enwik8-L3](cases/enwik8-L3-65536.json)|64|1526|39654522|39573564|39567460|-80958|-0.204158|6104|
|[enwik8-L3](cases/enwik8-L3-131072.json)|128|763|38510829|38386321|38383269|-124508|-0.323306|3052|
|[enwik8-L3](cases/enwik8-L3-262144.json)|256|382|37935213|37326215|37324687|-608998|-1.605363|1528|
|[enwik8-L3](cases/enwik8-L3-524288.json)|512|191|36535040|36535040|36534276|0|0.000000|764|
|[enwik8-L19](cases/enwik8-L19-65536.json)|64|1526|36265760|36244232|36238128|-21528|-0.059362|6104|
|[silesia-L3](cases/silesia-L3-65536.json)|64|3235|73587959|73434013|73421073|-153946|-0.209200|12940|
|[silesia-L3](cases/silesia-L3-262144.json)|256|809|69675977|69577856|69574620|-98121|-0.140825|3236|
|[silesia-L19](cases/silesia-L19-65536.json)|64|3235|65101245|64811561|64798621|-289684|-0.444975|12940|

All numbers include complete seek tables. Change compares contrib with checksums enabled on both sides. All 11667 patched data frames match pyzstd byte for byte. Every archive was restored bit for bit and every present seek-table XXH64 field was checked. [Independent size CSV](audit/independent-cases.csv).

At 512 KiB, all 191 original data frames have the same lengths and payload bytes as pyzstd except byte offset 5: `0x48` (524288-byte window) becomes `0x58` (2097152-byte window). The independent audit checked every byte, including the tail. Thus the observed extra size effect disappears at that boundary; frame-byte equality still requires the hint change.

## Every remaining byte

Contrib’s example enables optional seek-table checksums; pyzstd omits them. Each enabled entry stores compressed size (4 B), decompressed size (4 B), and the low 32 bits of XXH64 of the uncompressed frame with seed zero (4 B). Without checksum it stores only the two sizes. The skippable header is 8 B; the common footer is 9 B. Hence table sizes are `17 + 12*N` and `17 + 8*N`.

Removing each four-byte checksum, adjusting the little-endian skippable payload-length field and clearing footer descriptor bit 7 yields the exact pyzstd archive. Adding the independently calculated checksums, updating length and setting that bit reconstructs the exact patched contrib archive. All data-frame bytes stay untouched in both transformations; both directions were checked for all eight cases.

For the main anomaly: **608998 B of frame data + 1528 B of table fields = 610526 B**. The patch removes the frame-data difference and retains the checksum option. All multi-byte table fields are little-endian. For N=382 the table payload lengths are 4593 and 3065 B; including the 8-byte skippable header, tables are 4601 and 3073 B.

|main-case table|8-byte skippable header hex|9-byte footer hex|
|---|---|---|
|patched contrib|`5e2a4d18f1110000`|`7e01000080b1ea928f`|
|pyzstd|`5e2a4d18f90b0000`|`7e01000000b1ea928f`|

## One paired speed observation

[Preregistered timing scope](TIMING_PROTOCOL.md) · [Raw pair](timing/attempt-001/pair.json) · [Lock/load receipt](timing/attempt-001/ovh-bench.json) · [Untimed native selfcheck](timing/selfcheck.json)

Complete enwik8, L3, 256 KiB frames; same native writer/decoder paths, table checksums enabled in both. Buffers reside in RAM; fresh context initialization, prefault, hashing and byte comparisons are outside inner timers. Internal first-use codec allocations remain inside. Order was original encode, patched encode, original decode, patched decode. One observation each, no warmups.

|variant|compression ns|compression ms|full decode ns|full decode ms|archive B|
|---|---:|---:|---:|---:|---:|
|original|340959823|340.959823|81793021|81.793021|37935213|
|hint=0|312972138|312.972138|70095693|70.095693|37326215|

On this pair, compression elapsed changed -8.208499% and full decode elapsed changed -14.301132%. No speed penalty was observed in this pair. Fixed order and one pair do not establish a general ranking, distribution or throughput plateau.

Host: AMD EPYC 4344P 8-Core Processor, ace-core / CPU 0, 5.15.0-163-generic, schedutil. Boundary load1: 0.09 → 0.09; shared blocking OVH lock, threshold 2.0. 0 of 1 paired observations retaken; 0 LOADED attempts. All attempts, UTC date/loadavg/nproc, raw /proc/stat and observational other-core deltas are retained. Absolute times apply to this host and RAM-resident workload.

## Which output to choose

- For storage density on these small-frame cases, pyzstd’s no-hint policy is smaller overall. Patched contrib achieves the same data bytes while retaining its optional table checksums. Users wanting byte-identical complete pyzstd archives must also choose the no-checksum table representation; that is a separate format option, not another compression fix.
- For constrained encoder/window memory, the original hint remains a useful choice. In the minimal L3/256 KiB probe, `ZSTD_sizeof_CCtx` after encoding was 1566233 B with the hint and 3663385 B without it (2.338978×). This is CCtx accounting, not process RSS. The declared window grows from 256 KiB to 2 MiB. At 512 KiB the change buys no stored-byte saving.
- The one speed pair supports only its recorded observation. Choose a hint policy explicitly for the storage/memory budget; broader speed or default-policy recommendations require more evidence.

## Audit and scope

Independent controller: 24 actual archives, 35001 native frame decodes, two rebuilt minimal correctness encodings, zero clocks. [Audit output](audit/independent-audit.json), SHA-256 `5dbd418442c1961f6859582e445ae7a9950cfaf7d19686454aef15ecde80540a`; [separate parser/verifier source](audit/verify_independent.py). The controller imports neither primary run.py nor seekable.py.

[Additional read-only timing audit](audit/timing-audit.json), SHA-256 `3316277cbbcb853ed2d2f0b08dac3134e72ce8bfa16b20d46b6ea7468c8f15b6`, independently checked the selected result, raw stdout, lock/load receipts, per-core deltas and archive/build identities without rerunning a timed operation.

Preregistration 65baf466 was the first branch commit before encoding. Each verified chunk was committed/pushed before advancing. The separate method document is PR #91. Existing HW-GIFT-1/1b evidence remains unchanged. [Draft upstream issue](ZSTD_ISSUE_DRAFT.md) is a local unsent artifact; pyzstd issue #75 was not changed. PR #92 stays draft; no merge or external contact was performed.
