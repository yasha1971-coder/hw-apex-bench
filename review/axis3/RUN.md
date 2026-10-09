# Axes 3–5 operator runbook — protocol v1.1

Status: A2/S5 runbook for the existing entrypoints. This document does not
implement a new decoder or authorize a measurement, push, tag, release or post.
Apply/review this series and its CI before using the measurement command.
Commands labelled **checks on ace-core** have not been executed as benchmarks by
this patch producer. Historical evidence is read-only.

Authority: [PROTOCOL_AXIS3.md](PROTOCOL_AXIS3.md) and
[PROTOCOL_FREEZE.json](PROTOCOL_FREEZE.json). Canonical protocol SHA-256:
`4a0027fec59b3252dc07b29458a57a5a451957f1b64b36f3927765cbc6be7a5c`.
[VERDICT_JOB.md](VERDICT_JOB.md) defines the B plan, receipts and reader paths.
[METHODOLOGY.md](../../METHODOLOGY.md) is aligned with the frozen v1.1 contract.
It explains the method without replacing the protocol or authorizing a run.

## 1. What actually runs

| Operation | Implemented interface | What it does / limitation |
|---|---|---|
| Axis 3 windows, c0, D_Q and model verdict | `python3 -m tools.verdict_refrel3 prepare/run/verify` | Complete B job: common requests, persistent native readers, full-output SHA, raw logs, table and integrity verification. |
| Axis 4 cohort regions | `tools.axis4` | A6 CLI: explicit cohort groups, prepare SHA, silence-gated native run and independent verification. See [Axis 4](AXIS4.md). |
| Axis 5 single decoder case | `python3 -m review.axis3.native_d6_worker` | One subprocess, watchdog and byte/SHA classification. **SINGLE_CASE_ONLY**: not the complete 100-mutation experiment. |
| Axis 5 mutation loop | `tools.application_corruption.run_probes` | Python API for clean-baseline verification and 100 one-bit cases. No hash-bound multi-format/silence/evidence CLI exists at this revision. |

Do not invoke `python3 -m tools.cohort_region_engine` or
`python3 -m tools.application_corruption` and treat a zero exit status as a run:
these modules have no command-line dispatcher. The historical
`review/axis3/run_axis3_ace_core.sh` is **PREPARED_ONLY** and is not the B runner.
`RawFastaReader` is a preloaded truth reader, not a measured FASTA+faidx baseline.
A1's optional native-symbol SKIPs are not permission to skip an official format.
A missing library, reference, index or AGC geometry is FAILED, not a timing proxy.

This runbook completes documentation of available commands. It does not claim
that axes 4 and 5 have a complete official launcher, that all formats passed Q3,
or that symbol availability is a native correctness test.

## 2. Working roots, interpreter and accepted builds

Run from the clean, **applied** repository root. Set these operator variables to
existing retained directories/files; their values are launch parameters, not
absolute paths embedded in manifests:

- `REPO`: repository root; `PYTHON`: absolute path to the selected Python 3
  interpreter with the CI-pinned `jsonschema==4.26.0` installed;
- `INPUT_ROOT`: retained HPRC N=4 sources, archives, indexes, libraries, receipts,
  `cohort.json`, `prepared/`, frozen `RUN.md` and `plan.json`;
- `EVIDENCE_ROOT`: output parent, outside tracked source files. Every run/case
  gets a fresh child path. Do not put `INPUT_ROOT` inside the output directory.

<!-- runbook-command:environment -->
```sh
set -euo pipefail
: "${REPO:?repository root}" "${PYTHON:?selected Python interpreter}"
: "${INPUT_ROOT:?retained input root}" "${EVIDENCE_ROOT:?evidence parent}"
cd "$REPO"
test -d "$INPUT_ROOT"
mkdir -p "$EVIDENCE_ROOT"
git status --short
"$PYTHON" -c 'from tools.verdict_refrel3 import harness_identity, REPO; print(harness_identity(REPO))'
"$PYTHON" -c 'from importlib.metadata import version; assert version("jsonschema") == "4.26.0"; print("jsonschema=" + version("jsonschema"))'
```

