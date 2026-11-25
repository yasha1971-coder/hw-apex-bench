# HW-GIFT-1d: why the seekable writer sets a source-size hint

Опоры: [HW-GIFT-1c results](../hw-gift-1c/RESULTS.md),
[its pinned compression paths](../hw-gift-1c/SOURCE_PATHS.md),
[upstream PR #3544](https://github.com/meta/zstd/pull/3544), and
[the original Pijul report](https://github.com/meta/zstd/issues/2662#issuecomment-1443836186).

This document records source inspection. It contains no new encodings, timings,
chosen threshold, or evidence that a conditional policy meets HW-GIFT-1d's
predictions. The 1c result and the historical upstream measurements have
different scopes.

## Canonical upstream location and exact change

Live GitHub API requests to `facebook/zstd` return a redirect to repository ID
29759715; the returned HTML URLs now use `meta/zstd`. The GitHub connector reads
the repository successfully using that canonical name. The old Facebook URLs
refer to the same project and remain useful historical links.

| Item | Primary source and identity |
|---|---|
| PR | [#3544, improved seekable ingestion for small frames](https://github.com/meta/zstd/pull/3544), authored by `Cyan4973`, merged 2023-03-10 |
| Authored change | [`1df9f36c6c6cea08778d45a4adaf60e2433439a3`](https://github.com/meta/zstd/commit/1df9f36c6c6cea08778d45a4adaf60e2433439a3) |
| Parent before the change | [`d55a6483d7ec63b9175301d1849577f03a968ffb`](https://github.com/meta/zstd/commit/d55a6483d7ec63b9175301d1849577f03a968ffb) |
| Merge commit | [`134d332b10702e022745a10ff19e4725f87e5037`](https://github.com/meta/zstd/commit/134d332b10702e022745a10ff19e4725f87e5037), distinct from the authored commit |
| Current `dev` inspected | [`b022b64ea7d7577c4b3758d0449fb5f5a4606c60`](https://github.com/meta/zstd/commit/b022b64ea7d7577c4b3758d0449fb5f5a4606c60) |

The [authored diff](https://github.com/meta/zstd/commit/1df9f36c6c6cea08778d45a4adaf60e2433439a3)
adds the unconditional `ZSTD_c_srcSizeHint = maxFrameSize` call immediately
before input is limited to the current frame's remaining capacity. The same
choice is present at [current dev `zstdseek_compress.c:234`](https://github.com/meta/zstd/blob/b022b64ea7d7577c4b3758d0449fb5f5a4606c60/contrib/seekable_format/zstdseek_compress.c#L234).
The change also exposes the example encoder's compression-level argument and
reduces the seekable maximum decompressed-frame limit from 2 GiB to 1 GiB. A
hint-only experiment should isolate the hint change rather than attributing the
whole PR's diff to one line.

## Original reason and attribution

The [2023-02-24 comment 1443836186](https://github.com/meta/zstd/issues/2662#issuecomment-1443836186)
reports that Pijul's seekable usage was at least ten times slower with zstd 1.5
than 1.4.8. That comment does not specify the frame size, level, M1 timings, or a
read benchmark.

The [later reproducer, comment 1457696603](https://github.com/meta/zstd/issues/2662#issuecomment-1457696603),
specifies level 10, 256-byte frames and no read test. It provides the Rust
compression loop and identifies zstd-seekable crate 1.7.0 for reproduction;
later bindings could silently use an older bundled zstd. This explains why the
actually linked zstd version must be checked rather than inferred from the
system installation.

[PR #3544's own description](https://github.com/meta/zstd/pull/3544)
attributes the slowdown to very small seekable frames, especially with the
then-recent row-hash compression mode, and supplies approximate source-size
information to adapt compression parameters. Its local M1 observations were:

| Historical upstream scenario | Before → after |
|---|---:|
| enwik8, Pijul's 256-byte / level-10 settings | 35 s → 2.5 s, approximately 14× faster |
| all-zero input in the same corner case | 45 s → 0.5 s |
| enwik8, 4 KiB frames | 3.6 s → 1.8 s, with a small ratio improvement also reported |

These are the maintainer's historical observations, not measurements on the
HW-GIFT host. The PR states that this gain is additional to separate row-hash
optimization work. They provide a reason to preserve the small-frame benefit;
they do not establish a universal cutoff or today's speed ratio.

## Existing conditionals and the pinned 1c mechanism

Neither the authored #3544 line nor the inspected current seekable writer has
a `maxFrameSize < X` condition. This is a check of those upstream source
revisions, not a claim that no fork or unmerged proposal exists.

There are already conditional decisions inside the pinned zstd 1.5.7 library:

- [Hint fallback, `zstd_compress.c:1641-1650`](https://github.com/meta/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/compress/zstd_compress.c#L1641-L1650)
  substitutes a positive hint only when the pledged source size is unknown.
- [Size-tier selection:7761-7772](https://github.com/meta/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/compress/zstd_compress.c#L7761-L7772)
  chooses among source-size tables with boundaries at 16, 128 and 256 KiB.
- [Automatic row-matcher choice:237-244](https://github.com/meta/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/compress/zstd_compress.c#L237-L244)
  depends on supported compression strategy and enables row matching only when
  `windowLog > 14` in automatic mode.
- [Row-tag workspace handling:2032-2044](https://github.com/meta/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/compress/zstd_compress.c#L2032-L2044)
  already uses init-once storage and a changing salt for a CCtx; the CDict path
  has different initialization behavior.

Those are existing library adaptations, not an existing seekable cutoff rule.
They also prevent a simplistic claim that current zstd always clears the whole
row-tag table on every frame. The [discussion in #3426](https://github.com/meta/zstd/pull/3426#issuecomment-1382613487)
documents why initialization/reuse costs mattered. That PR is closed and
unmerged; its discussion is context, not proof that its proposed patch shipped.

HW-GIFT-1c proved the byte effect for its pinned
[`f8745da6ff1ad1e7bab384bd1f9d742439278e99:234`](https://github.com/meta/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/contrib/seekable_format/zstdseek_compress.c#L234)
path. The hint is not a pledged content size: 1c found no FCS in either actual
writer, and changing CONTINUE chunking alone did not explain the frame hashes.
Those source paths, exact release versions and file hashes remain recorded in
[the 1c source inventory](../hw-gift-1c/SOURCE_PATHS.md).

## Row-hash changes after the historical example

Two changes dated 2023-03-13 followed #3544's 2023-03-10 merge:

- [`9420bce8a491e21821c4b372f837bf4bd47e5870`](https://github.com/meta/zstd/commit/9420bce8a491e21821c4b372f837bf4bd47e5870),
  [PR #3529](https://github.com/meta/zstd/pull/3529), introduced workspace
  storage initialized once and moved row-tag allocation to that storage,
  replacing the previous per-reset tag-table clearing.
- [`91f4c23e634a1d260f290f00b6d870a56cd59ab6`](https://github.com/meta/zstd/commit/91f4c23e634a1d260f290f00b6d870a56cd59ab6),
  [PR #3533](https://github.com/meta/zstd/pull/3533), added changing row-hash
  salts to avoid regressions when successive compressions reuse tag storage
  with similar input. Both changes belong to [the #3528 work](https://github.com/meta/zstd/pull/3528).

Both mechanisms are present in the pinned 1.5.7 source: the CCtx branch at
[`zstd_compress.c:2032-2044`](https://github.com/meta/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/compress/zstd_compress.c#L2032-L2044)
reserves init-once tag storage and advances the hash salt; its CDict branch
still clears the tag storage. Automatic row-matcher selection also depends
on strategy and `windowLog`, at
[`zstd_compress.c:237-244`](https://github.com/meta/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/compress/zstd_compress.c#L237-L244).

The source-history inference is that the historical M1 ratios cannot be
assumed to transfer to this host and later library unchanged: relevant reset
and reuse behavior evolved just after that example. This is a plausible
explanation for a failed portability assumption, not a causal attribution of
HW-GIFT-1d's timing result. No old/new-version or feature ablation was run.

## Consequences for an unsent issue draft

Lead with #3544's intentional tiny-frame ingestion improvement. Then separate
the already verified 64–256 KiB size/memory trade-off from the new timing grid.
Do not present unconditional hint removal as cost-free: 1c's single fixed-order
pair at level 3 / 256 KiB did not test 256-byte / level-10 ingestion, and its
larger no-hint context remains a material memory trade-off.

Any cutoff selected from the development corpus must remain explicitly
empirical and be checked on the other corpus. A threshold for this host,
library version and level grid cannot be inferred from the old M1 numbers,
from the internal size-tier constants alone, or from an absent size gap at
512 KiB. The draft should retain losses and the preregistered kill condition.
No issue, comment, email or other external message was sent for this source
inspection.
