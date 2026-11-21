# Invalid attempts (2026-11-21) — harness / method errors, not part of the comparison with the prediction

All three ran under scripts/run_template.sh (aceapex repository) with the preregistration yasha-context
HW-APEX-BENCH/CALIBRATION.md adc245f + 787a9d6 + e49fc1b, unchanged. None of them is used for the verdict.

| attempt | stopped at | cause (method) | fix before the next attempt |
|---|---|---|---|
| 1-method | gate pick silesia_tar, 2 s | `pick` needs adapter receipts (`--check`), none in the new worktree | main.sh: `./run.sh --check` for bgzip, zstd_seekable, xz first (as HWAB-ZEEK-1 check/) |
| 2-silence | silence gate before the first check | one 1 s capture caught a burst of another Claude Code session on ace-core (pid 3102557, 11.8 % CPU) | silence.sh waits for a PASS: up to 40 captures 15 s apart, thresholds unchanged, all attempts kept |
| 3-harness | probe, repeat r0, g = 24M | the last block at g = 24 MiB is 8 MiB (5 GiB is not a multiple of 24 MiB); the A/C plan drew offsets within a full g -> `nbd_pread: request out of bounds` | plan_a_c: offset within the block's real length; test `test_last_block_shorter_than_g`; timing code unchanged (`nbd_xz_probe.attempt3.py` is the failed version) |

Attempt 3 passed `--check` and the gates (4/4) and measured repeat r0 for g = 1M…16M with 0 answer mismatches;
those partial numbers (`attempt3-harness/probe/`) were seen before the valid run. They are invalid: not compared
with the prediction. The valid run is the fresh one in this evidence directory (check, gates, 5 repeats, grid with 24M).

Pilot before all attempts: N = 5, 1 repeat (g 1M / 64M) on the real image in /tmp — numbers seen; the
preregistration was not changed after the pilot.
