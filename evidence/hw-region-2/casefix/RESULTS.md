[written by ChatGPT (AI) at the author's request; checked by the author]

# HW-REGION-2 — casefix continuation

**COMPLETE.** All 31 corpora / 186 main rows passed the resumed saved-data audit; the original load stop remains retained.

The retained [original Kill](../RESULTS-before-casefix.md) and its captures remain unchanged. The owner-authorized one-line [casefix](../lib2bit-casefix.patch) is the only lib2bit source change; no Kent/UCSC implementation or binary is used. [Full casefix stage report](RESULTS.md).

The unchanged reader’s case discrepancy from FASTA is limited to N inside soft-mask runs: full-archive N/mask overlap analysis identifies 181 such positions on chr1, first chr1:121757469 (one-based); the retained original native witness confirms n→N.

Scope: ace-core / AMD EPYC 4344P, one timed CPU0 and T=1, archive/index files warm in RAM/page cache; controller/build/correctness CPU15. These finite sampled coordinate results do not establish cross-host or exhaustive reader correctness. The terminal-packed-byte limitation remains unpatched; the frozen sampled grid has no terminal or last-packed-byte endpoint.

Equivalent rows return the same 16,384 case-preserved bases. ACEAPEX 2.6.5 interactive L2 (LIT=65536/FSE=4096), zstd 1.5.7 L3 and BGZF/HTSlib 1.24 L6 use 16 KiB FASTA blocks/frames plus all required FAI/GZI bytes. The .2bit-casefix row uses storeMasked=1. Original masked and case-folded diagnostics are excluded from P1–P3 and fastest/smallest decisions.

Main-cell protocol: a fresh process, one persistent handle, the same 12 warmups and 1000 saved starts mapped without resampling. Query timers include malloc-returning API work and ACE/zstd FAI span calculation, decode and newline removal. Validation, capture and free are outside. Open time is a separate single observation (n=1), excluding preload; RSS delta is after-open minus before-open, and peak RSS is the entire process including reference preparation, capture buffers, archive prefault and reader allocations. Neither is library-exclusive memory.

Recorded timing boundaries: **2026-11-26T17:40:09.671004+00:00 → 2026-11-26T19:03:40.406329+00:00 UTC**; ace-core, AMD EPYC 4344P 8-Core Processor, kernel 5.15.0-163-generic, governor schedutil, pinned core 0. Dates come from retained start/end receipts.

## Owner-authorized continuation

The [resume amendment](RESUME_PROTOCOL.md) authorizes one fresh maximum-three-attempt budget for the same blocked t2t-15 original/storeMasked=1 pass. The [authorization record](resume/authorization.json) and [continuation ledger](resume/ledger.json) bind the unchanged reader binaries, inputs, seed and offsets. Every earlier CLEAN unit is reused.

The original three LOADED admissions remain unchanged and do not consume the new budget. Polls inspect admission only; inadmissible polls and actual LOADED attempts require a five-minute cooldown. A CLEAN pass may proceed to the next target without that cooldown. The helper rechecks admission under the shared lock before every new attempt.

| Attempt set | Attempt | Status | Timed worker started | Receipt |
|---|---:|---|---|---|
| Original retained stop | 1 | LOADED | no | [raw](raw/main/t2t-15/twobit_original_mask1/attempt-1/ovh-bench.json) |
| Original retained stop | 2 | LOADED | no | [raw](raw/main/t2t-15/twobit_original_mask1/attempt-2/ovh-bench.json) |
| Original retained stop | 3 | LOADED | no | [raw](raw/main/t2t-15/twobit_original_mask1/attempt-3/ovh-bench.json) |
| Authorized replacement budget | 1 | CLEAN | yes | [raw](raw/main/t2t-15-resume-1/twobit_original_mask1/attempt-1/ovh-bench.json) |

Continuation ledger status: **COMPLETE**. The retained stop is history; only the current independently audited continuation can establish completion. No additional budget follows three further LOADED attempts without another owner authorization.

## Method gates

A/A requires the strict integer comparison `20 × abs(B−A) < A`; clean slow results are never retried.

| Reader | A p50 ns | B p50 ns | abs(B−A)/A | Result |
|---|---:|---:|---:|---|
| ACEAPEX 2.6.5 interactive L2 | 41057 | 41208 | 0.003678 | PASS |
| BGZF / HTSlib 1.24 L6 | 41508 | 41508 | 0.000000 | PASS |
| lib2bit-casefix (storeMasked=1) | 89938 | 89318 | 0.006894 | PASS |
| lib2bit (storeMasked=0): case-folded, not equivalent | 6823 | 6812 | 0.001612 | PASS |
| lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | 95990 | 97843 | 0.019304 | PASS |
| zstd-seekable 1.5.7 L3 | 47198 | 47139 | 0.001250 | PASS |

[A/A raw units](method-aa.json) · [Pre-timing execution clarification](EXECUTION_NOTE.md): each A/A pass is a separate load-admitted unit; the pair is judged once.

| Boundary control | Aligned p50 ns | Crossing p50 ns | Strict crossing > aligned |
|---|---:|---:|---|
| ACEAPEX 2.6.5 interactive L2 | 43542 | 60213 | PASS |
| BGZF / HTSlib 1.24 L6 | 32310 | 41197 | PASS |
| lib2bit-casefix (storeMasked=1) | 4358 | 6903 | PASS |
| zstd-seekable 1.5.7 L3 | 57528 | 69270 | PASS |

Real archive boundaries were selected by metadata alone; the .2bit control uses the preregistered uppercase/lowercase synthetic mask boundary. Fresh handles, 12 warmup pairs and 1000 AB/BA pairs separate aligned/crossing work. No timing-selected alternative or time-based retry is allowed. [Control plan](controls-plan.json) · [Control results](controls.json).

## Unchanged forecasts

| Forecast | Exact comparison | Verdict |
|---|---|---|
| P1 (65%) | 20 × 60440787 ≤ 19 × 64895635; ACE/.2bit = 60440787/64895635 | HIT |
| P2 (75%) | 4 × 88965 ≤ 41357; .2bit/ACE p50 = 88965/41357 | MISS |
| P3 (70%) | .2bit-casefix p50 < ACE p50 in 30/30 windows; required ≥28 | HIT |

The fixed reader passed the mandatory repeated lowercase-n witness and whole sampled grid before any timer.

## Complete same-run table

| Corpus | Reader | Stored B | p50 µs | p99 µs | Open µs (n=1) | Open RSS delta KiB | Peak whole-process KiB |
|---|---|---:|---:|---:|---:|---:|---:|
| chr1 | ACEAPEX 2.6.5 interactive L2 | 60440787 | 41.357 | 61.724 | 33.392 | 0 | 103892 |
| chr1 | zstd-seekable 1.5.7 L3 | 83924190 | 46.997 | 66.293 | 202.064 | 732 | 116620 |
| chr1 | BGZF / HTSlib 1.24 L6 | 80071586 | 41.526 | 59.931 | 241.017 | 516 | 112588 |
| chr1 | lib2bit-casefix (storeMasked=1) | 64895635 | 88.965 | 171.828 | 1163.393 | 5100 | 104300 |
| chr1 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 97.169 | 180.033 | 1094.847 | — | — |
| chr1 | lib2bit (storeMasked=0): case-folded, not equivalent | 64895635 | 6.823 | 9.248 | 12.804 | 0 | 104788 |
| t2t-00 | ACEAPEX 2.6.5 interactive L2 | 197011 | 44.442 | 80.148 | 14.917 | 0 | 35664 |
| t2t-00 | zstd-seekable 1.5.7 L3 | 201731 | 23.784 | 30.236 | 28.413 | 0 | 35660 |
| t2t-00 | BGZF / HTSlib 1.24 L6 | 177871 | 12.864 | 17.021 | 74.388 | 256 | 35732 |
| t2t-00 | lib2bit-casefix (storeMasked=1) | 525907 | 9.788 | 10.850 | 10.039 | 0 | 35728 |
| t2t-00 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 23.063 | 25.087 | 9.678 | — | — |
| t2t-00 | lib2bit (storeMasked=0): case-folded, not equivalent | 525907 | 4.639 | 6.322 | 9.578 | 0 | 35732 |
| t2t-01 | ACEAPEX 2.6.5 interactive L2 | 570782 | 32.741 | 60.522 | 20.719 | 0 | 35648 |
| t2t-01 | zstd-seekable 1.5.7 L3 | 745374 | 45.384 | 52.898 | 23.955 | 0 | 35704 |
| t2t-01 | BGZF / HTSlib 1.24 L6 | 692584 | 39.874 | 51.676 | 81.021 | 260 | 35704 |
| t2t-01 | lib2bit-casefix (storeMasked=1) | 606339 | 9.107 | 11.882 | 44.162 | 0 | 35632 |
| t2t-01 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 12.023 | 18.865 | 39.753 | — | — |
| t2t-01 | lib2bit (storeMasked=0): case-folded, not equivalent | 606339 | 4.609 | 5.470 | 10.790 | 0 | 35704 |
| t2t-02 | ACEAPEX 2.6.5 interactive L2 | 576197 | 33.653 | 60.924 | 12.945 | 0 | 35660 |
| t2t-02 | zstd-seekable 1.5.7 L3 | 774276 | 45.895 | 64.911 | 29.325 | 0 | 35732 |
| t2t-02 | BGZF / HTSlib 1.24 L6 | 726621 | 40.826 | 60.452 | 75.781 | 332 | 35656 |
| t2t-02 | lib2bit-casefix (storeMasked=1) | 623419 | 9.628 | 14.086 | 48.400 | 0 | 35728 |
| t2t-02 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 14.377 | 22.081 | 43.080 | — | — |
| t2t-02 | lib2bit (storeMasked=0): case-folded, not equivalent | 623419 | 4.589 | 4.980 | 11.361 | 0 | 35616 |
| t2t-03 | ACEAPEX 2.6.5 interactive L2 | 139502 | 37.440 | 67.155 | 14.096 | 0 | 35704 |
| t2t-03 | zstd-seekable 1.5.7 L3 | 198055 | 20.839 | 27.331 | 26.440 | 0 | 35664 |
| t2t-03 | BGZF / HTSlib 1.24 L6 | 194092 | 11.952 | 17.893 | 74.769 | 256 | 35724 |
| t2t-03 | lib2bit-casefix (storeMasked=1) | 524603 | 9.798 | 11.802 | 9.278 | 0 | 35704 |
| t2t-03 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 23.083 | 26.429 | 10.048 | — | — |
| t2t-03 | lib2bit (storeMasked=0): case-folded, not equivalent | 524603 | 4.628 | 5.570 | 9.418 | 0 | 35628 |
| t2t-04 | ACEAPEX 2.6.5 interactive L2 | 559760 | 33.102 | 71.332 | 14.427 | 0 | 35704 |
| t2t-04 | zstd-seekable 1.5.7 L3 | 740516 | 45.214 | 61.404 | 32.841 | 0 | 35632 |
| t2t-04 | BGZF / HTSlib 1.24 L6 | 689505 | 39.353 | 55.282 | 70.451 | 176 | 35704 |
| t2t-04 | lib2bit-casefix (storeMasked=1) | 600067 | 8.236 | 11.581 | 39.504 | 0 | 35624 |
| t2t-04 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 11.962 | 18.775 | 47.068 | — | — |
| t2t-04 | lib2bit (storeMasked=0): case-folded, not equivalent | 600067 | 4.598 | 4.989 | 10.940 | 0 | 35660 |
| t2t-05 | ACEAPEX 2.6.5 interactive L2 | 580205 | 34.605 | 64.440 | 13.375 | 0 | 35708 |
| t2t-05 | zstd-seekable 1.5.7 L3 | 777947 | 45.505 | 64.430 | 26.169 | 0 | 35716 |
| t2t-05 | BGZF / HTSlib 1.24 L6 | 729209 | 40.737 | 60.794 | 75.651 | 228 | 35648 |
| t2t-05 | lib2bit-casefix (storeMasked=1) | 645427 | 10.420 | 15.378 | 54.212 | 0 | 35640 |
| t2t-05 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 15.729 | 21.921 | 56.576 | — | — |
| t2t-05 | lib2bit (storeMasked=0): case-folded, not equivalent | 645427 | 4.589 | 4.970 | 11.171 | 0 | 35656 |
| t2t-06 | ACEAPEX 2.6.5 interactive L2 | 190102 | 40.316 | 74.299 | 12.904 | 0 | 35668 |
| t2t-06 | zstd-seekable 1.5.7 L3 | 232974 | 23.965 | 30.978 | 27.602 | 0 | 35660 |
| t2t-06 | BGZF / HTSlib 1.24 L6 | 192171 | 13.194 | 18.214 | 74.289 | 216 | 35672 |
| t2t-06 | lib2bit-casefix (storeMasked=1) | 525107 | 9.758 | 11.542 | 9.678 | 0 | 35672 |
| t2t-06 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 23.083 | 26.019 | 9.278 | — | — |
| t2t-06 | lib2bit (storeMasked=0): case-folded, not equivalent | 525107 | 4.628 | 5.370 | 9.137 | 0 | 35632 |
| t2t-07 | ACEAPEX 2.6.5 interactive L2 | 574126 | 33.001 | 60.363 | 14.828 | 0 | 35644 |
| t2t-07 | zstd-seekable 1.5.7 L3 | 768078 | 45.795 | 64.831 | 26.249 | 0 | 35708 |
| t2t-07 | BGZF / HTSlib 1.24 L6 | 719993 | 40.696 | 60.312 | 69.019 | 220 | 35628 |
| t2t-07 | lib2bit-casefix (storeMasked=1) | 610427 | 9.318 | 12.824 | 43.351 | 0 | 35728 |
| t2t-07 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 13.486 | 21.040 | 44.363 | — | — |
| t2t-07 | lib2bit (storeMasked=0): case-folded, not equivalent | 610427 | 4.589 | 4.939 | 10.629 | 0 | 35724 |
| t2t-08 | ACEAPEX 2.6.5 interactive L2 | 575985 | 33.232 | 60.603 | 12.694 | 0 | 35644 |
| t2t-08 | zstd-seekable 1.5.7 L3 | 774002 | 46.056 | 65.052 | 26.640 | 0 | 35716 |
| t2t-08 | BGZF / HTSlib 1.24 L6 | 725431 | 40.736 | 58.980 | 69.691 | 172 | 35704 |
| t2t-08 | lib2bit-casefix (storeMasked=1) | 620643 | 9.608 | 13.215 | 54.461 | 0 | 35660 |
| t2t-08 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 14.106 | 20.369 | 46.627 | — | — |
| t2t-08 | lib2bit (storeMasked=0): case-folded, not equivalent | 620643 | 4.608 | 5.009 | 11.251 | 0 | 35624 |
| t2t-09 | ACEAPEX 2.6.5 interactive L2 | 189604 | 35.046 | 64.931 | 13.165 | 0 | 35640 |
| t2t-09 | zstd-seekable 1.5.7 L3 | 278009 | 26.380 | 35.426 | 25.628 | 0 | 35660 |
| t2t-09 | BGZF / HTSlib 1.24 L6 | 214538 | 13.144 | 19.457 | 77.204 | 332 | 35656 |
| t2t-09 | lib2bit-casefix (storeMasked=1) | 524963 | 9.738 | 10.610 | 9.498 | 0 | 35732 |
| t2t-09 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 23.104 | 25.056 | 11.381 | — | — |
| t2t-09 | lib2bit (storeMasked=0): case-folded, not equivalent | 524963 | 4.609 | 5.421 | 9.278 | 0 | 35720 |
| t2t-10 | ACEAPEX 2.6.5 interactive L2 | 566854 | 32.781 | 59.842 | 13.425 | 0 | 35624 |
| t2t-10 | zstd-seekable 1.5.7 L3 | 736514 | 44.744 | 61.735 | 25.437 | 0 | 35664 |
| t2t-10 | BGZF / HTSlib 1.24 L6 | 686063 | 39.163 | 56.135 | 75.812 | 176 | 35704 |
| t2t-10 | lib2bit-casefix (storeMasked=1) | 596531 | 8.787 | 12.503 | 37.941 | 0 | 35728 |
| t2t-10 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 12.904 | 21.280 | 40.095 | — | — |
| t2t-10 | lib2bit (storeMasked=0): case-folded, not equivalent | 596531 | 4.599 | 5.531 | 10.990 | 0 | 35716 |
| t2t-11 | ACEAPEX 2.6.5 interactive L2 | 578986 | 33.793 | 62.196 | 14.978 | 0 | 35728 |
| t2t-11 | zstd-seekable 1.5.7 L3 | 775930 | 45.755 | 51.416 | 24.917 | 0 | 35704 |
| t2t-11 | BGZF / HTSlib 1.24 L6 | 729676 | 40.927 | 44.874 | 69.961 | 168 | 35644 |
| t2t-11 | lib2bit-casefix (storeMasked=1) | 634259 | 10.891 | 14.237 | 53.450 | 0 | 35652 |
| t2t-11 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 16.020 | 22.652 | 52.408 | — | — |
| t2t-11 | lib2bit (storeMasked=0): case-folded, not equivalent | 634259 | 4.618 | 5.370 | 11.411 | 0 | 35704 |
| t2t-12 | ACEAPEX 2.6.5 interactive L2 | 138646 | 34.444 | 70.372 | 13.676 | 0 | 35628 |
| t2t-12 | zstd-seekable 1.5.7 L3 | 187425 | 20.889 | 28.453 | 28.453 | 0 | 35656 |
| t2t-12 | BGZF / HTSlib 1.24 L6 | 172769 | 12.353 | 17.853 | 67.366 | 220 | 35624 |
| t2t-12 | lib2bit-casefix (storeMasked=1) | 526171 | 9.868 | 10.790 | 9.708 | 0 | 35672 |
| t2t-12 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 23.144 | 25.077 | 10.008 | — | — |
| t2t-12 | lib2bit (storeMasked=0): case-folded, not equivalent | 526171 | 4.579 | 5.020 | 9.688 | 0 | 35708 |
| t2t-13 | ACEAPEX 2.6.5 interactive L2 | 556113 | 30.957 | 55.915 | 14.026 | 0 | 35704 |
| t2t-13 | zstd-seekable 1.5.7 L3 | 729787 | 44.043 | 59.962 | 24.856 | 0 | 35648 |
| t2t-13 | BGZF / HTSlib 1.24 L6 | 672425 | 38.462 | 53.500 | 74.469 | 260 | 35704 |
| t2t-13 | lib2bit-casefix (storeMasked=1) | 580363 | 7.624 | 10.981 | 28.523 | 0 | 35732 |
| t2t-13 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 10.159 | 19.456 | 28.833 | — | — |
| t2t-13 | lib2bit (storeMasked=0): case-folded, not equivalent | 580363 | 4.608 | 6.492 | 9.588 | 0 | 35708 |
| t2t-14 | ACEAPEX 2.6.5 interactive L2 | 574906 | 32.871 | 61.665 | 12.754 | 0 | 35632 |
| t2t-14 | zstd-seekable 1.5.7 L3 | 764161 | 45.756 | 58.760 | 24.686 | 0 | 35644 |
| t2t-14 | BGZF / HTSlib 1.24 L6 | 717287 | 40.276 | 45.375 | 75.412 | 180 | 35724 |
| t2t-14 | lib2bit-casefix (storeMasked=1) | 605851 | 9.538 | 12.273 | 40.306 | 0 | 35728 |
| t2t-14 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 14.397 | 20.979 | 41.347 | — | — |
| t2t-14 | lib2bit (storeMasked=0): case-folded, not equivalent | 605851 | 4.599 | 5.099 | 10.900 | 0 | 35708 |
| t2t-15 | ACEAPEX 2.6.5 interactive L2 | 162326 | 38.873 | 72.215 | 14.818 | 0 | 35720 |
| t2t-15 | zstd-seekable 1.5.7 L3 | 210695 | 21.530 | 29.155 | 27.181 | 0 | 35708 |
| t2t-15 | BGZF / HTSlib 1.24 L6 | 205897 | 12.283 | 18.374 | 75.962 | 332 | 35656 |
| t2t-15 | lib2bit-casefix (storeMasked=1) | 525259 | 9.748 | 10.270 | 9.739 | 0 | 35660 |
| t2t-15 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 23.123 | 26.008 | 9.347 | — | — |
| t2t-15 | lib2bit (storeMasked=0): case-folded, not equivalent | 525259 | 4.618 | 5.250 | 9.357 | 0 | 35728 |
| t2t-16 | ACEAPEX 2.6.5 interactive L2 | 565981 | 31.249 | 57.688 | 13.746 | 0 | 35716 |
| t2t-16 | zstd-seekable 1.5.7 L3 | 739088 | 44.934 | 63.459 | 26.429 | 0 | 35708 |
| t2t-16 | BGZF / HTSlib 1.24 L6 | 686007 | 39.263 | 57.528 | 72.987 | 256 | 35732 |
| t2t-16 | lib2bit-casefix (storeMasked=1) | 588283 | 8.055 | 11.732 | 32.221 | 0 | 35700 |
| t2t-16 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 11.031 | 20.158 | 40.727 | — | — |
| t2t-16 | lib2bit (storeMasked=0): case-folded, not equivalent | 588283 | 4.609 | 5.400 | 9.538 | 0 | 35660 |
| t2t-17 | ACEAPEX 2.6.5 interactive L2 | 576720 | 32.381 | 58.900 | 13.395 | 0 | 35640 |
| t2t-17 | zstd-seekable 1.5.7 L3 | 770411 | 45.806 | 52.288 | 27.481 | 0 | 35660 |
| t2t-17 | BGZF / HTSlib 1.24 L6 | 721223 | 40.426 | 45.846 | 74.399 | 264 | 35712 |
| t2t-17 | lib2bit-casefix (storeMasked=1) | 606531 | 8.956 | 13.074 | 49.834 | 0 | 35728 |
| t2t-17 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 13.295 | 19.747 | 47.299 | — | — |
| t2t-17 | lib2bit (storeMasked=0): case-folded, not equivalent | 606531 | 4.599 | 5.460 | 11.151 | 0 | 35660 |
| t2t-18 | ACEAPEX 2.6.5 interactive L2 | 163105 | 42.850 | 80.602 | 15.840 | 0 | 35652 |
| t2t-18 | zstd-seekable 1.5.7 L3 | 210573 | 22.182 | 29.275 | 33.733 | 0 | 35664 |
| t2t-18 | BGZF / HTSlib 1.24 L6 | 169120 | 10.970 | 15.399 | 70.242 | 144 | 35656 |
| t2t-18 | lib2bit-casefix (storeMasked=1) | 525011 | 9.798 | 11.882 | 9.788 | 0 | 35644 |
| t2t-18 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 23.073 | 24.195 | 10.680 | — | — |
| t2t-18 | lib2bit (storeMasked=0): case-folded, not equivalent | 525011 | 4.619 | 5.260 | 8.296 | 0 | 35704 |
| t2t-19 | ACEAPEX 2.6.5 interactive L2 | 561679 | 31.399 | 58.870 | 13.605 | 0 | 35624 |
| t2t-19 | zstd-seekable 1.5.7 L3 | 729399 | 44.253 | 59.541 | 28.383 | 0 | 35656 |
| t2t-19 | BGZF / HTSlib 1.24 L6 | 674926 | 38.482 | 53.661 | 69.661 | 188 | 35724 |
| t2t-19 | lib2bit-casefix (storeMasked=1) | 586411 | 8.165 | 10.991 | 31.138 | 0 | 35644 |
| t2t-19 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 11.421 | 18.715 | 37.631 | — | — |
| t2t-19 | lib2bit (storeMasked=0): case-folded, not equivalent | 586411 | 4.618 | 5.200 | 10.249 | 0 | 35708 |
| t2t-20 | ACEAPEX 2.6.5 interactive L2 | 578722 | 33.823 | 62.037 | 13.926 | 0 | 35728 |
| t2t-20 | zstd-seekable 1.5.7 L3 | 775611 | 46.096 | 65.733 | 27.011 | 0 | 35720 |
| t2t-20 | BGZF / HTSlib 1.24 L6 | 728096 | 40.847 | 60.734 | 68.529 | 180 | 35720 |
| t2t-20 | lib2bit-casefix (storeMasked=1) | 631355 | 10.039 | 14.327 | 60.082 | 0 | 35704 |
| t2t-20 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 15.208 | 21.460 | 49.603 | — | — |
| t2t-20 | lib2bit (storeMasked=0): case-folded, not equivalent | 631355 | 4.599 | 5.330 | 11.462 | 0 | 35672 |
| t2t-21 | ACEAPEX 2.6.5 interactive L2 | 204356 | 42.810 | 76.764 | 20.088 | 0 | 35660 |
| t2t-21 | zstd-seekable 1.5.7 L3 | 217843 | 23.354 | 28.604 | 25.168 | 0 | 35660 |
| t2t-21 | BGZF / HTSlib 1.24 L6 | 185657 | 12.644 | 15.829 | 75.652 | 176 | 35704 |
| t2t-21 | lib2bit-casefix (storeMasked=1) | 527803 | 9.879 | 10.700 | 11.020 | 0 | 35644 |
| t2t-21 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 23.174 | 25.878 | 10.459 | — | — |
| t2t-21 | lib2bit (storeMasked=0): case-folded, not equivalent | 527803 | 4.599 | 4.980 | 9.087 | 0 | 35728 |
| t2t-22 | ACEAPEX 2.6.5 interactive L2 | 552517 | 32.301 | 59.281 | 14.918 | 0 | 35724 |
| t2t-22 | zstd-seekable 1.5.7 L3 | 713904 | 44.023 | 58.660 | 25.829 | 0 | 35660 |
| t2t-22 | BGZF / HTSlib 1.24 L6 | 659331 | 38.061 | 51.837 | 74.479 | 332 | 35656 |
| t2t-22 | lib2bit-casefix (storeMasked=1) | 585283 | 8.375 | 11.161 | 30.337 | 0 | 35648 |
| t2t-22 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 11.651 | 18.695 | 30.016 | — | — |
| t2t-22 | lib2bit (storeMasked=0): case-folded, not equivalent | 585283 | 4.618 | 5.139 | 9.278 | 0 | 35628 |
| t2t-23 | ACEAPEX 2.6.5 interactive L2 | 577833 | 33.874 | 62.337 | 13.375 | 0 | 35704 |
| t2t-23 | zstd-seekable 1.5.7 L3 | 775620 | 46.777 | 53.801 | 24.055 | 0 | 35728 |
| t2t-23 | BGZF / HTSlib 1.24 L6 | 728354 | 41.047 | 45.004 | 65.272 | 216 | 35672 |
| t2t-23 | lib2bit-casefix (storeMasked=1) | 630267 | 10.390 | 14.547 | 49.282 | 0 | 35676 |
| t2t-23 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 14.938 | 22.933 | 51.096 | — | — |
| t2t-23 | lib2bit (storeMasked=0): case-folded, not equivalent | 630267 | 4.599 | 4.980 | 11.241 | 0 | 35728 |
| t2t-24 | ACEAPEX 2.6.5 interactive L2 | 196870 | 43.201 | 78.557 | 13.816 | 0 | 35648 |
| t2t-24 | zstd-seekable 1.5.7 L3 | 206647 | 23.364 | 31.639 | 23.244 | 0 | 35644 |
| t2t-24 | BGZF / HTSlib 1.24 L6 | 174171 | 12.563 | 17.903 | 71.214 | 256 | 35728 |
| t2t-24 | lib2bit-casefix (storeMasked=1) | 524747 | 9.738 | 10.560 | 9.678 | 0 | 35716 |
| t2t-24 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 23.074 | 25.688 | 9.408 | — | — |
| t2t-24 | lib2bit (storeMasked=0): case-folded, not equivalent | 524747 | 4.628 | 5.069 | 9.488 | 0 | 35704 |
| t2t-25 | ACEAPEX 2.6.5 interactive L2 | 573132 | 33.032 | 59.562 | 14.427 | 0 | 35660 |
| t2t-25 | zstd-seekable 1.5.7 L3 | 749902 | 45.315 | 63.639 | 25.739 | 0 | 35624 |
| t2t-25 | BGZF / HTSlib 1.24 L6 | 702244 | 39.654 | 57.759 | 67.106 | 228 | 35644 |
| t2t-25 | lib2bit-casefix (storeMasked=1) | 602219 | 9.007 | 12.664 | 38.593 | 0 | 35728 |
| t2t-25 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 14.297 | 21.821 | 44.653 | — | — |
| t2t-25 | lib2bit (storeMasked=0): case-folded, not equivalent | 602219 | 4.599 | 5.060 | 11.331 | 0 | 35628 |
| t2t-26 | ACEAPEX 2.6.5 interactive L2 | 575709 | 32.962 | 60.293 | 15.580 | 0 | 35728 |
| t2t-26 | zstd-seekable 1.5.7 L3 | 769779 | 45.946 | 64.711 | 25.528 | 0 | 35724 |
| t2t-26 | BGZF / HTSlib 1.24 L6 | 720915 | 40.656 | 59.932 | 69.390 | 220 | 35624 |
| t2t-26 | lib2bit-casefix (storeMasked=1) | 614451 | 9.328 | 13.094 | 48.551 | 0 | 35704 |
| t2t-26 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 14.007 | 21.169 | 42.720 | — | — |
| t2t-26 | lib2bit (storeMasked=0): case-folded, not equivalent | 614451 | 4.599 | 5.069 | 11.021 | 0 | 35632 |
| t2t-27 | ACEAPEX 2.6.5 interactive L2 | 156050 | 45.976 | 86.482 | 18.335 | 0 | 35664 |
| t2t-27 | zstd-seekable 1.5.7 L3 | 145116 | 20.669 | 26.970 | 29.876 | 0 | 35660 |
| t2t-27 | BGZF / HTSlib 1.24 L6 | 136984 | 11.251 | 15.078 | 74.500 | 256 | 35732 |
| t2t-27 | lib2bit-casefix (storeMasked=1) | 526243 | 9.768 | 10.600 | 9.828 | 0 | 35704 |
| t2t-27 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 23.044 | 23.865 | 9.498 | — | — |
| t2t-27 | lib2bit (storeMasked=0): case-folded, not equivalent | 526243 | 4.628 | 5.080 | 9.668 | 0 | 35632 |
| t2t-28 | ACEAPEX 2.6.5 interactive L2 | 573276 | 33.562 | 60.644 | 15.439 | 0 | 35732 |
| t2t-28 | zstd-seekable 1.5.7 L3 | 749914 | 45.376 | 61.846 | 24.186 | 0 | 35704 |
| t2t-28 | BGZF / HTSlib 1.24 L6 | 703944 | 39.565 | 55.274 | 75.482 | 264 | 35720 |
| t2t-28 | lib2bit-casefix (storeMasked=1) | 598739 | 9.458 | 12.654 | 44.974 | 0 | 35728 |
| t2t-28 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 14.797 | 20.759 | 37.240 | — | — |
| t2t-28 | lib2bit (storeMasked=0): case-folded, not equivalent | 598739 | 4.619 | 5.360 | 10.861 | 0 | 35720 |
| t2t-29 | ACEAPEX 2.6.5 interactive L2 | 561715 | 33.032 | 61.586 | 14.577 | 0 | 35720 |
| t2t-29 | zstd-seekable 1.5.7 L3 | 728268 | 44.173 | 62.587 | 24.115 | 0 | 35704 |
| t2t-29 | BGZF / HTSlib 1.24 L6 | 680946 | 37.500 | 52.478 | 67.747 | 148 | 35732 |
| t2t-29 | lib2bit-casefix (storeMasked=1) | 586899 | 9.167 | 11.903 | 29.986 | 0 | 35672 |
| t2t-29 | lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs | — | 16.301 | 21.029 | 29.135 | — | — |
| t2t-29 | lib2bit (storeMasked=0): case-folded, not equivalent | 586899 | 4.619 | 5.460 | 9.668 | 0 | 35704 |

Original storeMasked=1 is a time-only diagnostic: stored bytes and RSS are deliberately omitted. All thirty frozen T2T sequences contain no N/n; the diagnostic label identifies the unchanged reader’s failure to preserve chr1 case. The separate original storeMasked=0 row is case-folded and not equivalent.

Primary chr1 p50, separate first-CLEAN passes: casefix/storeMasked=1 88.965 µs; original/storeMasked=1 97.169 µs; casefix/original 0.915570 (-8.44%). Original/storeMasked=0 6.823 µs is the separate case-folded diagnostic. These separate passes do not isolate a causal timing effect of the patch.

## Completed-corpus decisions — four equivalent rows only

- chr1: lowest p50 ACEAPEX 2.6.5 interactive L2 (41.357 µs); smallest ACEAPEX 2.6.5 interactive L2 (60440787 B).
- t2t-00: lowest p50 lib2bit-casefix (storeMasked=1) (9.788 µs); smallest BGZF / HTSlib 1.24 L6 (177871 B).
- t2t-01: lowest p50 lib2bit-casefix (storeMasked=1) (9.107 µs); smallest ACEAPEX 2.6.5 interactive L2 (570782 B).
- t2t-02: lowest p50 lib2bit-casefix (storeMasked=1) (9.628 µs); smallest ACEAPEX 2.6.5 interactive L2 (576197 B).
- t2t-03: lowest p50 lib2bit-casefix (storeMasked=1) (9.798 µs); smallest ACEAPEX 2.6.5 interactive L2 (139502 B).
- t2t-04: lowest p50 lib2bit-casefix (storeMasked=1) (8.236 µs); smallest ACEAPEX 2.6.5 interactive L2 (559760 B).
- t2t-05: lowest p50 lib2bit-casefix (storeMasked=1) (10.420 µs); smallest ACEAPEX 2.6.5 interactive L2 (580205 B).
- t2t-06: lowest p50 lib2bit-casefix (storeMasked=1) (9.758 µs); smallest ACEAPEX 2.6.5 interactive L2 (190102 B).
- t2t-07: lowest p50 lib2bit-casefix (storeMasked=1) (9.318 µs); smallest ACEAPEX 2.6.5 interactive L2 (574126 B).
- t2t-08: lowest p50 lib2bit-casefix (storeMasked=1) (9.608 µs); smallest ACEAPEX 2.6.5 interactive L2 (575985 B).
- t2t-09: lowest p50 lib2bit-casefix (storeMasked=1) (9.738 µs); smallest ACEAPEX 2.6.5 interactive L2 (189604 B).
- t2t-10: lowest p50 lib2bit-casefix (storeMasked=1) (8.787 µs); smallest ACEAPEX 2.6.5 interactive L2 (566854 B).
- t2t-11: lowest p50 lib2bit-casefix (storeMasked=1) (10.891 µs); smallest ACEAPEX 2.6.5 interactive L2 (578986 B).
- t2t-12: lowest p50 lib2bit-casefix (storeMasked=1) (9.868 µs); smallest ACEAPEX 2.6.5 interactive L2 (138646 B).
- t2t-13: lowest p50 lib2bit-casefix (storeMasked=1) (7.624 µs); smallest ACEAPEX 2.6.5 interactive L2 (556113 B).
- t2t-14: lowest p50 lib2bit-casefix (storeMasked=1) (9.538 µs); smallest ACEAPEX 2.6.5 interactive L2 (574906 B).
- t2t-15: lowest p50 lib2bit-casefix (storeMasked=1) (9.748 µs); smallest ACEAPEX 2.6.5 interactive L2 (162326 B).
- t2t-16: lowest p50 lib2bit-casefix (storeMasked=1) (8.055 µs); smallest ACEAPEX 2.6.5 interactive L2 (565981 B).
- t2t-17: lowest p50 lib2bit-casefix (storeMasked=1) (8.956 µs); smallest ACEAPEX 2.6.5 interactive L2 (576720 B).
- t2t-18: lowest p50 lib2bit-casefix (storeMasked=1) (9.798 µs); smallest ACEAPEX 2.6.5 interactive L2 (163105 B).
- t2t-19: lowest p50 lib2bit-casefix (storeMasked=1) (8.165 µs); smallest ACEAPEX 2.6.5 interactive L2 (561679 B).
- t2t-20: lowest p50 lib2bit-casefix (storeMasked=1) (10.039 µs); smallest ACEAPEX 2.6.5 interactive L2 (578722 B).
- t2t-21: lowest p50 lib2bit-casefix (storeMasked=1) (9.879 µs); smallest BGZF / HTSlib 1.24 L6 (185657 B).
- t2t-22: lowest p50 lib2bit-casefix (storeMasked=1) (8.375 µs); smallest ACEAPEX 2.6.5 interactive L2 (552517 B).
- t2t-23: lowest p50 lib2bit-casefix (storeMasked=1) (10.390 µs); smallest ACEAPEX 2.6.5 interactive L2 (577833 B).
- t2t-24: lowest p50 lib2bit-casefix (storeMasked=1) (9.738 µs); smallest BGZF / HTSlib 1.24 L6 (174171 B).
- t2t-25: lowest p50 lib2bit-casefix (storeMasked=1) (9.007 µs); smallest ACEAPEX 2.6.5 interactive L2 (573132 B).
- t2t-26: lowest p50 lib2bit-casefix (storeMasked=1) (9.328 µs); smallest ACEAPEX 2.6.5 interactive L2 (575709 B).
- t2t-27: lowest p50 lib2bit-casefix (storeMasked=1) (9.768 µs); smallest BGZF / HTSlib 1.24 L6 (136984 B).
- t2t-28: lowest p50 lib2bit-casefix (storeMasked=1) (9.458 µs); smallest ACEAPEX 2.6.5 interactive L2 (573276 B).
- t2t-29: lowest p50 lib2bit-casefix (storeMasked=1) (9.167 µs); smallest ACEAPEX 2.6.5 interactive L2 (561715 B).

## Retention and audit

Every timing unit uses blocking `flock /run/lock/ovh-bench.lock`. LOADED means load1−T>1 at either boundary or a surviving foreign process strictly above 10% of one CPU at admission; equality at 2.0/10% passes. At most three identical attempts retain all LOADED data and accept the first CLEAN; worker errors stop even on loaded attempts. Other-core CPU accounting is observational.

Saved audit counts: 202 accepted timing units; 206 attempts; 1 accepted units required a load retry; 4 LOADED attempts; 206000 accepted query timings. Full raw strings remain private and public deterministic gzip captures bind their raw/compressed hashes.

[Independent saved-data complete audit](audit/resumed-all.json) · [Machine-readable summary and selected raw links](summary.json) · [Correctness admission](admission.json) · [Native source/build bindings](native/build.json) · [Pinned inputs, libraries and indexes](setup.json).

## Foundations and reproduction

- [HW-REGION-1/RESULTS.md:24](../../hw-region-1/RESULTS.md#L24) retains the separate FASTA-byte experiment; its timings are not reused as 16,384-base measurements.
- [Original PROTOCOL.md:40](../PROTOCOL.md#L40) and [the retained Kill report](../RESULTS-before-casefix.md) define the original case mismatch; [this continuation protocol](PROTOCOL.md) preserves the forecasts and authorizes only the one-line patch.
- The pinned [lib2bit API, 2bit.h:90](https://github.com/dpryan79/lib2bit/blob/58e20daa898a6fc338eae82e5d2ef7108d4fc07f/2bit.h#L90) opens masked tables; [2bit.h:116](https://github.com/dpryan79/lib2bit/blob/58e20daa898a6fc338eae82e5d2ef7108d4fc07f/2bit.h#L116) returns a malloc-owned sequence. The unchanged archive information and the one-line softMask reader patch remain separate identities.
- [METHOD_PROGNOZ_ZADANIE.md:31](../../../docs/METHOD_PROGNOZ_ZADANIE.md#L31) requires method validation before the main grid; [CALIBRATION.md](CALIBRATION.md) retains the original four lines.

The standalone [sequence adapter](../../../codecs/twobit.sh) builds the same pinned reader with the same one-line fix without requiring study corpora; [usage and domain exclusions](../../../docs/TWOBIT.md) describe seq-reader-build, seq-build and seq-fetch. Generic byte-axis qualification excludes this base-coordinate adapter before builds or fixtures.

Render saved evidence only with `python3 -B evidence/hw-region-2/casefix/report.py`; the renderer imports no controller, library, clock or native code. The [original reader limitation](../PROTOCOL.md) is not broadened into an exhaustive correctness claim. No upstream post or merge is part of this experiment.
