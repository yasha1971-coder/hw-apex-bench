# HW-GIFT-1e results

Both full-input primary predictions HIT: the severe old-core slowdown is reproducible in this controlled native harness, and the modern pair differs by less than 1.2×. With identical seekable writer/decoder/header/bridge across the tags, this supports a core-version effect in this harness. The bounded prefix search below qualifies its transition/range; no global first-fast or original-Pijul application claim is made.

Independent saved-data audit: [audit/final.json](audit/final.json) (SHA-256 `39e70bf7eab9091cf37ee368c5f7c7d97ed10d1bd4fb37659337e0b63e6f9760`). All predicates use integer nanoseconds before display rounding. Compression times below are median/minimum of five CLEAN rounds; there is no decode timing. P1 uses an inclusive 5× boundary, P2 a strict symmetric <1.2× boundary, and Kill a strict <2× boundary.

| Gate | Preregistered condition | Verdict | Full-input fact |
| --- | --- | --- | --- |
| P1 | v1.5.4 FULL/L10/G256: median(B) ≥5×median(A) | HIT | A=2090112729 ns; B=65207374880 ns; B/A=31.198018; symmetric factor=31.198018 |
| P2 | v1.5.7 same FULL primary: max(medians)/min(medians) <1.2 | HIT | A=2087706392 ns; B=1916454131 ns; B/A=0.917971; symmetric factor=1.089359 |
| Kill | v1.5.4 FULL primary: median(B) <2×median(A) | NOT TRIGGERED | Proceeding does not imply P1 HIT |

## Version / scope / configuration grid

A has the PR #3544 assert and source-size hint setter; B literally omits the setter. Full enwik8 is 100,000,000 bytes; prefix is exactly its first 16,777,216 bytes. No full/prefix observations or A/A and A/B observations are pooled. Archive sizes include the complete seek table with checksums. Missing Kill cells contain no fabricated zero/timing/size.

| Core | Input scope | L | G B | A archive B | B archive B | A median ms | A min ms | B median ms | B min ms | B/A median | Symmetric factor | Status/source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v1.5.4 | full 100000000 B | 10 | 256 | 75980696 | 75963298 | 2090.112729 | 2084.311314 | 65207.374880 | 65163.936949 | 31.198018 | 31.198018 | [COMPLETE](cells/v1.5.4/full-L10-G256.json) |
| v1.5.4 | full 100000000 B | 10 | 1024 | 56879265 | 56920923 | 1482.281088 | 1477.512456 | 17503.997994 | 17482.461985 | 11.808825 | 11.808825 | [COMPLETE](cells/v1.5.4/full-L10-G1024.json) |
| v1.5.4 | full 100000000 B | 3 | 256 | 76167350 | 75917324 | 1210.095148 | 1205.648880 | 1043.583260 | 1038.622899 | 0.862398 | 1.159558 | [COMPLETE](cells/v1.5.4/full-L3-G256.json) |
| v1.5.4 | first 16777216 B | 10 | 256 | 12817014 | 12814908 | 352.017105 | 350.597944 | 10948.207939 | 10945.628649 | 31.101352 | 31.101352 | [COMPLETE](cells/v1.5.4/prefix-L10-G256.json) |
| v1.5.4 | first 16777216 B | 10 | 1024 | 9620827 | 9630843 | 249.916466 | 249.097451 | 2941.587021 | 2936.189271 | 11.770281 | 11.770281 | [COMPLETE](cells/v1.5.4/prefix-L10-G1024.json) |
| v1.5.4 | first 16777216 B | 3 | 256 | 12850104 | 12807363 | 203.825000 | 202.969054 | 174.320316 | 173.458408 | 0.855245 | 1.169256 | [COMPLETE](cells/v1.5.4/prefix-L3-G256.json) |
| v1.5.7 | full 100000000 B | 10 | 256 | 75980696 | 75963303 | 2087.706392 | 2082.430757 | 1916.454131 | 1880.850399 | 0.917971 | 1.089359 | [COMPLETE](cells/v1.5.7/full-L10-G256.json) |
| v1.5.7 | full 100000000 B | 10 | 1024 | 56879265 | 56920957 | 1489.064911 | 1484.982491 | 1264.499714 | 1223.737192 | 0.849190 | 1.177592 | [COMPLETE](cells/v1.5.7/full-L10-G1024.json) |
| v1.5.7 | full 100000000 B | 3 | 256 | 76166346 | 75917182 | 1038.358845 | 1035.689885 | 1089.011380 | 1085.036707 | 1.048781 | 1.048781 | [COMPLETE](cells/v1.5.7/full-L3-G256.json) |
| v1.5.7 | first 16777216 B | 10 | 256 | 12817014 | 12814909 | 350.636502 | 349.585519 | 327.163451 | 325.112593 | 0.933056 | 1.071747 | [COMPLETE](cells/v1.5.7/prefix-L10-G256.json) |
| v1.5.7 | first 16777216 B | 10 | 1024 | 9620827 | 9630855 | 249.771662 | 248.319696 | 216.315504 | 210.935375 | 0.866053 | 1.154664 | [COMPLETE](cells/v1.5.7/prefix-L10-G1024.json) |
| v1.5.7 | first 16777216 B | 3 | 256 | 12849991 | 12807349 | 174.923317 | 174.157299 | 183.020705 | 181.669970 | 1.046291 | 1.046291 | [COMPLETE](cells/v1.5.7/prefix-L3-G256.json) |

