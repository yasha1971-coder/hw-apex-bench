# Axis 3/4/5 contract — frozen protocol v1

This protocol is frozen before official measurements. Its SHA-256 is recorded in evidence. Any semantic change requires a new protocol version and a complete rerun. Corpus manifests and run receipts are separately SHA-256 locked before execution.

## Pinned implementations

OpenZL 0.3.0: 32246b48faee46807f84183dac4db479089f5445, inner frame version 27.
The currently approved paired variants are:

| Variant | Level | LZ windowLog | Independent frame target Q |
|---|---:|---:|---:|
| l1_w64k | 1 | 16 | 65,536 |
| l1_w1m | 1 | 20 | 1,048,576 |
| l3_w64k | 3 | 16 | 65,536 |
| l3_w1m | 3 | 20 | 1,048,576 |

Do not silently expand this to an eight-point Cartesian product. Such expansion
is a new protocol version. Frame count is ceil(sequence_bytes/Q); sum of ulen
must equal sequence bytes. LZ window and independent frame size stay distinct.

AGC 3.2.4: e67e3fc865a459779118d3d4e9fbdf42c70ba75e. One stock create; explicit
assembly/sample and contig IDs. Common [start,end] is 1-based inclusive and is
translated to AGC [start-1,end-1], both endpoints included. t2t includes a frozen
external reference; noref uses the first cohort member as internal seed.

Refrel3 v1: 5b6d5cec0f5962a561ac48822a1b5c48793a5b47. q4k RR_BS=4096;
q16k RR_BS=16384. The upstream frozen source is not edited. A CLI-only adapter
cannot be labelled in-process. Native integration is required before that scope.

BGZF: use the existing repository HTSlib/libdeflate pins. Keep default writing
and matched-g explicit-flush writing separate. Charge .fai and .gzi. The actual
BGZF ISIZE distribution supplies Q, not the nominal format limit.

Zstd-seekable and indexed LZ4 must have pinned build receipts and an independent
frame index. Plain unindexed streams do not qualify as random-access adapters.
Their native integrations remain a prerequisite, not a synthetic timing proxy.

## Cohort and sequence domain

HPRC N=4 is the initial official cohort. N=50/all are separate explicit plans.
Order, exact source URL, compressed-source SHA, uncompressed FASTA SHA, assembly
ID, contig IDs, sequence lengths, required references and sample mapping are
manifest data. Window truth removes FASTA line breaks and uses the declared
uppercase sequence-byte domain. Preserve original source objects unchanged.

## Axis 3 — one window

W = 1024, 8192, 65536 sequence bytes; 10,000 requests per W; seed 20261003.
Sampling is uniform over valid starts across eligible contigs and assemblies.
Store the PRNG identity, coordinates and per-window SHA before decoding.
One persistent CPU library handle and one decode thread. SHA each answer;
nearest-rank p50/p95/p99; raw nanoseconds; aggregate windows/s; build wall time;
stored bytes including indexes/reference; total and per-assembly storage; peak
RSS. Window-law primary model B is t(W)=c0+(W+Q-1)/D_Q. D_Q is measured independently by full sequential decode with one thread on the same format/corpus. c0 is not fitted to window results: c0 = median(t(W=1)) - Q/D_Q, where W=1 is a separate 10,000-request random-position probe using the same format, thread and seed rule. W=1 is calibration only and is excluded from the verdict set W={1024,8192,65536}. If c0<0, model B is FAIL for that format and is reported unchanged. Secondary model A, t(W)=(W+Q-1)/D_Q, is printed beside B but never affects the verdict. For model B the absolute p50 prediction error threshold is <=20% inclusive. No coefficients may be tuned from the 1/8/64 KiB observations. The comparison must include at least four non-ACEAPEX formats; declared candidates are BGZF default, BGZF matched-g, zstd seekable, indexed lz4, OpenZL-seg and AGC.

## Axis 4 — each region across the cohort

Freeze N query groups. Every group contains one explicit coordinate mapping for
every selected assembly; no missing sample or guessed contig homology is
allowed. Use FASTA+faidx, AGC and refrel3 through the same execution scope. Report
complete-group seconds and total disk bytes. Every response is checked by SHA.
The recorded timing boundary states whether judge work is included; it cannot
be compared to decoder-only timing without a separate row.

## Axis 5 — application corruption

For each format use a clean archive that first passes the full truth check.
Produce 100 independent one-bit mutations. Position and bit derive solely from
seed=20261003 and case ID; normalized positions map to each archive's own length.
Never mutate the clean archive. Each case uses a fresh process group, 10-second
watchdog and declared memory/output limits. Distinguish decoder failure, crash,
hang, harmless success and success with wrong bytes (SILENT). Pre-decode refusal
requires an explicit validation stage; it is not inferred from an arbitrary exit
code. Archive/input hashes and each mutation's position/bit belong in evidence.

## Safety and failure

Before official use collect hostname, uptime/load, one-second process CPU deltas,
CPU frequency policy and available storage. Host must be ace-core; one-minute
load <0.5; available storage >20,000,000,000 bytes; no foreign process consumes
10% or more of one CPU over the sample interval. Record thresholds and raw
telemetry; do not substitute a heuristic “machine seems quiet” statement.

Wrong SHA, short/extra output, malformed metadata, missing reference/index,
ambiguous contig, invalid/empty request, unsupported granularity, wrong pin or
thread count, protocol drift, non-comparable scope, native test failure or an
unavailable adapter produces FAILED with a reason. Failed rows do not carry
valid performance metrics. CI includes corruption and boundary tests and >1.6
GiB inputs before ace-core. Gate 1 alone does not prove every later QA condition.