A clean **tracked** tree is enforced by B. Keep untracked run material outside
source directories; this check does not claim that untracked files were audited.
The correct plan `harness_commit` is the actual `git rev-parse HEAD` after this
patch has been applied and committed. It is not the producer's authoring SHA.
The tree/postimage identity is checked when receiving patches; an official run
additionally records the receiving session's real commit and tree.

Builds and native correctness checks happen before the host silence check. Keep
accepted archives and successes; rebuild only missing or outdated libraries.
Do not change pins or repeat already verified measurements. In particular B added
full-decode exports to the refrel3/BGZF libraries; a window-only `.so` is refused.

| Retained build | Existing build entrypoint (run through bash) | Important condition |
|---|---|---|
| refrel3 q4k/q16k | `review/axis3/build_refrel3_native.sh` | Argument: existing build directory containing `aceapex/` at the frozen pin; produces `libhwa_refrel3.so`. |
| BGZF default/matched-g | `review/axis3/build_bgzf_axis3.sh` | Argument: pinned build directory; produces `libhwa_bgzf.so` and `bgzip`. |
| OpenZL native | `review/axis3/build_openzl_native.sh` | Argument: retained OpenZL directory; produces `libhwa_openzl.so`. Base CLI build is `build_openzl_v030.sh`; it is not permission to replace retained archives. |
| LZ4 native | `review/axis3/build_lz4_native.sh` | Argument is the output `.so` **file**, not a directory; `LZ4_ROOT` names the retained 1.10.0 source tree. |
| AGC | `AGC_PLATFORM=native bash review/axis3/build_agc_v324.sh <dir>` | Argument: build directory; produces `libhwa_agc.so` and `agc-cli`; creation must be one stock create, not append. `AGC_PLATFORM` is required (sse2, avx, avx2 or native; CI uses avx2); local ace-core builds use `native` explicitly and the value is recorded in `<dir>/AGC_PLATFORM` for the evidence. |
| zstd-seekable | `codecs/zstd_seekable.sh` | Use its retained pinned resident-context build. B does not construct canonical archives/indexes on import. |

No build command in this runbook is part of a timed interval. Actual compiler,
flags, dependencies, source commit and library SHA come from build receipts,
not guessed versions or this table. OpenZL's optional dependency-version probe
can be unavailable; that is **not** a verified dependency version for an official
receipt. The mandatory build/link/round-trip checks remain required.

Native full-decode/window checks available from B (checks on ace-core): set the
file variables to the already built small synthetic archive/source/reference.
Use the exact `VARIANT` and matching `GRANULE_RAW_BYTES` for the archive.

<!-- runbook-command:check-refrel3 -->
```sh
set -euo pipefail
"$PYTHON" -m review.axis3.check_verdict_native --family refrel3 \
  --variant "$VARIANT" --library "$REFREL3_SO" --archive "$SYNTHETIC_ARCHIVE" \
  --source "$SYNTHETIC_FASTA" --reference "$SYNTHETIC_REFERENCE"
```

<!-- runbook-command:check-bgzf-default -->
```sh
set -euo pipefail
"$PYTHON" -m review.axis3.check_verdict_native --family bgzf \
  --variant default --library "$BGZF_SO" --archive "$SYNTHETIC_ARCHIVE" \
  --source "$SYNTHETIC_FASTA"
```

<!-- runbook-command:check-bgzf-matched -->
```sh
set -euo pipefail
"$PYTHON" -m review.axis3.check_verdict_native --family bgzf \
  --variant matched-g --granule "$GRANULE_RAW_BYTES" --library "$BGZF_SO" \
  --archive "$SYNTHETIC_ARCHIVE" --source "$SYNTHETIC_FASTA"
```

These check commands do not time codecs. They are not the full large-input matrix
for every format; retain Q3 acceptance evidence before an official comparison.

## 3. Freeze the real inputs before any decoder timing

Use one ordered `window-law-corpus-v1` `cohort.json` with exactly four distinct
HPRC assembly IDs, actual source URLs and source-object SHA-256, plus a `fasta`
file reference per assembly. A file reference has exactly `path`, `bytes`,
`sha256`; paths are normalized relative to `INPUT_ROOT`. Never substitute toy
sources, invented URLs, the ZIP SHA for a FASTA SHA, or another assembly order.
Source objects remain unchanged. LF/CRLF FASTA is supported; nonuniform wrapping
within a contig is refused by preparation, not repaired silently.

