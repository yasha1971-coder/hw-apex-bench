# Working agreement

Read `docs/HISTORY.md` before continuing work. Verify the live Git branch and PR
state; the handoff is a checkpoint, not a substitute for GitHub evidence.

- Work only in this benchmark repository. Never modify `aceapex`, `glyph-engine`
  or `yasha-context`. Dependencies must use exact commits and clean source trees.
- Keep bgzip+htslib, zstd-seekable and ACEAPEX together in CPU comparisons.
  Publish losses and unsupported points honestly; never replace missing values
  with zero or with expected/historical measurements.
- Preserve raw measurement bytes and provenance. Compare complete archives plus
  required indexes, verify restored bytes, and keep distinct machines, runs,
  configurations and declared GPU evidence separate.
- Throughput headlines require the documented plateau. Unresolved curves remain
  `data_edge`. CPU/GPU and one-worker/multiple-worker paths are distinct scopes.
- For a publication change, run `python3 web/validate_publication.py` and
  `python3 web/build.py /tmp/cabench-pages/index.html`. Never bypass a failed
  integrity check by relaxing a validator or replacing expected values blindly.
- At a chat transition, update `docs/HISTORY.md` with exact commits, PRs, verified
  artifacts, outstanding problems, and the next bounded action. Commit and push
  completed work; do not leave the only copy in scratch or in conversation.
- Respect the review stops in the user's current instructions. The first-table
  stop is historical (stages 1–5 have merged). The five-point c(g) curve needs its
  own complete table and audit before merge or scientific claims.

Current user instructions take precedence if they change the scope.
