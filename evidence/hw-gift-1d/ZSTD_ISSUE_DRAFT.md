[PR #3544](https://github.com/meta/zstd/pull/3544) intentionally improved ingestion of tiny seekable frames by supplying an approximate source-size hint. Any proposed change should preserve that purpose.

# Draft: empirical source-size hint policy for the seekable writer

**UNSENT DRAFT.** No issue/comment has been posted. This document reports a pinned experiment and asks whether a conditional policy merits broader testing; it does not establish an upstream default.

The experimental rule **hint only when maxFrameSize < 1024 bytes** met the compression-time budget in 42/42 cells. Its actual archives were larger than the original in **14/42 cells**. The initial premise of a boundary below which the hint is needed for speed and above which it only costs bytes is not confirmed by this grid.

The original Pijul report described a regression, then supplied L10/256-byte settings. The PR author reported historical M1 enwik8 times of 35 s→2.5 s and 4 KiB-frame times of 3.6 s→1.8 s. Those are 2023 upstream observations, not the following measurements. Primary sources, attribution, exact commits and later row-hash changes are recorded in [SOURCE_PATHS.md](SOURCE_PATHS.md).

We compared original A (`hint=maxFrameSize`) and B (`hint=0`) with identical seek-table checksums, resident input/output, five interleaved pairs, deterministic ordering and full restoration checks. G=256/1024 B uses a 16 MiB prefix; G≥4096 uses the full named corpus. Timing includes native compression only; decode was observed once per variant/cell/phase. Complete archives include their seek tables.

| Forecast | Literal preregistered prediction | Verdict | Observed fact |
| --- | --- | --- | --- |
| P1 | At enwik8 first 16 MiB, L10/G256 B compression ≥3× A | MISS | A=348459318 ns; B=329174338 ns; B/A=0.944656 |
| P2 | Both corpora, L3/L10, G≥65536: 0.90≤B/A≤1.10 and B bytes≤A bytes | MISS | 4/12 violating cells |
| P3 | Some X in 1–64 KiB: C/A≤1.10 everywhere; at G≥X C bytes≤1.0005×B; actual policy byte identity | HIT | X=1024 B; 0/42 violating cells |
| Kill | L3/G65536 B/A≥1.10 on either corpus means size/speed trade-off | NOT TRIGGERED | enwik8: B/A=1.034643; silesia.tar: B/A=1.008450 |

The historical speed factor was a preregistered hypothesis, not a premise forced onto these results. Different CPU/API and later library behavior prevent direct transfer of the M1 ratio. The init-once/salt changes are source context; no old/new-version or feature ablation was run to attribute the measured timing outcome.

## Measured costs at 64–512 KiB

| Corpus | L | G B | Input scope | A bytes | B bytes | B size ΔA % | A median ms | A min ms | B median ms | B min ms | B/A median | A decode once ms | B decode once ms | Saved source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| enwik8 | 3 | 65536 | full (100000000 B) | 39654522 | 39573564 | -0.2042 | 292.657616 | 287.739825 | 302.796015 | 289.659388 | 1.034643 | 73.889431 | 72.479785 | [raw refs](cells/train/L3-G65536.json) |
| enwik8 | 3 | 262144 | full (100000000 B) | 37935213 | 37326215 | -1.6054 | 336.936578 | 321.237968 | 317.769241 | 301.240653 | 0.943113 | 79.139977 | 71.202668 | [raw refs](cells/train/L3-G262144.json) |
| enwik8 | 3 | 524288 | full (100000000 B) | 36535040 | 36535040 | 0.0000 | 328.475793 | 309.385946 | 331.148228 | 314.258324 | 1.008136 | 70.412316 | 70.179759 | [raw refs](cells/train/L3-G524288.json) |
| enwik8 | 10 | 65536 | full (100000000 B) | 37439722 | 37894875 | 1.2157 | 1454.589849 | 1452.225790 | 1142.172862 | 1131.664487 | 0.785220 | 77.760216 | 71.418120 | [raw refs](cells/train/L10-G65536.json) |
| enwik8 | 10 | 262144 | full (100000000 B) | 34792953 | 35065828 | 0.7843 | 1755.165764 | 1750.722177 | 1292.530803 | 1271.151579 | 0.736415 | 72.214436 | 67.822182 | [raw refs](cells/train/L10-G262144.json) |
| enwik8 | 10 | 524288 | full (100000000 B) | 33918396 | 33900850 | -0.0517 | 1318.298132 | 1314.203939 | 1365.947843 | 1343.200194 | 1.036145 | 66.992026 | 67.209302 | [raw refs](cells/train/L10-G524288.json) |
| enwik8 | 19 | 65536 | full (100000000 B) | 36265760 | 36244232 | -0.0594 | 13661.684045 | 13579.654551 | 14582.498987 | 14542.425359 | 1.067401 | 83.829753 | 89.833555 | [raw refs](cells/train/L19-G65536.json) |
| enwik8 | 19 | 262144 | full (100000000 B) | 33299917 | 33299933 | 0.0000 | 12799.382737 | 12704.502003 | 13291.176377 | 13029.832665 | 1.038423 | 79.500608 | 79.102541 | [raw refs](cells/train/L19-G262144.json) |
| enwik8 | 19 | 524288 | full (100000000 B) | 32045310 | 32045310 | 0.0000 | 11845.642466 | 11809.204147 | 12464.959365 | 12225.955409 | 1.052282 | 75.726592 | 76.250625 | [raw refs](cells/train/L19-G524288.json) |
| silesia.tar | 3 | 65536 | full (211947520 B) | 73587959 | 73434013 | -0.2092 | 450.809223 | 440.146838 | 454.618534 | 446.410447 | 1.008450 | 138.440970 | 135.455325 | [raw refs](cells/holdout/L3-G65536.json) |
| silesia.tar | 3 | 262144 | full (211947520 B) | 69675977 | 69577856 | -0.1408 | 507.487202 | 494.728920 | 475.688778 | 457.039991 | 0.937341 | 141.189018 | 129.673201 | [raw refs](cells/holdout/L3-G262144.json) |
| silesia.tar | 3 | 524288 | full (211947520 B) | 68319089 | 68319089 | 0.0000 | 490.868668 | 479.748003 | 490.272428 | 466.498850 | 0.998785 | 128.942480 | 128.515547 | [raw refs](cells/holdout/L3-G524288.json) |
| silesia.tar | 10 | 65536 | full (211947520 B) | 68781102 | 69857833 | 1.5654 | 2538.524452 | 2534.757896 | 2016.450076 | 2001.482717 | 0.794339 | 137.308810 | 127.935892 | [raw refs](cells/holdout/L10-G65536.json) |
| silesia.tar | 10 | 262144 | full (211947520 B) | 64420366 | 65128600 | 1.0994 | 2891.450461 | 2879.579046 | 2183.175849 | 2145.588101 | 0.755045 | 126.861331 | 121.078358 | [raw refs](cells/holdout/L10-G262144.json) |
| silesia.tar | 10 | 524288 | full (211947520 B) | 63318044 | 63293962 | -0.0380 | 2168.078908 | 2166.055861 | 2253.312965 | 2208.288527 | 1.039313 | 119.923490 | 119.320020 | [raw refs](cells/holdout/L10-G524288.json) |
| silesia.tar | 19 | 65536 | full (211947520 B) | 65101245 | 64811561 | -0.4450 | 35311.973532 | 35129.281359 | 37238.797463 | 36839.085662 | 1.054566 | 162.407774 | 163.363623 | [raw refs](cells/holdout/L19-G65536.json) |
| silesia.tar | 19 | 262144 | full (211947520 B) | 60374554 | 60374507 | -0.0001 | 31353.755730 | 31197.883698 | 32184.794880 | 31854.698882 | 1.026505 | 151.390585 | 150.644483 | [raw refs](cells/holdout/L19-G262144.json) |
| silesia.tar | 19 | 524288 | full (211947520 B) | 58655317 | 58655317 | 0.0000 | 28187.313706 | 28091.872860 | 29018.795456 | 28750.189267 | 1.029498 | 149.272088 | 146.696293 | [raw refs](cells/holdout/L19-G524288.json) |

All 42 baseline cells, including tiny frames and every density loss, are in [RESULTS.md](RESULTS.md); [TABLE.csv](TABLE.csv) retains integer ns/bytes, full SHA values and all five raw references. B is not assumed smaller or slower monotonically. Violations of the literal forecasts are retained:

All P2 violations:

| Corpus | L | G B | Median ratio | Failed conditions |
| --- | --- | --- | --- | --- |
| enwik8 | 10 | 65536 | 0.785220 | speed, size |
| enwik8 | 10 | 262144 | 0.736415 | speed, size |
| silesia.tar | 10 | 65536 | 0.794339 | speed, size |
| silesia.tar | 10 | 262144 | 0.755045 | speed, size |

All P3 violations: none.

## Frozen experimental conditional rule: X=1024 bytes

```c
maxFrameSize < 1024 ? (int)maxFrameSize : 0
```

The smallest qualifying measured X was selected from enwik8 alone and committed before development/holdout. Actual C was checked in 21 new enwik8 A/C cells and 21 silesia A/B/C cells; their repetitions are not pooled with training. P3 is HIT; 0/42 cells violate at least one declared C speed/byte predicate. The complete C byte counts, SHA values, contemporaneous A/C medians/minima and exact policy identities appear in [RESULTS.md](RESULTS.md).

P3 compares C size with B at G≥X; it does not promise C≤original A. C can inherit B density losses while satisfying that predicate. The observed threshold is not evidence that hinting is necessary below it or that every larger frame gains bytes. Holdout outcomes do not change X.

Actual C archives larger than original A: 14/42. Baseline B archives larger than A: 15/42. All such cells are listed in the report.

The preregistered Kill condition did not trigger. The other recorded forecast failures and density losses still limit the proposal.

## Reproduction scope and retained evidence

ace-core AMD EPYC 4344P, Linux, CPU 0, schedutil; zstd 1.5.7 source `f8745da6ff1ad1e7bab384bd1f9d742439278e99`; levels 3/10/19, two corpora, RAM-resident operation. This is a single-machine observation, not a universal boundary. No process-RSS measurement is claimed. HW-GIFT-1c showed that an equal archive size at 512 KiB can coexist with changed header/window parameters.

A/A passed the strict <5% median gate; known-answer complete 1c archive SHA values, positive/negative controls and every bit-perfect restore passed. All raw CLEAN/LOADED attempts and receipts are retained. Only load1>2.0 admits a mechanical retry, at most three attempts per pair, with no timing-based retakes.

The separate post-grid [native verifier](verify_native.py) passed: 127 actual archive paths checked, 85 distinct archive/source/frame identities independently decoded, 1593946 frame decodes and 9861078784 restored bytes across those distinct identities. It covers all retained attempts, verifies frame metadata and seek-table checksums against actual bytes, and confirms 42 complete conditional archives against the selected policy. The only permitted new encodings are two tiny known-answer controls; no clocks are read and no performance ranking is derived. 449 saved document hashes and the verifier source hash bind this proof to the inspected evidence. [Native proof](audit/native.json) is itself hash-bound by the independent [saved-data audit](audit/final.json); that audit separately recalculates timing medians, predicates, source bindings and load admission.

| Phase | M logical repeats | N retaken repeats | All attempts | LOADED attempts | Max start load1 | Max end load1 |
| --- | --- | --- | --- | --- | --- | --- |
| method | 5 | 0 | 5 | 0 | 0.21 | 0.21 |
| train | 105 | 0 | 105 | 0 | 1.12 | 1.12 |
| validate | 105 | 0 | 105 | 0 | 1.09 | 1.13 |
| holdout | 105 | 0 | 105 | 0 | 1.28 | 1.28 |

Protocol, selection/freeze, native build manifests and independent audit: [CALIBRATION.md](CALIBRATION.md), [PROTOCOL.md](PROTOCOL.md), [selection.json](selection.json), [audit/final.json](audit/final.json). A failed holdout prediction is not repaired by choosing another X. Further machines/versions/workloads would be needed before recommending an upstream conditional default.
