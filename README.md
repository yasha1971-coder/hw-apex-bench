# hw-apex-bench — Compressed Access Benchmark

## First-table comparison held after audit

The initial table used FSE_CHUNK=32768, whereas the reference lowlat claim uses 4096. Its general performance conclusion has been withdrawn.

A controlled audit is complete: on the same reference API, archive and query trace, unchanged libseek gives 0.154 ms and the common API-only harness gives 0.153988 ms. The original reproduce_paper5.sh gives 0.151 ms on this CI machine (AMD EPYC 9V74). The first table's 0.282 ms is not a matched reproduction of that claim.

[Read the findings and configuration inventory](AUDIT.md), including the full reproduction script's failures and the exact scope of the successful audit. [Raw audit evidence](evidence/audit-20260909/) is preserved permanently.

The [original three-codec measurements](evidence/stage1-20260909/README.original.md) remain available as historical evidence from [report commit f9225cf](https://github.com/yasha1971-coder/hw-apex-bench/commit/f9225cfe98f4697fd2e66f31242b80033c11b466). Their full restores and checked regions passed byte equality. Performance comparability is a separate gate.

No further benchmark axes have been added. Public performance comparison will resume only with explicitly reviewed codec profiles and one operation contract for all codecs.
