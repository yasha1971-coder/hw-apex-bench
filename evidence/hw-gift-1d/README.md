# HW-GIFT-1d: seekable source-size hint boundary

Follow-up to [HW-GIFT-1c](../hw-gift-1c/RESULTS.md), including the tiny-frame
ingestion reason for [zstd PR #3544](https://github.com/meta/zstd/pull/3544).
See [the unchanged preregistration](CALIBRATION.md), [execution protocol](PROTOCOL.md)
and [primary sources](SOURCE_PATHS.md). Results concern ace-core, CPU 0,
RAM-resident input/output and the pinned zstd 1.5.7 source, not disk ingestion.

The first commit contains CALIBRATION.md only. All timed stages must use the
shared blocking OVH-BENCH lock, load1 >2.0 exclusion and retained attempts.
No external issue is submitted; the repository PR remains draft.

Execution order on the isolated ace-core checkout:

Run every controller action through `taskset -c 0` with the pinned Python 3.12
interpreter from HW-GIFT-1b. For example, from the 1d checkout:

```sh
taskset -c 0 /home/ubuntu/hw-apex-bench-hw-gift-1b/.work/hw-gift-1b/venv/bin/python \
  -B evidence/hw-gift-1d/run.py method
```

The controller acquires the shared OVH lock for each timed pair itself; CPU
affinity is inherited by that helper and its native worker. Direct unpinned
worker invocation fails before reading a timing clock.

1. Commit instruments; `run.py prepare` builds outside the timing lock and checks
   known archive SHA, deterministic output, changed input and corruption.
2. `run.py method` performs the declared five same-writer timing-control pairs.
   A failed method gate stops before the grid.
3. `run.py cell --phase train --level L --frame G` for all 21 enwik8 cells,
   checkpointing and pushing each completed cell. Five counterbalanced A/B pairs.
4. `select_threshold.py` reads saved training results only. Commit selection.json
   and CONDITIONAL_PROTOCOL.md before conditional work or silesia observations.
5. If X exists, `--phase validate` tests original versus actual conditional on
   enwik8, five pairs per cell. `--phase holdout` tests silesia with five rotating
   original/nohint/conditional triples. A missing X skips conditional development
   but retains the full silesia original/nohint comparison.
6. Independent saved-data audit; generate RESULTS.md and the unsent issue draft.

Use the same interpreter and exact dependencies recorded in native build and
method receipts. `instrument.py` is the native API worker, `controls.py` contains
untimed controls, `run.py` retains/replays logical pairs, and `audit.py` independently
checks saved observations. Never invoke a worker directly to bypass the lock.
Finished CLEAN repetitions replay without new measurements. Incomplete/error
attempts require inspection; no data are silently overwritten.

Raw data are under requests/, selfchecks/, raw/, and cells/. Each summary binds
its selected result, all attempts, OVH boundaries and immutable input/build hashes.
Private full archives remain under `.work/hw-gift-1d/`, bound by SHA-256; complete
archive byte counts include the same checksum-bearing seek table in both variants.