All five integer compression observations, complete archive SHA values, input SHA and raw-result references appear in [TABLE.csv](TABLE.csv).

| Core | Scope | L | G B | Variant | Complete archive B | Complete archive SHA-256 | Source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v1.5.4 | full | 10 | 256 | A | 75980696 | b6b159c48d26b511d692a1214b0e6365a11ba1be8c7607ffa45511698e9703fc | [saved cell](cells/v1.5.4/full-L10-G256.json) |
| v1.5.4 | full | 10 | 256 | B | 75963298 | fc214e6ae294c40899a145210f79ec2d1ad768923cf08e66cd577916794c9f88 | [saved cell](cells/v1.5.4/full-L10-G256.json) |
| v1.5.4 | full | 10 | 1024 | A | 56879265 | bfbbbeb485d9cf6e013d66b0f771c0df4f55c0fd394d5af9390be64434e61f2f | [saved cell](cells/v1.5.4/full-L10-G1024.json) |
| v1.5.4 | full | 10 | 1024 | B | 56920923 | ee2ef6a8fcc39c65ca76edcb287ac39a0ed10647e85146c41281546338ccd320 | [saved cell](cells/v1.5.4/full-L10-G1024.json) |
| v1.5.4 | full | 3 | 256 | A | 76167350 | 1027db761e200d1da94c7a95c4e75fccc5952fbdff5ba8c51798556a862cffd2 | [saved cell](cells/v1.5.4/full-L3-G256.json) |
| v1.5.4 | full | 3 | 256 | B | 75917324 | 96f01dcf78ae294a9804a74269affc0b9d4bd1d7fd886822aa9366b0d9e76a13 | [saved cell](cells/v1.5.4/full-L3-G256.json) |
| v1.5.4 | prefix | 10 | 256 | A | 12817014 | 993664b1fad7ea4fea55977dc1d060463b9184c6fde31e1f01ca391d59784784 | [saved cell](cells/v1.5.4/prefix-L10-G256.json) |
| v1.5.4 | prefix | 10 | 256 | B | 12814908 | 8a619bfd34763d522004b27a7691c0c7493c0c01307f5a5a52166b60427df1ae | [saved cell](cells/v1.5.4/prefix-L10-G256.json) |
| v1.5.4 | prefix | 10 | 1024 | A | 9620827 | eeed7bfb01b77022c77797cb153edc8ec1ab81eb12e1921fadd0dbb5f3285bb4 | [saved cell](cells/v1.5.4/prefix-L10-G1024.json) |
| v1.5.4 | prefix | 10 | 1024 | B | 9630843 | d2950b9b205a41a2c69744cbe2a5004cd22ff0db0fb0051d74f0d9be75948d8b | [saved cell](cells/v1.5.4/prefix-L10-G1024.json) |
| v1.5.4 | prefix | 3 | 256 | A | 12850104 | b8e1171c8d975f801ba18577625b00118a1463e3798e1240fd9043db1b281bc8 | [saved cell](cells/v1.5.4/prefix-L3-G256.json) |
| v1.5.4 | prefix | 3 | 256 | B | 12807363 | ced3b220357ab9b99b0fbd547aeec5566a338363e6e6d9f3cae556be1de64d8d | [saved cell](cells/v1.5.4/prefix-L3-G256.json) |
| v1.5.7 | full | 10 | 256 | A | 75980696 | b6b159c48d26b511d692a1214b0e6365a11ba1be8c7607ffa45511698e9703fc | [saved cell](cells/v1.5.7/full-L10-G256.json) |
| v1.5.7 | full | 10 | 256 | B | 75963303 | 598e91b8f76b6fe470357936fdbed294f88d81a4f2b0ace264900d30fbe940e3 | [saved cell](cells/v1.5.7/full-L10-G256.json) |
| v1.5.7 | full | 10 | 1024 | A | 56879265 | bfbbbeb485d9cf6e013d66b0f771c0df4f55c0fd394d5af9390be64434e61f2f | [saved cell](cells/v1.5.7/full-L10-G1024.json) |
| v1.5.7 | full | 10 | 1024 | B | 56920957 | 6c5130f17c0fd64fe204446fbeee21fc2b23322eb2203ac3a03b1b1faccc89a6 | [saved cell](cells/v1.5.7/full-L10-G1024.json) |
| v1.5.7 | full | 3 | 256 | A | 76166346 | 05ee8bf74c2ca09896d61d71ff3fbec91c29e00d935966c05bb0055a471f6268 | [saved cell](cells/v1.5.7/full-L3-G256.json) |
| v1.5.7 | full | 3 | 256 | B | 75917182 | 4f46bc04e6eeffbe03be0d2a99df0d979ad721aeedfb618875e0a8b7176a6c33 | [saved cell](cells/v1.5.7/full-L3-G256.json) |
| v1.5.7 | prefix | 10 | 256 | A | 12817014 | 993664b1fad7ea4fea55977dc1d060463b9184c6fde31e1f01ca391d59784784 | [saved cell](cells/v1.5.7/prefix-L10-G256.json) |
| v1.5.7 | prefix | 10 | 256 | B | 12814909 | c5b12476ca37bcf02a0cef3326d5cf89105e632316b763eb4e931116d746de1a | [saved cell](cells/v1.5.7/prefix-L10-G256.json) |
| v1.5.7 | prefix | 10 | 1024 | A | 9620827 | eeed7bfb01b77022c77797cb153edc8ec1ab81eb12e1921fadd0dbb5f3285bb4 | [saved cell](cells/v1.5.7/prefix-L10-G1024.json) |
| v1.5.7 | prefix | 10 | 1024 | B | 9630855 | 1bbfd272252ce2d2c971f284b6a08914195efd5e9e70bb66ea643860f6c9dd2e | [saved cell](cells/v1.5.7/prefix-L10-G1024.json) |
| v1.5.7 | prefix | 3 | 256 | A | 12849991 | 063c8cf4fb4bfe0daadc7b6c568ea6e341430893c65c491d0757017766cf7e6e | [saved cell](cells/v1.5.7/prefix-L3-G256.json) |
| v1.5.7 | prefix | 3 | 256 | B | 12807349 | f575381cfbd98a0e9cd5b23d59da2a1d2f7043bd81853e4737a213f468f2a2bf | [saved cell](cells/v1.5.7/prefix-L3-G256.json) |

