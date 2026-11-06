# HWAB-PICK-3b — pick with a cross-codec Pareto front, chrX record (2026-11-06, ace-core)

Preregistration: yasha-context HW-APEX-BENCH/CALIBRATION.md (commit b648b6c), written before the run.
Code: branch hwab-pick-3 at d23be88 (`pick: select Pareto frontier across all codecs`) + corpora.json entry
`t2t_chm13v2_0_chrX_record` (record `>CP068255.2 Homo sapiens isolate CHM13 chromosome X`, offset 2 936 814 021,
156 187 863 B, sha256 46acaa78…3eb240; t2t.fa md5 cd1e52ce… checked).

Adapter receipts: `check/` (`./run.sh --check codecs/<codec>.sh`, real silence gate PASS before each, load1 0.20 / 0.27 / 0.31).
One machine (ace-core, AMD EPYC 4344P), `./run.sh --pick <corpus> --output-dir <dir>`, silence gate before each corpus.

## Attempt 1 — invalid (`attempt1-invalid/`)

Gate c failed: silesia_tar, zstd-seekable 4 KiB, p50 0.0253 ms against 0.0220 ms in PR #78 (+15.1 %, limit ±10 %).
Gates a, b, d held (`attempt1-invalid/gates-b-c.txt`). By the preregistration the run is invalid: the chrX result of
this attempt was not compared with the prediction; the run was repeated.

## Attempt 2 — valid (this directory)

Gates (before any comparison with the prediction):
- a) silesia_tar, enwik8 and chrX in the same run, same machine, the same 7 rows (bgzip 65 280 B; zstd-seekable and
  xz 4/16/64 KiB) on each — PASS;
- b) ratio and the SHA-256 of every archive of silesia_tar and enwik8 == archive-state.json of PR #78 — PASS (14/14);
- c) p50 of every silesia_tar and enwik8 row within ±10 % of PR #78 — PASS (largest: enwik8 xz 4 KiB -2.6 %);
- d) silence gate PASS before each corpus (load1 0.239 / 0.257 / 0.243) — PASS.
`gates-b-c.txt` (made by `gates.py` with NEW = this attempt's directory).

chrX, front across all codecs (`on_front` in pick.json; a row is on the front iff no other row has ratio >= and
p50 <= with one strict):

| row | ratio | p50 ms | p99 ms | on_front | predicted |
|---|---:|---:|---:|---|---|
| zstd-seekable 4 KiB | 2.690 | 0.0317 | 0.0353 | yes | yes |
| zstd-seekable 16 KiB | 2.802 | 0.0417 | 0.0466 | yes | yes |
| zstd-seekable 64 KiB | 2.940 | 0.0568 | 0.116 | yes | yes |
| bgzip 65 280 B | 3.170 | 0.0711 | 0.145 | yes | yes |
| xz 4 KiB | 2.810 | 0.222 | 0.231 | no (by zstd-seekable 64 KiB, bgzip) | no |
| xz 16 KiB | 3.177 | 0.314 | 0.328 | yes | yes |
| xz 64 KiB | 3.414 | 0.564 | 1.15 | yes | yes |

Prediction: 7/7 rows on the predicted side — hit. xz 16 KiB is on the front by 3.1768 against bgzip 3.1702 (+0.2 %).

Secondary observation (not a prediction): against chr1 (PR #78) every chrX row has ratio -3.3 … -5.3 % and p50
-2.1 … +3.3 %, inside ±10 % / ±25 %.
