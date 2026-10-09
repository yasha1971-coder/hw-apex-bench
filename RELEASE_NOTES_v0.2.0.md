# hw-apex-bench v0.2.0 — prepared release

This release document records local acceptance facts from A6–A8. No GitHub CI run or official HPRC
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

## A8: verified deterministic leaderboard generation

`tools/build_leaderboard.py` consumes anchored evidence catalogs for Axis 3
(including the B-job window-law schema), Axis 4 and Axis 5. It invokes each
axis's verifier, then emits LEADERBOARD.md, leaderboard.csv and leaderboard.json.
Every row links an exact source JSON copy and its full SHA-256. No new decoder
or timing measurements are performed; displayed values come from verified
source evidence and its hash-bound companions.

Duplicate variants and mixed requests/machines/scopes/protocols refuse. Synthetic
A6/A7 has no machine ID: default tables are source-specific singletons, and
forcing those sources into a common comparison refuses. Missing metrics remain
empty/null. Synthetic timings are not presented as performance measurements.

Preserved A6/A7 golden fixtures produce 4 tables/4 rows, byte-identical on rerun,
relocation and input-order changes. The complete seven-variant A6/A7 input set
produces 21 separate tables/rows after verification. Source logs, input catalogs,
output hashes and complete tables are retained in HWAPEX_PR63_A8.zip.

A8 adds 37 tests; actual collection is 306. Local full suite: 306 PASS with all
native libraries; 296 PASS and 10 allowed skips without. NATIVE_SKIP_GATE PASS
both. Workflow expected_total=306 and a golden/determinism synthetic step with
artifact retention was added; GitHub CI execution is not claimed.


## Source receipts and official measurement status

A6/A7 numeric facts above are recorded in
[A6 native log](review/axis3/results/a7-synthetic/A6_NATIVE.log),
[A6 native suite](review/axis3/results/a7-synthetic/A6_UNIT_with-native.log),
[A6 optional-native suite](review/axis3/results/a7-synthetic/A6_UNIT_no-native.log),
[A7 native log](review/axis3/results/a7-synthetic/A7_NATIVE.log),
[A7 native suite](review/axis3/results/a7-synthetic/A7_UNIT_with-native.log), and
[A7 optional-native suite](review/axis3/results/a7-synthetic/A7_UNIT_without-native.log).
Their [SHA256SUMS](review/axis3/results/a7-synthetic/SHA256SUMS) binds exact bytes.

A8 collection/native/skip facts come from the original final
[with-native receipt](review/axis3/results/a8-acceptance/a8-final-with-native.json)
and [without-native receipt](review/axis3/results/a8-acceptance/a8-final-without-native.json).
The [golden log](review/axis3/results/a8-acceptance/a8-final-synthetic.log) and
[seven-variant log](review/axis3/results/a8-acceptance/a8-final-all-native.log)
record table counts and output hashes; all are bound by
[SHA256SUMS](review/axis3/results/a8-acceptance/SHA256SUMS).
These are historical A8 results, not the current A9 suite count.

Official ace-core HPRC measurements: **PENDING**, no numeric placeholder.
The server must add real, supported evidence in place of the
[pending evidence file](review/axis3/results/v0.2.0/ace-core/EVIDENCE_PENDING.json),
with anchored catalogs and original artifacts. A pending file fails release
verification. Axis 5 v1 remains synthetic-only and lacks recorded machine/scope;
it needs a separately frozen protocol/schema before an official experiment.

A9 adds offline release assembly and independent manifest verification;
[methodology](METHODOLOGY.md) defines its provenance and reproduction contracts.
Citation version and deposit metadata are prepared for v0.2.0, with no invented
new DOI, publication date, upload or GitHub CI claim. A prior release's DOI is
not assigned to this version. Nothing in this package authorizes publication.
