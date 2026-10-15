# Axis 4 native decoder workers (v0.3.0 draft)

Use `python3 -m tools.axis4 run --root ROOT --plan plan.json --out RUN
--decoder-threads N`. Explicit thread configuration produces evidence-v5;
omitting the argument retains the legacy evidence-v3/v4 contracts unchanged.
Prepared-v1 and compressed-truth prepared-v2 are both supported.

`decoder_threads` counts native decoder workers, not Python request concurrency
or total OS threads. The caller performs synchronous window requests and hashes
responses. BGZF uses one shared htslib pool of N workers for the whole cohort,
with queue capacity 2N per handle. htslib may also own I/O coordinator threads.
The pool size is checked using `hts_tpool_size`. All faidx handles are destroyed
before the shared pool. A native error is FAILED; a missing configuration API is
NOT_SUPPORTED. No request-executor emulation, codec replacement, or zero timings.

Current pinned reader APIs support a scalar decoder path for every family.
Only BGZF exposes native decoder worker configuration in these adapters.
refrel3, zstd-seekable, fasta-faidx, AGC, lz4-indexed and ozseg requests above one
worker produce explicit NOT_SUPPORTED evidence and do not start a decoder.
This describes the current pinned reader API, not all upstream codec APIs.

Evidence records observed CPU model strings and caller affinity. These are
telemetry claims, not independently authenticated hardware attestations.
Background workers inherit caller affinity at pool creation. No affinity changes
are silently applied. `--decoder-threads` accepts integers 1..256; 1/2/8/16 are
required acceptance points, not assumed observed OS-thread totals.

Independent verify scans the FASTA source, comparing every response SHA and all
sampled bytes exactly as in legacy Axis4. It never starts a decoder or creates a
pool. Thread capability is checked against the current adapter contract.
NOT_SUPPORTED diagnostics cannot pass correctness verification or become a
performance leaderboard row.

Leaderboard v5 conditions include decoder count, CPU models and affinity.
Different counts may have separate tables for the same format/variant; an
explicit common table label refuses mixed conditions. Duplicate observations
within one decoder count remain errors. Legacy duplicate rules are unchanged.

Native reordered request acceptance:

```sh
set -euo pipefail
python3 -m tools.axis4_threads_synthetic \
  --root ROOT --plan plan.json --out thread-experiment --repeats 20
```

Requires a SHA-pinned synthetic BGZF plan. Each of 20 independently seeded
request orders runs at 1/2/8/16 workers and receives independent verification.
Response identities (assembly, contig, coordinates, length, SHA) must match for
all 80 runs. Timings are correctness harness observations, not throughput claims.
The package log and SHA-bound run files are the source for actual counts.
