# HWAPEX v2.2.0 continuity checkpoint — 2026-09-30

## Read live state first

Repository: `yasha1971-coder/hw-apex-bench`; PR #61;
branch `upgrade/aceapex-v220`. Read main, PR state/head, workflow runs and
review threads before any new write. GitHub is authoritative for whether the PR
has merged; do not infer that from this pre-merge checkpoint.

## Frozen measurement boundary — do not repeat

Successful CPU/qualification Actions run: `36751391857`, completed 2026-09-30.
Run head: `a22075e3f3b51a012bb6dff34d5e5643e43e428f`.
Actual PR-merge checkout: `876c0bef8f7b2c2681e9bd9c94bd2c88d2b09688`.
Parents: main `ec6cd69a203057ba3c9b8219684f8ac7450c0718` and the run head.

CPU artifact: `11115186898`, SHA-256
`be1ce4937041678bf396bfd3c98a821417d141f717073a50477920e151681717`.
Qualification artifact: `11115131449`, SHA-256
`08d498dda02886a76924f0f59f37c1b13c4bd5687398775d714ff477ef26998a`.

ACEAPEX tag v2.2.0: `0a143cd64b35a802835f18c361f981968edf25a1`.
DOI: `10.5281/zenodo.23061934`. ADR-020: DNA default l1;
AX_ENC=chain is the old matcher inside v2.2.0, not a new v2.1.0 row.
Strict full-chr1 c_file(16 KiB): l1 **1.701752%**, chain **1.719814%**.

## Publication is committed

Evidence import commit: `2863f9da294444e6eb74faccfa60cb3b8f8eb4f9`.
Publication-only import run: `36771584516` (successful, not a benchmark).
All 24 original UTF-8 members are in
`evidence/aceapex-v220-cpu-20260930/`, with original paths, sizes and hashes in
`receipt.json`. The generated `publication-check.json` verifies 20 codec/g rows,
600 archive configurations, 360000 region samples, 120000 amplification samples,
1800 full-decode samples and 4 c(g) archive records without executing a codec.

The report is `docs/RESULTS/ACEAPEX_V220_20260930.md`, indexed in the results
scope index. Ratio, p50/p99, amplification, break-even and c(g) have separate
tables; GPU is a separate measured-import scope with the missing raw-log caveat.
GPU source commit is `27b61b1430715e47848cea6d54a333b2f1642334`, external Colab,
RTX PRO 6000 Blackwell, median of three, upstream-reported bit-perfect.
GPU numbers are not independently reproduced by this publication.

Historical 2.1.0 and earlier evidence, the original 435 rows, main README and
Pages data are unchanged. There is no first-screen promotion in this PR.
The ratio excludes BGZF sidecar bytes only for this explicit assignment;
sidecar sizes/hashes are retained, not the original .gzi binary files.
Qualification and measurement CLI hashes differ and are explicitly disclosed.

## Safe checks and merge boundary

The measurement workflow `aceapex-v220-refresh.yml` is manual-only. Do not
run it to fix documentation, CI or publication. The publication workflow is
read-only and has no automatic commit, download or codec execution step.

```sh
python3 review/aceapex_v220/publish.py --check
python3 review/aceapex_v220/test_publication.py
python3 review/aceapex_v220/check_gpu_import.py
python3 web/validate_publication.py
```

Before merge, require all final-HEAD CI checks to pass, inspect the complete
changed-file list and review threads, record the review, and merge with an
expected-head guard. Confirm PR.merged and main afterward. If already merged,
this upgrade is complete; do not start another experiment or external post.
