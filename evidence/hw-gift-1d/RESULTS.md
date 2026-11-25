# HW-GIFT-1d results

The experimental rule **hint only when maxFrameSize < 1024 bytes** met the compression-time budget in 42/42 cells. Its actual archives were larger than the original in **14/42 cells**. The initial premise of a boundary below which the hint is needed for speed and above which it only costs bytes is not confirmed by this grid.

Complete saved-data report; the independent final audit passed. Predictions are evaluated before rounding, using integer nanoseconds and bytes. A PASS audit establishes completeness/integrity; each forecast has its own HIT/MISS below.

Protocol: [CALIBRATION.md](CALIBRATION.md), [PROTOCOL.md](PROTOCOL.md), [SOURCE_PATHS.md](SOURCE_PATHS.md), [audit/final.json](audit/final.json), [TABLE.csv](TABLE.csv).

A = original `hint=maxFrameSize`; B = `hint=0`; C = the frozen conditional implementation. Archive bytes include the complete seek table with per-frame checksums in every variant. Compression figures are median/minimum of five CLEAN observations; decode is one full-decode observation per variant/cell/phase, with no decode ranking claim. Ratios are ratios of compression medians.

| Forecast | Literal preregistered prediction | Verdict | Observed fact |
| --- | --- | --- | --- |
| P1 | At enwik8 first 16 MiB, L10/G256 B compression ≥3× A | MISS | A=348459318 ns; B=329174338 ns; B/A=0.944656 |
| P2 | Both corpora, L3/L10, G≥65536: 0.90≤B/A≤1.10 and B bytes≤A bytes | MISS | 4/12 violating cells |
| P3 | Some X in 1–64 KiB: C/A≤1.10 everywhere; at G≥X C bytes≤1.0005×B; actual policy byte identity | HIT | X=1024 B; 0/42 violating cells |
| Kill | L3/G65536 B/A≥1.10 on either corpus means size/speed trade-off | NOT TRIGGERED | enwik8: B/A=1.034643; silesia.tar: B/A=1.008450 |

P2 uses an inclusive ±10% band. Kill uses an inclusive 1.10 boundary, so both predicates can be true at exactly 1.10. P3 compares its size allowance with B, not with original A. A P3 HIT does not promise a universal free win or that hinting is necessary below X.

All P2 violations:

| Corpus | L | G B | Median ratio | Failed conditions |
| --- | --- | --- | --- | --- |
| enwik8 | 10 | 65536 | 0.785220 | speed, size |
| enwik8 | 10 | 262144 | 0.736415 | speed, size |
| silesia.tar | 10 | 65536 | 0.794339 | speed, size |
| silesia.tar | 10 | 262144 | 0.755045 | speed, size |

All P3 violations: none.

## Complete baseline A/B grid

The following 42 rows preserve the training enwik8 A/B phase and holdout silesia A/B phase. G=256 and 1024 B use only the first 16 MiB; all larger G use the full corpus. These different source scopes do not form a size-independent curve.

