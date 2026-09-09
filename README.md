# hw-apex-bench — Compressed Access Benchmark

## Latency comparison under audit

The first-table performance conclusion is withdrawn pending a matched-configuration and matched-harness audit. The earlier measurements remain preserved as evidence; they are not a reproduction of ACEAPEX's lowlat_region_p50_ms claim.

Confirmed configuration mismatch: stage 1 used FSE_CHUNK=32768; reproduce_paper5.sh uses FSE_CHUNK=4096 for the low-latency claim. Both use an archive-resident library call. Warmups, query trace, compiler optimization, encoder entry point and timed FASTA normalization also differ.

See [audit protocol](AUDIT.md), [preserved first report](evidence/stage1-20260909/README.original.md), and [original report commit](https://github.com/yasha1971-coder/hw-apex-bench/commit/f9225cfe98f4697fd2e66f31242b80033c11b466). The receipt's root-file hashes identify that original report commit, not this notice.

All three full restores and checked regions passed byte equality. Performance comparability is a separate gate. No further benchmark axes will be introduced during this audit.
