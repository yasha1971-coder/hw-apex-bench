# Five-point curve: audit and claim boundary

The full candidate table is in [CG_CURVE_RESULTS.md](../RESULTS/CG_CURVE_RESULTS.md).
Draft PR #14 has not been merged. The public homepage remains the recovered
stage-5 snapshot from PR #13.

## Evidence checked

- Workflow `34543023595` succeeded at benchmark source
  `d84f38af3b26d830fbc1cc654174f2bd673178ab`.
- Original artifact ID `10178051601`; its local SHA-256 matched GitHub's digest:
  `7b26a032aa21b7c39c599dc833494cfd7b186c4c26278d259faa6322f2d4566d`.
- All previous 420 JSONL rows are retained as an identical byte prefix.
- 15 grid entries: 13 supported points plus two unsupported BGZF sizes.
- CI reports 15 successful complete byte-identical restores (13 points and
  two whole-input baselines), plus 2,600 timed byte-verified regional responses.
- Independently recomputed: all 13 raw sample SHA-256 values, identical query
  traces, nearest-rank p50/p99, archive+index accounting, ratios and c(g).
- The recovered measurement JSONL is unchanged. The original reports differed
  on replay only in JSON metadata key order. The renderer now sorts those keys;
  a regression test first reproduced the failure and then passed. All 18 sweep
  tests pass. The candidate reports now regenerate exactly from the JSONL.

Detailed receipt: `evidence/cg-curve-20260910/receipt.json`.
Raw ZIP is retained privately for the owner as `cabench-cg-curve-evidence.zip`.
Archive files themselves are not contained in that ZIP; full-restore evidence
comes from the successful CI run, not a second local decompression.

The nine-axis recovery rechecked this ZIP with `harness/audit_curve.py`, including
the exact 420-row prefix and all 2,600 raw region samples. Generated reports now
put each unavailable reason in its cell; the original 435 JSONL records and this
receipt's measurement hashes are unchanged. The combined report remains a draft
candidate until review and merge; no new codec measurement was executed.

## Findings, with limits

CLAIM: At g=16 KiB, the default ACEAPEX configuration loses 1.630135% of ratio
against its own whole-input baseline; zstd-seekable loses 6.569397% against its
own same-container baseline.
SCOPE: chr1, this one AMD EPYC 7763 runner, the exact dependency revisions and
settings in the table. Complete archive/index bytes count.
STATUS: measured; c(g) independently recomputed from the recorded file sizes.
EVIDENCE: `results.jsonl`, group `cg-five-point-v1`, both compression commands and
restore receipts in every numeric pair.
FALSIFIER: nonidentical restored bytes, differing fixed settings within a pair,
or archive accounting inconsistent with the recorded complete files.

CLAIM: The measured default ACEAPEX region path is slow: p50 61.93–63.31 ms over
the five sizes; at 16 KiB it is 62.379022 ms versus zstd's 0.069890 ms and BGZF's
0.070392 ms. The cost of independence in ratio and the speed of regional access
are separate measured properties.
STATUS: measured. All these queries passed byte equality; this is not a timer
around a separate command-line process.
SCOPE: default ACEAPEX, not the previous interactive/dense configurations. The
same machine and trace were used for all points in this new curve.

CLAIM: The tested default code selects coarse literal partitions when LIT_CHUNK
is absent; lit_range expands intersecting quarters of the literal stream.
STATUS: code-proven path selection. The proportion of the observed latency
caused by that work is still a hypothesis, not a profiled measurement.
EVIDENCE: `src/aceapex_main.cpp` at
`ee5a37eda18b81c1300a1ee44a7e06b6be925bd2`: `lit_chunk_size()` returns zero with no
environment setting, `lit_compress()` selects the legacy layout, and
`lit_range()` uses `(orig_sz+3)/4` for that layout. The local reviewed source
SHA-256 `a1f5208e8381b6480380c3e1af3bf335693feb544bcc5b926989683b3c2338b1`
matches the runner's compiled-source provenance. FSE_CHUNK defaults to 512 KiB.
FALSIFIER for the causal hypothesis: explicit work counters or profiling show
that the coarse literal expansion does not dominate the measured latency.

The nearly constant default latency is therefore not sufficient evidence of
cheap arbitrary access. Do not attach the interactive profile's old latency to
this default profile's new c(g).

zstd's 1 MiB point has c(g) = -0.509942%: its blocked archive is smaller than
its measured whole-input baseline. Preserve the negative sign. The zstd curve
is nonmonotone. ACEAPEX's 1 MiB archive is also less dense than zstd's at that
point. No monotonicity or universal superiority is established.

## Next experiment after review

Keep this default curve intact. A separate curve can hold explicit literal/FSE
chunk sizes fixed across all g values and the whole-input baseline, preserving
the exact codec SHA and all other settings. Measure its own ratios and latency
and expose the actual entropy units touched. That would test whether small
independence cost and fast access coexist in one configuration. It must not be
presented as a correction that erases this default result.

Paper 6 may cite the matched density observation with its scope and losses.
The claim that a single configuration combines the favorable density curve and
fast regional access remains open pending the separate controlled experiment.
