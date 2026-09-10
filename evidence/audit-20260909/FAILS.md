# Exact contract failures on EPYC 9V74

Command: `grep FAIL evidence/audit-20260909/reproduce.log`

```text
  FAIL parse_chained_percent       (exp 5.46)
  FAIL parse_run_median            (exp 4)
  FAIL batch_speedup_over_loop    4.8x (exp >=5x)
```

The first two follow `ModuleNotFoundError: No module named 'numpy'`.
They are failed checks without computed parse values, not measured departures
from 5.46% or median 4. The batch failure is a measured failure of the >=5x
same-machine predicate, and must not be dismissed as a missing dependency.

The exact batch row in the log is:

```text
uniform        5000  11.77 |       911.4       190.7 |    4.78x |       5486      26225
```

The script rounds that row to 4.8x for its claim. The log alone does not establish
whether the difference from other machines is hardware, scheduling or repeat
variation. No rerun has replaced this observation.

A separate script error also occurs at line 450: batch stdout overwrites `OUT`,
which is then used as the JSON output filename, causing `No such file or directory`.
The original script exits 1; its summary is 13 pass, 3 fail, 14 skipped.

[Complete original log](reproduce.log), SHA-256
`ed4fa1340ec1de1ae93515acd215f31931cb8ad62c564af39023d28c76725bcb`.
ACEAPEX SHA: `1b13df34ac8e839dd3232b59bc59560d689a435a`.
[Workflow](https://github.com/yasha1971-coder/hw-apex-bench/actions/runs/34417102681).

Benchmark interpretation: `parse_chained_percent` and `parse_run_median` are `skipped` with reason `missing numpy`; no numerical result was produced. The raw upstream log remains unchanged and still prints FAIL. Correcting that upstream contract is separate work.

Historical comparison: EPYC 9V74 measured 4.78x (log and command linked above). The user reports 13.3x on EPYC 4344P; it is declared, not a matched benchmark measurement because an exact command/configuration/receipt for that point has not been supplied here. These points are not used for this benchmark's pass/fail.
