[written by ChatGPT (AI) at the author's request; checked by the author]

# HW-REGION-2: equivalence admission before any timing

The exact owner-authored CALIBRATION was the sole file in first commit
`7fdcbd78b27739cbe1739bf0a8650f395c2afbde`, based on merged main
`e5d6158a99afa9a62c91723c26ace083ac0ac125`. Its forecasts and Kill are unchanged.
No latency, open-time or memory benchmark may begin until sequence equivalence
passes. A mismatch stops the experiment; do not replace it with a case-folded
comparison, fix the reader, or show a timing table.

Consumer and decision: Yakov needs a same-function genome-coordinate comparison
against `.2bit` before publishing genome-access claims. The required result is
the exact case-preserved 16,384-base string, rather than a FASTA byte range.
HW-REGION-1 is historical input/provenance, not a new coordinate timing result.

## Read foundations and live state

- [HW-REGION-1 results](../hw-region-1/RESULTS.md), [calibration](../hw-region-1/CALIBRATION.md),
  [protocol](../hw-region-1/PROTOCOL.md), [source paths](../hw-region-1/SOURCE_PATHS.md)
  and [setup](../hw-region-1/setup.json) retain the original host, byte-domain
  semantics, dependency pins, offsets and correctness proofs.
- [Project method](../../docs/METHOD_PROGNOZ_ZADANIE.md) and
  [working agreement](../../docs/AGENTS.md) require first-commit calibration,
  same-function comparisons, correctness before timing and retained attempts.
- [Capacity-only 2-bit script](../../review/axis3/two_bit_capacity.py) is not a
  `.2bit` coordinate reader and folds case; it is not an equivalence reference.
  [Existing faidx shim](../../review/axis3/bgzf_shim.c) provides the required
  inclusive-end HTSlib API; its generic byte-read counterpart from REGION-1 is
  not substituted for faidx.
- The live lib2bit pin is
  `58e20daa898a6fc338eae82e5d2ef7108d4fc07f` (2026-11-22), MIT licensed.
  Its [API header](https://github.com/dpryan79/lib2bit/blob/58e20daa898a6fc338eae82e5d2ef7108d4fc07f/2bit.h)
  defines the malloc-owned sequence result and `storeMasked=1`.
  Its [source](https://github.com/dpryan79/lib2bit/blob/58e20daa898a6fc338eae82e5d2ef7108d4fc07f/2bit.c#L107-L190)
  applies N blocks, then soft-mask blocks, explicitly excluding `N` from case
  conversion. Source inspection predicts a lowercase-`n` incompatibility;
  an actual successful API call must confirm it before declaring Kill.

## Untimed admission procedure

1. Read/hash every retained input: exact chr1 FASTA MD5
   `9465e0f0df6e2c6eb39729c39cee5465`, SHA256
   `04ee6db2e94ccc4daddc168453189d8c17a01454ba67ac0443a73a0401408ee0`,
   plus all thirty frozen case-preserved T2T windows. Preserve source bytes.
   Strip only FASTA line terminators/header when defining sequence coordinates.
   The completed untimed [preflight](input-preflight.json) records 248,956,422
   chr1 bases, including 181 lowercase `n`; the first is coordinate 121,757,468
   (zero-based). No unsupported alphabet symbol is present.
2. Use the original project [Apache-2.0](../../LICENSE) implementation in
   [writer.py](writer.py), not Kent binaries or code. Encode N/n intervals and
   lowercase intervals independently, including their overlap. The `.2bit`
   format supports this information. Retain `seq.bin`, `.fai`, `.2bit`, metadata
   and hashes under the new owned `.work/hw-region-2` directory.
   An independent structural reader must restore the entire exact case-preserved
   sequence and match its SHA256. Known packed bits for `TCAGtcagNNnnACTG` are
   `1b1b0093`, N interval `[8,12)`, mask intervals `[4,8)` and `[10,12)`.
3. Compile an unmodified clean lib2bit checkout at the exact pin, with all build
   outputs outside its source tree. Record source/header/license/compiler,
   commands and binary SHA256. Build on CPU15 without a benchmark lock; no
   clocks, worker timing API, benchmark, or performance-derived selection exists
   in this admission path.
4. The `.2bit` integers use the valid little-endian format variant, matching the
   pinned reader on ace-core. Packed bases remain most-significant pair first
   (`TCAG` = `00 01 10 11`). The
   [format specification](https://genome.ucsc.edu/FAQ/FAQformat.html#format7)
   is the only format reference; this is not a copy of a Kent implementation.
5. First check successful nonterminal positive calls on the invented fixture:
   `[0,8)` returns `TCAGtcag`, `[8,10)` returns `NN`, using `storeMasked=1`.
   A NULL pointer or wrong length is a method error, not evidence of `n→N`.
6. Make one actual chr1 query through the unchanged API with length 16,384 and
   start `first_lowercase_n - 8192`. The reference comes independently from the
   original plain FASTA through its `.fai` line geometry, removing only CR/LF;
   no case conversion or postprocessing of the library result is allowed.
   Save both complete strings and the first mismatch coordinate/bytes. This is
   an untimed equivalence witness, not a replacement performance trace.
7. Stop immediately if the strings differ. Do not proceed to coordinate trace
   mapping, four-codec archive preparation, masked=0 measurements, A/A, boundary
   timing, open-time/RSS or the main grid. Report P1–P3 as NOT TESTED: Kill and
   publish no timing table or README performance row.

The witness is deliberately nonterminal: the pinned reader also rejects reads
ending exactly at the last packed byte (`twobitRead`, source line 23). This
prevents that separate EOF error from obscuring a successful lowercase-case
comparison; no padding, extra chromosome or source patch is introduced.

## Conditional main experiment

If equivalence passes, a complete measurement protocol must be committed before
any timers: chr1 and the same thirty windows, ACEAPEX 2.6.5, zstd 1.5.7, HTSlib
1.24/faidx and this lib2bit pin; g=16 KiB for the framed FASTA formats, R=16,384
bases, persistent handles and shared mapped coordinates. Newline removal belongs
inside ACE/zstd query timers. Required indexes count toward stored bytes.
The mask-disabled row is case-folded, separately labelled and excluded from the
equivalent four-way comparison. It is not permission to normalize the main row.
OVH shared flock, CPU0, the REGION-1 admission/retry rules, twelve warmups,
1000 requests, A/A <5%, actual-boundary negative controls, separate open time and
peak RSS remain mandatory. None may run after an equivalence Kill.

No codec optimization, closed literal/FSE/DCtx tuning, upstream post or merge is
part of this task. Retain all evidence on branch `hw-region-2`, in a draft PR
with the exact ChatGPT signature.
