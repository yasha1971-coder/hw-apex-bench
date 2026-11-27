[written by ChatGPT (AI) at the author's request; checked by the author]

# TB-LVL-0 — density and whole-file speed

**COMPLETE.**

Consumer: Yakov / CROWN-3. Scope: the pinned silesia.ref.tar input (211947520 B, SHA256 a667bac80089b3d04d5496772149e632f0758974b0579d743cd8d6e5e0d63eb2), ace-core AMD EPYC 4344P / CPU0; input and archives in memory during codec timers. MB/s uses 1,000,000 input bytes. These are whole-file compression/decompression speeds within the registered configuration grid, not random-access latency or a universal codec frontier.

Build provenance: static GitHub Actions build of TurboBench `4aa97c8`, with the explicit ACEAPEX `c53f3a04` checkout override. Exact codec pins, compiler/Go versions, flags and native version/registry captures are retained in the [build manifest](build/build.json) and its linked registry evidence.

The actual Go minlz module is **v1.3.1**; the native registry banner says **v1.3.0**. This distinction is retained in [go.mod](build/go.mod) and checked by the independent [audit](audit.json).

50/50 configurations have three selected CLEAN external roundtrips; planned main roundtrips: 150. Each round restores and compares the complete input. Sizes and C/D throughputs are component-wise medians; all comparisons use exact rationals before the display rounding below.

Mapping owner confirmation: **no**. RESOLVED_BY_SOURCE is not an owner confirmation. The literal request remains documented as 60 rows; unsupported fast labels9–18 are not fabricated.

Independent integrity audit: **PASS**. Mathematical analysis status is separate from completion.

## Forecasts from Claude, unchanged

| Forecast | Probability | Verdict |
|---|---:|---|
| P1 | 75% | MISS |
| P2 | 55% | HIT |

P1 is existential over default ACE1–4 at 27–33% compressed size inclusive, against the eleven named zstd/brotli/lzma rows only. P2 requires a compression-axis dominator for each API fast13–18 (source-mapped TB labels3–8), allowing every configuration in the registered grid. Missing required data means NOT TESTED; it is never a forecast miss.

ACE row candidates on the **GLOBAL strict D-front**: `aceapex_fast,1`, `aceapex_fast,2`, `aceapex_fast,3`, `aceapex_fast,5`, `aceapex_fast,6`.

## Configuration medians

| Configuration | Fast API level | Archive B | Archive % of input | C MB/s | D MB/s | Global D-front | Separate C-front | Size range B |
|---|---:|---:|---:|---:|---:|---|---|---|
| aceapex,1 | — | 69391151 | 32.740 | 90.111 | 1693.467 | no | no | constant |
| aceapex,2 | — | 68987186 | 32.549 | 65.110 | 1702.677 | no | no | constant |
| aceapex,3 | — | 66632815 | 31.438 | 208.546 | 1824.476 | no | no | constant |
| aceapex,4 | — | 68626422 | 32.379 | 64.800 | 1706.200 | no | no | constant |
| aceapex_fast,1 | 11 | 130490328 | 61.567 | 1101.650 | 12811.141 | yes | yes | constant |
| aceapex_fast,2 | 12 | 114728299 | 54.131 | 25.493 | 11303.868 | yes | no | constant |
| aceapex_fast,3 | 13 | 95266170 | 44.948 | 24.965 | 10051.099 | yes | no | constant |
| aceapex_fast,4 | 14 | 86234053 | 40.687 | 24.809 | 7528.417 | no | no | constant |
| aceapex_fast,5 | 15 | 117347683 | 55.366 | 1.362 | 12148.078 | yes | no | constant |
| aceapex_fast,6 | 16 | 103552607 | 48.858 | 1.316 | 11195.791 | yes | no | constant |
| aceapex_fast,7 | 17 | 88580614 | 41.794 | 1.317 | 9477.598 | no | no | constant |
| aceapex_fast,8 | 18 | 83113789 | 39.214 | 1.312 | 8602.464 | no | no | constant |
| brotli,11 | — | 49426256 | 23.320 | 0.866 | 437.465 | yes | no | constant |
| brotli,4 | — | 64122989 | 30.254 | 133.104 | 768.742 | no | yes | constant |
| brotli,6 | — | 58470485 | 27.587 | 78.172 | 765.980 | no | yes | constant |
| brotli,9 | — | 56703948 | 26.754 | 18.946 | 803.763 | no | no | constant |
| bsc,0e0 | — | 50266774 | 23.717 | 33.433 | 75.475 | no | yes | constant |
| kanzi,5 | — | 54025965 | 25.490 | 36.807 | 87.112 | no | yes | constant |
| kanzi,6 | — | 49517577 | 23.363 | 28.371 | 50.949 | no | yes | constant |
| kanzi,7 | — | 47308169 | 22.321 | 17.868 | 22.829 | yes | yes | constant |
| kanzi,8 | — | 43250394 | 20.406 | 5.117 | 5.164 | yes | yes | constant |
| lz4,1 | — | 100338342 | 47.341 | 998.838 | 6296.344 | no | yes | constant |
| lz4,12 | — | 77385621 | 36.512 | 19.850 | 5995.856 | no | no | constant |
| lz4,3 | — | 81441820 | 38.425 | 149.245 | 5608.116 | no | no | constant |
| lz4,9 | — | 78002294 | 36.803 | 51.813 | 5813.311 | no | no | constant |
| lzav,1 | — | 83147688 | 39.230 | 805.878 | 4559.286 | no | yes | constant |
| lzav,2 | — | 73216492 | 34.545 | 135.963 | 4551.844 | no | no | constant |
| lzma,9 | — | 48682007 | 22.969 | 4.101 | 162.435 | yes | no | constant |
| minlz,1 | — | 89896508 | 42.415 | 902.907 | 2867.217 | no | yes | constant |
| minlz,3 | — | 71215081 | 33.600 | 77.568 | 2999.413 | no | no | constant |
| minlz,7 | — | 59174101 | 27.919 | 85.910 | 4727.384 | no | yes | constant |
| misa77,0 | — | 94526454 | 44.599 | 408.700 | 9526.588 | no | no | constant |
| misa77,1 | — | 90385428 | 42.645 | 129.033 | 9964.622 | yes | no | constant |
| misa77,2 | — | 85476705 | 40.329 | 99.866 | 9384.853 | no | no | constant |
| misa77,3 | — | 80028646 | 37.759 | 25.490 | 9739.340 | yes | no | constant |
| misa77,4 | — | 68541226 | 32.339 | 4.038 | 8634.707 | yes | no | constant |
| misa77,5 | — | 52566845 | 24.802 | 2.127 | 4787.935 | yes | no | constant |
| zstd,1 | — | 73292638 | 34.581 | 338.161 | 2416.293 | no | yes | constant |
| zstd,15 | — | 57031041 | 26.908 | 14.223 | 2528.483 | no | no | constant |
| zstd,19 | — | 52839872 | 24.931 | 4.598 | 2206.821 | no | no | constant |
| zstd,22 | — | 52288827 | 24.671 | 3.210 | 1959.810 | yes | no | constant |
| zstd,3 | — | 66217592 | 31.242 | 246.272 | 2201.823 | no | yes | constant |
| zstd,9 | — | 59179155 | 27.922 | 94.570 | 2387.872 | no | yes | constant |
| zxc,1 | — | 130896288 | 61.759 | 1144.586 | 9836.065 | no | yes | constant |
| zxc,2 | — | 114152506 | 53.859 | 781.664 | 9446.340 | no | no | constant |
| zxc,3 | — | 98875304 | 46.651 | 325.241 | 7711.108 | no | no | constant |
| zxc,4 | — | 92052403 | 43.432 | 239.744 | 7404.798 | no | no | constant |
| zxc,5 | — | 86544351 | 40.833 | 140.358 | 7177.606 | no | no | constant |
| zxc,6 | — | 76900560 | 36.283 | 18.460 | 6607.255 | no | no | constant |
| zxc,7 | — | 70129881 | 33.088 | 12.150 | 5287.716 | no | no | constant |

D-dominance requires strictly fewer archive bytes AND strictly higher D MB/s; equality in either coordinate is not dominance. C-dominance uses the same strict size rule with C MB/s. Partial-data fronts are provisional over available complete medians.

## Fixed density bands — local D-fronts

| Archive % of input | Available configurations | Local D-front | Also globally on D-front |
|---|---:|---|---|
| [0,5)% | 0 | empty | none |
| [5,10)% | 0 | empty | none |
| [10,15)% | 0 | empty | none |
| [15,20)% | 0 | empty | none |
| [20,25)% | 9 | brotli,11, kanzi,7, kanzi,8, lzma,9, misa77,5, zstd,22 | brotli,11, kanzi,7, kanzi,8, lzma,9, misa77,5, zstd,22 |
| [25,30)% | 6 | brotli,9, kanzi,5, minlz,7, zstd,15 | none |
| [30,35)% | 11 | brotli,4, misa77,4, zstd,3 | misa77,4 |
| [35,40)% | 7 | misa77,3, zxc,6 | misa77,3 |
| [40,45)% | 9 | aceapex_fast,3, aceapex_fast,7, misa77,1, misa77,2 | aceapex_fast,3, misa77,1 |
| [45,50)% | 3 | aceapex_fast,6, zxc,3 | aceapex_fast,6 |
| [50,55)% | 2 | aceapex_fast,2, zxc,2 | aceapex_fast,2 |
| [55,60)% | 1 | aceapex_fast,5 | aceapex_fast,5 |
| [60,65)% | 2 | aceapex_fast,1 | aceapex_fast,1 |
| [65,70)% | 0 | empty | none |
| [70,75)% | 0 | empty | none |
| [75,80)% | 0 | empty | none |
| [80,85)% | 0 | empty | none |
| [85,90)% | 0 | empty | none |
| [90,95)% | 0 | empty | none |
| [95,100]% | 0 | empty | none |
| >100% | 0 | empty | none |

All twenty fixed five-percentage-point bands and the >100% expansion band remain visible. Each local front is recomputed using only its band; a point can be locally on the front and globally dominated.

## Density-nearest ACE for every misa77 level

| misa77 | Nearest ACE | Signed byte gap | Archive gap pp of input | Archive gap % of misa | misa D MB/s | ACE D MB/s | D gap MB/s | D gap % of misa |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| misa77,0 | aceapex_fast,3 | 739716 | +0.349 | +0.783 | 9526.588 | 10051.099 | +524.511 | +5.506 |
| misa77,1 | aceapex_fast,7 | -1804814 | -0.852 | -1.997 | 9964.622 | 9477.598 | -487.025 | -4.888 |
| misa77,2 | aceapex_fast,4 | 757348 | +0.357 | +0.886 | 9384.853 | 7528.417 | -1856.436 | -19.781 |
| misa77,3 | aceapex_fast,8 | 3085143 | +1.456 | +3.855 | 9739.340 | 8602.464 | -1136.876 | -11.673 |
| misa77,4 | aceapex,4 | 85196 | +0.040 | +0.124 | 8634.707 | 1706.200 | -6928.508 | -80.240 |
| misa77,5 | aceapex,3 | 14065970 | +6.637 | +26.758 | 4787.935 | 1824.476 | -2963.459 | -61.894 |

Selection minimizes absolute archive-byte distance, then prefers greater D, then smaller archive, then canonical identifier. The same ACE point may be selected for several misa77 levels. Positive archive gaps mean ACE is larger; positive D gaps mean ACE decompresses faster. Partial selections use available complete medians only and remain provisional.

Exact medians, all dominance witnesses and retained native references are in [analysis.json](analysis.json). The independent [audit](audit.json), [calibration](CALIBRATION.md) and recorded [mapping amendment](GRID_AMENDMENT.md) govern final acceptance. No previous row or clean slow run is excluded because of its speed.

## Retention

1 of 151 started logical units used more than one actual attempt; 152 actual attempts and 1 LOADED attempts are retained. The method-only known answer is excluded from all main medians.

| Logical unit | Round | Attempt | Excluded status | Native started |
|---|---:|---:|---|---|
| aceapex_fast,5 | 3 | 1 | LOADED | yes |
