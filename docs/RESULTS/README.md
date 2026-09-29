# Results by scope

- [Complete historical CPU report](FULL_REPORT.md): all former README tables,
  machine identity, methods, commands and review boundaries.
- [Nine-axis coverage](AXES_RESULTS.md): implemented, measured and unsupported points.
- [Batch matrix](BATCH_RESULTS.md): all measured profiles and request counts.
- [Five-point c(g)](CG_CURVE_RESULTS.md): separate baseline, revision and granularity sweep.
- [Default ACEAPEX refresh](DEFAULT_RESULTS.md): separate configuration and evidence.
- [ACEAPEX v2.1.0 / open refresh, 2026-09-30](ACEAPEX_UPGRADE_20260930.md): same-run matched-g legacy/v2.1/open vs BGZF plus open c(g).
- [Measured open-profile GPU evidence, 2026-09-29](GPU_OPEN_20260929.md): external runner Colab, chr1/T2T, bit-perfect, raw logs retained.

The 435 historical records are in [results.jsonl](../../results.jsonl).
[Native full-run comparison](../../review/native-full-comparison.json) retains
its original 98/101 verdict; the [untimed BGZF audit](../AUDITS/BGZF_BACKEND_REVIEW.md)
resolves the remaining backend difference separately.
Historical GPU declarations remain in the full report; the current measured open-profile GPU evidence is indexed above and documented in [GPU scope](../GPU.md).
XZ qualification is documented in [ADAPTERS](../ADAPTERS.md).

[Interactive explorer](https://yasha1971-coder.github.io/hw-apex-bench/)

Separate follow-up: [T2T regional density, 2026-09-16](T2T_REGIONS_20260916.md),
30 windows / 90 restored archives; not part of the historical 435-row snapshot.

[T2T granularity sweep and BGZF block audit](T2T_GRANULARITY_20260916.md):
same 30 windows, five block/frame sizes, 300 restored archives. At comparable
approximately64KiB blocks, ACEAPEX's HOR ratio exceeds BGZF's; the earlier
16KiB cross-preset loss is retained and explained, not generalized to the codec.

[Window-local T2T c(g)](T2T_WINDOW_CG_20260916.md): verified one-window baselines
complete the five-point curves for HOR, controls and terminal context. This is
not a whole-T2T baseline or a latency comparison; the full-genome gate is explicit.