Copy this exact runbook to INPUT_ROOT once. The recipe is idempotent only for
identical bytes; it refuses a changed retained runbook. Run the block below from `REPO` after the environment block. This step only
copies/hashes text, not codec data.

<!-- runbook-recipe:freeze-runbook -->
```python
import json
import os
from pathlib import Path
from review.axis3.verdict_data import file_ref, verify_protocol
repo = Path.cwd()
root = Path(os.environ["INPUT_ROOT"]).resolve(strict=True)
protocol = verify_protocol(repo)
source = (repo / "review/axis3/RUN.md").read_bytes()
destination = root / "RUN.md"
if destination.is_symlink():
    raise SystemExit("retained RUN.md must not be a symlink")
if destination.exists():
    if destination.read_bytes() != source:
        raise SystemExit("RUN.md changed: select a new input/run directory")
else:
    with destination.open("xb") as stream:
        stream.write(source)
print(json.dumps({"runbook": file_ref(root, destination),
                  "protocol_sha256": protocol["sha256"]}, sort_keys=True))
```

B's `run` checks the hash of the **input copy** named by the plan; it does not
itself assert equality with the tracked RUN.md. The recipe and input-readiness
check below enforce that equality for this runbook. Do not edit its copy after
forming the plan. A source/protocol change needs a new prepared dataset; an
execution-plan/runbook change needs a new run identity. Do not amend old evidence.

Request preparation, with **no codec opens or decoder timings**:

<!-- runbook-command:prepare -->
```sh
set -euo pipefail
"$PYTHON" -m tools.verdict_refrel3 prepare --root "$INPUT_ROOT" \
  --manifest cohort.json --out prepared --windows 1,1024,8192,65536
```

This is the minimal calibration/verdict list. Omitting `--windows` produces the
optional powers-of-two sweep W=1,2,...,65536. Freeze that decision before use.
Each W has 10,000 shared requests, seed 20261003 and recorded PRNG identity.
An existing `prepared` directory is refused; reuse accepted requests rather than
regenerating them. Preparation prints the exact `prepared/prepared.json` file
reference for the plan; `prepared/corpus.json` and each `w<W>.jsonl` are hash-bound.

The canonical request is `(assembly_id, contig_id, start0, end0)`, zero-based
half-open. It never crosses a contig. Headers/line separators do not count as
bases. Truth is the SHA-256 of uppercase sequence bytes. htslib/AGC receive
`[start0,end0-1]` at their library boundary; both conventions appear in evidence.

### Plan assembly and readiness

Create `plan.json` as specified completely in [VERDICT_JOB.md](VERDICT_JOB.md).
This is an input artifact, not a command that B generates automatically. Required
fields are `schema=window-law-plan-v1`, unique `run_id`, actual `harness_commit`,
`scope=cpu-in-process`, `threads=1`, `seed=20261003`, `dq_warmups=3`, `dq_repeats=9`,
and hash-bound `runbook`, `prepared`, `variants`. The three/nine values are the
accepted B execution-plan contract, not a newly invented v1.1 protocol clause.

Each variant names the exact library and its real build receipt, archives and
required references/sidecars. Both refrel3 Q values and both BGZF configurations
are required. At least four **distinct foreign families** are required; default
and matched-g BGZF count as one family. RAW FASTA truth is not a foreign codec
for B coverage. AGC needs archive-bound canonical geometry evidence and its
source-log SHA, not nominal segment size. Without it AGC is FAILED and does not
count toward the four-family requirement. No successful AGC run is implied here.

Use the existing `file_ref` function to obtain references from actual files. Set
`FILES` in Python to the retained root-relative paths; for example, this block
prints the two references that every plan needs. It does not fabricate build
receipts or select codec settings.

<!-- runbook-recipe:file-references -->
```python
import json
import os
from pathlib import Path
from review.axis3.verdict_data import file_ref, resolve
root = Path(os.environ["INPUT_ROOT"]).resolve(strict=True)
FILES = ["RUN.md", "prepared/prepared.json"]
print(json.dumps([file_ref(root, resolve(root, name)) for name in FILES], sort_keys=True))
```