| Corpus | L | G B | Input scope | A bytes | B bytes | B size ΔA % | A median ms | A min ms | B median ms | B min ms | B/A median | A decode once ms | B decode once ms | Saved source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| enwik8 | 3 | 256 | 16 MiB prefix (16777216 B) | 12849991 | 12807349 | -0.3318 | 174.900929 | 174.162674 | 183.923736 | 183.188577 | 1.051588 | 78.200227 | 78.247215 | [raw refs](cells/train/L3-G256.json) |
| enwik8 | 3 | 1024 | 16 MiB prefix (16777216 B) | 9801995 | 9737756 | -0.6554 | 85.692390 | 85.372791 | 86.767629 | 86.388787 | 1.012548 | 31.672511 | 28.488276 | [raw refs](cells/train/L3-G1024.json) |
| enwik8 | 3 | 4096 | full (100000000 B) | 48077060 | 48231128 | 0.3205 | 367.309183 | 366.245787 | 359.254295 | 353.569450 | 0.978071 | 116.493408 | 110.797095 | [raw refs](cells/train/L3-G4096.json) |
| enwik8 | 3 | 16384 | full (100000000 B) | 42939459 | 42970678 | 0.0727 | 336.354835 | 333.788977 | 315.373382 | 308.825948 | 0.937621 | 92.990613 | 84.670977 | [raw refs](cells/train/L3-G16384.json) |
| enwik8 | 3 | 65536 | full (100000000 B) | 39654522 | 39573564 | -0.2042 | 292.657616 | 287.739825 | 302.796015 | 289.659388 | 1.034643 | 73.889431 | 72.479785 | [raw refs](cells/train/L3-G65536.json) |
| enwik8 | 3 | 262144 | full (100000000 B) | 37935213 | 37326215 | -1.6054 | 336.936578 | 321.237968 | 317.769241 | 301.240653 | 0.943113 | 79.139977 | 71.202668 | [raw refs](cells/train/L3-G262144.json) |
| enwik8 | 3 | 524288 | full (100000000 B) | 36535040 | 36535040 | 0.0000 | 328.475793 | 309.385946 | 331.148228 | 314.258324 | 1.008136 | 70.412316 | 70.179759 | [raw refs](cells/train/L3-G524288.json) |
| enwik8 | 10 | 256 | 16 MiB prefix (16777216 B) | 12817014 | 12814909 | -0.0164 | 348.459318 | 347.599045 | 329.174338 | 325.966224 | 0.944656 | 79.605414 | 79.066553 | [raw refs](cells/train/L10-G256.json) |
| enwik8 | 10 | 1024 | 16 MiB prefix (16777216 B) | 9620827 | 9630855 | 0.1042 | 248.089811 | 247.518458 | 217.956686 | 216.078809 | 0.878539 | 31.248799 | 30.471992 | [raw refs](cells/train/L10-G1024.json) |
| enwik8 | 10 | 4096 | full (100000000 B) | 46939136 | 47536272 | 1.2721 | 1492.455954 | 1491.639622 | 1060.225350 | 1057.354273 | 0.710390 | 113.473172 | 109.877482 | [raw refs](cells/train/L10-G4096.json) |
| enwik8 | 10 | 16384 | full (100000000 B) | 41173170 | 41805127 | 1.5349 | 1929.562149 | 1925.077755 | 1079.150722 | 1061.907006 | 0.559272 | 91.431939 | 83.237125 | [raw refs](cells/train/L10-G16384.json) |
| enwik8 | 10 | 65536 | full (100000000 B) | 37439722 | 37894875 | 1.2157 | 1454.589849 | 1452.225790 | 1142.172862 | 1131.664487 | 0.785220 | 77.760216 | 71.418120 | [raw refs](cells/train/L10-G65536.json) |
| enwik8 | 10 | 262144 | full (100000000 B) | 34792953 | 35065828 | 0.7843 | 1755.165764 | 1750.722177 | 1292.530803 | 1271.151579 | 0.736415 | 72.214436 | 67.822182 | [raw refs](cells/train/L10-G262144.json) |
| enwik8 | 10 | 524288 | full (100000000 B) | 33918396 | 33900850 | -0.0517 | 1318.298132 | 1314.203939 | 1365.947843 | 1343.200194 | 1.036145 | 66.992026 | 67.209302 | [raw refs](cells/train/L10-G524288.json) |
| enwik8 | 19 | 256 | 16 MiB prefix (16777216 B) | 12567880 | 12567957 | 0.0006 | 1048.466669 | 1044.304919 | 1087.544653 | 1077.229527 | 1.037272 | 79.247483 | 79.752641 | [raw refs](cells/train/L19-G256.json) |
| enwik8 | 19 | 1024 | 16 MiB prefix (16777216 B) | 9564908 | 9515232 | -0.5194 | 1112.956685 | 1108.278055 | 1129.746167 | 1122.395331 | 1.015085 | 32.568412 | 32.402260 | [raw refs](cells/train/L19-G1024.json) |
| enwik8 | 19 | 4096 | full (100000000 B) | 46300878 | 46213272 | -0.1892 | 8585.556422 | 8578.470396 | 9240.232650 | 9128.836757 | 1.076253 | 122.067217 | 122.079910 | [raw refs](cells/train/L19-G4096.json) |
| enwik8 | 19 | 16384 | full (100000000 B) | 40284083 | 40260131 | -0.0595 | 11005.877850 | 10996.241888 | 11603.370238 | 11577.000755 | 1.054288 | 97.746134 | 98.940126 | [raw refs](cells/train/L19-G16384.json) |
| enwik8 | 19 | 65536 | full (100000000 B) | 36265760 | 36244232 | -0.0594 | 13661.684045 | 13579.654551 | 14582.498987 | 14542.425359 | 1.067401 | 83.829753 | 89.833555 | [raw refs](cells/train/L19-G65536.json) |
| enwik8 | 19 | 262144 | full (100000000 B) | 33299917 | 33299933 | 0.0000 | 12799.382737 | 12704.502003 | 13291.176377 | 13029.832665 | 1.038423 | 79.500608 | 79.102541 | [raw refs](cells/train/L19-G262144.json) |
| enwik8 | 19 | 524288 | full (100000000 B) | 32045310 | 32045310 | 0.0000 | 11845.642466 | 11809.204147 | 12464.959365 | 12225.955409 | 1.052282 | 75.726592 | 76.250625 | [raw refs](cells/train/L19-G524288.json) |
| silesia.tar | 3 | 256 | 16 MiB prefix (16777216 B) | 13543167 | 13494669 | -0.3581 | 152.235661 | 152.012004 | 162.636344 | 160.720448 | 1.068320 | 58.307152 | 58.703907 | [raw refs](cells/holdout/L3-G256.json) |
| silesia.tar | 3 | 1024 | 16 MiB prefix (16777216 B) | 10960465 | 10907252 | -0.4855 | 77.448504 | 76.734203 | 79.498843 | 78.731512 | 1.026474 | 25.486924 | 22.300221 | [raw refs](cells/holdout/L3-G1024.json) |
| silesia.tar | 3 | 4096 | full (211947520 B) | 90686087 | 91371397 | 0.7557 | 627.275605 | 624.379539 | 625.453745 | 615.386878 | 0.997096 | 221.152450 | 202.458180 | [raw refs](cells/holdout/L3-G4096.json) |
| silesia.tar | 3 | 16384 | full (211947520 B) | 79417442 | 80085106 | 0.8407 | 525.263252 | 522.547074 | 487.449191 | 478.526300 | 0.928009 | 166.768183 | 153.446255 | [raw refs](cells/holdout/L3-G16384.json) |
| silesia.tar | 3 | 65536 | full (211947520 B) | 73587959 | 73434013 | -0.2092 | 450.809223 | 440.146838 | 454.618534 | 446.410447 | 1.008450 | 138.440970 | 135.455325 | [raw refs](cells/holdout/L3-G65536.json) |
| silesia.tar | 3 | 262144 | full (211947520 B) | 69675977 | 69577856 | -0.1408 | 507.487202 | 494.728920 | 475.688778 | 457.039991 | 0.937341 | 141.189018 | 129.673201 | [raw refs](cells/holdout/L3-G262144.json) |
| silesia.tar | 3 | 524288 | full (211947520 B) | 68319089 | 68319089 | 0.0000 | 490.868668 | 479.748003 | 490.272428 | 466.498850 | 0.998785 | 128.942480 | 128.515547 | [raw refs](cells/holdout/L3-G524288.json) |
| silesia.tar | 10 | 256 | 16 MiB prefix (16777216 B) | 13490114 | 13478489 | -0.0862 | 314.469392 | 313.506746 | 294.550160 | 292.715045 | 0.936658 | 60.123283 | 59.470879 | [raw refs](cells/holdout/L10-G256.json) |
| silesia.tar | 10 | 1024 | 16 MiB prefix (16777216 B) | 10806905 | 10801358 | -0.0513 | 225.176191 | 224.268406 | 201.473357 | 199.816888 | 0.894736 | 24.678697 | 23.703567 | [raw refs](cells/holdout/L10-G1024.json) |
| silesia.tar | 10 | 4096 | full (211947520 B) | 88166012 | 89629142 | 1.6595 | 3469.832610 | 3468.091278 | 2019.780363 | 1960.644431 | 0.582097 | 210.687875 | 195.581788 | [raw refs](cells/holdout/L10-G4096.json) |
| silesia.tar | 10 | 16384 | full (211947520 B) | 75915143 | 77411797 | 1.9715 | 4767.534185 | 4761.491998 | 1948.417608 | 1898.952081 | 0.408685 | 156.899770 | 145.966800 | [raw refs](cells/holdout/L10-G16384.json) |
| silesia.tar | 10 | 65536 | full (211947520 B) | 68781102 | 69857833 | 1.5654 | 2538.524452 | 2534.757896 | 2016.450076 | 2001.482717 | 0.794339 | 137.308810 | 127.935892 | [raw refs](cells/holdout/L10-G65536.json) |
| silesia.tar | 10 | 262144 | full (211947520 B) | 64420366 | 65128600 | 1.0994 | 2891.450461 | 2879.579046 | 2183.175849 | 2145.588101 | 0.755045 | 126.861331 | 121.078358 | [raw refs](cells/holdout/L10-G262144.json) |
| silesia.tar | 10 | 524288 | full (211947520 B) | 63318044 | 63293962 | -0.0380 | 2168.078908 | 2166.055861 | 2253.312965 | 2208.288527 | 1.039313 | 119.923490 | 119.320020 | [raw refs](cells/holdout/L10-G524288.json) |
| silesia.tar | 19 | 256 | 16 MiB prefix (16777216 B) | 13294733 | 13294512 | -0.0017 | 947.342063 | 945.270699 | 980.477723 | 978.215052 | 1.034978 | 60.484394 | 59.887777 | [raw refs](cells/holdout/L19-G256.json) |
| silesia.tar | 19 | 1024 | 16 MiB prefix (16777216 B) | 10739861 | 10690110 | -0.4632 | 1053.128293 | 1048.072095 | 1070.635815 | 1054.293261 | 1.016624 | 25.671444 | 25.319992 | [raw refs](cells/holdout/L19-G1024.json) |
| silesia.tar | 19 | 4096 | full (211947520 B) | 84759819 | 84512891 | -0.2913 | 24318.335721 | 24293.983922 | 25256.393370 | 25047.202429 | 1.038574 | 239.456510 | 235.464955 | [raw refs](cells/holdout/L19-G4096.json) |
| silesia.tar | 19 | 16384 | full (211947520 B) | 72371450 | 72212619 | -0.2195 | 30182.712111 | 30161.461387 | 31271.758710 | 31255.159096 | 1.036082 | 186.026256 | 185.893417 | [raw refs](cells/holdout/L19-G16384.json) |
| silesia.tar | 19 | 65536 | full (211947520 B) | 65101245 | 64811561 | -0.4450 | 35311.973532 | 35129.281359 | 37238.797463 | 36839.085662 | 1.054566 | 162.407774 | 163.363623 | [raw refs](cells/holdout/L19-G65536.json) |
| silesia.tar | 19 | 262144 | full (211947520 B) | 60374554 | 60374507 | -0.0001 | 31353.755730 | 31197.883698 | 32184.794880 | 31854.698882 | 1.026505 | 151.390585 | 150.644483 | [raw refs](cells/holdout/L19-G262144.json) |
| silesia.tar | 19 | 524288 | full (211947520 B) | 58655317 | 58655317 | 0.0000 | 28187.313706 | 28091.872860 | 29018.795456 | 28750.189267 | 1.029498 | 149.272088 | 146.696293 | [raw refs](cells/holdout/L19-G524288.json) |

