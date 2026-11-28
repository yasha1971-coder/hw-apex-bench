[written by ChatGPT (AI) at the author's request; checked by the author]

# TB-LVL-0 — pre-measurement calibration

Owner instruction: Yakov, 2026-11-27 20:29. First commit of this task contains
this file alone, before any method or main measurement. Consumer: Yakov and
CROWN-3. Decision: identify ACEAPEX levels on the measured density/decompression
frontier and density-nearest targets against misa77 0/1/3/4/5; show misa77 2 too.
Results apply to this input, reader builds, host and finite registered grid.

Foundations checked: docs/AGENTS.md, EXTERNAL_TEXTS.md, METHOD_PROGNOZ_ZADANIE.md,
HISTORY, STATUS, TOOL_ROADMAP and the existing TurboBench adoption reviews;
no prior TB-LVL-0 result or closed equivalent task was found. Live main is
705f686c88b93570f2b5cdd9393bf02c12dc54b3; HW-REGION-2 PR97 is merged. Primary
TurboBench source was checked before choosing command/parse semantics.

## Frozen sources, input and stop time

Build TurboBench 4aa97c8c37311e399ea3e7782c18c652c5bdb69f statically in this
repository's GitHub Actions. The owner-specified ACE source is dev commit
c53f3a04f3dbac8590e46a1f86c5fded1e69e065. The selected TurboBench tree's
recorded ACE gitlink is different (022af6126de42e63450a45557676ba30bfd6caa9);
the explicit ACE checkout override must be recorded, not hidden as upstream's
current pin. Retain every other codec gitlink, compiler/Go versions, flags,
source receipts and final binary SHA. No codec source tuning or host build.

Only corpus: /home/aeterna/golden/mixed/silesia.ref.tar, 211947520 bytes,
SHA256 a667bac80089b3d04d5496772149e632f0758974b0579d743cd8d6e5e0d63eb2.
Run on ace-core AMD EPYC4344P, CPU0, one CPU; archives/input in memory during
TurboBench's codec timers. MB/s means 1000000 original bytes per second.

Host must be released by 2026-11-28 06:30 Europe/Berlin = 05:30 UTC, including
lock waiters and children. Refuse new attempts from 05:25 UTC; watchdog TERM
only this task's process group at 05:29:40, KILL if needed at 05:29:50, reap
and release the lock by 05:30. At deadline report partial rows as incomplete,
stop and yield for ACEAPEX J5. Never stop or alter another session's process.

## Grid and pending level-name clarification

Requested set: aceapex_fast1-18; aceapex1-4; misa770-5; zxc1-7; lz4 1/3/9/12;
lzav1-2; minlz1/3/7; zstd1/3/9/15/19/22; brotli4/6/9/11; lzma9; bsc0e0;
kanzi5-8. This literal set has 60 configurations /180 main roundtrips.

Source inspection found TurboBench aceapex_fast supports only labels1-8,
mapping to ACE API11-18. A question is pending with the owner whether the task
means those eight rows, and forecast fast13-18 means API13-18 (=TB labels3-8).
If confirmed, freeze that mapping in an owner-reply amendment before any timer:
the grid then has 50 configurations /150 main roundtrips, including 12 ACE
rows. Unsupported labels9-18 must never silently fall back or be invented.
Until resolved, builds and correctness preparation may continue, but neither
the known-answer method timing nor main timing starts. Forecast probabilities
and numeric thresholds below remain unchanged after a naming clarification.

## Forecasts, from Claude before this run

P1 (75%): some default-profile ACE level with archive size27-33% of input is
not dominated versus zstd/brotli/lzma. Exact test: at least one aceapex1-4 has
27 <=100*compressed_bytes/input_bytes <=33 and no registered zstd/brotli/lzma
point has BOTH strictly fewer compressed bytes AND strictly greater median
decompression MB/s. The comparison subset is zstd6+bro tli4+lzma1=11 rows.

P2 (55%): fast13-18 are dominated on compression. Subject to the pending alias
confirmation, every one of API13-18 (TB fast3-8) must have a witness in the full
registered grid with BOTH strictly fewer compressed bytes AND strictly greater
median compression MB/s. P2 uses the compression axis, not the main D frontier;
this operational universal-six interpretation is fixed before seeing numbers.

PASS means HIT under these exact predicates; otherwise MISS. Any missing
required row means NOT TESTED / INCOMPLETE, never a forecast miss. No threshold,
probability or comparison universe is revised after viewing measurements.

## Method first, then exactly three external rounds

The first method-only aceapex_fast,1 native roundtrip must produce exactly
130490328 compressed bytes. This timed method check uses the OVH lock and is
excluded from the three main rounds. Input size/SHA and exact codec selection
must match first. Any mismatch, missing codec, byte-restore error or malformed
native result stops admission; keep all outputs, do not tune until it matches.

Each main configuration gets three fresh-process external roundtrips, fresh
empty cwd each time. Use TurboBench -i0,0 (one compression and one decompression
call), -C3 (full byte comparison), one whole-file block (1GiB > input), exact
input cap211947520B, and fixed verbosity/cache flags from the committed runner.
Retain native stdout, stderr and fresh .tbb. Never mix previous .tbb minimums.
Read .tbb ctime/dtime as seconds, not CSV fields with the same names (CSV prints
rounded MB/s). Use the highest-precision saved native times and exact rational
arithmetic for all comparisons; display rounding is last. Report median of
three sizes and median C/D throughputs; retain ranges if sizes vary.

Freeze execution order before the method timer: canonical sorted grid in round1,
reverse in round2, canonical rotation by floor(grid_count/2) in round3. No clean
slow result is rerun or discarded. Method roundtrip/known answer and controls
of parser, comparison and deadline/load gates precede the main table.

## OVH-BENCH admission and retention

Only a timed attempt holds blocking flock /run/lock/ovh-bench.lock. Builds,
hashing and correctness are outside the lock. Pin worker CPU0 and controller
CPU15. Record date -u, /proc/loadavg, nproc, CPU, kernel, governor and pin at
both boundaries; retain other-core /proc/stat delta as observational data.
LOADED if load1-T>1.0 (T=1) at either boundary, or a surviving foreign process
exceeds10% of one CPU in the one-second pre-start observation. Equality passes;
inspection errors are ERROR. Wait at least300s after an inadmissible poll or
LOADED attempt. Waiting consumes no attempt; recheck admission under the lock.

A LOADED attempt alone is repeated with the same input/configuration/round,
at most3 actual attempts, every attempt retained. Three LOADED => BLOCKED: load,
save ps top8 and stop for the owner. Worker errors/byte differences stop even
if loaded; no exception based on observed speed. Preserve every CLEAN pass and
checkpoint immediately, allowing resume without repeated measurements.

## Delivered comparisons and next action

Main D-dominance is the owner's strict rule: smaller archive AND faster D at
the same time. Equality in either coordinate is not dominance. Separately show
global D-front within the registered grid and local fronts in fixed5 percentage
point density bands [0,5),...,[95,100], with an explicit >100% overflow band;
empty bands stay visible. A local frontier need not be globally non-dominated.
Do not substitute the repository's historical weak-Pareto predicate.

For each misa77 level choose ACE by minimum absolute compressed-byte distance;
ties: greater D, then smaller compressed size, then canonical identifier. Show
signed archive gap in percentage points of input AND percent of misa size,
both D MB/s and signed/relative D gaps, computed before rounding. Same input
makes byte-nearest equal density-nearest; no handpicked speed target.

Deliver evidence/tb-lvl-0/RESULTS.md, exact machine-readable medians/frontiers,
raw roundtrips, all exclusions, source/build/input provenance and independent
saved-data audit. HIT => row candidates and bounded CROWN-3 targets; MISS =>
publish the losses and their witnesses. Incomplete/deadline => retain partial
evidence and yield. Keep outputs inside this repository; no upstream message,
release, merge or publication elsewhere. External prose uses the ChatGPT line.
