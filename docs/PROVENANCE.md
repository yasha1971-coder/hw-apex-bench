# Reading the evidence

The root results.jsonl is the frozen 435-row historical publication. Native runs
write separate result files; they do not overwrite it. These formats are related,
but their field names differ. Inspect the actual row, not a hypothetical schema.

| Meaning | Historical publication | Native result rows |
|---|---|---|
| Measurement identity | codec, metric, configuration | codec, axis, configuration and scope |
| Value and unit | value, unit | value, unit |
| Claim status | status; correctness/full_restore where applicable | level, verified and qualification evidence |
| Reproduction | commands | command |
| Corpus | corpus with checksum | corpus and checksum fields |
| Machine and libraries | hardware, versions | host, toolchain |
| Run origin | run_id, benchmark_commit, evidence_group | run manifest and qualification receipt |
| Same-run baseline | explicit relative metric rows | baseline_ratio |

Fields vary by axis. A null value needs its reason; it is not zero.
The code defining native serialization is [native_results.py](../harness/native_results.py).
The historical validator is [report.py](../harness/report.py).

## Follow one claim

1. Select its codec, configuration, metric and run identity.
2. Read its exact commands, corpus checksum, versions and hardware.
3. Check correctness and the raw sample or archive hashes cited by the row.
4. Locate a matching baseline from the same run before comparing timing ratios.
5. Keep strict c(g), CPU timing and owner-declared GPU scopes separate.

Stored ratios and displayed rounding have different purposes. The graph and table
round for readability; the JSONL retains the original numeric values.
Configuration includes granularity, thread policy and backend, not just a codec name.
Qualification demonstrates restored bytes; it does not make timings universal.

## Release and live presentation

The immutable release is [v0.1](https://github.com/yasha1971-coder/hw-apex-bench/releases/tag/v0.1).
Its identities and asset hashes are in [the release receipt](../release/v0.1-receipt.json).
The live publication manifest hashes current presentation files as well as data;
changing documentation hashes does not change the historical measurement provenance.
The separate full-run artifact contains 236 native rows; the untimed BGZF audit
closes its three backend-dependent differences without rewriting that run.

[Complete report](RESULTS/FULL_REPORT.md) · [Audits](AUDITS/README.md)
