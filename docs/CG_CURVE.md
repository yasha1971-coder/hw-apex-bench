# Five-point density/access tradeoff

Run `./run.sh --cg-curve` from a clean clone. This mode downloads and MD5-checks
chr1 itself, measures only this sweep, retains earlier evidence verbatim in
`results.jsonl`, and regenerates `README.md` plus `docs/CG_CURVE_RESULTS.md` from the new
evidence group. It does not rerun or silently replace the CPU/GPU results.

The planned grid is **4, 16, 64, 256 KiB and 1 MiB**. This is a comparison of
observed tradeoffs, not a new repetitiveness measure. No expected winner, slope,
historical 0.41% target or monotonicity is an acceptance condition.

`c(g) = 100 * (1 - ratio_g / ratio_whole) = 100 * (1 - bytes_whole / bytes_g)`.
Count complete archive files and required indexes, NOT entropy payload alone.
Negative costs and nonmonotone points remain visible. Each numeric pair must
restore every input byte exactly. The report prints both sizes, both ratios,
both commands, encoder threads and per-point API-only region p50/p99.

| Format | Controlled change | Fixed configuration | Whole-input baseline |
|---|---|---|---|
| ACEAPEX | `ACEAPEX_BS` | `ee5a37eda18b81c1300a1ee44a7e06b6be925bd2`, Makefile `src/aceapex_main.cpp`, default level 2, 8 encoder threads; other overrides absent | Same binary, `ACEAPEX_BS=253935557` |
| zstd-seekable | reference `FRAME_SIZE` argument | `f8745da6ff1ad1e7bab384bd1f9d742439278e99` (1.5.7), level 3, 1 thread, seek-table checksums on | Same seekable compressor and container, one nonempty frame over the input |
| BGZF/htslib | explicit flush interval in a small htslib adapter | Installed htslib version, level 6, 1 thread | `n/a`: cannot represent one independent block covering chr1 |

Both ACEAPEX and seekable zstd link the same pinned static libzstd. Compiler
tracing verifies the actual codec translation units and clean dependency SHAs;
ACEAPEX's API includes the same `src/aceapex_main.cpp` built by Makefile. No upstream
source is edited. Installed htslib source-build provenance remains explicitly n/a.

The ACEAPEX sweep is **default**, not the earlier interactive/dense profiles.
Deterministic implementation behavior caused by changing boundaries is part of
the observation, not proof of a unique causal mechanism. The new seekable baseline
must not be silently substituted into historical CLI-versus-seekable results.

BGZF has 4/16 KiB controlled flush points and a 64 KiB requested ceiling capped
at htslib's safe `BGZF_BLOCK_SIZE`. The exact resulting block-size histogram is
parsed from the archive. The other two requests are n/a. Strict BGZF c(g) is n/a
even for supported points; ratio and API latency are still measured. A 32 KiB
DEFLATE history window does not make gzip a sequence of independent 32 KiB blocks.

All measured points reuse `harness/region_latency.c`: 16,384 original-file bytes,
one resident archive/handle, two untimed boundary checks, ten random warmups,
200 common seeded requests, nearest-rank p50/p99, direct byte comparisons outside
the API timer. This sweep makes no plateau, batch, or amplification claim.

The CI workflow keeps raw per-query samples, complete-file hashes, parsed geometry,
all command logs and compiler traces. Missing/failed points stop publication;
they never become zeros. After the run, inspect the whole curve before any claim
that it is nearly flat. Stop for review before merge.
