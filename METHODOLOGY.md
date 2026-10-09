# Compression access methodology

Status: review draft aligned with frozen protocol v1.1. This document does not
authorize measurements, a release, a Pages update or an external publication.

## Authority and immutable comparison contract

[PROTOCOL_AXIS3.md](review/axis3/PROTOCOL_AXIS3.md) is the canonical contract for
axes 3–5. [PROTOCOL_FREEZE.json](review/axis3/PROTOCOL_FREEZE.json) identifies its
exact bytes. This methodology explains that contract; it does not replace or
amend it. [RUN.md](review/axis3/RUN.md) describes implemented commands and their
remaining limitations. If any implementation or supporting document disagrees
with the frozen protocol, stop: do not publish non-comparable results with a
qualification. A semantic change requires a new protocol version and full rerun.

Before an official run, freeze the protocol, runbook, ordered source manifest,
exact request lists and optional diagnostic-W list. Record SHA-256 of their
bytes and the codec build receipts in evidence. Never amend a measured row by
silently replacing an input or a configuration. Old evidence stays historical
and byte-identifiable. Synthetic CI evidence remains labelled synthetic; it
must never become an ace-core performance row.

## Stock and equal-granularity configurations

Use the competitor's best documented stock configuration for the declared
workload. Record source pins, author-supported build instructions, compiler
flags, library versions and environment settings before the run. Failure to
reproduce that configuration produces FAILED with a reason, not a compromised
score. AGC cohort construction uses one create with all selected assemblies,
not a chain of append calls. Freeze input order and explicit sample/contig IDs.
AGC noref uses the first cohort member as internal seed; AGC t2t includes the
frozen external reference. N counts queried assemblies, not extra references.

Keep BGZF-default and BGZF-matched-g as separate configuration rows in the same
execution scope. Neither replaces the other. The matched-g writer flushes at
its declared raw input-byte boundary; the emitted block geometry, not a nominal
limit, determines the decode granules. ISIZE counts raw FASTA bytes, not Q in
canonical sequence bytes. Use the frozen FASTA-to-sequence mapping to obtain
canonical bytes represented in each actual block. Preserve the geometry and
its declared aggregation rule; do not relabel raw ISIZE as canonical Q.

Charge archives, frame indexes, FASTA .fai/.gzi sidecars, required references and
other access dependencies. A shared reference is counted once, never omitted.
Report total and per-queried-assembly stored bytes. Missing dependencies or
unestablished independent decode geometry must not become a valid model row.
Q is not the LZ lookback window; keep the latter in a separate column. AGC's
nominal segment size is not evidence of its actual independently decoded Q.

## Canonical bytes and coordinates

Truth is uppercase sequence bytes without FASTA headers or line separators.
Preserve the original source objects unchanged. A common request is
`(assembly_id, contig_id, start0, end0)`, using zero-based half-open coordinates
`[start0,end0)`. It is valid iff `0 <= start0 < end0 <= contig_length`; its length
is exactly `end0-start0`. A request never crosses a contig boundary.

Adapters translate only at the library boundary:

| Interface | Translated coordinates | Convention |
|---|---|---|
| Common request | `[start0,end0)` | 0-based half-open |
| htslib faidx_fetch_seq64 | `[start0,end0-1]` | 0-based inclusive |
| AGC range API | `[start0,end0-1]` | 0-based inclusive |
| One-based inclusive API | `[start0+1,end0]` | 1-based inclusive |
| Sequence-byte raw-offset API | `prefix+start0`, `end0-start0` | Canonical offset and length |

Record both canonical and translated coordinates with their conventions in
evidence. A native FASTA-aware reader may use a verified FASTA index internally;
raw FASTA offsets are never substituted for canonical coordinates. The external
request space is per contig even when a codec stores concatenated sequence bytes.
Do not clip, substitute another contig, shrink W or repair an invalid/empty
request. Such requests produce FAILED. Contigs shorter than W have no valid
starts for that W; sampling excludes those starts, not failures after decoding.

## Same machine and execution boundary

CPU in-process, GPU in-process and process-per-request CLI are separate scopes;
never rank across them. CPU in-process uses one persistent library handle and
one decode thread. Open/index/reference setup occurs outside window timing;
the reader operation, including its required lookups and decoding, remains
inside. Do not silently substitute a helper process, a decoded-data cache or a
different machine. Declare residency and use the same access/cache policy for
each comparable configuration.

The official host must be ace-core. Before running, retain hostname, uptime/load,
one-second process CPU deltas, frequency policy and available storage. The gate
requires load <0.5, storage >20,000,000,000 bytes, and no foreign process consuming
10% or more of one CPU over the sample interval. Keep thresholds and raw telemetry.
A passing sample is not proof of continuous quiescence. A GitHub-hosted runner
is not a substitute for ace-core, and a green PR does not authorize a measurement.

## Requests, timing and truth

The initial official cohort is HPRC N=4; N=50/all require separate explicit plans.
Freeze source URLs, source and FASTA hashes, assembly/contig IDs, lengths, ordering
and references. Sample uniformly over valid starts in eligible contigs across
the cohort. Use 10,000 requests per W, seed 20261003 and the recorded PRNG identity.
Reuse the same frozen requests and per-answer SHA for all eligible formats.

| W in sequence bytes | Role | Contributes model-B error verdict |
|---|---|---|
| 1 | CALIBRATION_ONLY | No |
| 1024 | VERDICT | Yes |
| 8192 | VERDICT | Yes |
| 65536 | VERDICT | Yes |
| Other predeclared W with 1 < W <= 65536 | DIAGNOSTIC_ONLY | No |