## Archive losses against original

Every baseline cell in which B is larger than A is retained below, including cells outside P2. Faster compression does not imply a smaller archive.

| Phase | Corpus | L | G B | Extra B bytes | B size ΔA % | B/A median |
| --- | --- | --- | --- | --- | --- | --- |
| train | enwik8 | 3 | 4096 | 154068 | 0.3205 | 0.978071 |
| train | enwik8 | 3 | 16384 | 31219 | 0.0727 | 0.937621 |
| train | enwik8 | 10 | 1024 | 10028 | 0.1042 | 0.878539 |
| train | enwik8 | 10 | 4096 | 597136 | 1.2721 | 0.710390 |
| train | enwik8 | 10 | 16384 | 631957 | 1.5349 | 0.559272 |
| train | enwik8 | 10 | 65536 | 455153 | 1.2157 | 0.785220 |
| train | enwik8 | 10 | 262144 | 272875 | 0.7843 | 0.736415 |
| train | enwik8 | 19 | 256 | 77 | 0.0006 | 1.037272 |
| train | enwik8 | 19 | 262144 | 16 | 0.0000 | 1.038423 |
| holdout | silesia.tar | 3 | 4096 | 685310 | 0.7557 | 0.997096 |
| holdout | silesia.tar | 3 | 16384 | 667664 | 0.8407 | 0.928009 |
| holdout | silesia.tar | 10 | 4096 | 1463130 | 1.6595 | 0.582097 |
| holdout | silesia.tar | 10 | 16384 | 1496654 | 1.9715 | 0.408685 |
| holdout | silesia.tar | 10 | 65536 | 1076731 | 1.5654 | 0.794339 |
| holdout | silesia.tar | 10 | 262144 | 708234 | 1.0994 | 0.755045 |

