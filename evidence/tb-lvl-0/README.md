[written by ChatGPT (AI) at the author's request; checked by the author]

# TB-LVL-0: compact review package

Yakov accepted the [results](RESULTS.md) of [PR #98](https://github.com/yasha1971-coder/hw-apex-bench/pull/98) on 2026-11-28. This package transfers those results onto a new branch from main `705f686c88b93570f2b5cdd9393bf02c12dc54b3`. It replaces the 181-commit review branch with a compact, isolated change. No measurements were repeated.

## Reproduce the accepted artifacts

From the repository root, using Python 3.11 or newer:

```console
python -X utf8 -m unittest discover -s evidence/tb-lvl-0 -p test_replay.py -v
python -X utf8 evidence/tb-lvl-0/replay.py --check
```

The replay verifies the archive and its original Git commit/tree membership, checks every member's path, mode, length and SHA256, and checks the visible copies against their frozen originals. It restores the original layout in a temporary directory under `.work`, runs the unchanged saved-data audit, regenerates the analysis/table, then runs the audit again. All three accepted output files must reproduce byte for byte. It uses no codec executable, private corpus, Git command, network or Colab runtime.

The original `runner.py` and `build_static.py` are retained for source review. Use `replay.py` for this review; the historical runner is not an instruction to start another experiment.

| Accepted artifact | SHA256 |
|---|---|
| [RESULTS.md](RESULTS.md) | `e25d72e3e484d3606e4d47f4d5935b994f7492f878d06043ffb9fad8e4af6495` |
| [analysis.json](analysis.json) | `7eae0ddc10e9322e40930acf2c093d5651a7f61d194e9909d8da3f42b56f33bd` |
| [audit.json](audit.json) | `ab9755b1c5bb5cff3fc320a5d0273139463b1ea30b7ebe735694d1b3a165186b` |

The new [rebuild audit](rebuild-audit.json) records the replay and identity checks. [FILES.txt](FILES.txt) lists every file in the new change.

## What is preserved

[BUNDLE.json](BUNDLE.json) describes 3245 original Git blobs, totaling 100401327 bytes before compression, from source commit `25f9459c87485a1d47950ebea031e39ec441942a`. [evidence.tar.gz](evidence.tar.gz) retains every TB-LVL-0 source, raw attempt, poll, receipt, selected-unit manifest, build log, failed build attempt and original publication check. The only external members are the original build workflow and two frozen telemetry helpers required by the accepted audit. Their original paths are restored only inside the temporary replay tree. No older corpora or unrelated task history is added to the change.

The visible reports, calibration, protocol, audit/analysis sources, original run/build scripts and [build manifest](build/build.json) remain unchanged. The two helper [source copies](adapters/SOURCES.json) and the pinned TurboBench codec adapter are visible under `adapters/` for review. Git commit/tree proofs retain the provenance link without importing the old branch's commit ancestry.

The original calibration was committed as `fa8a9cf801b2dcf62356b5d9c00c23c680836d21` before measurement. Its saved GitHub receipt remains in the archive. This transfer is not a new preregistration. The [source-derived mapping amendment](GRID_AMENDMENT.md), including `owner_confirmed:false`, stays unchanged: TB fast1–8 = ACE API11–18. The registered grid has 50 configurations and 150 accepted main roundtrips; one separate method unit and one excluded LOADED attempt are retained. P1 remains MISS and P2 HIT.

## Scope and handoff

The measurements apply to the pinned `silesia.ref.tar` input, ace-core EPYC 4344P / CPU0, and input/archives in RAM. The original task-owned measurement groups were reaped by 2026-11-27T23:21:34Z. This rebuild performs saved-data checks only. The main branch and the accepted source branch are not rewritten; the existing historical evidence on main is unchanged. Keep the replacement PR draft for Yakov/controller review. Candidate tasks wait for Yakov's word.

HW's Colab limit is at most 20 units/month, as instructed by Yakov on 2026-11-28. The referenced `claude/BUDGETS_2026-11-28.md` and the `colab` CLI were unavailable in this environment; account usage is unknown. No Colab runtime is started for this local rebuild, so there is no task-owned Colab session to stop. The before/after `colab usage` availability checks are reported in the handoff.
