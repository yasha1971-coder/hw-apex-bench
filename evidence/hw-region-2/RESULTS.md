[written by ChatGPT (AI) at the author's request; checked by the author]

# HW-REGION-2 — equivalence Kill before timing

**KILL confirmed by an actual successful `twobitSequence` call, not source inspection alone.** On the exact chr1 source, `storeMasked=1` returns uppercase `N` where the required reference contains lowercase `n`. The writer retains both the N interval and overlapping lowercase mask; its independent structural reader restores the full case-preserved sequence. The unchanged library API fails the mandatory result-equivalence condition.

**P1: NOT TESTED: Kill. P2: NOT TESTED: Kill. P3: NOT TESTED: Kill.** No timing table, p50/p99 ranking, size-forecast verdict, or four-codec performance comparison is produced.

## Actual saved witness

- Sequence: `chr1`, 248956422 bases; exact FASTA 253935557 B, SHA256 `04ee6db2e94ccc4daddc168453189d8c17a01454ba67ac0443a73a0401408ee0`. Case-preserved sequence SHA256 `7f99a160ce64b77f61798ba650f63f0e787e9b8cc463fed905c12e9776c6507d`; preflight counts 181 lowercase `n` over the full chromosome.
- Query, zero-based half-open: **[121749276, 121765660)**, exactly 16384 returned bases. The pointer was non-NULL and the returned string had the required length; the native program exited **2 (KILL)**, rather than **3 (method/input error)**.
- First differing coordinate: **121757468 zero-based / 121757469 one-based**; expected `n` (ASCII 110, hex `6e`), actual `N` (ASCII 78, hex `4e`). Full captured-string mismatch count: **2**; all differences are `n→N`. Expected/actual lowercase-`n` counts in this interval: 2 / 0.
- The first difference lies in **both** writer intervals: N block [121757468, 121757469) and lowercase-mask block [121736570, 121757525). This information is present in the `.2bit` file; it was not lost by normalization or omitted by the writer.
- Reference `.fai`: name `chr1`, length 248956422, byte offset 6, line bases 50, line width 51; the independent plain-FASTA reference reads byte span [124184267, 124200979) and removes only CR/LF. Case is unchanged.

[Complete reference capture](returned/chr1-first-lowercase-n-expected.seq) (SHA256 `881d38a50b3506a700b6febd92e89648ce6f152152054ee2c784fd684d2a980f`) · [Complete actual capture](returned/chr1-first-lowercase-n-actual.seq) (SHA256 `a43dee0ed4a9d10fd7d21d1dd1e8a418168306e937524faf24a71ca741a64227`) · [Native command/stdout](commands/chr1-first-lowercase-n/command.json) · [Admission](admission.json).

## Controls and stop

Two preceding successful nonterminal calls on the invented `TCAGtcagNNnnACTG` fixture returned `TCAGtcag` for [0,8) and `NN` for [8,10), exactly. The known packed bases are `1b1b0093`, with N [8,12) and mask [4,8),[10,12). These are correctness controls, not benchmark observations. The actual chr1 witness is also nonterminal, so a NULL/short EOF result cannot be mislabelled as this case mismatch.

The retained inventory contains exactly **3 correctness-native calls**, including the two positive controls, and **0 performance-native calls / 0 clock calls**. The driver stops after this witness; no fourth query is admitted. Coordinate trace mapping, other-codec archive preparation, A/A, boundary-performance controls, warmup/query timing, open-time measurements, peak-RSS measurements, the main grid and the separate `storeMasked=0` row **were not run**. No reader patch, output postprocessing, case normalization, replacement sequence or Kent/UCSC binary was used.

A generic byte-reader/capacity row does not qualify this required genome-coordinate operation. The four-way coordinate adapter, `codecs/twobit.sh` promotion and a new README performance row are withheld because the mandatory Kill fired. The previous byte-domain measurements remain their own evidence and do not supply missing coordinate timings.

## Source and artifact provenance

First unchanged calibration commit `7fdcbd78b27739cbe1739bf0a8650f395c2afbde`; frozen admission source commit `327090a021ee09754d98f62576ef594cd1f6c1f6`. The original writer is [Apache-2.0](../../LICENSE), [writer.py:1](writer.py#L1); lib2bit remains the clean, unmodified **MIT** source at `58e20daa898a6fc338eae82e5d2ef7108d4fc07f`. The admission verifies the checkout pin and tracked source hashes before/after the build; this renderer rechecks the saved public source/receipt/capture bytes.

The standard little-endian `.2bit` integer variant has magic bytes `4327411a`; packed bases remain MSB-first TCAG=00/01/10/11. This matches the pinned reader on the executor. [Format specification](https://genome.ucsc.edu/FAQ/FAQformat.html#format7) · [Full writer metadata](writer-metadata/chr1.json.gz) · [Fixture writer metadata](writer-metadata/fixture.json.gz). The structural whole-sequence restored SHA256 `7f99a160ce64b77f61798ba650f63f0e787e9b8cc463fed905c12e9776c6507d` equals the preflight sequence SHA256.

- Upstream C source SHA256: `9e41b65b0842bf541518bd785e7ca35c51f3fe5183676cbb62f96e4c96710318`.
- Upstream API header SHA256: `2b39f06cb307f3a9791deadd9ac19578aadf7eba10632fd9edcf53cf6cfd7d49`; MIT license SHA256: `d05362559cd44fa77d1166dd4276aebeab2dcfa0b62b0ab8ffef3b14d684f719`.
- Compiled object SHA256: `929939357bd71381744adc019d7b7264032a9a2359dce62d441e856694e26baf`; static library SHA256: `db880d210b9d298fa73571b8a6f9d50f50f3d24cd46296eaeb8e683d18f5ba8b`.
- Actual correctness executable SHA256: `37088b778681df80d715dd97e7eb228abf9f2bc11c3eada84a0bdf68529782a3`.
- Exact `.2bit` archive: 64895635 B, SHA256 `97089d3613f38df64c04b73651c791c46b5a4e3cce09d2540dee0bc3c5435cce`; writer source SHA256: `044611e3e2cd714c83860d74979e464af85f267172cdd6801fe440d345fb583a`.
- Admission SHA256: `fe94288bc3aa23b325c976d5eee845c39f068b2ca75fabf341b3d0a6d4c92619`; saved-data renderer SHA256: `9465df6e2fc5b68d5b7abc1c8965070042ffa15865f834da85df5132567e0a1e`. 41 retained public artifacts were hash-checked.

This admission ran on `ace-core`, kernel `5.15.0-163-generic`, correctness/build CPU affinity `[15]`; the planned CPU0 / RAM performance experiment was never admitted.

## Foundations

- [HW-REGION-1/RESULTS.md:5](../hw-region-1/RESULTS.md#primary-measured-tradeoff) retains the earlier chr1 **FASTA-byte** comparison on EPYC 4344P; its p50/p99 are not 16384-base coordinate measurements.
- [docs/METHOD_PROGNOZ_ZADANIE.md:31](../../docs/METHOD_PROGNOZ_ZADANIE.md#2-проверка-метода-до-основного-прогона) requires known-answer and correctness gates before the main run; [PROTOCOL.md](PROTOCOL.md) makes this admission stop explicit.
- [lib2bit/2bit.h:90](https://github.com/dpryan79/lib2bit/blob/58e20daa898a6fc338eae82e5d2ef7108d4fc07f/2bit.h#L90) and [2bit.h:116](https://github.com/dpryan79/lib2bit/blob/58e20daa898a6fc338eae82e5d2ef7108d4fc07f/2bit.h#L116) document masked open and malloc-owned sequence retrieval; [2bit.c:126](https://github.com/dpryan79/lib2bit/blob/58e20daa898a6fc338eae82e5d2ef7108d4fc07f/2bit.c#L126) assigns N-block bases, [2bit.c:155](https://github.com/dpryan79/lib2bit/blob/58e20daa898a6fc338eae82e5d2ef7108d4fc07f/2bit.c#L155) excludes `N` from lowercasing, and [2bit.c:187–190](https://github.com/dpryan79/lib2bit/blob/58e20daa898a6fc338eae82e5d2ef7108d4fc07f/2bit.c#L187-L190) applies N masking before soft masking. The actual saved captures above, not the source prediction alone, determine Kill.
- [review/axis3/bgzf_shim.c:50](../../review/axis3/bgzf_shim.c#L50) shows `faidx_fetch_seq64` with inclusive end; the proposed operation would use start+16384−1. That adapter and the other coordinate codecs were not executed after the failed admission.

## Reproduction without another query

From a completed owned admission checkout, the retained-data replay command verifies hashes and returns without invoking lib2bit again:

```bash
taskset -c 15 python3 -B evidence/hw-region-2/reproduce.py
python3 -B evidence/hw-region-2/report.py
```

`reproduce.py` is a build/admission driver on a fresh checkout; its documented hash-only branch applies when the completed `admission.json` and retained artifacts already exist. Generating this report itself only reads saved JSON/gzip/capture files. No external issue/post or merge was performed.
