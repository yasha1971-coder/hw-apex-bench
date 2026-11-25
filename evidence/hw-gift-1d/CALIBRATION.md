Predictions (not measurements):
 P1 At 256 B frames, level 10, enwik8 first 16 MiB: hint=0 compression is at least 3x slower
    than hint=maxFrameSize (PR #3544 reports ~14x on M1 for the whole of enwik8).
 P2 At 64 KiB and above, levels 3 and 10: hint=0 compression time is within +/-10% of
    hint=maxFrameSize, and hint=0 archives are smaller or equal.
 P3 There is a frame size X between 1 KiB and 64 KiB such that the rule
    "hint only when maxFrameSize < X" is never more than 10% slower than the original and never
    larger than hint=0 by more than 0.05% at frame sizes >= X.
 Kill: hint=0 at 64 KiB level 3 is >= 1.10x slower (median) than the original -> the size gain
 costs speed and the issue must be framed as a pure trade-off.

Method check before the main grid (stop if any fails):
 - the original and patched writers reproduce the HW-GIFT-1c archive SHA for enwik8 L3 256 KiB;
 - timing self-check: the same writer timed twice in a row differs by < 5% median;
 - every archive restores bit for bit.

Grid: frame sizes 256 B, 1 KiB, 4 KiB, 16 KiB, 64 KiB, 256 KiB, 512 KiB; levels 3, 10, 19;
corpora enwik8 and silesia.tar (same hashes as HW-GIFT-1b). For 256 B and 1 KiB use the first
16 MiB of each corpus, state it in the table. Variants: original (hint=maxFrameSize),
hint=0, and the conditional rule once X is chosen from the data (chosen X is a development
step: record it separately and confirm on the corpus not used to choose it).

Timing: under the OVH-BENCH lock (flock /run/lock/ovh-bench.lock, LOADED if load1 > 2.0),
input and output in RAM, 5 repeats per cell, order interleaved A B A B (not fixed), median and
min reported. Compression time is the main metric; full decode time once per cell as an
observation. Sizes include the full seek table.

Deliver: evidence/hw-gift-1d/RESULTS.md on branch hw-gift-1d, draft PR: table
(size and compression time, both variants, every cell), the boundary X, the conditional
one-line patch, its bytes/speed check, and ZSTD_ISSUE_DRAFT.md rewritten to: cite PR #3544 and
its reason first, show what the hint costs at 64-256 KiB, propose the conditional rule with
numbers. Draft only, not sent.