Readiness check after `plan.json` is complete (no `.so` loading, no decode, no
wall-clock sampling). It hashes all input references, so I/O can be substantial:

<!-- runbook-recipe:validate-inputs -->
```python
import os
from pathlib import Path
from review.axis3.verdict_data import checked_file
from tools.verdict_refrel3 import REPO, collect_file_refs, harness_identity, load_plan
root = Path(os.environ["INPUT_ROOT"]).resolve(strict=True)
plan, prepared, corpus, requests, protocol = load_plan(root, "plan.json", REPO)
identity = harness_identity(REPO)
if plan["harness_commit"] != identity["commit"]:
    raise SystemExit("plan harness_commit differs from actual applied HEAD")
runbook = checked_file(root, plan["runbook"])
if runbook.read_bytes() != (REPO / "review/axis3/RUN.md").read_bytes():
    raise SystemExit("plan runbook differs from tracked RUN.md")
for ref in collect_file_refs([plan, prepared, corpus]):
    checked_file(root, ref)
print("INPUT_HASHES_PASS; native readiness and live host gate remain required")
```

The Python recipes above are complete code blocks. Execute them with the selected
interpreter, from the repository root; the delivery tests compile and exercise
the recipes on tiny fixtures. They do not run measurement commands. `prepare`
does not authenticate source URL ownership or fetch the source object; the
source-retaining session must verify those source-object hashes separately.

## 4. Axis 3 / verdict_refrel3 — one official execution command

**Checks on ace-core; measurement authorization and accepted native/Q3 evidence
are required. Do not execute this during patch acceptance.** Set the output child
name once and never reuse a directory that already contains a partial/successful
run. The job refuses an existing output directory.

<!-- runbook-command:verdict-run -->
```sh
set -euo pipefail
"$PYTHON" -m tools.verdict_refrel3 run --root "$INPUT_ROOT" \
  --plan plan.json --out "$EVIDENCE_ROOT/window-law-B"
```

Execution order for each variant is independent full sequential D_Q (3 warmups,
9 recorded repetitions), then separate W=1 calibration and the frozen W sweep.
Every full output, including every warmup, is checked in canonical sequence
bytes **outside the timer**. D_Q uses canonical bytes, not FASTA bytes; raw native
output size and canonical size are retained. Q is independent canonical decode
granularity, never a relabelled raw BGZF ISIZE or LZ lookback window.

Model B is `t(W)=c0+(W+Q-1)/D_Q`, with
`c0=median(t(W=1))-Q/D_Q` obtained only from the independent probe. The W=1 p50
uses the protocol's nearest-rank convention; D_Q's nine run times use their
median. No coefficient comes from the verdict windows. If `c0<0`, retain it and
report FAIL. Secondary A is displayed but never controls the verdict.

| W role | Window sizes | Acceptance effect |
|---|---|---|
| CALIBRATION_ONLY | 1 byte | 10,000 requests, outside the model-error verdict. |
| VERDICT | 1024, 8192, 65536 bytes | Model B absolute relative error <=20% inclusive. |
| DIAGNOSTIC_ONLY | Other frozen W in 2..65536 | Prediction error is informational; no model-error vote. |

Signed error is `100*(measured-predicted)/predicted`. SHA mismatch, short/extra
answer or decoder failure at **any** W is FAILED regardless of W role. A valid
measurement can fail the model: `data_status=PASS` is not `verdict=PASS`.
The job contains no undocumented window warmup phase; archive/handle preparation
and the preceding D_Q series are the actual cache-order context. Do not insert a
silent warmup, reorder requests, drop slow samples or tune against verdict rows.

### Hardware, silence, memory, time and space

CPU scope only, host `ace-core`, one decoder thread, persistent library handles.
Before the bounded sequential job, B records a live snapshot and requires load1
<0.5, available bytes >20,000,000,000, and no foreign process using >=10% of one
CPU over the sampled interval. `silence-initial.json` records CPU model, uptime,
load, one-second process deltas and available frequency-policy data. A missing
frequency value is marked unavailable, not guessed. Do not use a GitHub VM or GPU
as a substitute for ace-core.

