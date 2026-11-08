# HWAB-ZEEK-1b — zstd-seekable frame size vs read size (2026-11-07, ace-core)

Preregistration: yasha-context HW-APEX-BENCH/CALIBRATION.md (commit 108f842), written before the run.
Code: branch hwab-zeek-1 at 1339a7d (`--g`, `--region-size`; pick.json records `region_size_bytes`, `zstd_level`).
One machine (ace-core, AMD EPYC 4344P), silence gate before each corpus run (`pick1.sh`, `main.sh`).

- `check/` — adapter receipts (`--check` bgzip, zstd_seekable, xz).
- `calibration/` — gate c calibration before the main run: 3 default silesia_tar runs, per-row p50 spread
  0.5–4.9 %, tolerance max(10 %, 2 × spread) = 10 % on every row (`gate-c-tolerance.json`).
- `default/` — default grid, silesia_tar and enwik8. `r4K/`, `r64K/` — `--g 64K,256K,1M,2M,4M,8M,16M`
  with `--region-size 4K` / `64K` on silesia_tar, enwik8, t2t_chrX record.
- `gates_z.py` → `gates.json`, `ratios.json`, `gates-and-ratios.txt`. Ratios are computed only after all gates pass.

## Gates (before any comparison with the prediction)
- a) default grid 7/7 measured rows on silesia_tar and enwik8, one host ace-core — PASS;
- b) ratio and SHA-256 of every default archive == PR #78 — PASS (14/14);
- c) default p50 within the calibrated tolerance (10 %) of PR #78 — PASS (largest: silesia_tar xz 64 KiB +3.8 %);
- d) silence gate PASS before all 8 corpus runs (load1 0.213–0.288) — PASS;
- e) zstd level 3 and read size recorded (4096 / 65536 / 16384) — PASS.

## zstd-seekable, p50 4K / p50 64K / p99 4K (ms), ratio

| g | silesia_tar | enwik8 | chrX |
|---|---|---|---|
| 64 KiB | 0.0407 / 0.0821 / 0.0953, 2.880 | 0.0447 / 0.0912 / 0.0916, 2.522 | 0.0571 / 0.1114 / 0.1132, 2.940 |
| 256 KiB | 0.1119 / 0.1674 / 0.2845, 3.042 | 0.1894 / 0.2007 / 0.2966, 2.636 | 0.2022 / 0.2255 / 0.3441, 2.902 |
| 1 MiB | 0.3144 / 0.3392 / 0.8888, 3.140 | 0.3550 / 0.4351 / 0.7591, 2.776 | 0.4757 / 0.4878 / 0.7909, 3.057 |
| 2 MiB | 0.5796 / 0.6010 / 1.5961, 3.165 | 0.7356 / 0.7135 / 1.4404, 2.800 | 0.8770 / 0.9655 / 1.5643, 3.060 |
| 4 MiB | 1.0656 / 1.1336 / 3.0244, 3.175 | 1.4715 / 1.5838 / 2.9146, 2.805 | 1.3623 / 1.7728 / 3.2252, 3.051 |
| 8 MiB | 2.0591 / 2.2711 / 5.6986, 3.184 | 2.8357 / 2.8882 / 5.8733, 2.808 | 2.9017 / 3.3486 / 6.2984, 3.047 |
| 16 MiB | 4.8388 / 4.4044 / 10.8789, 3.186 | 5.8832 / 5.2936 / 11.4118, 2.810 | 6.6241 / 6.6285 / 12.9267, 3.046 |

## Prediction vs fact

| corpus | p50(2M)/p50(256K) at 4K, pred [5.5, 8.5] | at 64K, pred [3.5, 6.5] | ratio gain 2M vs 256K, pred [1.0, 6.0] % |
|---|---|---|---|
| silesia_tar | 5.18 out | 3.59 in | 4.04 % in |
| enwik8 | 3.88 out | 3.55 in | 6.21 % out |
| chrX | 4.34 out | 4.28 in | 5.44 % in |

Result: miss (prediction 1 out on all three corpora, prediction 3 out on enwik8). By the preregistration the
conclusion for zeekstd is not filled and not sent. No repeat: the gates passed, so the run is valid.
