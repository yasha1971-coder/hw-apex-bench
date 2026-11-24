# HW-GIFT-1 | pre-run protocol, 2026-11-24

Prediction (not a measurement): for enwik8, level 3, 4 KiB reads, the
64 MiB / 64 KiB first-read p50 ratio is at least 10, and the 64 KiB
archive is at most 15% larger than the 64 MiB archive. Both conditions
must hold. Do not tune thresholds, seeds or frame sizes after inspection.
Report a miss. No external contact or publication of benchmark claims.

One host, one pinned CPU, single-thread encoding and reading. Record CPU,
OS/kernel, affinity, CLI and linked zstd/seekable revisions and commands.
Inputs: enwik8 and silesia_tar from corpora.json; Fedora raw.xz and raw
digests from HWAB-NBD-1c image/. Check both stages before encoding.
Use seekable-format archives including the seek table in byte counts.
Inspect observed decompressed frame sizes (last may be short).
Grid: 64, 256 KiB; 1, 4, 16, 64 MiB; levels 3, 19. Encode each archive
once; keep sizes, hashes, encoder options. Use one archive at a time.

For each corpus and read length (4 or 64 KiB), use Python Random with
integer seeds 2026112400 through 2026112404, one seed per repeat, 1000
randrange(size-length+1) offsets drawn with replacement. Retain offset
lists. Reuse across all frame sizes/levels. No alignment or exclusion of
zero-filled areas. Let cross-frame reads cross. Report this distribution
when interpreting the sparse Fedora image.

Use resident archive pages and the native ZSTD_seekable_decompress path
(codecs/native/zstd_seekable.c). Each pair starts with a new initialized
reader outside the timer. First read and immediate same-offset, same-size
repeat on that reader are timed separately (monotonic clock). No app-level
result cache. No disk-cache flush. Reader reset is not disk cold; repeat
is an observed operation, not a guaranteed cache hit. Compare BOTH returned
byte strings and lengths to source outside timing, retaining both before
reuse. Peak RSS (KiB, ru_maxrss on Linux): fresh reader process per repeat,
including resident archive and buffers, excluding encoding and the parent
verifier. Do not interpret it as decoder-only memory. Keep all samples.
Negative control: destroy magic of a known data frame on a private archive
copy and read inside that frame: native error required, byte mismatch alone
is insufficient. Run outside timing. Stop on any failed check.

Report nearest-rank p50 and p99 per repeat for each series; take the
median of the five corresponding statistics, likewise peak RSS.
Relative archive bytes = 100*(size(g)/size(64MiB)-1), within corpus and
level. Include exact bytes and hashes; failed/incomplete runs are not
successes. No other codec. No new measurement before resource approval.
