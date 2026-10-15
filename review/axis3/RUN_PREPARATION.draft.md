# Run preparation — local draft, not an executable benchmark runbook

Native integration and the HPRC N=4 source manifest are still prerequisites.
No command for an unimplemented harness is invented here. The commands below
only freeze/verify already prepared contract files; they do not run benchmarks.

Run from a prepared evidence root containing protocol.md, RUN.md, cohort.tsv and
requests.tsv. The source manifest must already contain real source URL/SHA
pairs, not placeholders.

```sh
set -euo pipefail
python3 /path/to/hw-apex-bench/tools/run_contract.py freeze \
  --root . --output contract.lock.json \
  --protocol protocol.md --runbook RUN.md \
  --corpus-manifest cohort.tsv --requests requests.tsv
python3 /path/to/hw-apex-bench/tools/run_contract.py verify \
  --root . --output contract.lock.json
```

The absolute checkout location is a launch parameter only, not written into the
lock. Input references inside the lock are root-relative. An existing lock
cannot be replaced with changed content. A protocol change requires a new
version and a full new run; do not reuse old measured rows.

Outstanding before an official RUN.md can be frozen: connect the six native
adapters, verify all requested boundary/large-input/corruption tests, provide
HPRC N=4 and optional T2T source hashes, integrate real silence telemetry, and
expose reviewed CLI entrypoints for axes 3/4/5. The current local engines and
mock tests are not that finished integration.
