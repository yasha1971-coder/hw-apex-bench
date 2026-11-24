Prediction (not a measurement):
 (a) enwik8, level 3, 4 KiB reads: first-read p50 at the default
     max_frame_content_size (1 GiB, so the whole corpus is one frame) is at
     least 20x the 1 MiB first-read p50.
 (b) For every corpus/level/frame size in the shared grid, pyzstd archive
     bytes are within 1% of the HW-GIFT-1 bytes.
Both must hold. Report a miss. Do not tune after inspection.

Setup: same host class as HW-GIFT-1, one pinned CPU, single thread.
pyzstd from PyPI, latest release, pinned by exact version and wheel hash;
record pyzstd.__version__ and pyzstd.zstd_version. CPython version recorded.
Inputs: enwik8, silesia.tar (same hashes as HW-GIFT-1).
Grid: 64, 256 KiB; 1, 4, 16, 64 MiB; plus default (argument omitted).
Levels 3 and 19. Write each archive once with
SeekableZstdFile(..., 'wb', level_or_option=L, max_frame_content_size=G);
keep bytes, sha256, frame count from the seek table.

Reads: 4 KiB and 64 KiB. Reuse the HW-GIFT-1 offset lists exactly
(seeds 2026112400..2026112404, 1000 offsets each).
Archive resident in memory (bytes, wrapped in io.BytesIO per pair).
Per pair: open a new SeekableZstdFile in 'rb' outside the main timer, but
time the open separately (open_ns). Then time seek(off)+read(n) as first
read, then the same seek+read again as repeat. Compare both results to the
source outside timing. Report p50 and p99 per repeat; median of 5 repeats.
Also report open_ns p50.

Negative control: corrupt the magic of one data frame in a private copy,
read inside that frame; pyzstd must raise. Byte mismatch alone does not count.

Resilience as in HW-GIFT-1: one checkpoint per corpus/level, push each
checkpoint to the branch, resumable. Stop on any failed check.
Deliver: evidence/hw-gift-1b/RESULTS.md with a table in the HW-GIFT-1 form
(size delta vs 64 MiB, first-read p50, open p50), plus a column for the
default. Open the PR as draft. Nothing outside hw-apex-bench.

Pre-measurement host amendment: the HW-GIFT-1 host is not available. HW-GIFT-1b runs on ace-core (AMD EPYC 4344P); record CPU, kernel, governor, pinned core and other load at start and end. On the same host and pinned core, also rerun the HW-GIFT-1 C reader (evidence/hw-gift-1/reproduce.sh, unchanged) on the same grid, so both readers share one host. HW-GIFT-1 data on main stay unchanged. Predictions (a) and (b) unchanged.
