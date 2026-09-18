# ACEAPEX interactive vs BGZF — exact matched-g legal corridor (2026-09-18)

**Current external random-access comparison.** This supersedes the earlier default-profile Pareto interpretation while retaining that run as historical evidence.

ACEAPEX uses the documented interactive entropy profile at every point:
`LIT_CHUNK=65536`, `FSE_CHUNK=4096`, `MIN_MATCH` unset, and
`ACEAPEX_BS=g`. BGZF is unchanged.

Same thirty frozen 2 MiB T2T-CHM13v2.0 windows, same resident 16 KiB request trace,
same in-process native wrappers, same x86 GitHub runner, and full byte-perfect
restore before timing.

| exact g (B) | ACE ratio | BGZF ratio | ACE p50 (ms) | BGZF p50 (ms) | ACE density gain | ACE latency penalty |
|---:|---:|---:|---:|---:|---:|---:|
| 4,096 | 4.682708 | 3.794020 | 0.129884 | 0.053380 | +23.42% | +143.32% |
| 8,192 | 5.010591 | 4.139526 | 0.135144 | 0.053901 | +21.04% | +150.73% |
| 16,384 | 5.219838 | 4.406650 | 0.136646 | 0.063028 | +18.45% | +116.80% |
| 32,768 | 5.344308 | 4.643726 | 0.151254 | 0.058850 | +15.09% | +157.02% |
| 65,280 | 5.412621 | 4.810834 | 0.173986 | 0.100158 | +12.51% | +73.71% |

Density is total input / complete stored bytes; BGZF includes `.gzi`.
p50 is nearest-rank over 18,000 verified resident requests per codec per point
(30 windows × 3 passes × 200 requests).

## What replaces the default-profile Pareto

ACE remains denser at every legal g and BGZF remains lower-latency at every legal
g on this workload, so the two current implementation paths remain Pareto-incomparable.
But the latency gap is materially smaller than in the default-profile run.

The interactive ACE/BGZF total-latency ratio is approximately:
**2.43×, 2.51×, 2.17×, 2.57×, 1.74×** from 4 KiB through 65,280 B.

ACE density advantage decreases monotonically as g grows:
**+23.42% → +21.04% → +18.45% → +15.09% → +12.51%**.

Absolute latencies are declared machine-specific. The portable comparison is the
same-run curve and ratios.

The shape again supports searching g near the application's request scale and below
it rather than assuming one universal block size. On this mixed-window run ACE's
minimum p50 is at 4 KiB; 4/8/16 KiB are close, then latency rises as g grows.
BGZF is also fastest in the small-g end and slows sharply at the legal ceiling.

## Correctness and boundary

All **300 codec/window/g archive configurations** restored byte-perfect before
timing. Total timed requests: **180,000**.

The exact legal corridor remains 4,096 / 8,192 / 16,384 / 32,768 / 65,280 B.
No compatible matched-g point above 65,280 B is admitted.

## Provenance

Measurement run: **35364484648** on AMD EPYC 7763, Linux
6.17.0-1022-azure x86_64, affinity CPU 0.

Each g has an independent checkpoint artifact; IDs, digests and result hashes are
in `evidence/matched-g-interactive-20260918/run-receipt.json`.

The workflow's five measurement points all succeeded. The final curve step used
the old `/tmp/matched-g` root by mistake and failed only during aggregation;
the committed curve was rebuilt from the five retained point artifacts without
rerunning measurements.

Historical default-profile result:
`docs/RESULTS/MATCHED_G_BGZF_20260918.md`.

Current interactive result:
`evidence/matched-g-interactive-20260918/curve.json`.
