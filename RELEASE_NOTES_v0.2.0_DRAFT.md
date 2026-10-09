# v0.2.0 draft: A6 and A7

This draft records local acceptance facts. No GitHub CI run or official HPRC
performance measurement is claimed. Synthetic outcomes do not establish
corruption rates for production data or relative codec performance.

## A6: cohort random access

Accepted tree: `fdcad5f790ddeb3879d5b793b446b588f010bd13`.
Axis 4 CLI freezes input FASTA and requests at prepare, runs persistent native
readers, and independently verifies every response SHA against FASTA. It also
compares bytes for 32 seed-selected responses, with an external prepare-SHA anchor.
Evidence has a JSON Schema; adversarial tests cover bytes, FASTA, SHA, duplicates
and coordinates. Seven native synthetic variants each verified 40 responses and
32 byte samples; each rejected a forged nonsampled response SHA.

Local suite: 236 PASS with native libraries; 226 PASS and 10 allowed skips without.
Both NATIVE_SKIP_GATE checks passed. Logs: `review/axis3/results/a7-synthetic/A6_NATIVE.log`,
`A6_UNIT_with-native.log`, `A6_UNIT_no-native.log`; hashes in that directory's
`SHA256SUMS`. Complete original A6 receipts are retained in the accepted A6 ZIP.

## A7: application corruption

Protocol: `PROTOCOL_AXIS5.md`, SHA-256
`e30f78ff89acad8386afb883c14d0e841ead5851ec3cd88a5c861c33723e811e`.
For A7 this supersedes the earlier Axis 5 one-bit-only experiment description.
Seed 20261003, 20 cases for each of five physical corruption kinds, 100 mutations
per variant, hashes ON/OFF, 10-second case watchdog. Block operations use archive
byte blocks, not semantic codec frames. Native internal checksum checks remain on.
Clean native baselines match the independently scanned full-contig FASTA truth.
Every mutated archive, output (including partial output) and diagnostic is retained.
Verifier independently recomputes all classifications and rejects forged labels.

Seven native variants yielded 1400 verified observations. Hash ON detected all
100 changes in each variant before starting a decoder, through the generic
application SHA guard. Hash OFF results follow; every row sums to 100.

| Native variant | Detected | Silent error | Refusal | Hang | Crash | Harmless | Integrity |
|---|---:|---:|---:|---:|---:|---:|---|
| refrel3 q4k | 0 | 0 | 100 | 0 | 0 | 0 | PASS |
| refrel3 q16k | 0 | 0 | 100 | 0 | 0 | 0 | PASS |
| zstd-seekable | 0 | 0 | 100 | 0 | 0 | 0 | PASS |
| BGZF | 0 | 0 | 99 | 0 | 0 | 1 | PASS |
| plain FASTA/faidx | 0 | 78 | 20 | 0 | 0 | 2 | FAIL |
| AGC noref | 0 | 41 | 45 | 6 | 1 | 7 | FAIL |
| AGC t2t | 0 | 56 | 34 | 5 | 1 | 4 | FAIL |

These are observed outcomes under the stated limits, not claims that a codec
always detects corruption. Integrity FAIL means at least one silent_error,
as fixed before the run; faithful harness acceptance still passes.
Source: `review/axis3/results/a7-synthetic/A7_NATIVE.log`. Full per-case evidence,
inputs and raw process results accompany HWAPEX_PR63_A7.zip.

Local suite: 269 collected, 269 PASS with native libraries; 259 PASS and 10 allowed
skips without. A7 adds 33 harness/watchdog/verifier tests. Both NATIVE_SKIP_GATE
checks passed. Logs: `A7_UNIT_with-native.log`, `A7_UNIT_without-native.log` in the
same results directory. Workflow expected_total is 269; synthetic CI invokes
refrel3 q4k/q16k prepare/corrupt/run/verify and retains evidence. Other variants
were executed locally with pinned native implementations. The existing OpenZL
large-input regression remains enabled.