## Frozen threshold and actual conditional check

X = **1024 bytes**, selected only from enwik8 A/B by the frozen smallest-eligible-candidate rule. [selection.json](selection.json) and [CONDITIONAL_PROTOCOL.md](CONDITIONAL_PROTOCOL.md) were committed before conditional development and holdout. No threshold adjustment uses holdout outcomes.

The actual native argument patch is:

```c
maxFrameSize < 1024 ? (int)maxFrameSize : 0
```

The 42 checks below keep post-freeze enwik8 A/C separate from holdout silesia A/B/C. C/A compares contemporaneous observations; earlier training A observations are not pooled. At G<X C must equal the original archive; at G≥X C must equal nohint. The displayed complete-archive SHA and byte count belong to actual C outputs, not a simulated policy.

| Phase | Corpus | L | G B | Input B | A median ms | A min ms | C median ms | C min ms | C/A median | C bytes | Policy target | C archive SHA-256 | Exact target match | Saved source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| validate | enwik8 | 3 | 256 | 16777216 | 174.815848 | 173.867157 | 176.505297 | 175.235335 | 1.009664 | 12849991 | original | 063c8cf4fb4bfe0daadc7b6c568ea6e341430893c65c491d0757017766cf7e6e | YES | [raw refs](cells/validate/L3-G256.json) |
| validate | enwik8 | 3 | 1024 | 16777216 | 85.522796 | 85.076617 | 87.052345 | 86.314641 | 1.017885 | 9737756 | nohint | 71117202cbeb9ce7539ffcd8f8c0e64162656ec8056af6944df6cbbb56e12336 | YES | [raw refs](cells/validate/L3-G1024.json) |
| validate | enwik8 | 3 | 4096 | 100000000 | 370.248323 | 363.917775 | 360.851038 | 352.708110 | 0.974619 | 48231128 | nohint | b0259bef0b42d3ece6d0360218d9be3c5a061aec82eca9daf06c7c07eae057d3 | YES | [raw refs](cells/validate/L3-G4096.json) |
| validate | enwik8 | 3 | 16384 | 100000000 | 337.463457 | 334.919961 | 312.841999 | 312.215328 | 0.927040 | 42970678 | nohint | 7432f62e4e312144716bb635e7a0e7e7cd95f0a54dfcd9cff78ff515b0750d29 | YES | [raw refs](cells/validate/L3-G16384.json) |
| validate | enwik8 | 3 | 65536 | 100000000 | 294.844805 | 293.283355 | 309.026748 | 306.082796 | 1.048100 | 39573564 | nohint | 572a1585a096f94d95b0a425fae352dbb80376d62ffd091d43e2eff3d43971a3 | YES | [raw refs](cells/validate/L3-G65536.json) |
| validate | enwik8 | 3 | 262144 | 100000000 | 336.755620 | 335.590343 | 317.722049 | 300.377507 | 0.943480 | 37326215 | nohint | 2348eccad7ede20ff4867e8370e63f7ab6ebd91ceaca7545ce15e573a37c8ebc | YES | [raw refs](cells/validate/L3-G262144.json) |
| validate | enwik8 | 3 | 524288 | 100000000 | 326.827834 | 309.555388 | 323.940652 | 309.952942 | 0.991166 | 36535040 | nohint | f973d908e6d88b7c91e89c047ec2c74bcd9c23e0c0c501cbe70e50b4922ec8a2 | YES | [raw refs](cells/validate/L3-G524288.json) |
| validate | enwik8 | 10 | 256 | 16777216 | 348.878515 | 347.873506 | 350.277640 | 347.803798 | 1.004010 | 12817014 | original | 993664b1fad7ea4fea55977dc1d060463b9184c6fde31e1f01ca391d59784784 | YES | [raw refs](cells/validate/L10-G256.json) |
| validate | enwik8 | 10 | 1024 | 16777216 | 248.216922 | 247.642543 | 217.207284 | 214.070950 | 0.875070 | 9630855 | nohint | 1bbfd272252ce2d2c971f284b6a08914195efd5e9e70bb66ea643860f6c9dd2e | YES | [raw refs](cells/validate/L10-G1024.json) |
| validate | enwik8 | 10 | 4096 | 100000000 | 1492.951945 | 1490.857962 | 1078.618914 | 1072.234051 | 0.722474 | 47536272 | nohint | 14f8e308d07c5a99edd459cccc88852dae922be1ecc4f0a3af58d949c5e72b67 | YES | [raw refs](cells/validate/L10-G4096.json) |
| validate | enwik8 | 10 | 16384 | 100000000 | 1924.450396 | 1923.306224 | 1057.341837 | 1053.838929 | 0.549425 | 41805127 | nohint | c6ed06d61dd5c9318bc104e13d83032ae2ef223e132748aca91c8577f0421a5f | YES | [raw refs](cells/validate/L10-G16384.json) |
| validate | enwik8 | 10 | 65536 | 100000000 | 1452.985629 | 1446.576881 | 1146.604839 | 1144.802379 | 0.789137 | 37894875 | nohint | 109e255a0bbccab1205007c229ab09af511dfa48661be428b72b41b2e90d7afb | YES | [raw refs](cells/validate/L10-G65536.json) |
| validate | enwik8 | 10 | 262144 | 100000000 | 1757.429973 | 1749.616533 | 1281.376635 | 1265.330758 | 0.729120 | 35065828 | nohint | e4a8c6243261078224582a6046181073799e729954c0ec9e837530d593fb9eb7 | YES | [raw refs](cells/validate/L10-G262144.json) |
| validate | enwik8 | 10 | 524288 | 100000000 | 1322.379242 | 1315.434145 | 1366.351201 | 1346.146115 | 1.033252 | 33900850 | nohint | b2a21bb4a20dd44c914d7a689c4c51dd193bac71fe60e398d85f16627e3c2987 | YES | [raw refs](cells/validate/L10-G524288.json) |
| validate | enwik8 | 19 | 256 | 16777216 | 1045.858965 | 1044.466638 | 1047.888268 | 1043.716342 | 1.001940 | 12567880 | original | 52afd73a8ecc40627c96b39cf0e5f7469abf87293d4453bbab6873f737f1743f | YES | [raw refs](cells/validate/L19-G256.json) |
| validate | enwik8 | 19 | 1024 | 16777216 | 1127.878238 | 1110.095590 | 1129.378799 | 1121.632196 | 1.001330 | 9515232 | nohint | 1d8e6fd0c957a5951e2ac4281ace180ced6ef884f1c8cd538c1561219135a179 | YES | [raw refs](cells/validate/L19-G1024.json) |
| validate | enwik8 | 19 | 4096 | 100000000 | 8573.937992 | 8551.139211 | 9255.296957 | 9095.529424 | 1.079469 | 46213272 | nohint | f8635d176563873606cf611aaef3ef261ea4772fa5f791f62f76bbbaed22ae75 | YES | [raw refs](cells/validate/L19-G4096.json) |
| validate | enwik8 | 19 | 16384 | 100000000 | 11019.609334 | 10976.661073 | 11586.425328 | 11462.806421 | 1.051437 | 40260131 | nohint | 7f4a620791b7001430bec156144fb54acd883a617e74db4025187865fb633dc4 | YES | [raw refs](cells/validate/L19-G16384.json) |
| validate | enwik8 | 19 | 65536 | 100000000 | 13679.238050 | 13525.795772 | 14620.123087 | 14557.320774 | 1.068782 | 36244232 | nohint | 3e77c0fbb2615aaa4538e1a9e671362e8b78fcdcb5484e85ba327aa5d126ae83 | YES | [raw refs](cells/validate/L19-G65536.json) |
| validate | enwik8 | 19 | 262144 | 100000000 | 12819.559609 | 12707.755030 | 13371.758901 | 13273.974190 | 1.043075 | 33299933 | nohint | 45fcaabc9681423974285bc6597d6f7d64030dd41ad3565166560c2b0438d472 | YES | [raw refs](cells/validate/L19-G262144.json) |
| validate | enwik8 | 19 | 524288 | 100000000 | 11843.615386 | 11785.530054 | 12550.292510 | 12523.301569 | 1.059667 | 32045310 | nohint | 7900fb78a80642f71db0de35e49f8967742f94313ee030d225e259a080301ec9 | YES | [raw refs](cells/validate/L19-G524288.json) |
| holdout | silesia.tar | 3 | 256 | 16777216 | 152.235661 | 152.012004 | 151.916331 | 151.787991 | 0.997902 | 13543167 | original | 35a38a39f9db30f0ea3913dfbdb153b07037fd27ad7707701bfd541c92db297f | YES | [raw refs](cells/holdout/L3-G256.json) |
| holdout | silesia.tar | 3 | 1024 | 16777216 | 77.448504 | 76.734203 | 78.971462 | 77.720074 | 1.019664 | 10907252 | nohint | e2041c67be3157467eaebc9cd3250d3447f21492384b6dbf192141b8dc83eb87 | YES | [raw refs](cells/holdout/L3-G1024.json) |
| holdout | silesia.tar | 3 | 4096 | 211947520 | 627.275605 | 624.379539 | 626.172206 | 609.134290 | 0.998241 | 91371397 | nohint | 5ffbbb665a16aee5c29fd14cd00858a65abfd343969d61e1c0749f6773c4a56f | YES | [raw refs](cells/holdout/L3-G4096.json) |
| holdout | silesia.tar | 3 | 16384 | 211947520 | 525.263252 | 522.547074 | 501.798356 | 483.248684 | 0.955327 | 80085106 | nohint | fc8888b19bf845569e8708e184ffa5a3bd31d64d4300b3b48cfac5a8c47ca9ce | YES | [raw refs](cells/holdout/L3-G16384.json) |
| holdout | silesia.tar | 3 | 65536 | 211947520 | 450.809223 | 440.146838 | 472.751493 | 465.738768 | 1.048673 | 73434013 | nohint | 6b51172c145037697cd54c7a9ec42edc81d616c637523ca94026df06c6b60956 | YES | [raw refs](cells/holdout/L3-G65536.json) |
| holdout | silesia.tar | 3 | 262144 | 211947520 | 507.487202 | 494.728920 | 482.146009 | 477.858552 | 0.950065 | 69577856 | nohint | 2e2bf0806bef62f9035cfce042d498c33b38a222de9abd27206ea195b8eec8f4 | YES | [raw refs](cells/holdout/L3-G262144.json) |
| holdout | silesia.tar | 3 | 524288 | 211947520 | 490.868668 | 479.748003 | 489.544722 | 469.910073 | 0.997303 | 68319089 | nohint | f85e7b972403a3efedb140837940ad054c839657d102b9ee9fa53179edd99f4a | YES | [raw refs](cells/holdout/L3-G524288.json) |
| holdout | silesia.tar | 10 | 256 | 16777216 | 314.469392 | 313.506746 | 314.671813 | 313.589110 | 1.000644 | 13490114 | original | 238980ed5e72fa19ab3c7d63d65d45d813e7516498c0b5e75518547f3eee1055 | YES | [raw refs](cells/holdout/L10-G256.json) |
| holdout | silesia.tar | 10 | 1024 | 16777216 | 225.176191 | 224.268406 | 203.029737 | 202.640688 | 0.901648 | 10801358 | nohint | 22b7e15cd03213c76ba0d1d73d584ebb07aaaaa6e77c286b109c9d158cd94287 | YES | [raw refs](cells/holdout/L10-G1024.json) |
| holdout | silesia.tar | 10 | 4096 | 211947520 | 3469.832610 | 3468.091278 | 2032.323244 | 2016.047193 | 0.585712 | 89629142 | nohint | 1d670a9f698e5790a58101406fd2fbe911adbafcc8a53ac991ef932024e3eaf7 | YES | [raw refs](cells/holdout/L10-G4096.json) |
| holdout | silesia.tar | 10 | 16384 | 211947520 | 4767.534185 | 4761.491998 | 1963.317413 | 1929.846037 | 0.411810 | 77411797 | nohint | 65b5a0be126333772a9f598663be0ef0195b983584acd3121407808074f40507 | YES | [raw refs](cells/holdout/L10-G16384.json) |
| holdout | silesia.tar | 10 | 65536 | 211947520 | 2538.524452 | 2534.757896 | 2023.929325 | 1988.416136 | 0.797286 | 69857833 | nohint | d8a5488c531c4b93ac01fcd2b035062851d80c9b9eec5d69a7718d6e1199ddde | YES | [raw refs](cells/holdout/L10-G65536.json) |
| holdout | silesia.tar | 10 | 262144 | 211947520 | 2891.450461 | 2879.579046 | 2154.588150 | 2125.023960 | 0.745158 | 65128600 | nohint | e7fdab31fe8b693cedc42ad7b12058bb3fa9aef2b114413790636b6d89b9166b | YES | [raw refs](cells/holdout/L10-G262144.json) |
| holdout | silesia.tar | 10 | 524288 | 211947520 | 2168.078908 | 2166.055861 | 2242.780166 | 2208.225391 | 1.034455 | 63293962 | nohint | 416314fb44e72494bb6470d6cbf52ab1ea927ea2c77035916cc44d875376ec54 | YES | [raw refs](cells/holdout/L10-G524288.json) |
| holdout | silesia.tar | 19 | 256 | 16777216 | 947.342063 | 945.270699 | 951.640811 | 945.759596 | 1.004538 | 13294733 | original | 2961349a6362d3c9e6a63f818f749b6b55c90ab5ec04fae94007678bdbb1141e | YES | [raw refs](cells/holdout/L19-G256.json) |
| holdout | silesia.tar | 19 | 1024 | 16777216 | 1053.128293 | 1048.072095 | 1069.814372 | 1061.348904 | 1.015844 | 10690110 | nohint | f17f70ac0e40b41a7fa01b950ca46a73095e8df2292c006b3bc9ad6ce4150564 | YES | [raw refs](cells/holdout/L19-G1024.json) |
| holdout | silesia.tar | 19 | 4096 | 211947520 | 24318.335721 | 24293.983922 | 25250.373877 | 25192.152115 | 1.038327 | 84512891 | nohint | 90d71523c6840f579b32b92118af62e448153533d565c571f439c169af76a5ba | YES | [raw refs](cells/holdout/L19-G4096.json) |
| holdout | silesia.tar | 19 | 16384 | 211947520 | 30182.712111 | 30161.461387 | 31232.016125 | 31102.081693 | 1.034765 | 72212619 | nohint | 0618dc7aef6dd1d76c86bb9d1fa8c2b54e276eb14e2ed1351a73daacfdf26163 | YES | [raw refs](cells/holdout/L19-G16384.json) |
| holdout | silesia.tar | 19 | 65536 | 211947520 | 35311.973532 | 35129.281359 | 37201.086505 | 36782.785903 | 1.053498 | 64811561 | nohint | f82dee8b0086706c24739e5febc75af86444c2a7533d9caaca5f96e515609ec9 | YES | [raw refs](cells/holdout/L19-G65536.json) |
| holdout | silesia.tar | 19 | 262144 | 211947520 | 31353.755730 | 31197.883698 | 32235.851288 | 31850.029964 | 1.028134 | 60374507 | nohint | d6997798abfc2a96e4eb60be6bf60cfa160c45c3bf1db559e3ea47ad01e76516 | YES | [raw refs](cells/holdout/L19-G262144.json) |
| holdout | silesia.tar | 19 | 524288 | 211947520 | 28187.313706 | 28091.872860 | 29147.472608 | 28836.915583 | 1.034064 | 58655317 | nohint | 3bb1376478e96a84ec07025773b2bf163a449d2ed985f493f58de88e13b2ca69 | YES | [raw refs](cells/holdout/L19-G524288.json) |

