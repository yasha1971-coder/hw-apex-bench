[written by ChatGPT (AI) at the author's request; checked by the author]

# HW-REGION-2 — casefix continuation

**BLOCKED: load.** Three retained LOADED attempts; no fourth attempt or elapsed-based retry.

The retained [original Kill](../RESULTS-before-casefix.md) and its captures remain unchanged. The owner-authorized one-line [casefix](../lib2bit-casefix.patch) is the only lib2bit source change; no Kent/UCSC implementation or binary is used. [Full casefix stage report](RESULTS.md).

The unchanged reader’s case discrepancy from FASTA is limited to N inside soft-mask runs: full-archive N/mask overlap analysis identifies 181 such positions on chr1, first chr1:121757469 (one-based); the retained original native witness confirms n→N.

Scope: ace-core / AMD EPYC 4344P, one timed CPU0 and T=1, archive/index files warm in RAM/page cache; controller/build/correctness CPU15. These finite sampled coordinate results do not establish cross-host or exhaustive reader correctness. The terminal-packed-byte limitation remains unpatched; the frozen sampled grid has no terminal or last-packed-byte endpoint.

Equivalent rows return the same 16,384 case-preserved bases. ACEAPEX 2.6.5 interactive L2 (LIT=65536/FSE=4096), zstd 1.5.7 L3 and BGZF/HTSlib 1.24 L6 use 16 KiB FASTA blocks/frames plus all required FAI/GZI bytes. The .2bit-casefix row uses storeMasked=1. Original masked and case-folded diagnostics are excluded from P1–P3 and fastest/smallest decisions.

Main-cell protocol: a fresh process, one persistent handle, the same 12 warmups and 1000 saved starts mapped without resampling. Query timers include malloc-returning API work and ACE/zstd FAI span calculation, decode and newline removal. Validation, capture and free are outside. Open time is a separate single observation (n=1), excluding preload; RSS delta is after-open minus before-open, and peak RSS is the entire process including reference preparation, capture buffers, archive prefault and reader allocations. Neither is library-exclusive memory.

Recorded timing boundaries: **2026-11-26T17:40:09.671004+00:00 → 2026-11-26T18:04:12.200950+00:00 UTC**; ace-core, AMD EPYC 4344P 8-Core Processor, kernel 5.15.0-163-generic, governor schedutil, pinned core 0. Dates come from retained start/end receipts.

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
| P3 (70%) | .2bit-casefix p50 < ACE p50 in 15 wins among 15/30 observed T2T windows; 15 pending; required ≥28 of 30 | PENDING |

The fixed reader passed the mandatory repeated lowercase-n witness and whole sampled grid before any timer.

## Audited partial same-run table

**Partial: 16/31 complete corpora, 96/186 main rows.** Checkpoint integrity is PASS; experiment completion is **BLOCKED: load**. The retained CLEAN rows remain valid. No final P3 verdict or README performance row is admitted.

**Not measured:** t2t-15, t2t-16, t2t-17, t2t-18, t2t-19, t2t-20, t2t-21, t2t-22, t2t-23, t2t-24, t2t-25, t2t-26, t2t-27, t2t-28, t2t-29. No zero-valued rows stand in for these missing measurements.

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

## Blocked logical unit

The three admissions below never started the timed worker: no warmups, query timers or open timers ran for this blocked unit. Foreign CPU strictly above 10% is an independent LOADED criterion, even when load1 is below 2.0. The linked raw receipts retain the one-second process observations and top-eight `ps` output.

| Unit / profile | Attempt | load1 start / end | Foreign process admission CPU | Worker started | Receipt + ps |
|---|---:|---:|---|---|---|
| t2t-15 / twobit_original_mask1 | 1 | 0.58 / 0.58 | PID 124200 cc1plus 99.57% | no | [raw](raw/main/t2t-15/twobit_original_mask1/attempt-1/ovh-bench.json) |
| t2t-15 / twobit_original_mask1 | 2 | 0.58 / 0.58 | PID 124200 cc1plus 99.57% | no | [raw](raw/main/t2t-15/twobit_original_mask1/attempt-2/ovh-bench.json) |
| t2t-15 / twobit_original_mask1 | 3 | 0.61 / 0.61 | PID 124200 cc1plus 98.60% | no | [raw](raw/main/t2t-15/twobit_original_mask1/attempt-3/ovh-bench.json) |

Recorded `ps -eo pid,user,pcpu,comm --sort=-pcpu | head -8`, third LOADED admission:

```text
    PID USER     %CPU COMMAND
 124200 aeterna  86.4 cc1plus
 124261 ubuntu    3.0 python
 124519 ubuntu    2.0 python
4181850 ubuntu    0.7 2.1.314
3450996 aeterna   0.5 2.1.332
 124201 root      0.2 sshd
3277404 root      0.2 cloudflared
```


**One next step:** the owner provides a quiet window and explicitly authorizes a fresh three-attempt budget for this same blocked unit, with the same reader binaries, seed and offsets. Preserve its three old LOADED admissions and reuse every CLEAN unit; no CLEAN measurement needs to be rerun.


## Retention and audit

Every timing unit uses blocking `flock /run/lock/ovh-bench.lock`. LOADED means load1−T>1 at either boundary or a surviving foreign process strictly above 10% of one CPU at admission; equality at 2.0/10% passes. At most three identical attempts retain all LOADED data and accept the first CLEAN; worker errors stop even on loaded attempts. Other-core CPU accounting is observational.

Saved checkpoint: 112 CLEAN timing units (96 main + 16 method), 1 blocked unit, 115 total attempts, 3 LOADED admissions, 0 accepted units retaken, and 116000 accepted query timings. Full raw strings remain private and public deterministic gzip captures bind their raw/compressed hashes.

[Independent saved-data checkpoint audit](audit/checkpoint.json) · [Machine-readable summary and selected raw links](summary.json) · [Correctness admission](admission.json) · [Native source/build bindings](native/build.json) · [Pinned inputs, libraries and indexes](setup.json).

## Foundations and reproduction

- [HW-REGION-1/RESULTS.md:24](../../hw-region-1/RESULTS.md#L24) retains the separate FASTA-byte experiment; its timings are not reused as 16,384-base measurements.
- [Original PROTOCOL.md:40](../PROTOCOL.md#L40) and [the retained Kill report](../RESULTS-before-casefix.md) define the original case mismatch; [this continuation protocol](PROTOCOL.md) preserves the forecasts and authorizes only the one-line patch.
- The pinned [lib2bit API, 2bit.h:90](https://github.com/dpryan79/lib2bit/blob/58e20daa898a6fc338eae82e5d2ef7108d4fc07f/2bit.h#L90) opens masked tables; [2bit.h:116](https://github.com/dpryan79/lib2bit/blob/58e20daa898a6fc338eae82e5d2ef7108d4fc07f/2bit.h#L116) returns a malloc-owned sequence. The unchanged archive information and the one-line softMask reader patch remain separate identities.
- [METHOD_PROGNOZ_ZADANIE.md:31](../../../docs/METHOD_PROGNOZ_ZADANIE.md#L31) requires method validation before the main grid; [CALIBRATION.md](CALIBRATION.md) retains the original four lines.

The standalone [sequence adapter](../../../codecs/twobit.sh) builds the same pinned reader with the same one-line fix without requiring study corpora; [usage and domain exclusions](../../../docs/TWOBIT.md) describe seq-reader-build, seq-build and seq-fetch. Generic byte-axis qualification excludes this base-coordinate adapter before builds or fixtures.

Render saved evidence only with `python3 -B evidence/hw-region-2/casefix/report.py`; the renderer imports no controller, library, clock or native code. The [original reader limitation](../PROTOCOL.md) is not broadened into an exhaustive correctness claim. No upstream post or merge is part of this experiment.
