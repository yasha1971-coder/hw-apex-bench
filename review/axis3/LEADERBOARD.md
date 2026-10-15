# A8 evidence-only leaderboard generator

`tools/build_leaderboard.py` verifies complete evidence before writing any output.
It never starts a decoder or benchmark. Unsupported schemas, wrong hashes, failed
axis verification, duplicate format/variant evidence within an axis, or mixed
comparison conditions are fatal. No historical numbers, inferred hardware,
imputed zeros, winners or fitted values are supplied.

## Input catalogs and external anchors

Each input directory contains `leaderboard-input.json`:

```json
{
  "schema": "leaderboard-input-v1",
  "records": [
    {
      "evidence": {
        "path": "data/evidence/evidence.json",
        "bytes": 12345,
        "sha256": "EXTERNAL_EVIDENCE_SHA256"
      },
      "input_root": "data",
      "prepared_sha256": "EXTERNAL_PREPARE_SHA256"
    }
  ]
}
```

The example placeholders and size must be replaced with independently retained
identities. File refs are exact `{path,bytes,sha256}` objects. Evidence paths and
input roots are catalog-relative, traversal-free and symlink-contained. `table`
is an optional stable label matching `[A-Za-z0-9][A-Za-z0-9_.-]*`; it cannot
override comparison conditions or machine identity. An explicit catalog avoids
accidentally importing tamper-test files, receipts, plans or prepare documents.
Axis 4/5 require the external prepare SHA, not one inferred from mutable evidence.
Catalogs and SHA anchors provide byte consistency, not cryptographic authorship.

```bash
set -euo pipefail
python3 -m tools.build_leaderboard /absolute/input-a /absolute/input-b \
  --out /absolute/new-leaderboard
```

Output: `LEADERBOARD.md`, `leaderboard.csv`, `leaderboard.json`, plus exact source
JSON copies at `evidence/<full-sha256>/evidence.json`. Every row names that relative
file and its full SHA-256. Copies preserve the source bytes; verification still
requires the original companion data and external anchors. No local source paths,
run IDs, creation timestamps or commands appear in the three tables. Evidence
copies retain original provenance unmodified, including any recorded paths.

## Axis adapters

* Axis 3 `axis3-evidence-v1`: schema/hash validator, then the existing raw-log
  recomputation of correctness, counts, quantiles and throughput. PASS also
  requires all samples verified. Measured silence snapshots are re-judged.
* Axis 3 `window-law-verdict-v1`: the existing B-job `verify_result`, including
  raw decode/window hashes and model arithmetic. Requires `results.json` and its
  retained contract/log tree. Per-format canonical request sets must agree.
  Every window size has its own table. Valid FAILED entries carry no numbers.
* Axis 4 `axis4-evidence-v3`: independent FASTA verifier with external prepare
  anchor; input/storage ledgers and seeded response bytes are checked.
* Axis 5 `axis5-evidence-v1`: independent FASTA/classification verifier with
  external prepare anchor; all mutation, worker archive/index/output bytes and
  classifications are checked. Integrity FAIL remains visible as a valid result.

All displayed numeric values are copied from verified evidence or its hashed
plan/prepare companions. A8 computes only comparison identities and output
checksums. Synthetic latency/throughput/resource timing is not promoted to
performance metrics. Empty cells/null mean unreported; literal zero is emitted
only when present in verified evidence, such as an Axis 5 count.

## Comparison contract

Conditions bind axis/schema, evidence kind, scope, machine, protocol, corpus and
requests. Axis 3 also binds window size, cohort size, thread count, runbook and
recorded hardware/frequency policy. Axis 4 binds byte domain, timing boundary,
decoder threads, all FASTA identities and the full ordered request groups.
Axis 5 binds full-contig coordinates, corpus, seed, population and watchdog.
Hash ON/OFF have separate tables. Physical mutation offsets are format-dependent;
the common corruption contract remains the normalized seed/kind/index population.

Known machines with different requests, scope, protocol, corpus or hardware
cannot share a table: the generator refuses, rather than silently partitioning
an intended comparison. Separate explicit table labels can retain distinct
experiments without comparing them; duplicates within an axis still refuse.

Synthetic A6/A7 evidence has no machine identifier. Missing identity is never
interpreted as a common host: default tables are source-specific singletons.
Window-law synthetic entries additionally remain separate by format/variant.
Explicitly forcing unknown machines together refuses. Axis 5 also has no recorded
scope field; this is null/empty, not an inferred CPU claim. Measured Axis 4/B-job
machine IDs are taken only from verified silence snapshots. Hardware attestation
and recording additional A5 provenance require a future evidence version.

## Determinism and fixtures

Sort tables by stable ID, rows by literal format/variant/mode/window; JSON keys
are sorted, UTF-8 with LF and one terminal newline. CSV uses fixed columns and LF.
MD/CSV numbers use exact decimal spellings of the JSON values, without grouping,
scientific notation, locale or fixed-precision rounding. JSON retains numeric
types with Python's deterministic JSON float representation. There are no current
clock values or input-directory paths in the output. Changing input bytes changes
their SHA and is therefore a different input, even if extracted metrics agree.

`tests/fixtures/leaderboard/input` contains exact preserved A6 q4k/q16k and A7 q4k
native evidence/companions from the accepted A7 package. Its JSON is not rewritten
to hide original commands or timings. `expected/` contains byte-exact MD/CSV/JSON.
The native library is retained only to satisfy input SHA verification; the
generator never loads it. Unit tests cover both Axis 3 schema families, all
required refusals, valid comparable grouping, relocation/order determinism,
source-link hashes and synthetic metric isolation. Synthetic CI invokes:

```bash
set -euo pipefail
python3 -m tools.leaderboard_synthetic --out /absolute/new-synthetic-receipt
```

This verifies the fixture twice and compares all three outputs with the golden
files. GitHub CI execution is separate from local workflow acceptance.
