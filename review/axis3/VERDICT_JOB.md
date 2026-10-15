# B input contract and implementation boundaries

Authority: `PROTOCOL_AXIS3.md` and its updated `PROTOCOL_FREEZE.json`. Model B,
pins, canonical half-open coordinates and inclusive 20% threshold are unchanged.
The clarification only makes diagnostic/calibration roles explicit. New request
preparation is required because the frozen protocol bytes changed.

## Immutable file references

Every input reference has exactly `path` (normalized POSIX path relative to
INPUT_ROOT), `bytes` (file size) and `sha256` (lowercase digest). Absolute paths,
parent traversal, symlink escapes, duplicate JSON keys and changed files fail.
Input-source and output-evidence roots are distinct namespaces. `SHA256SUMS` in
output contains only paths relative to the output directory.

The operator creates `cohort.json` with schema `window-law-corpus-v1` and ordered
`assemblies`, each with `assembly_id`, a `fasta` file reference, original
`source_url`, and `source_sha256`. No fake source URL or digest is supplied by the
job. HPRC N=4 is the initial official cohort. The prepare command derives actual
contig IDs/lengths and full canonical hashes from FASTA and retains LF/CRLF-aware
truth offsets without retaining every sequence in RAM. Nonuniform wrapping is an
explicit preparation error, not guessed offsets. Existing objects are unchanged.

`plan.json` requires:

- `schema`: `window-law-plan-v1`; `run_id`: a unique filename-safe ID;
- `harness_commit`: the real applied clean Git HEAD, not a local patch-author SHA;
- `scope`: `cpu-in-process`; `threads`: 1; `seed`: 20261003;
- `dq_warmups`: 3; `dq_repeats`: 9 (explicit execution-plan values);
- `runbook`: the frozen copy of RUN.md, as a file reference;
- `prepared`: the file reference printed by prepare;
- `variants`: the explicit set of configurations below, in execution order.

Each variant has a unique safe `id`, `family`, `variant`, native `library` file
reference and `build_receipt` file reference. The receipt contains the actual
`source_commit`, `codec_version`, `compiler`, `flags` array, `dependencies` object,
`decoder_threads`:1 and `library_sha256`. These describe the real build, not this
schema example. Pinned families are checked against the existing repository pins;
LZ4 keeps retained version 1.10.0 with its full source commit from the receipt.

## Connections

| Family | Variant | Additional inputs / actual read path |
|---|---|---|
| refrel3 | q4k, q16k | `reference`; ordered `archives` rows with `assembly_id`, `archive`. Same persistent `hwa_rr3_fetch`; new `hwa_rr3_decode` loops frozen `block_v1` once per block with block hashes, no FASTA formatting/thread pool. |
| bgzf | default, matched-g | Ordered `archives` with `archive`, `fai`, `gzi`. Same pinned faidx path for windows; separate persistent BGZF cursor in the same library for sequential raw-FASTA decode. Matched-g also requires `granule_raw_bytes`; actual emitted block lengths must match. |
| zstd-seekable | retained configuration label | Ordered `archives` with `archive`, `contig_map`. Resident-context ABI, same seekable full-decode API. Contig map must be canonical sequence bytes and match the source order. |
| lz4-indexed | retained configuration label | Ordered `archives` with `archive`, `index`. Independent native LZ4 block decoder; no full-stream fallback. Index uoff/coff/ulen/clen must partition the source/archive with no gaps, overlap or extra bytes. |
| ozseg | l1_w64k, l1_w1m, l3_w64k, l3_w1m | Ordered `archives` with `archive`. The OZSEG table and contig prefix are checked; each touched frame uses the native OpenZL decode primitive. Paired level/window/Q fields must match the frozen four variants. |
| agc | t2t, noref | One `archive` (shared cohort), `reference` only for t2t, and `geometry` receipt. Same persistent public libagc path; full decode visits complete contigs in frozen order with one thread. Receipt must show selected mode, one create, zero appends, and exact `cohort_order`. |

A single assembly archive row can cover all its contigs but cannot impersonate
another assembly ID. Canonical and real shim/library coordinates are recorded.
The refrel3 shim ABI is half-open (the old CLI is one-based; the job does not call
that CLI). Missing whole-decode symbols demand a rebuild, not a fake full-decode
rate assembled from timings of random windows.

## Q in canonical sequence bytes

Refrel3 uses native header RR_BS as frozen for q4k/q16k. OZSEG uses its independent
frame target Q, with actual frame lengths (including the shorter tail) in evidence.
For BGZF, a FASTA offset/line-width map intersects actual raw member boundaries;
ISIZE is never relabelled as canonical Q. Zstd reads native seek-table geometry;
LZ4 reads its verified independent-frame index. For these variable-unit formats,
Q is the arithmetic mean of positive canonical unit lengths across the whole
cohort, not a mean of per-assembly means. Zero-canonical framing-only BGZF units
remain visible in geometry; they do not invent a positive base length.

AGC's public API does not expose an independently decodable canonical granule.
Therefore `geometry` must be retained real source-level evidence, schema
`agc-canonical-geometry-v1`, with `source_commit`, `archive_sha256`,
`domain`:`canonical-sequence`, a nonempty `independent_unit_definition`,
`canonical_unit_sizes` (nonnegative integers) and `source_log` file reference.
Its arithmetic positive-unit mean is the model Q. A target segment-size parameter,
metadata-pack size, or guessed value is not accepted as this evidence. Until
such an artifact exists, AGC is FAILED for this job and cannot contribute to the
four-family coverage requirement. This is not a claim that AGC has been measured.

## Timers, judge and failure

D_Q logs every warmup and measured full decode. Refrel3/BGZF full output buffers
are allocated outside the timer; the native fill is timed. The other public
reader paths retain their declared adapter materialization boundary. No FASTA
normalization or SHA is inside that timer; each assembly's native/canonical byte
counts and source SHA checks are logged afterward. The rate is canonical cohort
bytes divided by median of the nine complete-cohort intervals. Native/library
setup, source hashing and request preparation are outside window timing.

Window p50 uses the protocol's nearest-rank convention. c0 uses that independent
W=1 p50, not a fitted intercept. Primary signed error is
`100*(observed_p50-predicted_B)/predicted_B`. Role codes are CALIBRATION_ONLY,
DIAGNOSTIC_ONLY, VERDICT. Model-error failures differ from corrupted data:
valid observations with c0<0 or >20% model error retain their numbers and FAIL
model B; a wrong SHA/short read/decoder error produces data_status FAILED, null
D_Q/quantiles/predictions, and retained diagnostic raw logs. No sample is dropped.
A failed optional diagnostic *prediction* cannot fail the aggregate; a failed
optional diagnostic *byte check* must fail it.

Results distinguish data validity, refrel3's two-Q verdict and whole-comparison
coverage/verdict. Multiple BGZF configurations never satisfy multiple foreign
format slots. Missing formats remain FAILED with a reason, never optional SKIP
in an official run. CI's optional native smoke tests have a different purpose.

## Local versus CI proof

Local B tests exercise production orchestration and the judge with artificial
clocks and byte fixtures. They are never native throughput evidence. The existing
CI builds the pinned refrel3 and BGZF sources and now calls
`check_verdict_native.py` on the actual synthetic archives: full decode and
window SHA, without measuring a time. No upstream codec source or pin is edited.
Native build/run acceptance must come from the ace-core/CI environment with those
libraries. The job does not infer native success from .so symbol presence alone.