There is one initial preflight, not proof of continuous quiescence and not a
separate gate after each decoder (our own work would affect load). Capture any
external contention independently and reject non-comparable evidence rather
than inventing a corrected rate. The disk threshold is a safety gate, **not** a
capacity estimate for HPRC archives/reference/full-output buffers.

No elapsed-time or peak-memory estimate is supplied: **needs measurement on
ace-core**. Planning work counts are exact: for every variant, 12 full decodes
and `10000 * len(windows_bytes)` requests; at the four-point list this is 40,000
requests. A dependency/reference loader, source hashing, normalization, SHA,
evidence writes and the initial gate add untimed work. Native buffer allocation
boundaries are recorded by B; do not present its decoder-only sums as total job
wall time. B does not currently report a complete peak-RSS measurement.
Required memory includes resident archives/reference, native output, normalization
copies and codec workspaces; no numeric VRAM or RAM requirement is asserted.

### Output and failure handling

| Artifact below `window-law-B/` | Meaning |
|---|---|
| `results.json` | `window-law-verdict-v1` schema, real harness commit/tree, coverage and per-format statuses. |
| `<variant-id>/dq.jsonl` | Every warmup/recorded full decode, native/canonical sizes, SHA checks and raw ns. |
| `<variant-id>/w<W>.jsonl` | Every attempted request: canonical/translated coordinates, observed/expected SHA, raw ns or error. |
| `table.md` | Rendered from verified evidence, with raw-log SHA captions. |
| `contract/review/axis3/PROTOCOL_AXIS3.md` and `PROTOCOL_FREEZE.json` | Exact frozen protocol retained with results. |
| `silence-initial.json` | Live preflight. On gate failure this can be the only complete evidence file. |
| `SHA256SUMS` | Relative file paths; written after successful internal evidence verification. |

The original `plan.json`, `cohort.json`, prepared requests, runbook copy, receipts
and data remain in INPUT_ROOT. B retains their hash references but does not copy
all input bytes into output. Preserve **both roots**. B's `verify` reads the
schema from the current checkout, so use the same accepted checkout as the run.
A missing results/table/sums file after an early error is not a completed report.

Exit 0 from `run` means the comparison verdict passed. Exit 1 means B completed
but its comparison verdict did not pass; retain failing rows. Exit 2 is an input,
protocol, host-gate or handled operational error; inspect stderr and partial
artifacts. An unexpected exception can also yield nonzero status before a report
is complete: always inspect evidence, never infer completion from a code alone.
Do not delete a failed directory or rerun successful points automatically.

<!-- runbook-command:verify -->
```sh
set -euo pipefail
"$PYTHON" -m tools.verdict_refrel3 verify --root "$EVIDENCE_ROOT/window-law-B"
(cd "$EVIDENCE_ROOT/window-law-B" && sha256sum -c SHA256SUMS)
```

`verify` success means evidence is internally consistent, not that model B passed.
Read `results.json.summary.comparison_verdict` for that conclusion. Neither run
nor verify publishes anything. No performance value may be copied out of unit
tests or synthetic acceptance evidence.

## 5. Axis 4 — A6 CLI and explicit cohort mappings

[AXIS4.md](AXIS4.md) documents the official `tools.axis4` prepare/run/verify
commands, manifest and native-plan format, mandatory ace-core silence gate,
32-response byte sample and independent FASTA verifier. It also documents
synthetic acceptance, whose timings are never official measurements.

The existing `run_cohort` API remains available. A6 has its own streaming runner
so evidence includes complete-group raw times and bounded sample storage.
Every group still explicitly maps every assembly; no homology is inferred.

This command tests the original API with tiny synthetic data/artificial clocks;
use the A6 synthetic CLI acceptance for actual native reader coverage:

<!-- runbook-command:axis4-tests -->
```sh
set -euo pipefail
"$PYTHON" -m unittest discover -s tests -p test_cohort_region_engine.py -v
```

## 6. Axis 5 — available single-case diagnostic

`native_d6_worker` delegates to `decode_once`; the executable decoder argv is an
explicit caller input. There is no automatic all-codec decoder dispatcher. It
hashes the file written by that command **without normalization**. Therefore a
canonical `TRUTH_BASES` file requires a decoder command that actually writes
canonical uppercase sequence bytes. A refrel3 CLI returning serialized FASTA
cannot be compared directly to that truth; do not silently relabel its bytes.

