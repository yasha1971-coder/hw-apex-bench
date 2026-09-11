# Contributing

Add codecs through adapters; keep measurement methods and published evidence stable.

- Start with [ADAPTERS.md](ADAPTERS.md), including the native ABI and declared helper files.
- Use Linux, Bash, Python 3, Git, GCC/G++, Make, CMake, Autoconf, Automake and zlib development headers.
- Add `codecs/NAME.sh` without codec-specific harness dispatch; keep helpers outside the `codecs/*.sh` discovery set.
- Implement `codec_name`, `codec_version`, `codec_build`, `codec_compress`, `codec_decompress`, `codec_region` and `codec_supports`.
- Give each configuration a unique name; pin source commits and record library backend, level and thread counts.
- Declare only implemented axes in `codec_supports`; give every other axis a reason in `codec_unavailable`.
- Missing backends are errors, not codec limitations; every generated `n/a` must include its reason.
- Declare all companion sources, binaries and required indexes so qualification can detect changes.
- For native regions, add a C/C++ companion using ABI 2; prepare indexes before timing, then time lookup and decoding.
- Keep counting instrumentation separate from timed libraries; c(g) varies only granularity from a one-block baseline.
- Run `./run.sh --check codecs/NAME.sh`: it builds pinned code, verifies byte-exact restoration and supported regions, and prints capabilities.
- A passing current receipt is required before measurement; changed code, binaries or configuration require a fresh check.
- Run `./run.sh --plan --codec NAME`; use the explicit `--measure` commands in ADAPTERS.md for candidate results.
- Absolute timings are `declared` because they depend on the host; compare against a baseline measured in the same run, and require a plateau for throughput headlines.
- Retain raw samples, hashes and reproduction commands; generate reports from JSONL, never edit the published 435 rows or tables by hand.
- Submit a PR with the check receipt and scope of changes; code is Apache-2.0, measurements CC BY 4.0, and citation metadata is in CITATION.cff.