## Method and retained attempts

| Core | A/A first median ns | A/A second median ns | Admission |
| --- | --- | --- | --- |
| v1.5.4 | 2091170858 | 2094120785 | [PASS: strict <5%](method-v1.5.4.json) |
| v1.5.7 | 2094915764 | 2092272503 | [PASS: strict <5%](method-v1.5.7.json) |

Each method gate is five fresh full/L10/G256 A/A rounds and uses `20*abs(second-first)<first`; it is never retried for elapsed-time instability. Untimed positive/changed-input/corrupt-magic checks, runtime CLI/library versions, known saved 1d prefix bytes, all frame checksums and legitimate terminal empty-frame checks passed before main use. See [method-controls.json](method-controls.json).

| Core | Stage | M logical rounds | N retaken rounds | All attempts | LOADED attempts | Max start load1 | Max end load1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v1.5.4 | AA method | 5 | 0 | 5 | 0 | 0.49 | 0.53 |
| v1.5.4 | A/B grid | 30 | 0 | 30 | 0 | 1.22 | 1.22 |
| v1.5.7 | AA method | 5 | 0 | 5 | 0 | 0.70 | 0.75 |
| v1.5.7 | A/B grid | 30 | 0 | 30 | 0 | 0.92 | 0.92 |

All CLEAN and LOADED requests/results/receipts/stdout/stderr are retained. Only successful rounds with load1>2.0 at either boundary are mechanically retaken, immediately, at most three attempts; first CLEAN wins. ERROR is fatal. These maxima include loaded attempts. Other-core /proc/stat deltas are observations, not exclusion rules.

## Conditional core search

