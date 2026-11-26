[written by ChatGPT (AI) at the author's request; checked by the author]

# HW-REGION-2: owner-authorized admission amendment

Owner instruction, 2026-11-26, committed before any new admission attempt:

> T2T-15: 3 попытки LOADED из-за постороннего cc1plus ~99 % CPU; выдан новый бюджет 3 попытки для того же прохода

This amendment supplements the frozen [protocol](PROTOCOL.md) without changing
its source-bound historical bytes. The three old LOADED admissions in
`units/main/t2t-15/twobit_original_mask1.json` remain excluded and retained.
The same pass gets a fresh maximum of three actual attempts, separately named
`t2t-15-resume-1`, with identical reader binary, archive, seed and offsets.

Wait for admission rather than a fixed quiet window. While inadmissible, observe
load and foreign CPU every five minutes; do not consume an attempt on a waiting
observation. Start an actual attempt only after load1 minus T is at most 1.0
(T=1) and no foreign process exceeds 10% of one CPU in the one-second admission
observation. Exactly load1=2.0 and CPU=10% pass. Live process inspection errors
are errors, not a reason to waive admission. Keep every observation and decision.

After an inadmissible observation or an actual LOADED attempt, wait at least
300 seconds before the next admission observation. After a CLEAN unit, the
next unit can proceed directly to its admission check. Each actual attempt
uses one fresh passing observation; the unchanged shared-flock helper then
rechecks admission under the lock and records both boundaries. If conditions
change before or during that attempt, retain its LOADED receipt and outputs,
exclude it from results, and count it against the actual-attempt budget.

All LOADED attempts remain saved. No CLEAN cell is retaken: reuse all 96 retained
main cells and all 16 CLEAN method units. The original four-line calibration,
P1–P3, comparison criteria, host, CPU0, reader binaries, archives, trace and timer
scope are unchanged. Remaining cells keep their original maximum of three
actual attempts and use the same admission waiting procedure. No new library
source change, native rebuild or correctness/timing grid is introduced.

If the new budget is exhausted by three LOADED attempts, stop again, retain
the names and observations of foreign processes in the report, and leave the
next decision to the owner. Never start a fourth actual attempt or bypass a
blocked unit. No foreign process is stopped by this experiment.

The resume controller, ledger, passing/waiting polls and this amendment receive
their own source/commit bindings. Original execution sources and evidence stay
unchanged. A resumed final audit must verify all 31 corpora and 186 main cells,
including reuse of the original CLEAN cells and retention of the old blocked
budget; a partial integrity PASS cannot promote a complete comparison.
Keep PR #97 draft. No upstream post or merge.
