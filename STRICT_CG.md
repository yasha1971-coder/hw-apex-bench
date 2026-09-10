# ACEAPEX strict c(g) reproduction

This claim pins ACEAPEX at
`7216280298baa976152f6978ea1ac9c7b65fc4ad` and changes exactly one explicit
encoder setting: `ACEAPEX_BS=16384` versus `ACEAPEX_BS=253935557`. Both calls
use eight requested threads and the CLI's default level. This revision has no
`--profile` flag. `LIT_CHUNK`, `FSE_CHUNK`, `HASH_LOG`, `MIN_MATCH` and every
other known override are absent from both encoder environments.

```bash
python3 harness/aceapex_strict_cg.py
```

The script downloads chr1 hg38, verifies MD5
`9465e0f0df6e2c6eb39729c39cee5465` and size 253935557 bytes, builds the exact
ACEAPEX SHA, writes both archives, parses their headers, restores both, and
checks the results byte for byte.

Two quantities are deliberately reported:

- **Strict archive c(g)** uses `input bytes / complete .aet file bytes`, as the
  benchmark's ratio definition requires. It includes the AET header and its
  per-block random-access table.
- **Payload-only loss** reproduces the scope printed by this ACEAPEX CLI:
  `zlit + zoff + zlen + zcmd`. The CLI excludes the AET header and the
  64-byte `BlockOffsets` entry for each block from its `Compressed` and `Ratio`
  lines. Therefore the rounded 3.18065 and 3.19373 ratios cannot by themselves
  establish the archive-size c(g).

`whole` means one independent ACEAPEX block spanning the complete input. The
block logic remains active. Deterministic encoder behavior caused by changing
that block boundary is part of this one-parameter experiment.

The measured claim is not copied into `results.jsonl` until the CI artifact has
provided both exact archive sizes, both ratios, commands, versions and passing
byte-for-byte restores.

If either compression command fails, the runner writes `failure.json` and exits
nonzero. A failed one-block encode is evidence that this revision does not
provide a reproducible strict pair on that machine; a ratio printed after
undefined behavior is not accepted as a benchmark point.

## Source-layout warning at the pinned SHA

There are two diverging encoder sources in that revision. The root
`aceapex_depth.cpp` contains the guard
`c_off <= local_pos && local_pos < ORIGIN_CAP`. The committed `Makefile`, however,
sets `SRCS = src/aceapex_main.cpp`; that compiled file only checks
`c_off <= local_pos` before reading `origin[src_local]`. The CI diagnostic rebuilds
the actual Makefile target with AddressSanitizer and records the resulting stack
trace. A source argument based on the guarded root file does not establish the
behavior of the binary produced by `make`.
