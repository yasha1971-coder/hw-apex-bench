# HW-GIFT-1e source and version inventory

Read first: the [task protocol](CALIBRATION.md),
[HW-GIFT-1d results](../hw-gift-1d/RESULTS.md),
[1d source history](../hw-gift-1d/SOURCE_PATHS.md), and
[1c mechanism proof](../hw-gift-1c/minimal-proof.json).
This inventory records source inspection, not new performance evidence.

## Live upstream identities

The official GitHub API was read before setup implementation. These are
annotated tag objects and their peeled commits, not interchangeable hashes.

| Tag | Annotated tag object | Peeled source commit | Tag date UTC |
| --- | --- | --- | --- |
| v1.5.4 | [`48c325656391f471396d57800b0bc99408ae6fbf`](https://api.github.com/repos/meta/zstd/git/tags/48c325656391f471396d57800b0bc99408ae6fbf) | [`945f27758c0fd67b636103a38dbf050266c6b90a`](https://github.com/meta/zstd/commit/945f27758c0fd67b636103a38dbf050266c6b90a) | 2023-02-10 |
| v1.5.7 | [`ac66b19e6bd6b83238bf008eecc1298105298532`](https://api.github.com/repos/meta/zstd/git/tags/ac66b19e6bd6b83238bf008eecc1298105298532) | [`f8745da6ff1ad1e7bab384bd1f9d742439278e99`](https://github.com/meta/zstd/commit/f8745da6ff1ad1e7bab384bd1f9d742439278e99) | 2025-02-19 |

[PR #3544](https://github.com/meta/zstd/pull/3544), merged 2023-03-10, has
authored commit `1df9f36c6c6cea08778d45a4adaf60e2433439a3` and merge commit
`134d332b10702e022745a10ff19e4725f87e5037`. Its own description supplies
the M1 enwik8 / level-10 / 256-byte example (35 s to 2.5 s). The earlier
[Pijul comment](https://github.com/meta/zstd/issues/2662#issuecomment-1443836186)
reports the regression; the detailed scenario and those timings should be
attributed to the PR rather than that earlier comment.

## Frozen writer and core separation

Fetched tagged `zstdseek_compress.c` files differ by exactly two inserted
lines before the input-length limit: `assert(maxFrameSize < INT_MAX)` and
`ZSTD_CCtx_setParameter(..., ZSTD_c_srcSizeHint, maxFrameSize)`.
Removing those exact lines from the v1.5.7 file reproduces the complete
v1.5.4 file byte for byte. The corresponding Git blob identities are
`113f6f99ce254e4a47679cdf749840f0670c7738` (B/v1.5.4) and
`4997807d2514a6aee7bab288412610fe99eb53e3` (A/v1.5.7).
See the [original writer](https://github.com/meta/zstd/blob/945f27758c0fd67b636103a38dbf050266c6b90a/contrib/seekable_format/zstdseek_compress.c#L228)
and [hinted writer](https://github.com/meta/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/contrib/seekable_format/zstdseek_compress.c#L232).

Setup materializes both exact sources, the v1.5.4 seekable header/decoder,
and the retained 1c native bridge. They stay fixed across cores. Each core
supplies its own `zstd.h`, `zstd_errors.h`, `mem.h`, `xxhash.h`, static library
and CLI. Source SHA256, build commands, compiler, headers, binaries and
`zstd -V` are retained in setup/build receipts. The tagged header's maximum
frame constant changed from 2 GiB to 1 GiB; explicit 256/1024-byte frames
avoid this default-size difference. The decoder also changed between tags,
so it is frozen rather than included in a core-only attribution.

B literally omits the setter. On a fresh context, setting hint zero selects
the same no-hint policy, but still executes an extra API call per writer
invocation. It is not the identical historical timing path. Both versions
initialize requested parameters to zero and only substitute a positive
hint for unknown input size: [v1.5.4 initialization](https://github.com/meta/zstd/blob/945f27758c0fd67b636103a38dbf050266c6b90a/lib/compress/zstd_compress.c#L363),
[v1.5.4 hint handling](https://github.com/meta/zstd/blob/945f27758c0fd67b636103a38dbf050266c6b90a/lib/compress/zstd_compress.c#L1555),
[v1.5.7 hint handling](https://github.com/meta/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/compress/zstd_compress.c#L1638).
The hint is experimental API: use the matching core's headers rather than
carrying numeric enum values or private layouts between versions.

## Scope of the historical question

The saved 1d prefix result was B/A = 329174338/348459318 at L10/G256,
with 16 MiB enwik8. It did not reproduce the historical large slowdown on
1.5.7. It did not test 1.5.4 or full enwik8 at that tiny frame size.
The other 1d cells preserve size and speed trade-offs by level; they do not
establish a version attribution. In particular, L10/G65536 enwik8 B/A was
0.785220 while B was 1.2157% larger. Exact integers and all other cells
remain in the [saved 1d table](../hw-gift-1d/TABLE.csv).

The official comparison reports v1.5.4 as an ancestor of v1.5.7 and 1068
added DAG commits. A bounded search must retain the selected ancestry
path, FAST predicate, every attempted build and any skips. Without a
monotonicity proof, an observed adjacent slow/fast pair is a boundary on
that path, not proof of the globally earliest fast commit or of one causal
patch inside a merge. The 12-build limit and the P1/P2 gates apply before
any such search; historical source explanations do not replace those gates.