C size losses against contemporaneous original A are listed separately from the literal P3 allowance against B:

| Phase | Corpus | L | G B | Extra C bytes | C size ΔA % | C/A median |
| --- | --- | --- | --- | --- | --- | --- |
| validate | enwik8 | 3 | 4096 | 154068 | 0.3205 | 0.974619 |
| validate | enwik8 | 3 | 16384 | 31219 | 0.0727 | 0.927040 |
| validate | enwik8 | 10 | 1024 | 10028 | 0.1042 | 0.875070 |
| validate | enwik8 | 10 | 4096 | 597136 | 1.2721 | 0.722474 |
| validate | enwik8 | 10 | 16384 | 631957 | 1.5349 | 0.549425 |
| validate | enwik8 | 10 | 65536 | 455153 | 1.2157 | 0.789137 |
| validate | enwik8 | 10 | 262144 | 272875 | 0.7843 | 0.729120 |
| validate | enwik8 | 19 | 262144 | 16 | 0.0000 | 1.043075 |
| holdout | silesia.tar | 3 | 4096 | 685310 | 0.7557 | 0.998241 |
| holdout | silesia.tar | 3 | 16384 | 667664 | 0.8407 | 0.955327 |
| holdout | silesia.tar | 10 | 4096 | 1463130 | 1.6595 | 0.585712 |
| holdout | silesia.tar | 10 | 16384 | 1496654 | 1.9715 | 0.411810 |
| holdout | silesia.tar | 10 | 65536 | 1076731 | 1.5654 | 0.797286 |
| holdout | silesia.tar | 10 | 262144 | 708234 | 1.0994 | 0.745158 |

