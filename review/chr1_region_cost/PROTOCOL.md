# chr1 ACE region-cost baseline — current API, before optimization

Purpose: measure the cost floor of the current ACEAPEX random-access library path
on a full-size archive before any resident-context optimization is attempted.

This is not a codec comparison and not a new g sweep.

## Frozen configuration

- corpus: UCSC hg38 chr1 FASTA from \`corpora.json\`
- required uncompressed MD5: \`9465e0f0df6e2c6eb39729c39cee5465\`
- required uncompressed bytes: 253,935,557
- ACEAPEX source: \`4915321bf118e564ef3883e58927992c7f9d8dc3\`
- linked zstd: \`f8745da6ff1ad1e7bab384bd1f9d742439278e99\`
- encoder: level 2, 8 threads
- \`ACEAPEX_BS=16384\`
- no explicit \`LIT_CHUNK\`, \`FSE_CHUNK\`, \`MIN_MATCH\`, or profile override
- request length R = 16,384 bytes
- archive resident in memory before timing
- one CPU affinity selected and recorded
- 12 warmups before latency sampling
- bit-perfect full restore before any profile result is accepted

The archive configuration intentionally matches the matched-g experiment's ACE
settings at g=16 KiB. Changing FSE/LIT chunk policy here would confound API cost
with archive configuration.

## Measurements

1. **Current full resident API latency**
   Existing \`harness/native_measure.c\`, 200 verified random 16 KiB regions,
   seed 20260909. p50/p99 retained.

2. **perf stat on current hc_region**
   A dedicated hot-loop process opens the same resident archive/context before
   executing N precomputed 16 KiB requests. \`perf stat\` records
   \`instructions\` and \`cycles\`. A zero-query setup run and an ABI stub loop
   are retained so query-loop overhead can be measured rather than assumed.
   No source change is made to ACEAPEX.

3. **malloc/free count per request**
   An LD_PRELOAD counter is enabled only around each \`hc_region()\` call.
   Counts are retained per request. This is a separate run and is not used for
   the uninstrumented latency number.

4. **header/range bookkeeping micro-path**
   An isolated probe reproduces the current top-of-call header validation and
   block/range locator logic over the same resident chr1 archive. It is measured
   directly; it is not estimated by subtracting from total latency.

5. **linear stream-index scan micro-path**
   A separate probe executes the metadata traversal shape used by current
   \`lit_range\` / \`fse_range\` on the full chr1 archive, without entropy
   decoding. This directly tests the archive-size-sensitive scan concern.
   It is reported as an isolated component and is not claimed to be additive
   with the other rows.

## Interpretation boundary

The final table is a baseline ledger for later optimization:

\`layer -> measured time or count\`.

Rows are not summed into a synthetic latency decomposition because isolated
micro-probes overlap with work inside the full API. Future optimizations must
rerun the same probes and report deltas against this baseline.

Absolute timings on GitHub-hosted hardware are declared machine-specific.
Instructions/cycles, call counts, and same-run relative changes are the more
portable diagnostics.
