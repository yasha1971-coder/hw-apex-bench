# ACEAPEX v2.1.0 / open-profile refresh — 2026-09-30

This refresh adds two current ACEAPEX configurations without rewriting the historical publication:

- **v2.1.0 interactive**, exact tag SHA `50723533be48a8d9ed42e4b0f9e1f9106ef169b7`;
- **main open**, exact SHA `ec3477877e7ed3f9792885a1a8beb26e48f4b717`, encoded with `AX_PROFILE=open`.

The old `1b13df3` publication remains historical evidence. A same-run `1b13df3` row is included below only as a control.

For the modern rows, region reads use the persistent C99 decoder handle
`aceapex_dec_open / aceapex_dec_region / aceapex_dec_close`. BGZF keeps its persistent
htslib context. Archive loading, context open, output allocation/prefault and warmups are
outside the per-request timer.

## Matched-g against BGZF

Corpus: the same thirty frozen 2 MiB T2T-CHM13v2.0 windows.  
Exact g: 4,096 / 8,192 / 16,384 / 32,768 / 65,280 B.  
Request: resident 16 KiB.  
Each codec/g: 30 windows × 3 passes × 200 requests = **18,000 verified samples**.

| g | codec | ratio | p50 ms | p99 ms | p50 / BGZF | density vs BGZF |
|---:|---|---:|---:|---:|---:|---:|
| 4,096 | ACEAPEX 1b13df3 interactive — legacy one-shot | 4.682708 | 0.136184 | 0.269816 | 2.57× | +23.42% |
| 4,096 | ACEAPEX v2.1.0 interactive — persistent | 4.682708 | 0.068290 | 0.135201 | 1.29× | +23.42% |
| 4,096 | ACEAPEX main open — persistent | 4.455378 | 0.211221 | 0.458329 | 3.99× | +17.43% |
| 4,096 | BGZF + htslib | 3.794020 | 0.052949 | 0.067827 | 1.00× | — |
| 8,192 | ACEAPEX 1b13df3 interactive — legacy one-shot | 5.010591 | 0.141694 | 0.263842 | 2.60× | +21.04% |
| 8,192 | ACEAPEX v2.1.0 interactive — persistent | 5.010591 | 0.067162 | 0.139417 | 1.23× | +21.04% |
| 8,192 | ACEAPEX main open — persistent | 4.879676 | 0.153141 | 0.467160 | 2.81× | +17.88% |
| 8,192 | BGZF + htslib | 4.139526 | 0.054550 | 0.071012 | 1.00× | — |
| 16,384 | ACEAPEX 1b13df3 interactive — legacy one-shot | 5.219838 | 0.143850 | 0.272584 | 2.20× | +18.45% |
| 16,384 | ACEAPEX v2.1.0 interactive — persistent | 5.219838 | 0.074632 | 0.149201 | 1.14× | +18.45% |
| 16,384 | ACEAPEX main open — persistent | 5.148826 | 0.176257 | 0.482423 | 2.69× | +16.84% |
| 16,384 | BGZF + htslib | 4.406650 | 0.065482 | 0.083762 | 1.00× | — |
| 32,768 | ACEAPEX 1b13df3 interactive — legacy one-shot | 5.344308 | 0.156778 | 0.303165 | 2.51× | +15.09% |
| 32,768 | ACEAPEX v2.1.0 interactive — persistent | 5.344308 | 0.083464 | 0.180311 | 1.33× | +15.09% |
| 32,768 | ACEAPEX main open — persistent | 5.307601 | 0.216979 | 0.529897 | 3.47× | +14.30% |
| 32,768 | BGZF + htslib | 4.643726 | 0.062581 | 0.142081 | 1.00× | — |
| 65,280 | ACEAPEX 1b13df3 interactive — legacy one-shot | 5.412621 | 0.210062 | 0.438012 | 1.93× | +12.51% |
| 65,280 | ACEAPEX v2.1.0 interactive — persistent | 5.412621 | 0.124668 | 0.277486 | 1.15× | +12.51% |
| 65,280 | ACEAPEX main open — persistent | 5.395254 | 0.271045 | 0.757243 | 2.49× | +12.15% |
| 65,280 | BGZF + htslib | 4.810834 | 0.108651 | 0.244448 | 1.00× | — |

