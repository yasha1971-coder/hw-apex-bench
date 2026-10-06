# Compression access methodology

Status: local review draft. No measurements are authorized by this document.

## One comparison has one immutable contract

Before any official run, freeze the protocol, runbook, ordered source manifest
and exact request list. Record the SHA-256 of their bytes in evidence. A changed
file is a new protocol/run version, never an amendment to an already measured
row. Old evidence stays historical and byte-identifiable. Synthetic CI evidence
must be labelled synthetic and must never become an ace-core performance row.

## Stock configurations and equal-granularity configurations

Report a competitor's best documented stock configuration for the declared
workload. Record the authors' build instructions, source commit, compiler flags,
library versions and any explicit environment variables. An adapter that cannot
reproduce this configuration reports FAILED with a cause; it does not report a
compromised score with a disclaimer. AGC cohort construction is one create with
all selected assemblies, not a series of append operations.

Where default and controlled conditions diverge, publish separate scopes.
BGZF-default uses ordinary BGZF writing. BGZF-matched-g additionally flushes at
the declared source-byte granularity. Neither row replaces the other. Inspect
actual emitted blocks: a nominal limit is not an observed average block size.
Store all archives, frame indexes, FASTA indexes and required reference storage
in the accounting ledger. A shared reference is counted once, never omitted.

AGC noref means no external reference: its first cohort input still supplies the
internal seed. AGC t2t explicitly includes the external T2T seed. The denominator
is the number of queried cohort assemblies; extra required reference storage is
still charged to the numerator. Input order and sample names must be frozen.

## Same requests, same machine, same execution boundary

Use one frozen request list and one sequence-byte SHA per request for all
eligible adapters. Coordinate conversion is adapter code, not a new request list.
Common coordinates are 1-based inclusive; AGC C API uses 0-based inclusive.
No clipping, substituting another contig, ignoring empty contigs or reducing W
is allowed to turn an invalid request into success. An unsupported request must
produce an explicit refusal. A wrong returned byte makes the result row FAILED.

CPU in-process, GPU in-process and process-per-request CLI are different tables.
Do not rank across them. CPU in-process uses a persistent library handle, one
decode thread, identical cache/warmup policy and declared residency. Do not
silently launch a helper process for one format. No work begins on ace-core
unless the recorded silence gate passes; a GitHub-hosted VM is not a substitute.

## Timing, truth and raw data

For window latency, time the reader operation only. Hash and length-check every
answer immediately outside that interval. Keep the per-request raw nanoseconds,
request ID, observed SHA and expected SHA. Emit p50/p95/p99 by nearest rank and
aggregate windows/s from raw samples. Failed rows retain diagnostics but have no
valid latency or throughput fields. Never drop failing or slow samples.

For D_Q, use the same decoder implementation, archive and machine as the window
row, exactly one decode thread, three warmups and nine recorded full decodes.
Verify each full output. Record the exact byte domain: sequence bytes and raw
FASTA-file bytes are not interchangeable. Median, min, max and all raw times are
retained; peak memory includes the stated handle/cache/output boundary.

## Window-law diagnostic

Use only R = D_Q/(W + Q - 1), without fitted multipliers or overhead subtraction.
Q is measured from independent decode units; LZ lookback window is a different
column. For unequal units retain the complete size geometry and state which
average is used. Where Q is not established, prediction is unavailable, not an
invented number. The reciprocal predicts a latency scale; calling it a p50
prediction is a testable heuristic, not a theorem about medians. Report signed
and absolute relative error and the fixed inclusive 20% verdict. CPU D_Q cannot
predict a GPU or CLI row.

## Evidence-derived reports

Regenerate tables and graphs from validated evidence and raw logs. Captions must
contain source-log SHA-256. Keep synthetic data separate. The “where we lose”
section is mandatory; it may state that no comparable baseline exists, but may
not call missing evidence a victory. Raw logs, failures, exact commands and
storage sidecars remain part of the review package. No tag, release, Pages
update or external post occurs merely because a draft PR becomes green.
