# Axis 3 window-law diagnostic

For every valid in-process cohort row add the diagnostic model

`R ≈ D_Q / (W + Q − 1)`

where `D_Q` is one-thread full sequential decode throughput (uncompressed output bytes/s) measured for the same codec/configuration on the same ace-core run, `Q` is the measured mean uncompressed independently decoded block/granule, and W is the requested window size (256, 4096, 65536, 1048576).

Predicted p50 latency is `(W + Q − 1)/D_Q`. Report:

| format | N | W | Q | D_Q | predicted p50 | measured p50 | error % |

Signed error = `100 × (measured − predicted)/predicted`.

Rules:
- CPU in-process, GPU in-process and CLI remain separate scopes. Never use CPU D_Q to predict GPU or CLI.
- D_Q is measured with exactly one decode thread for the CPU model. GPU requires a separately declared GPU full-decode D_Q and residency boundary.
- Q comes from actual archive/index geometry and is averaged over the cohort weighted by uncompressed bytes represented, not by assembly count.
- AGC: Q must describe the minimum independently decoded unit actually touched by the chosen getctg/getset path; if that unit cannot be established, prediction is n/a with reason.
- BGZF: derive Q from actual BGZF block uncompressed sizes across the cohort.
- ACEAPEX open: derive Q from actual block geometry. If literal/token chunking makes the effective touched unit larger than block Q, report both `Q_block` and `Q_effective`; the primary law row must state which one it uses.
- 2-bit capacity has no D_Q prediction until a measured accessor exists.
- ACEAPEX-refrel remains n/a until format freeze.
- Never import D_Q from another machine, thread count, decoder implementation, or historical run.
