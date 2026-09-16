# T2T frozen-window granularity sweep — 2026-09-16

300 complete archives restored byte-exactly. All 60 archives at 16 KiB
reproduce the earlier pilot byte-for-byte (SHA-256). No timing claims.

The same thirty 2 MiB sequences are used at every size: ten annotated HOR
windows, ten telomere-context windows and ten annotation-complement controls.
Ratio is total input bytes / total stored bytes, not a mean of window ratios.
BGZF is the fixed verified baseline from the previous pilot, including .gzi.

## centromeric_HOR

| Block / frame | ACEAPEX ratio | zstd-seekable ratio | BGZF ratio (fixed) | ACE size vs BGZF | zstd size vs BGZF | ACE / zstd wins vs BGZF |
|---|---:|---:|---:|---:|---:|---:|
| 4 KiB | 14.717 | 9.202 | 41.617 | +182.8% | +352.2% | 0/10 / 0/10 |
| 16 KiB | 31.932 | 24.044 | 41.617 | +30.3% | +73.1% | 0/10 / 0/10 |
| 64 KiB | 54.721 | 48.315 | 41.617 | -23.9% | -13.9% | 10/10 / 9/10 |
| 256 KiB | 70.613 | 63.380 | 41.617 | -41.1% | -34.3% | 10/10 / 10/10 |
| 1024 KiB | 78.740 | 71.485 | 41.617 | -47.1% | -41.8% | 10/10 / 10/10 |

## telomere_context

| Block / frame | ACEAPEX ratio | zstd-seekable ratio | BGZF ratio (fixed) | ACE size vs BGZF | zstd size vs BGZF | ACE / zstd wins vs BGZF |
|---|---:|---:|---:|---:|---:|---:|
| 4 KiB | 3.601 | 2.865 | 3.417 | -5.1% | +19.3% | 10/10 / 0/10 |
| 16 KiB | 3.772 | 2.989 | 3.417 | -9.4% | +14.3% | 10/10 / 0/10 |
| 64 KiB | 3.822 | 3.145 | 3.417 | -10.6% | +8.7% | 10/10 / 0/10 |
| 256 KiB | 3.838 | 3.136 | 3.417 | -11.0% | +9.0% | 10/10 / 0/10 |
| 1024 KiB | 3.845 | 3.296 | 3.417 | -11.1% | +3.7% | 10/10 / 1/10 |

## annotation_complement

| Block / frame | ACEAPEX ratio | zstd-seekable ratio | BGZF ratio (fixed) | ACE size vs BGZF | zstd size vs BGZF | ACE / zstd wins vs BGZF |
|---|---:|---:|---:|---:|---:|---:|
| 4 KiB | 3.491 | 2.749 | 3.258 | -6.7% | +18.5% | 10/10 / 0/10 |
| 16 KiB | 3.643 | 2.859 | 3.258 | -10.6% | +13.9% | 10/10 / 0/10 |
| 64 KiB | 3.684 | 3.004 | 3.258 | -11.6% | +8.5% | 10/10 / 0/10 |
| 256 KiB | 3.695 | 2.991 | 3.258 | -11.8% | +8.9% | 10/10 / 0/10 |
| 1024 KiB | 3.697 | 3.155 | 3.258 | -11.9% | +3.3% | 10/10 / 0/10 |

## Exact ACEAPEX size accounting

The format stores 68 header bytes plus 64 bytes per block. All remain
in the reported ratio. “Streams” below means all four compressed streams;
it is not a metadata-free payload comparable to another codec.

| Block | Header + table / window | HOR metadata share | Control metadata share |
|---|---:|---:|---:|
| 4 KiB | 32,836 B | 23.04% | 5.47% |
| 16 KiB | 8,260 B | 12.58% | 1.43% |
| 64 KiB | 2,116 B | 5.52% | 0.37% |
| 256 KiB | 580 B | 1.95% | 0.10% |
| 1024 KiB | 196 B | 0.74% | 0.03% |