All **600 generated archives** passed full byte-exact restore before timing. The run contains **360,000 verified timed region requests**.

## Does open remove the constant region cost?

**No in this implementation.**

The clean improvement is from the persistent v2.1.0 decoder lifecycle. Relative to the
same-run legacy one-shot control, v2.1.0 interactive cuts p50 by **40.65%–52.60%** across
the five g values. Its remaining p50 gap over BGZF is only **9.15–20.88 µs**.

Open then moves in the wrong direction for region latency:

| g | v2.1 interactive p50 µs | main open p50 µs | open adds µs |
|---:|---:|---:|---:|
| 4,096 | 68.290 | 211.221 | **+142.931** |
| 8,192 | 67.162 | 153.141 | **+85.979** |
| 16,384 | 74.632 | 176.257 | **+101.625** |
| 32,768 | 83.464 | 216.979 | **+133.515** |
| 65,280 | 124.668 | 271.045 | **+146.377** |

So the hypothesis that removing zstd frames would remove the remaining roughly constant
region overhead is **not supported by this sweep**. Open is slower than v2.1.0 interactive
at **5/5 matched-g points** and widens the gap to BGZF.

This does not identify which open decoder sub-step is responsible. No internal timers were
added; the result is an external same-run API comparison only.

A second loss is also visible: on these frozen T2T windows, open is **less dense** than
v2.1.0 interactive at all five matched g values, although it remains denser than BGZF.

## c(g) at 16 KiB — separate full-chr1 scope

For current main open on full hg38 chr1:

- 16 KiB archive: **68,998,725 B**, ratio **3.680293**;
- one whole-input block: **67,801,892 B**, ratio **3.745258**;
- **c_file(16 KiB) = 1.734573%**.

Historical strict default at `ee5a37e` remains **1.632267%**. Open is therefore
**+0.102306 percentage point** higher in this separate chr1 independence-cost scope.
The historical default evidence is retained unchanged.

## GPU — measured external evidence

The current GPU presentation is [GPU_OPEN_20260929.md](GPU_OPEN_20260929.md).

Those rows are imported byte-for-byte from `yasha1971-coder/aceapex/results`; they were
**not rerun by hw-apex-bench**. Every published row is labelled
**measured — external runner: Colab** and retains GPU identity, driver, CUDA, nvCOMP,
ACE commit, corpus identity, archive bytes and bit-perfect verdict from its source log.

Measured devices represented:

- Tesla T4 — chr1;
- NVIDIA L4 — chr1;
- NVIDIA A100-SXM4-40GB — chr1;
- NVIDIA A100-SXM4-80GB — chr1 and T2T;
- NVIDIA RTX PRO 6000 Blackwell Server Edition — chr1 and T2T.

GPU region seek remains **n/a** because these retained Colab logs do not measure it.
Missing GPU/corpus combinations are not synthesized.

## Provenance

CPU workflow: **Actions run 36641590388**.  
CPU artifact: **11066383397**, digest
`sha256:55c4e34f0728e8e6051a938a3bffd4375f6a9e74fa71461193e8f92f05e68314`.  
Host: **Intel Xeon Platinum 8573C**, Ubuntu 24.04 GitHub-hosted runner, CPU affinity 0.

Exact ACE pins:

- legacy control: `1b13df34ac8e839dd3232b59bc59560d689a435a`;
- v2.1.0: `50723533be48a8d9ed42e4b0f9e1f9106ef169b7`;
- current-main open: `ec3477877e7ed3f9792885a1a8beb26e48f4b717`.

Compact result: `evidence/aceapex-upgrade-20260930/results.json`.  
Run receipt: `evidence/aceapex-upgrade-20260930/run-receipt.json`.

The expensive refresh workflow is manual-only after the verified run. Existing historical
`results.jsonl` bytes and the old 1b13df3 publication are not rewritten.
