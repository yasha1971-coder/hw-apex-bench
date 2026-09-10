# ACEAPEX strict c(g) reproduction

This claim pins ACEAPEX at
`ee5a37eda18b81c1300a1ee44a7e06b6be925bd2` and changes exactly one explicit
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

## Historical source-layout defect and its closure

At `7216280298baa976152f6978ea1ac9c7b65fc4ad` there were two diverging encoder sources. The root
`aceapex_depth.cpp` contains the guard
`c_off <= local_pos && local_pos < ORIGIN_CAP`. The committed `Makefile`, however,
sets `SRCS = src/aceapex_main.cpp`; that compiled file only checks
`c_off <= local_pos` before reading `origin[src_local]`. The CI diagnostic rebuilds
the actual Makefile target with AddressSanitizer and records the resulting stack
trace. A source argument based on the guarded root file does not establish the
behavior of the binary produced by `make`.

On the GitHub Ubuntu 24.04 runner the diagnostic used GCC 13.3.0, libzstd 1.5.5,
a 16 MiB stack limit, 15 GiB RAM and 3 GiB swap. ASan reports a read fault in
worker T3 at `src/aceapex_main.cpp:243`, exactly the unguarded
`origin[src_local]` read, reached through `worker_func`, `encode_file` and
`do_compress`. This rules out the proposed small-stack explanation for this
runner. A successful non-sanitized run on another machine does not remove the
undefined behavior in the Makefile-built source.

ACEAPEX `ee5a37eda18b81c1300a1ee44a7e06b6be925bd2` adds the bound to
`src/aceapex_main.cpp`, the translation unit selected by the Makefile. The
strict claim now pins that fixed revision. Before either archive is measured,
the compiler wrapper records the source it actually compiled and the provenance
validator requires `src/aceapex_main.cpp` at the pinned commit and records its
SHA-256. This prevents an unbuilt sibling copy from being cited again.
