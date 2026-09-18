# Benchmark claim ledger

Identifiers here belong to hw-apex-bench (HWB), not the upstream ACEAPEX C-series.
Evidence status and publication/review status are separate. C-035 was referenced
by the owner; its exact statement and source have not been verified here.

## HWB-001 — Selected HOR windows have greater local granularity cost

Evidence: measured and hash-reproduced; publication: reviewed and merged in PR #43.
At 16 KiB, ACEAPEX 4915321 c_window(g) is 60.565% on the ten selected HOR
windows and 1.492% on ten chromosome-paired controls: a 59.073 percentage-point
difference between group aggregates. At 64 KiB the figures are 32.422% and
0.379%. HOR exceeds the paired control in all ten chromosomes at every tested g.
zstd-seekable also has a steeper selected-HOR response; its full table retains
exceptions in paired comparisons. This statement is about selected inputs.

Evidence and reproduction: [local report](RESULTS/T2T_WINDOW_CG_20260916.md),
[baseline audit](../evidence/t2t-window-cg-20260916/audit.json),
[retained sweep](RESULTS/T2T_GRANULARITY_20260916.md).
Use [c_window(g), not historical c_file(g)](CG_SCOPES.md).
No claim of measured latency, genome-wide effect, universal codec weakness,
statistical population significance, or first-ever scientific priority follows.

## HWB-002 — Longer useful references explain the HOR response

Status: plausible mechanism, NOT established by these measurements.
A block boundary can remove useful references. A repeat thousands of bases long
is not automatically unavailable in a 16 KiB block: distance, position and
remaining block length matter. The sweep changes more than reference reach:
block-table overhead, parser decisions and entropy statistics can also change.
The accounting attributes 20.7% of ACE's HOR stored-byte saving from 16 KiB to
1 MiB to header/table bytes and 79.3% to compressed streams. The latter is not
a measurement of long-reference contribution.

To test the mechanism separately, collect match-distance/length and boundary
statistics or a controlled parser experiment with byte-exact verification.
This would be new work, not a reinterpretation of current density results.
Inter-block references change the independence contract and must not be added
as a silent optimization. No upstream codec change is authorized by this ledger.

## HWB-003 — Larger HOR blocks improve the random-access trade-off

Status: OPEN; density gain measured, access costs not yet measured here.
Next sweep after corpus identity and first-run gates: reuse the same 30 frozen
windows and five granularities; measure native resident region p50/p99 and
actual decoded-byte amplification for ACEAPEX and zstd-seekable, with fixed BGZF.
Freeze identical request offsets/lengths, include within-block and boundary-
crossing reads, prepare indexes outside the timer, retain lookups and decoding
inside it, and verify every output outside timing. Record native decoder threads,
versions and complete archive identities; document unsupported counters as n/a.
Do not extrapolate from the historical chr1 latency table or publish a preferred
granularity until both density and access cost are observed on the same inputs.
