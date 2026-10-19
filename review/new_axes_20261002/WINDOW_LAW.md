# Axis 2 window-law diagnostic

Diagnostic model: `R ≈ D_Q / (W + Q − 1)`; predicted single-window latency is `t_pred = (W + Q − 1) / D_Q`.

For each format/corpus/in-process row measure on ace-core: `D_Q` = full sequential decode with exactly one decode thread, output bytes per wall-clock second; `Q` = mean uncompressed independently decoded block/granule from the actual archive/index; `W=5000`. Measured p50 remains the frozen value from evidence commit `7bd8e0091d0b54895abc5ad9b354ad7d5f7d5883`.

Error is signed: `100 × (measured − predicted) / predicted`.

C++ ACE and C99 ACE may share archive Q, but each decoder gets its own one-thread D_Q if their full-decode implementations differ. BGZF/htslib gets its own one-thread full-decode D_Q. CLI/process-per-request rows are excluded from the in-process law table unless a separate CLI model is measured.

Do not backfill D_Q from prior multithread, GPU, or differently scoped measurements. Missing D_Q means pending measurement, never an estimate.