Across the ten HOR archives, moving from 16 KiB to 1 MiB saves 390,412 bytes:
80,640 bytes (20.7%) from header/block-table accounting and
309,772 bytes (79.3%) from smaller compressed streams.

At 16 KiB, even removing the entire header/table counterfactually leaves
ACE streams 13.9% larger than the complete BGZF baseline.
This is a diagnostic accounting exercise, not a valid stripped-archive ratio.

Metadata has a larger archive share on highly compressible inputs, not on
poorly compressible inputs. Its input-byte fraction is fixed at a given block size.

## Interpretation and limits

At comparable approximately 64 KiB granularity, ACEAPEX has a 31.5%
higher aggregate ratio than BGZF (54.721 vs 41.617), equivalent to a
23.9% smaller complete stored representation, and wins on all ten HOR windows.
ACEAPEX also has a higher aggregate ratio than zstd-seekable at each of
the five tested granularities. These are density results on selected windows.

The [BGZF specification](https://samtools.github.io/hts-specs/SAMv1.pdf)
limits both compressed blocks and uncompressed contents to 65,536 bytes;
it does not require fixed 64 KiB uncompressed blocks. Inspection of all
30 actual baseline archives found 32 blocks of 65,280 bytes, an 8,192-byte
tail and an empty EOF block per archive. ACE uses 65,536-byte blocks
(0.392% larger). Thus granularity is comparable, not exactly matched.
See the [block audit](../../evidence/t2t-granularity-20260916/bgzf-block-audit.json).

The earlier +30.3% archive-size loss remains true for ACE at 16 KiB
against native BGZF; it is not a codec-intrinsic centromere weakness.
Do not replace that configuration-specific result with the 64 KiB result,
or infer that centromeric weaknesses do not exist under other settings.

Both codecs gain much more density on these HOR windows than on controls
when blocks grow. Both exceed the fixed BGZF aggregate ratio at 64 KiB.
This supports sensitivity to block/frame granularity shared by these two
implementations on this selected input, not a universal law of seekable formats.

The gap is not explained solely by the ACE block table. Larger blocks change
match opportunities and compressed-stream statistics as well as overhead.
This experiment cannot assign the stream improvement solely to long-distance
HOR matches. A repeat of a few thousand bases is not inherently excluded by
a 16 KiB block; match distance and block boundaries matter.

No region latency, amplification or throughput was measured. Higher density
with larger blocks does not establish a better random-access trade-off.
This is not c(g): no single-block 2 MiB baseline is included.

These are ten selected long-HOR autosomes, not a genome-wide estimate.
Terminal windows contain mostly adjacent context, not pure telomeric repeats.
Controls are not GC matched. See the [original sampling limitations](T2T_REGIONS_20260916.md).

## Configuration and reproduction

- ACEAPEX `4915321bf118e564ef3883e58927992c7f9d8dc3`, default level 2,
  eight encoder threads, only ACEAPEX_BS changes. No profile or explicit
  LIT_CHUNK/FSE_CHUNK/MIN_MATCH; automatic policy retained. Linked zstd 1.5.7.
- zstd-seekable `f8745da6ff1ad1e7bab384bd1f9d742439278e99`, level 3,
  one encoder thread. Only frame size changes. Complete seek table and
  the reference encoder’s trailing empty frame remain included at every size.
- BGZF: unchanged htslib 1.19 / libdeflate 1.19, level 6, eight threads,
  native block ceiling 65,280 bytes, .gzi included; not a swept parameter.

Each result retains commands, input/archive/log hashes, block/frame counts
and archive decomposition. Build the original pinned dependencies, recover
the frozen inputs, then use the [sweep instructions](../../review/t2t_regions/README.md).

[300 rows](../../evidence/t2t-granularity-20260916/results.jsonl) ·
[provenance](../../evidence/t2t-granularity-20260916/provenance.json) ·
[summary](../../evidence/t2t-granularity-20260916/summary.json) ·
[archive receipt](../../evidence/t2t-granularity-20260916/archive-bundle.json).

The original 435 records, earlier 90 pilot records, DOI and release tag are unchanged.
Generated by review/t2t_regions/summarize_sweep.py.
