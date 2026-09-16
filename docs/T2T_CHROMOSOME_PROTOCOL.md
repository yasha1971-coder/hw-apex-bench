# T2T chromosome/sequence granularity protocol

Status: recorded on 2026-09-16; **not executed**. No codec modifications,
new measurements or replacement of previous results are authorized by this
checkpoint. The next run requires a separate execution stage.

## Question and baseline

Cover the complete T2T assembly, rather than a sample, while comparing each
chromosome/FASTA sequence with its own single-block baseline. This is distinct
from both the existing 2 MiB window curves and one block spanning an entire
multi-sequence FASTA file. Never label the aggregate as whole-file c(g).

For sequence i, retain full archive/index sizes B_i(g) and B_i(one block).
Report per-sequence ratio loss and the aggregate:

`C_sequences(g) = 1 - sum_i B_i(one block) / sum_i B_i(g)`.

Use sums of bytes, not the arithmetic mean of per-sequence losses. Keep negative
values and nonmonotonic points. No cross-chromosome matches exist in this baseline.

## Why the original whole-file baseline is unavailable

Pinned zstd-seekable 1.5.7 defines its maximum decompressed frame size as
`0x40000000U` (1 GiB). Its initializer rejects larger requests. A diagnostic
using the retained 2 MiB chr2 HOR input accepted 1,073,741,824 and rejected
1,073,741,825 with exit11 / `Unsupported frame parameter`. This tests parameter
acceptance, not a compression run on a 1 GiB input.

The pinned T2T FASTA is 3,156,259,565 bytes. Thus this encoder cannot supply
its whole-file single-frame baseline. This is an implementation restriction;
do not call it the seekable format's theoretical size limit. Do not patch the
encoder, silently clamp its frame size or substitute ordinary zstd.

Sources: [pinned public header](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/contrib/seekable_format/zstd_seekable.h),
[initializer](https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/contrib/seekable_format/zstdseek_compress.c).

## Frozen input and representation

- Use the already registered NCBI GCA_009914755.4 T2T-CHM13v2.0 source,
  expanded MD5 `cd1e52ce400c027ed0b7ab4b9d613f5a`, 3,156,259,565 bytes.
- Verify source bytes before extraction. Preserve every sequence record in source
  order, including sex chromosomes and any mitochondrial/other records present.
  Freeze accession, record count, lengths and hashes before encoding; no silent exclusions.
- Extract bases only, preserving case and every sequence symbol; remove FASTA
  headers and line terminators. Do not join records, filter ambiguity symbols,
  uppercase bases or drop difficult regions. Reconcile extracted lengths with
  the assembly report, retaining explicit explanations for any discrepancy.
- This covers all sequence content, not byte-exact storage of the original FASTA.
  Window comparisons use the same base-only representation. Any full-FASTA
  operational benchmark must be reported separately.

## Configuration

Use the existing pinned builds, not latest releases:

- ACEAPEX `4915321bf118e564ef3883e58927992c7f9d8dc3`, default level2,
  eight requested encoder threads; change only ACEAPEX_BS. Other codec overrides
  unset, automatic literal policy retained. Record actual literal chunking and
  source-size-dependent hash configuration; chromosome and window settings may differ.
- zstd-seekable `f8745da6ff1ad1e7bab384bd1f9d742439278e99`, level3, one
  encoder thread, same reference encoder on both sides; complete seek table,
  checksums and any empty terminal frame remain counted and separately audited.
- Granularities: 4, 16, 64, 256 KiB and 1 MiB. Baseline: one LZ block/nonempty
  frame spanning the complete individual sequence. Parse actual geometry.
- BGZF stays in absolute-density comparisons using pinned htslib1.19 /
  libdeflate1.19, level6, eight threads; count .gzi. Strict c(g) remains
  `n/a — no comparable single-parameter baseline`. Do not invent a large BGZF block.

## Execution gates

1. Review and accept window-local curve PR43 independently; its data stay frozen.
2. Freeze the complete input manifest and check every sequence against the
   reference encoder's frame limit. If any is unsupported, stop before claiming
   complete coverage; no subdivision hidden under the same baseline name.
3. Audit ACE integer bounds, peak memory and exact restoration on an initial
   bounded sequence before starting the full matrix. CPU/memory limits and disk
   budget must be recorded; no unsafe full-genome allocation probe.
4. Run untimed density measurements sequentially by sequence, with explicit
   commands, source/binary versions, hashes and byte-exact restores. Checkpoint
   each completed sequence. New evidence directory only; no historical reruns.
5. Publish complete per-sequence and aggregate tables with the baseline scope
   in their titles. Audit and review before merge. No latency/throughput claims.

## Interpretation and external context

This experiment answers whether granularity sensitivity persists across the
complete assembly under a per-sequence baseline. Comparing its magnitude with
2 MiB HOR/control curves is descriptive, not an isolated causal test of HOR:
input size, composition, baseline span and automatic encoder choices also change.
Uniform length-matched windows are a separate possible study, not a substitute
for complete assembly coverage or an automatically authorized extra experiment.

Related work exists: [Hecate (2026)](https://arxiv.org/abs/2603.15390) describes
indexed blocks, random-access slicing and CHM13 benchmarks preserving original
FASTA representation; [AGC (2023)](https://doi.org/10.1093/bioinformatics/btad097)
addresses assembled-genome collections with fast access. No first-ever claim is
established by the current literature check, and their published ratios must not
be pasted into our table as if measured with our protocol.

Historical435, pilot90, sweep300, local c(g), release tag and DOI remain unchanged.