## Method and retained attempts

A/A medians: first=336806350 ns, second=337270581 ns; strict gate `20*abs(second-first)<first` passed. This is a method admission gate, with no time-based exclusion of grid observations. The untimed controls reproduce both complete HW-GIFT-1c enwik8 L3/256 KiB archive SHA values, distinguish changed input and reject corrupt magic; every produced archive restores bit for bit. See [method-controls.json](method-controls.json) and [method-check.json](method-check.json).

The raw five A/A pairs: [0](raw/method/L3-G262144/repeat-0/attempt-1/result.json), [1](raw/method/L3-G262144/repeat-1/attempt-1/result.json), [2](raw/method/L3-G262144/repeat-2/attempt-1/result.json), [3](raw/method/L3-G262144/repeat-3/attempt-1/result.json), [4](raw/method/L3-G262144/repeat-4/attempt-1/result.json).

| Phase | M logical repeats | N retaken repeats | All attempts | LOADED attempts | Max start load1 | Max end load1 |
| --- | --- | --- | --- | --- | --- | --- |
| method | 5 | 0 | 5 | 0 | 0.21 | 0.21 |
| train | 105 | 0 | 105 | 0 | 1.12 | 1.12 |
| validate | 105 | 0 | 105 | 0 | 1.09 | 1.13 |
| holdout | 105 | 0 | 105 | 0 | 1.28 | 1.28 |

