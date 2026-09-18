# T2T window-local c_window(g) — 2026-09-16

A completed local curve, not a whole-T2T curve. Sixty new one-whole-window
baselines complete the retained 300 measurements without rerunning them.
Each baseline restores byte-exactly; a second encoding reproduced all 60 hashes.

[c_window(g), distinct from historical c_file(g)](../CG_SCOPES.md), is ratio loss relative to one block covering the same 2 MiB window:
`(ratio_whole - ratio_g) / ratio_whole = 1 - bytes_whole / bytes_g`.
The aggregate uses sums of stored bytes, not mean per-window c(g).
Its baseline is ten separate one-window archives, never a concatenated 20 MiB file.

## aceapex

| g | HOR c_window(g) | Control c_window(g) | Terminal-context c_window(g) | HOR > control, paired |
|---|---:|---:|---:|---:|
| 4 KiB | 81.825% | 5.604% | 6.384% | 10/10 |
| 16 KiB | 60.565% | 1.492% | 1.949% | 10/10 |
| 64 KiB | 32.422% | 0.379% | 0.645% | 10/10 |
| 256 KiB | 12.796% | 0.106% | 0.230% | 10/10 |
| 1024 KiB | 2.760% | 0.032% | 0.036% | 10/10 |

## zstd-seekable

| g | HOR c_window(g) | Control c_window(g) | Terminal-context c_window(g) | HOR > control, paired |
|---|---:|---:|---:|---:|
| 4 KiB | 87.248% | 13.085% | 13.147% | 10/10 |
| 16 KiB | 66.681% | 9.597% | 9.397% | 10/10 |
| 64 KiB | 33.046% | 5.043% | 4.669% | 10/10 |
| 256 KiB | 12.169% | 5.432% | 4.950% | 9/10 |
| 1024 KiB | 0.937% | 0.259% | 0.093% | 8/10 |

BGZF c(g): **n/a — no comparable single-parameter whole-window baseline**.
Its verified fixed-block density comparison remains in the
[granularity report](T2T_GRANULARITY_20260916.md); no synthetic BGZF baseline is used.

BGZF blocks are 65,280 bytes; ACE at 64 KiB uses 65,536 bytes (0.392% larger).
The comparison is close in granularity, not identical.

## What this establishes

See [HWB-001 (measured) and HWB-002 (mechanism unproven)](../CLAIM_LEDGER.md).

Relative to its own one-window baseline, each tested codec loses substantially
more density on these selected HOR windows at small blocks than on controls.
This is a granularity penalty, not an absolute density weakness: ACEAPEX can
beat BGZF around 64 KiB while still paying a large penalty relative to its own baseline.
The local c(g) is not a latency, amplification or throughput measurement.

The retained paired differences and per-window ranges matter: ten selected
long-HOR autosomes do not establish a genome-wide effect size or significance.
Negative individual values and nonmonotonicity are not clipped or smoothed.

## Baseline audit

Same binaries, input hashes, level and requested encoder threads as the sweep.
ACEAPEX4915321: one 2 MiB LZ block, default level2, eight requested threads.
LIT_CHUNK/FSE_CHUNK/MIN_MATCH remain unset. Every parsed ACE archive has
64 KiB literal chunks on both sides; FSE defaults to512KiB in the pinned source.
DNA/zstd decisions within chunks remain automatic. Only requested LZ block size changes.
One LZ block is not one entropy chunk, and actual parallel work changes with block count.
zstd1.5.7 reference seekable encoder: level3, one thread; one nonempty frame
plus one terminal empty frame and seek table. Complete stored files are counted.
Frame-size-induced internal parameter changes remain part of the operational curve.

## Whole-T2T comparison: next gate, not a completed claim

No matched whole-T2T curve exists in the retained evidence. The historical
c(g) curve uses hg38 chr1 and ACEAPEXee5a37e, not T2T and4915321.
Owner-provided whole-T2T CLI ratio is stream-only, not a complete-file c(g) baseline.

Do not overlay these as one measured curve. Before a whole-T2T run:

1. Fix representation: these windows contain bases only, case preserved;
   FASTA headers/wrapping and cross-chromosome concatenation require explicit handling.
2. Freeze the same codec commits, level, overrides, thread policy and five granularities.
3. Verify whole-input single-block support and resource bounds before a full run.
   ACE uses a32-bit block-size header and source-size-dependent hash sizing;
   inspect offset/length limits and memory, not just environment acceptance.
4. Retain complete-file sizes and byte-exact restores; do not substitute CLI stream ratios.
5. Treat genome-vs-window differences as scale/composition effects as well as locality.
   A size-matched representative-window stratum is cleaner for region attribution.

Recommended next experiment: preregister a uniformly sampled, length-matched
T2T window stratum (including repeats rather than annotation-excluded controls),
then compare local curves. Keep full-FASTA operational c(g) separate.
No additional windows or whole-genome measurements were run in this stage.

## Evidence

[Baselines](../../evidence/t2t-window-cg-20260916/baselines.jsonl) ·
[300 derived points](../../evidence/t2t-window-cg-20260916/derived.jsonl) ·
[Summary and paired differences](../../evidence/t2t-window-cg-20260916/summary.json) ·
[Audit](../../evidence/t2t-window-cg-20260916/audit.json) ·
[Reproduction](../../review/t2t_regions/README.md).

The historical435 records, prior pilot/sweep, DOI and tag remain unchanged.
Generated and verified with review/t2t_regions/window_cg.py.
