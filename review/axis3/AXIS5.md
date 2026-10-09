# A7 corruption CLI

Use the frozen root `PROTOCOL_AXIS5.md` for population, physical mutation semantics,
classification precedence, resource limits and predeclared integrity verdict.
This bounded experiment tests the first per-assembly archive, or the whole AGC
cohort archive, using complete-contig requests. It is not a performance benchmark.

Use an Axis 4 native `plan.json` with immutable FASTA, archives, indexes, reference,
native library and build receipt. Select a nonidentical donor archive of the same
format. The synthetic helper builds the donor for AGC using the other stock mode.

```bash
set -euo pipefail
python3 -m tools.axis5 prepare --root "$ROOT" --plan plan.json \
  --donor donor.archive --out a7-prepared > "$ROOT/prepare-receipt.json"
# Record the returned SHA independently, outside mutable run evidence.
PREPARE_SHA=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sha256"])' "$ROOT/prepare-receipt.json")
python3 -m tools.axis5 corrupt --root "$ROOT" \
  --prepared a7-prepared/prepared.json --out a7-corrupt
python3 -m tools.axis5 run --root "$ROOT" \
  --corrupt a7-corrupt/corrupt.json --out a7-run
python3 -m tools.axis5 verify --root "$ROOT" \
  --evidence "$ROOT/a7-run/evidence.json" --prepared-sha256 "$PREPARE_SHA"
```

All output directories must be new, root-relative, writable paths. Failed clean
baseline decoding aborts rather than classifying an unavailable native reader as
a corruption refusal. Hash ON refuses before native open through an explicit
application SHA check. Hash OFF uses the same pinned native readers as Axis 4,
with a private target copy and unchanged private faidx/BGZF indexes; only the
original target SHA guard is disabled. Every OFF case starts a fresh process
rather than opening potentially corrupt native data in the controller process.

Evidence schema: `schemas/axis5-evidence-v1.schema.json`. Verify independently
rescans FASTA, checks the original SHA identities, recreates mutations, compares
worker target/index bytes and classifies all cases from output bytes and raw OS
results. OS observations are consistency evidence, not cryptographic attestation.
All failures retain files for investigation; no response sampling is used on A7.

For native synthetic creation and CLI acceptance:

```bash
set -euo pipefail
python3 -m tools.axis5_synthetic --root "$NEW_ROOT" \
  --family refrel3 --variant q4k --library "$SO" --encoder "$ENCODER" \
  --source-root "$PINNED_CLEAN_SOURCE"
```

Supported native families: refrel3 q4k/q16k, zstd-seekable, bgzf default,
fasta-faidx plain, agc noref/t2t. JSON Schema validation requires jsonschema 4.26.0.
Sources must match the pins and remain clean; unsupported or absent libraries
never select a Python or CLI decoding fallback. Seven local native result logs
and their hashes are in `review/axis3/results/a7-synthetic/`; complete raw case
artifacts and clean-patch acceptance receipts accompany the handoff ZIP.