Counts include retained rejected attempts. Only successful pairs with load1>2.0 at a boundary are LOADED; each logical pair has at most three attempts, first CLEAN wins, and worker/byte errors are fatal. All request/result/receipt/stdout/stderr files remain linked from the cell summaries. Maximum loads above include CLEAN and LOADED attempts. Other-core /proc/stat deltas are observations, not admission criteria.

## Independent post-grid native proof

The separate post-grid [native verifier](verify_native.py) passed: 127 actual archive paths checked, 85 distinct archive/source/frame identities independently decoded, 1593946 frame decodes and 9861078784 restored bytes across those distinct identities. It covers all retained attempts, verifies frame metadata and seek-table checksums against actual bytes, and confirms 42 complete conditional archives against the selected policy. The only permitted new encodings are two tiny known-answer controls; no clocks are read and no performance ranking is derived. 449 saved document hashes and the verifier source hash bind this proof to the inspected evidence. [Native proof](audit/native.json) is itself hash-bound by the independent [saved-data audit](audit/final.json); that audit separately recalculates timing medians, predicates, source bindings and load admission.

## Scope and limits

Measured host: ace-core, AMD EPYC 4344P, Linux, pinned CPU 0, schedutil governor; zstd 1.5.7 at `f8745da6ff1ad1e7bab384bd1f9d742439278e99`. Input/output are resident in RAM. Fresh contexts and prefaulted outer buffers precede each compression timer; codec internal lazy allocation is included. Hashing, restoration, disk I/O and context telemetry are outside compression timing. Native build/compiler/source digests are retained in the public native manifests and bound by each request.

This is one machine, two corpora and the stated levels/frame grid. It establishes no universal threshold, process-RSS result, or performance claim for other APIs/versions/hosts. HW-GIFT-1c showed a window/header change at 512 KiB even where archive sizes match. Internal context size is not process RSS.

The 2023 M1 numbers in PR #3544 are historical context. P1 tested the assumption that its speed factor persisted on this later library/host/API; the literal verdict above records whether that assumption survived. Later row-hash initialization/salt changes are present in pinned 1.5.7, but no version/feature ablation identifies the cause of this timing result. See [SOURCE_PATHS.md](SOURCE_PATHS.md).

Kill did not trigger; the complete speed and density losses above still qualify any proposal.

Final audit SHA-256: `c1a263b73198bb4c10ff2247a2a3ef0e9c74ffb2eaec53c8fbdd65c741579e11`. Private artifact hashes verified by that audit: 134; private paths unavailable on the audit host: 0. Archive files themselves remain in the experiment work area; public manifests bind their byte counts and SHA. This renderer uses only retained files and invokes no codecs, clocks, Git or remote commands. The issue draft is unsent.
