# Decoded-byte amplification

`A = sum over queries of bytes actually expanded by the decoder / sum of requested bytes`.
The denominator is 200 × 16,384 = 3,276,800 original-file bytes. No base-coordinate
conversion or FASTA processing is involved. Numerator units are actual inflated
BGZF blocks, reconstructed zstd blocks in frames, and touched ACEAPEX chunks in
its literal, offset, length and command streams. Repeated expansions are counted
again; this is decoder work in bytes, not compressed I/O or total memory traffic.

The pinned chr1 trace explains the previously reviewed numbers exactly:

* BGZF: 158 requests expand one 65,280-byte block; 42 expand two. Thus
  `(158 + 2 × 42) × 65280 / 3276800 = 4.82109375`.
  The displayed 65,536 is a format ceiling, not the actual block length.
* ACEAPEX interactive: all 200 unaligned 16,384-byte requests touch two output
  blocks. The four entropy streams have their own chunk boundaries. Their
  decoded totals are respectively 17,760,256; 933,888; 585,728; 1,089,536 bytes.
  `20369408 / 3276800 = 6.21625`. Equivalently, 271 literal chunks and
  637 FSE chunks give `(271 × 65536 + 637 × 4096) / 3276800 = 6.21625`.
  There are 129 requests with one literal chunk and 71 with two.
  Complete global streams are not decoded or counted.
  `(65536 + 3 × 4096) / 16384 = 4.75` assumes exactly one chunk in each stream;
  actual requests can touch two literal chunks, multiple FSE chunks, or no length
  chunk. Output-block size alone cannot determine the numerator.
* zstd-seekable: these requests each cross two 16,384-byte frames, giving 2.0.
* ACEAPEX dense: the same counter rule gives 83.4318716430664, including its
  1 MiB literal chunks and 32 KiB entropy chunks. No streams are excluded.

These explanations refer to the reproducible trace at benchmark commit
`bc8e5a99fe6878e3a7e0f70cc432cb12e193f9e0`; raw per-query counters are in
[evidence](evidence/stage2-20260910/). New reports derive their totals from their
own counter pass and carry histograms and per-stream totals in results.jsonl.

The earlier uniform N=5000 single-call loops measured zstd-seekable at 14,913.914
ranges/s versus interactive at 5,785.304, about 2.58× faster. This disadvantage
is retained. Lower amplification is consistent with lower latency, but does not
alone prove the cause: decoding cost per byte and API overhead also differ.
The old native four-worker result cannot isolate the effect of grouping; the
current protocol compares loop with batch at one worker each.