One concrete available case is OZSEG CLI decode through the existing adapter.
Set `CASE_ARCHIVE` to a retained case copy (never mutate the clean original),
`TRUTH_BASES` to the canonical whole-assembly truth, `DECODED_CASE` to a new
scratch output path, `CASE_JSON` to a new JSON file and `OPENZL_HELPER` to the
retained pinned OpenZL CLI helper. The operation launches processes intentionally;
it is not a CPU in-process latency row. **SINGLE_CASE_ONLY**, checks on ace-core:

<!-- runbook-command:axis5-case -->
```sh
set -euo pipefail
: "${OPENZL_HELPER:?retained pinned OpenZL CLI helper}"
export OPENZL_HELPER
test -f "$CASE_ARCHIVE"
test -f "$TRUTH_BASES"
test -d "$(dirname -- "$CASE_JSON")"
test -d "$(dirname -- "$DECODED_CASE")"
if [ -e "$DECODED_CASE" ]; then
  echo 'refuse to overwrite an existing decoded-case artifact' >&2
  exit 1
fi
set -o noclobber
"$PYTHON" -m review.axis3.native_d6_worker --archive "$CASE_ARCHIVE" \
  --truth "$TRUTH_BASES" --output "$DECODED_CASE" --timeout 10 -- \
  bash "$REPO/review/axis3/openzl_adapter.sh" decode '{archive}' '{output}' \
  > "$CASE_JSON"
for artifact in "$CASE_ARCHIVE" "$TRUTH_BASES" "$DECODED_CASE" "$CASE_JSON"; do
  if [ -f "$artifact" ]; then sha256sum -- "$artifact"; fi
done
```

On caught/crash/hang the decoded file can be absent. The diagnostic hashes
only existing files; retain `CASE_JSON` even when no output was created.
This terminal diagnostic lists launch paths and is not a package SHA256SUMS;
use root-relative references in the final evidence manifest. `set -o noclobber`
protects CASE_JSON, and the explicit output-exists check is needed because the
worker normally unlinks its output path before decoding. Do not run concurrent
cases targeting the same output paths.

**The worker's process exit 0 is not a correctness verdict.** Read JSON `outcome`:
`harmless` means size and SHA match, `SILENT` means decoder exit 0 but wrong/missing
output; positive decoder exit is `caught`, a signal is `crash`, timeout is `hang`.
The limit is a fresh process group with a 10-second watchdog; memory limit defaults
to 2048 MiB and output cap to `max(1 MiB, 2*truth_bytes + 1 MiB)` in `decode_once`.
The CLI cannot adjust memory/output limits. These are **implementation limits**,
not an HPRC capacity recommendation; a limit hit is not proof of a codec bug.
There is no explicit pre-decode validation stage, so do not report `refused` from
an arbitrary exit code. SHA verification done by this worker is canonical only
when its given output and truth already satisfy that domain.

The worker neither checks ace-core silence nor freezes a 100-position mutation
plan. `run_probes` can generate 100 cases at seed 20261003 through its Python API,
but still lacks an official per-format input contract and host-gated CLI. The
complete Axis 5 comparison is therefore **NOT_OFFICIAL_READY** at this revision.
This documentation does not count a single case as the whole experiment.

## 7. Receiving patches and closing the run

Accept a patch by exact parent/base, file modes, preimage blobs, postimage SHA-256
and resulting tree. `git am` can change the committer/date and hence commit SHA;
do not require the patch author's commit object. Record the real applied HEAD in
subsequent measurement plans. Each following series is authored only after its
predecessor's accepted HEAD/bundle, not on an invented commit.

Required before official evidence is used: CI, actual native correctness on the
intended paths, completed applicable Q3 acceptance, frozen input identities,
authorized live ace-core gate, SHA on every answer/full decode, raw records and
an evidence-derived report. Native-symbol mocks test discovery/loading only.
Unittest counts and SKIP reasons are CI facts, not performance results. Preserve
failures and historical source hashes; do not replace v1.1 with another coordinate
or fitting rule in a runbook. A2 does not modify PROTOCOL_AXIS3.md or its FREEZE.