Time the reader call only. Immediately outside that interval, check the length
and SHA-256 of every canonical answer. Retain every request ID, canonical and
translated coordinates, expected/observed SHA and raw nanoseconds. Report
nearest-rank p50/p95/p99 and windows/s from the raw samples; do not drop slow or
failed observations. W=1 uses the same nearest-rank p50 convention for calibration.

For D_Q, independently perform full sequential decode of the same corpus with
the same format, configuration, archive, library and one decode thread. The
accepted B run plan in [tools/verdict_refrel3.py](tools/verdict_refrel3.py) fixes
three warmups and nine measured full decodes; verify every decode, including
warmups. Retain all measured times, their median/min/max and both native and
canonical output-byte counts. D_Q is canonical sequence bytes divided by the
median measured full-decode time, in bytes/s.

D_Q and Q use the same canonical sequence-byte domain as W for every format.
If native full decode emits serialized FASTA, framing removal, canonicalization
and SHA validation occur outside the timed decode boundary. State both output
domains and that boundary in evidence. A native sequence-byte full-decode path
is also valid. If neither implements the required boundary, the row is FAILED.
Do not count FASTA framing in D_Q's numerator or Q, or charge framing removal to
one decoder's timer and exclude it for another.

## Window law: primary B and secondary A

Let D_Q be the independent sequential throughput in canonical bytes/s and Q the
observed canonical-byte decode granule. Times below are in seconds; convert to
microseconds only for display. The primary model is B:

```text
t_B(W) = c0 + (W+Q-1)/D_Q
c0 = median(t(W=1)) - Q/D_Q
t_A(W) = (W+Q-1)/D_Q
error_B_percent = 100 * (measured_p50 - predicted_B_p50) / predicted_B_p50
```

The c0 probe is a separate 10,000-request W=1 random-position experiment, using
the same format, thread, corpus and seed rule. W=1 is excluded from the verdict
set. No coefficients are fitted to the 1/8/64 KiB observations or to additional
diagnostic windows. A changed codec or output domain needs its own c0 and D_Q;
do not reuse historical values from another implementation, configuration or host.

Only W = {1024,8192,65536} contributes to the p50 model-B error verdict. The fixed
criterion is |error_B_percent| <=20% inclusive at each of the three windows.
Both signs of the boundary are included. Retain predictions from both models.
An extra predeclared window is DIAGNOSTIC_ONLY: its prediction error does not
change the aggregate verdict. Freeze that W list before execution; it cannot be
selected from successful observations afterward.

### Applicability and diagnostic fallback

If c0<0, model B is FAIL for that format and c0 is reported unchanged. Do not
clamp it to zero, refit it, change the seed or discard the format. In this case
use secondary model A as the diagnostic reference only, not as a replacement
primary acceptance rule. Model A never affects the verdict. Its prediction may
be printed beside B, but cannot turn a model-B FAIL into PASS. For c0=0, B remains
applicable and its prediction equals A; the ordinary B criterion still applies.

The p50 prediction is a falsifiable model, not a theorem about medians. All
windows must remain byte-correct even when a latency model is outside its domain.
A negative c0 is a model failure, not by itself evidence of a decoding error.

## Model verdict, correctness and comparison coverage

Distinguish model FAIL from data FAILED. Correct output can fail the latency
prediction; retain that measured evidence with its model FAIL. A wrong SHA,
short/extra output, decoder error, malformed metadata, missing reference/index,
wrong pin/thread/scope or protocol drift makes the data row FAILED and suppresses
valid performance fields. This also applies to CALIBRATION_ONLY and
DIAGNOSTIC_ONLY observations: no correctness failure is waived as diagnostic.
A successful evidence-integrity verification is not a model-B PASS.

Include at least four non-ACEAPEX format families with valid data. BGZF default
and matched-g are two required configurations but one family, not two foreign
formats. Candidate families are BGZF, zstd seekable, indexed LZ4, OpenZL-seg and
AGC. Keep each configuration visible; do not cherry-pick successful variants or
omit failed ones to meet coverage. A failed prediction remains visible; a missing
or data-FAILED family does not count as valid coverage. The refrel3 comparison
also requires q4k and q16k, as specified in the B job. No claim of refrel3 model
success follows from synthetic tests, symbol checks or missing official logs.

## Evidence-derived reports and other axes

Regenerate tables and graphs from validated evidence and raw logs. Captions
contain source-log SHA-256. Keep the “where we lose” section, failures, exact
commands and storage ledger; missing evidence is not a victory. Report memory
only when the complete declared scope is captured. Do not invent times, peak
memory or storage from estimates labelled as measurements.

Axis 4 maps each query group explicitly to every selected assembly, verifies
each canonical response by SHA and reports the timing boundary and total stored
bytes. Do not infer contig homology or equate group timing including the SHA
judge with decoder-only latency. Axis 5 requires a clean baseline, 100 independent
one-bit mutations per format, the frozen seed rule, fresh process groups and the
10-second watchdog with resource limits. Pre-decode refusal requires an explicit
validation stage. A worker's successful process exit does not prove that its
output is correct. RUN.md distinguishes the available APIs/single-case worker
from complete official CLI experiments that still need separate implementation.
No availability smoke test, unit suite or prepared Q3 generator proves that all
native large-input, corruption or boundary checks have run.
