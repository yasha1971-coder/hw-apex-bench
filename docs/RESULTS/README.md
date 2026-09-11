# Results by scope

- [Complete historical CPU report](FULL_REPORT.md): all former README tables,
  machine identity, methods, commands and review boundaries.
- [Nine-axis coverage](AXES_RESULTS.md): implemented, measured and unsupported points.
- [Batch matrix](BATCH_RESULTS.md): all measured profiles and request counts.
- [Five-point c(g)](CG_CURVE_RESULTS.md): separate baseline, revision and granularity sweep.
- [Default ACEAPEX refresh](DEFAULT_RESULTS.md): separate configuration and evidence.

The 435 historical records are in [results.jsonl](../../results.jsonl).
[Native full-run comparison](../../review/native-full-comparison.json) retains
its original 98/101 verdict; the [untimed BGZF audit](../AUDITS/BGZF_BACKEND_REVIEW.md)
resolves the remaining backend difference separately.
GPU observations are retained in the full report and [GPU scope](../GPU.md).
XZ qualification is documented in [ADAPTERS](../ADAPTERS.md).

[Interactive explorer](https://yasha1971-coder.github.io/hw-apex-bench/)