Search result: **ADJACENT TRANSITION**; 4/12 total core builds, including the two endpoints. The prefix16MiB search is distinct from the full-input primary gates; its fresh endpoint bracket/classifier has its own protocol and audit.

[search/result.json](search/result.json), [search/audit.json](search/audit.json). Global first-fast claim: **false**.

| New forecast | Exact tested pair | Verdict | Observed classifications |
| --- | --- | --- | --- |
| Source-informed first-parent pair e2965edd -> 9420bce8 changes from SLOW to FAST | e2965edd107acd0123294e23848cdc00af906468 → 9420bce8a491e21821c4b372f837bf4bd47e5870 | HIT | SLOW → FAST |

Observed adjacent first-parent boundary: `e2965edd107acd0123294e23848cdc00af906468` → `9420bce8a491e21821c4b372f837bf4bd47e5870` (Add init once memory (#3528) (#3529)). This is a measured transition on the chosen path, not proof of the earliest fast commit anywhere in the DAG or attribution of a merge to one side-branch patch.

| Core commit | Title | Classification | Candidate median ns | Candidate min ns | Reference median ns | Reference min ns | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 945f27758c0fd67b636103a38dbf050266c6b90a | Merge pull request #3487 from facebook/dev | SLOW | 10951488609 | 10935109364 | 325867241 | 322993343 | [saved pairs](search/endpoints.json) |
| f8745da6ff1ad1e7bab384bd1f9d742439278e99 | Merge pull request #4298 from facebook/dev | FAST | 325867241 | 322993343 | 325867241 | 322993343 | [saved pairs](search/endpoints.json) |
| e2965edd107acd0123294e23848cdc00af906468 | Bump github/codeql-action from 2.2.5 to 2.2.6 (#3549) | SLOW | 5683351415 | 5680251333 | 328850076 | 326790271 | [saved pairs](search/pairs/e2965edd107acd0123294e23848cdc00af906468.json) |
| 9420bce8a491e21821c4b372f837bf4bd47e5870 | Add init once memory (#3528) (#3529) | FAST | 319755040 | 310873054 | 327526753 | 317441669 | [saved pairs](search/pairs/9420bce8a491e21821c4b372f837bf4bd47e5870.json) |

The two tag endpoint rows share one fresh five-pair stage; the modern endpoint row reports that stage's actual R observations, not an extra R/R timing.

Search rounds (deduplicating shared endpoint evidence): 0 retaken / 15 logical, 15 total attempts, 0 LOADED. Every raw attempt is retained.

Source-ancestry qualification: [SEARCH_AMENDMENT.md](SEARCH_AMENDMENT.md) and [the saved pre-build amendment](search/source-branch-amendment.json) (SHA-256 `f942f452e7303802dff43fd39b50cdfa62852ed615b3250875b765fb28bac686`) retain the original ancestry-gate rejection before candidate reservation, build or timing; [the rejected plan](search/plans/plan-001.json) is preserved. All 22 recorded sampling/native-interface/classifier function AST fingerprints are unchanged, and the original tag endpoint observations were retained without retiming. The measured adjacent edge is on a source side branch, **outside the v1.5.4-to-v1.5.7 tag ancestry path**; its fast child is an ancestor of v1.5.7. It is a measured first-parent transition on that branch, not a direct tag-path bisect boundary or a globally first-fast commit.

Source change at the measured S1 SLOW→FAST edge: the [parent reset code](https://github.com/meta/zstd/blob/e2965edd107acd0123294e23848cdc00af906468/lib/compress/zstd_compress.c#L1969) uses `memset` to reset the row-tag table; the child introduces init-once reuse in [compression reset handling](https://github.com/meta/zstd/blob/9420bce8a491e21821c4b372f837bf4bd47e5870/lib/compress/zstd_compress.c#L1958) and the [workspace allocator](https://github.com/meta/zstd/blob/9420bce8a491e21821c4b372f837bf4bd47e5870/lib/compress/zstd_cwksp.h#L402). This is commit-level evidence for the init-once change. The complete commit also changes workspace layout, so the experiment does not isolate a `memset`-only ablation or establish a unique instruction-level cause.

## Saved HW-GIFT-1d hint trade-offs

These are separate saved v1.5.7 observations. 1d B calls the setter with zero; 1e B omits the call. Exact prefix archive equality is a known answer, not permission to pool their timings. Here hint time A/B means median(hint)/median(zero setter). Hint archive ΔB% is `100*(hint bytes − zero-hint bytes)/zero-hint bytes`: negative means hinting is smaller. Ranges use exact fractions and name their extreme points; the scoped summaries do not hide the other points.

| Saved 1d scope | Hint time A/B range | Time extrema point IDs | Hint archive Δ vs B % range | Size extrema point IDs |
| --- | --- | --- | --- | --- |
| L3, all 14 corpus/frame cells (tiny frames use prefixes) | 0.936049 … 1.077575 | silesia.tar/L3/G256/prefix16MiB … silesia.tar/L3/G16384/full | -0.833693 … 1.631556 | silesia.tar/L3/G16384/full … enwik8/L3/G262144/full |
| L10, full input at 4–256 KiB (8 cells) | 1.258908 … 2.446875 | silesia.tar/L10/G65536/full … silesia.tar/L10/G16384/full | -1.933367 … -0.778179 | silesia.tar/L10/G16384/full … enwik8/L10/G262144/full |
| L19, full input at 4–256 KiB (8 cells) | 0.929149 … 0.974179 | enwik8/L19/G4096/full … silesia.tar/L19/G262144/full | -0.000048 … 0.446963 | enwik8/L19/G262144/full … silesia.tar/L19/G65536/full |

All 42 baseline 1d points follow, including tiny prefixes, the 512 KiB points outside the scoped 4–256 KiB summaries, opposite-direction outcomes, and exact byte-sized differences:

| 1d point / input scope | Hint A B | Zero-hint B B | A−B bytes | A size ΔB % | Hint A median ms | Zero-hint B median ms | Hint time A/B | Source | Cell JSON SHA-256 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| enwik8/L3/G256/prefix16MiB | 12849991 | 12807349 | 42642 | 0.3329 | 174.900929 | 183.923736 | 0.950943 | [saved cell](../hw-gift-1d/cells/train/L3-G256.json) | 8e8612189f7b4cb504888e71b47c69d09e25481aedb0b610432ef694eae54272 |
| enwik8/L3/G1024/prefix16MiB | 9801995 | 9737756 | 64239 | 0.6597 | 85.692390 | 86.767629 | 0.987608 | [saved cell](../hw-gift-1d/cells/train/L3-G1024.json) | 898e6461f34a64feffd423693281393f4917d3da25f9f3205d12dbab2b8f1c57 |
| enwik8/L3/G4096/full | 48077060 | 48231128 | -154068 | -0.3194 | 367.309183 | 359.254295 | 1.022421 | [saved cell](../hw-gift-1d/cells/train/L3-G4096.json) | 9143ccd02839763c1f3d2b04eab5f897effc44053b2d32e7874da3d8c8446e8a |
| enwik8/L3/G16384/full | 42939459 | 42970678 | -31219 | -0.0727 | 336.354835 | 315.373382 | 1.066529 | [saved cell](../hw-gift-1d/cells/train/L3-G16384.json) | 28ae4f7aabe1c47085fa2823e3ac38d78fe8d3cc8a473b484ffda19640b25dfe |
| enwik8/L3/G65536/full | 39654522 | 39573564 | 80958 | 0.2046 | 292.657616 | 302.796015 | 0.966517 | [saved cell](../hw-gift-1d/cells/train/L3-G65536.json) | acb3b61d18dfd33e8db49eba80718fe7d40895724f99b90386cc7940771b4241 |
| enwik8/L3/G262144/full | 37935213 | 37326215 | 608998 | 1.6316 | 336.936578 | 317.769241 | 1.060318 | [saved cell](../hw-gift-1d/cells/train/L3-G262144.json) | 30e09bfad097817ac9204a0a555aac148acaa9f805433b55b6ac3e39df121ecc |
| enwik8/L3/G524288/full | 36535040 | 36535040 | 0 | 0.0000 | 328.475793 | 331.148228 | 0.991930 | [saved cell](../hw-gift-1d/cells/train/L3-G524288.json) | 1e3150e4c0e5e76ad6d46b85606c8c41eb700fd5bd1bdd36b99e8c82582af401 |
| enwik8/L10/G256/prefix16MiB | 12817014 | 12814909 | 2105 | 0.0164 | 348.459318 | 329.174338 | 1.058586 | [saved cell](../hw-gift-1d/cells/train/L10-G256.json) | 704ff44b2c926c35d8f31832fbbb0d2d9ffc190a0b8aafa933670b699fae5036 |
| enwik8/L10/G1024/prefix16MiB | 9620827 | 9630855 | -10028 | -0.1041 | 248.089811 | 217.956686 | 1.138253 | [saved cell](../hw-gift-1d/cells/train/L10-G1024.json) | 2614e70602399e2f1867df35b6f2e094d8207393c02bb51bdf5f4a191aa3a209 |
| enwik8/L10/G4096/full | 46939136 | 47536272 | -597136 | -1.2562 | 1492.455954 | 1060.225350 | 1.407678 | [saved cell](../hw-gift-1d/cells/train/L10-G4096.json) | c37c00861f473cd3c9f851ed2f9983394ad51f1cb32e153e19a92db7466a28ac |
| enwik8/L10/G16384/full | 41173170 | 41805127 | -631957 | -1.5117 | 1929.562149 | 1079.150722 | 1.788038 | [saved cell](../hw-gift-1d/cells/train/L10-G16384.json) | ade45aa6da94fb4474ea6874b1886a4cece7dd0444934b2d7e53669a65c6b2af |
| enwik8/L10/G65536/full | 37439722 | 37894875 | -455153 | -1.2011 | 1454.589849 | 1142.172862 | 1.273529 | [saved cell](../hw-gift-1d/cells/train/L10-G65536.json) | df66d7aabf6409627434b0b5e74c180c242e5926b350c73abc0c2da5da6cf4d8 |
| enwik8/L10/G262144/full | 34792953 | 35065828 | -272875 | -0.7782 | 1755.165764 | 1292.530803 | 1.357930 | [saved cell](../hw-gift-1d/cells/train/L10-G262144.json) | 36c3138e5831fe7ca201bb10fd0e7b8ca71f3a25a30772576c03689401477f7b |
| enwik8/L10/G524288/full | 33918396 | 33900850 | 17546 | 0.0518 | 1318.298132 | 1365.947843 | 0.965116 | [saved cell](../hw-gift-1d/cells/train/L10-G524288.json) | 805bf14d5ff5c4bf530578e4ec2f39f43fd7bdbb9cbdfdf5ac38ef89c8b60f53 |
| enwik8/L19/G256/prefix16MiB | 12567880 | 12567957 | -77 | -0.0006 | 1048.466669 | 1087.544653 | 0.964068 | [saved cell](../hw-gift-1d/cells/train/L19-G256.json) | 58f2e233239ebbbff0afb26909c36b9a3fe4cbca82004159fcc94ed39a94b104 |
| enwik8/L19/G1024/prefix16MiB | 9564908 | 9515232 | 49676 | 0.5221 | 1112.956685 | 1129.746167 | 0.985139 | [saved cell](../hw-gift-1d/cells/train/L19-G1024.json) | 5ef8f3fe4b25987dea5244723d1d8e3a34ab53f95d0673918cc94533ff7c8c05 |
| enwik8/L19/G4096/full | 46300878 | 46213272 | 87606 | 0.1896 | 8585.556422 | 9240.232650 | 0.929149 | [saved cell](../hw-gift-1d/cells/train/L19-G4096.json) | b77470f6f3004f8fb3ad3e46e5b1a027f5e8dc1eb0dc7193f607fa33d9910e31 |
| enwik8/L19/G16384/full | 40284083 | 40260131 | 23952 | 0.0595 | 11005.877850 | 11603.370238 | 0.948507 | [saved cell](../hw-gift-1d/cells/train/L19-G16384.json) | 2285a96896364110ee0d1a071e791261fc64331b8d15dd86d687d2af969abb90 |
| enwik8/L19/G65536/full | 36265760 | 36244232 | 21528 | 0.0594 | 13661.684045 | 14582.498987 | 0.936855 | [saved cell](../hw-gift-1d/cells/train/L19-G65536.json) | 11674f3c82182096a65ff47b4768dd9d6dc72cca3574810e13b61cea9d2ebf63 |
| enwik8/L19/G262144/full | 33299917 | 33299933 | -16 | -0.0000 | 12799.382737 | 13291.176377 | 0.962998 | [saved cell](../hw-gift-1d/cells/train/L19-G262144.json) | 1180714abb54b488a782926ac072ad38826c4c544922d23056dfc43cf725013b |
| enwik8/L19/G524288/full | 32045310 | 32045310 | 0 | 0.0000 | 11845.642466 | 12464.959365 | 0.950315 | [saved cell](../hw-gift-1d/cells/train/L19-G524288.json) | fc15cbfb0d9ad8aa17eac31fa4ef384a74ed40bccea9d9a6df1a175132c39641 |
| silesia.tar/L3/G256/prefix16MiB | 13543167 | 13494669 | 48498 | 0.3594 | 152.235661 | 162.636344 | 0.936049 | [saved cell](../hw-gift-1d/cells/holdout/L3-G256.json) | 1f9bfffb0d9e92a13e5be37f3be90ded03425d4096e55e3f3d6971837d74bead |
| silesia.tar/L3/G1024/prefix16MiB | 10960465 | 10907252 | 53213 | 0.4879 | 77.448504 | 79.498843 | 0.974209 | [saved cell](../hw-gift-1d/cells/holdout/L3-G1024.json) | 446cb11d0e5809049cc867fb56a94a626e34de9982306b1c277634fd06fc477e |
| silesia.tar/L3/G4096/full | 90686087 | 91371397 | -685310 | -0.7500 | 627.275605 | 625.453745 | 1.002913 | [saved cell](../hw-gift-1d/cells/holdout/L3-G4096.json) | 08370c88105092956b3dced962e5ae27d3e6ed4737620df65cf65e19d3e68ed8 |
| silesia.tar/L3/G16384/full | 79417442 | 80085106 | -667664 | -0.8337 | 525.263252 | 487.449191 | 1.077575 | [saved cell](../hw-gift-1d/cells/holdout/L3-G16384.json) | a119e0b09a453847e05dc04b1619fce49d5c0aaec73edf4b8c2bd9312ffdf40f |
| silesia.tar/L3/G65536/full | 73587959 | 73434013 | 153946 | 0.2096 | 450.809223 | 454.618534 | 0.991621 | [saved cell](../hw-gift-1d/cells/holdout/L3-G65536.json) | 6ea855294b2fdc27e41ed76d57e217acbe3917b7c234a4b0bf1a2c4068d182b2 |
| silesia.tar/L3/G262144/full | 69675977 | 69577856 | 98121 | 0.1410 | 507.487202 | 475.688778 | 1.066847 | [saved cell](../hw-gift-1d/cells/holdout/L3-G262144.json) | 937c1656e55e04c6486a2fe3f9fedfafcba91973dc19d6110167707b147f958e |
| silesia.tar/L3/G524288/full | 68319089 | 68319089 | 0 | 0.0000 | 490.868668 | 490.272428 | 1.001216 | [saved cell](../hw-gift-1d/cells/holdout/L3-G524288.json) | 9b9ac0e6bea4672fbc0fc639311627d191b0c8e369370c9bdafde0148a5fb710 |
| silesia.tar/L10/G256/prefix16MiB | 13490114 | 13478489 | 11625 | 0.0862 | 314.469392 | 294.550160 | 1.067626 | [saved cell](../hw-gift-1d/cells/holdout/L10-G256.json) | a4266f236e101c7a1cf0e85a5229b33ef1abd8e2a3cbcdbedd0e402f39b56f93 |
| silesia.tar/L10/G1024/prefix16MiB | 10806905 | 10801358 | 5547 | 0.0514 | 225.176191 | 201.473357 | 1.117647 | [saved cell](../hw-gift-1d/cells/holdout/L10-G1024.json) | 6205198f79ee97228a14f788c46f86063c9660de3cf4335b97a497c35c2c1a52 |
| silesia.tar/L10/G4096/full | 88166012 | 89629142 | -1463130 | -1.6324 | 3469.832610 | 2019.780363 | 1.717926 | [saved cell](../hw-gift-1d/cells/holdout/L10-G4096.json) | fef4b5cb2185b1e56b591977c445363237827cd0474df555a7b580425870292c |
| silesia.tar/L10/G16384/full | 75915143 | 77411797 | -1496654 | -1.9334 | 4767.534185 | 1948.417608 | 2.446875 | [saved cell](../hw-gift-1d/cells/holdout/L10-G16384.json) | 5cf256cae1b4fccfcf4fb69bd2c5efb7be8e468bdfe94ba2027bb50913c48266 |
| silesia.tar/L10/G65536/full | 68781102 | 69857833 | -1076731 | -1.5413 | 2538.524452 | 2016.450076 | 1.258908 | [saved cell](../hw-gift-1d/cells/holdout/L10-G65536.json) | 73f32d713b92e1a00a4d3cf96613952cd1e93be664470ffd3f048b6e532e9fda |
| silesia.tar/L10/G262144/full | 64420366 | 65128600 | -708234 | -1.0874 | 2891.450461 | 2183.175849 | 1.324424 | [saved cell](../hw-gift-1d/cells/holdout/L10-G262144.json) | 44ca17a1f6d5f123f08c254a32881f16398baf0140874cb411468c9715b094f2 |
| silesia.tar/L10/G524288/full | 63318044 | 63293962 | 24082 | 0.0380 | 2168.078908 | 2253.312965 | 0.962174 | [saved cell](../hw-gift-1d/cells/holdout/L10-G524288.json) | e65709bca04c1c3b03cbf233c562344e365bee5881285d6b97d4d2058a4de605 |
| silesia.tar/L19/G256/prefix16MiB | 13294733 | 13294512 | 221 | 0.0017 | 947.342063 | 980.477723 | 0.966205 | [saved cell](../hw-gift-1d/cells/holdout/L19-G256.json) | 114e75b779d398da4daa62708d635259216e3c0dfacaa4af821c37ccb3a1c28e |
| silesia.tar/L19/G1024/prefix16MiB | 10739861 | 10690110 | 49751 | 0.4654 | 1053.128293 | 1070.635815 | 0.983648 | [saved cell](../hw-gift-1d/cells/holdout/L19-G1024.json) | 53581e48db4112161d95b0a797c0ce5e6b1e713ad2dc8cc8da2d3434583d60fd |
| silesia.tar/L19/G4096/full | 84759819 | 84512891 | 246928 | 0.2922 | 24318.335721 | 25256.393370 | 0.962859 | [saved cell](../hw-gift-1d/cells/holdout/L19-G4096.json) | efd2385e533230a1eaafe08ab457ebba036ce1930a691f48d916ef3124515a14 |
| silesia.tar/L19/G16384/full | 72371450 | 72212619 | 158831 | 0.2199 | 30182.712111 | 31271.758710 | 0.965175 | [saved cell](../hw-gift-1d/cells/holdout/L19-G16384.json) | 875769422ef5e5174c6ab4933aea54b015bdf235e973c1191be66331e5274c84 |
| silesia.tar/L19/G65536/full | 65101245 | 64811561 | 289684 | 0.4470 | 35311.973532 | 37238.797463 | 0.948258 | [saved cell](../hw-gift-1d/cells/holdout/L19-G65536.json) | 034fabf2c821b0aa6bd69e5ca3aa63289f1a1954bc0903e897529ec237060b99 |
| silesia.tar/L19/G262144/full | 60374554 | 60374507 | 47 | 0.0001 | 31353.755730 | 32184.794880 | 0.974179 | [saved cell](../hw-gift-1d/cells/holdout/L19-G262144.json) | ef875857517665553600203d0f9b75ba728b8f4326fcedfc75af551abfab3bc3 |
| silesia.tar/L19/G524288/full | 58655317 | 58655317 | 0 | 0.0000 | 28187.313706 | 29018.795456 | 0.971347 | [saved cell](../hw-gift-1d/cells/holdout/L19-G524288.json) | 626a4174b4329ed614c40b4e97da1daff735bd87dd400169ab383f647de9ceb1 |

Saved 1d audit: [../hw-gift-1d/audit/final.json](../hw-gift-1d/audit/final.json); SHA-256 `c1a263b73198bb4c10ff2247a2a3ef0e9c74ffb2eaec53c8fbdd65c741579e11`. Each displayed cell SHA binds its five original raw compression results. No 1d archive was regenerated.

## Scope and source controls

ace-core, AMD EPYC 4344P, Linux, pinned CPU 0, schedutil; one thread, input/output resident in RAM. Both cores were built with the same compiler and `-O3 -fPIC -fno-lto`; shared libraries use `-Bsymbolic` and RTLD_LOCAL. Each core supplies its own headers/static library. The v1.5.4 seekable writer/decoder/header and the retained resident bridge are frozen across cores; A adds only the two PR lines. The untimed checksum/terminal-frame validation helpers are identical across libraries and outside encode intervals. Fresh contexts and prefaulted outer buffers precede timers; codec first-use allocation remains inside. No universal-machine, process-RSS or original-application performance claim follows from this native harness.

The final independent native verifier performed zero encodings and read no clocks; 30 actual archive paths and 22 distinct archives were checked, with 3537317 frame decodes. See [audit/native.json](audit/native.json).

Builds, annotated tag/source/binary/header hashes, linked version numbers/strings and `zstd -V`: [setup.json](setup.json), [SOURCE_PATHS.md](SOURCE_PATHS.md). The 2023 M1 35 s→2.5 s observations are attributed to the PR description; the later reproducer confirms L10/256-byte settings. Later core optimizations are source context, not a substitute for these measured gates or an unmeasured ablation.

Draft PR #94 remains draft. [ZSTD_ISSUE_DRAFT.md](ZSTD_ISSUE_DRAFT.md) is unsent; no upstream issue/comment or merge is performed.
