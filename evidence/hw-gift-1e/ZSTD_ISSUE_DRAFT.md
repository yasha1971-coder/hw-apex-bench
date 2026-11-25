[PR #3544](https://github.com/meta/zstd/pull/3544) intentionally improved ingestion of very small seekable frames by providing a source-size hint.

# Draft: historical tiny-frame slowdown and the current hint trade-off

**UNSENT DRAFT.** No upstream issue/comment has been sent.

The PR description reports historical M1 enwik8 L10/256-byte times of 35 s→2.5 s. The [original Pijul comment](https://github.com/meta/zstd/issues/2662#issuecomment-1443836186) reports the regression; the [later reproducer](https://github.com/meta/zstd/issues/2662#issuecomment-1457696603) supplies the L10/256-byte scenario. Those historical observations are distinct from the present host and native harness.

Both full-input primary predictions HIT: the severe old-core slowdown is reproducible in this controlled native harness, and the modern pair differs by less than 1.2×. With identical seekable writer/decoder/header/bridge across the tags, this supports a core-version effect in this harness. The bounded prefix search below qualifies its transition/range; no global first-fast or original-Pijul application claim is made.

| Gate | Full-input condition | Verdict | Observed fact |
| --- | --- | --- | --- |
| P1 | v1.5.4 FULL/L10/G256: median(B) ≥5×median(A) | HIT | A=2090112729 ns; B=65207374880 ns; B/A=31.198018; symmetric factor=31.198018 |
| P2 | v1.5.7 same FULL primary: max(medians)/min(medians) <1.2 | HIT | A=2087706392 ns; B=1916454131 ns; B/A=0.917971; symmetric factor=1.089359 |
| Kill | v1.5.4 FULL primary: median(B) <2×median(A) | NOT TRIGGERED | Proceeding does not imply P1 HIT |

The primary question uses full enwik8 (100,000,000 bytes), not a substituted 16 MiB prefix. The entire version/scope grid, including explicit NOT RUN: Kill entries, medians/minima, complete archive bytes/SHA and five raw observations, is in [RESULTS.md](RESULTS.md) and [TABLE.csv](TABLE.csv).

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

## What the saved v1.5.7 hint trade-off costs by level

Separate HW-GIFT-1d data: A sets hint=maxFrameSize; B calls the setter with zero. HW-GIFT-1e B omits the call, so timing observations from these studies are not pooled. The time ratio is hint/zero-hint; the signed archive percentage is `100*(hint bytes − zero-hint bytes)/zero-hint bytes`. Negative size percentages mean the hint produces a smaller archive.

| Saved 1d scope | Hint time A/B range | Time extrema point IDs | Hint archive Δ vs B % range | Size extrema point IDs |
| --- | --- | --- | --- | --- |
| L3, all 14 corpus/frame cells (tiny frames use prefixes) | 0.936049 … 1.077575 | silesia.tar/L3/G256/prefix16MiB … silesia.tar/L3/G16384/full | -0.833693 … 1.631556 | silesia.tar/L3/G16384/full … enwik8/L3/G262144/full |
| L10, full input at 4–256 KiB (8 cells) | 1.258908 … 2.446875 | silesia.tar/L10/G65536/full … silesia.tar/L10/G16384/full | -1.933367 … -0.778179 | silesia.tar/L10/G16384/full … enwik8/L10/G262144/full |
| L19, full input at 4–256 KiB (8 cells) | 0.929149 … 0.974179 | enwik8/L19/G4096/full … silesia.tar/L19/G262144/full | -0.000048 … 0.446963 | enwik8/L19/G262144/full … silesia.tar/L19/G65536/full |

These scoped ranges are derived from saved integer medians and byte counts, rather than copied approximate forecasts. L3 includes all 14 points and explicitly includes 16 MiB prefixes at 256/1024-byte frames. L10/L19 summaries cover the eight full-input 4–256 KiB points on two corpora. All tiny, 512 KiB, opposite-direction and exact-byte differences remain in the complete 42-point table with source SHA in [RESULTS.md](RESULTS.md). A conditional rule need not be a free win: hint speed and density can change in either direction.

ace-core AMD EPYC 4344P, Linux CPU 0, schedutil, RAM input/output, one thread; exact v1.5.4/v1.5.7 sources and equal compiler flags, fixed historical seekable writer/decoder/header/bridge, matching per-core headers/static libraries. Five interleaved A/B rounds; fresh contexts and prefaulted outer buffers outside the encode timer, internal first-use allocation inside. Full byte/checksum/empty-frame checks are untimed. Both actually linked versions and CLI versions are recorded. This is not the original Pijul application or a universal-machine result.

Executed full-input A/A gates (v1.5.4, v1.5.7) passed strict <5% before their grids; a version stopped by Kill has no substituted method observation. Mechanically excluded load rounds and all raw attempts are retained. Independent controller: [audit/final.json](audit/final.json). Source/history and primary URLs: [SOURCE_PATHS.md](SOURCE_PATHS.md). No global first-fast, universal threshold, or individual side-branch causal claim follows from a bounded path search.

Given this version-specific result and the saved level-dependent size/speed trade-offs, would you prefer an explicit configurable source-size-hint policy for the seekable writer?
