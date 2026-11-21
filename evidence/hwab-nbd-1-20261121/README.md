# HWAB-NBD-1c — nbdkit-xz-filter: cold 4 KiB read cost versus xz block size (2026-11-21, ace-core)

Question (E1): Richard W.M. Jones, guestfs 16.11 — "is there a better block size to recommend"; the speed of the
filter at different block sizes had not been measured.
Preregistration: yasha-context HW-APEX-BENCH/CALIBRATION.md adc245f, amendments 787a9d6 (N = 1 000 per g and series,
5 repeats) and e49fc1b (grid + 24M, support, ceiling, probabilities 0.45 / 0.7), all written before the run.
Run: scripts/run_template.sh of the aceapex repository (STATUS, watchdog 9 h, PID wait), `main.sh`, 11:49–17:50 UTC.
One machine: ace-core, AMD EPYC 4344P, Ubuntu 22.04. ACEAPEX is not part of this work.

## Tools
nbdkit 1.24.1 (Ubuntu 22.04 package — an old release; current nbdkit may differ), libnbd 1.10.5 (python3-libnbd),
liblzma 5.2.5 (the same library for the filter, the host `xz` and HWAB-ZEEK-1), /usr/bin/time -v for peak RSS.

## Test image (not opened before the run)
- Fedora 45 Cloud Base, the release's only raw.xz: `Fedora-Cloud-Base-AmazonEC2-45-1.4.x86_64.raw.xz`,
  604 092 132 B, sha256 e55e78f53fa7647505d564394538fcf3319ba4bae7d93f5d4ae32052b3b6f8a0 = official CHECKSUM
  (`image/`; the PGP signature of CHECKSUM was not checked). Raw: 5 368 709 120 B,
  sha256 0b3aae677ecde8d27e1c43c154877faca5cec2172d519bb3556d8b17fe314f92.
- Preset: `xz --robot --list -vv` — 214 blocks of 24 MiB, `--lzma2=dict=8MiB`, no BCJ, CRC64 (`image/fedora_xz_list.txt`).
  dict 8 MiB is -5 or -6; -6 (the xz default) was taken. Confirmed: `xz -6 --block-size=24MiB` of the raw image is
  byte-identical to Fedora's archive (`image/archives.sha256`). Fedora 45 uses 24 MiB blocks, not 16 MiB.
- Archives: the same raw, `xz -6 -T16 --block-size=g`, g = 1, 2, 4, 8, 16, 24, 32, 64 MiB (`image/recompress_sizes.txt`).
- Data blocks (>= 1 non-zero byte), computed from the raw image before the reads: 861 of 5 120 MiB.

## Method (harness/nbd_xz_probe.py, tests/test_nbd_xz_probe.py)
`nbdkit -f -U <socket> --filter=xz file <archive>` (xz-max-depth default 8), a fresh nbdkit per (g, repeat); libnbd
client, 4 KiB reads: A cold — a uniformly drawn data block not among the last 8 blocks read; C warm — right after
each A read, another 4 KiB in the same (cached) block; B — uniform over the whole image. N = 1 000 per series,
seed 20261121, 5 repeats; per repeat p50 / p99, table = median of the 5. Every answer compared with the raw image
(SHA-256): 0 mismatches in 45 (g, repeat) runs. NBD overhead: `nbdkit file` on the raw image, same reads.
Silence gate (`silence.sh`) before every check, pick and (g, repeat): 50 PASS (3 check + 2 pick + 45 probe).

## Gates (before any comparison with the prediction) — PASS
- adapter receipts `--check` bgzip, zstd_seekable, xz: PASS (`run/check/`);
- `./run.sh --pick --g 1M,16M --region-size 4K`, xz rows against HWAB-ZEEK-1 r4K (`run/gates/gates.json`):
  silesia_tar 1M / 16M and enwik8 1M / 16M — ratio and archive SHA-256 equal 4/4, p50 −0.6 %, +0.6 %, +1.1 %, +0.8 %
  (tolerance 10 %).

## Result (`table.md`, `predictions.json`)

| g | archive B | ratio | A p50 cold ms | A p99 ms | A p50/g ms/MiB | B p50 ms | C p50 warm ms | peak RSS MiB |
|---|---|---|---|---|---|---|---|---|
| 1M | 622 662 840 | 8.622 | 27.08 | 34.41 | 27.08 | 1.935 | 0.0241 | 16.2 |
| 2M | 617 687 448 | 8.692 | 51.52 | 69.08 | 25.76 | 3.719 | 0.0226 | 26.1 |
| 4M | 613 057 580 | 8.757 | 110.24 | 137.45 | 27.56 | 7.280 | 0.0242 | 48.3 |
| 8M | 609 063 636 | 8.815 | 143.54 | 272.01 | 17.94 | 15.62 | 0.0249 | 116.1 |
| 16M | 606 230 884 | 8.856 | 224.02 | 545.44 | 14.00 | 28.73 | 0.0262 | 157.3 |
| 24M | 604 092 132 | 8.887 | 275.53 | 803.53 | 11.48 | 42.96 | 0.0284 | 253.4 |
| 32M | 603 419 892 | 8.897 | 360.15 | 1 073.38 | 11.25 | 74.23 | 0.0285 | 301.3 |
| 64M | 602 547 976 | 8.910 | 596.64 | 2 128.37 | 9.32 | 140.86 | 0.0288 | 589.3 |
| nbdkit file on raw (NBD overhead) | 5 368 709 120 | 1 | 0.0138 | 0.0219 | — | 0.0141 | 0.0135 | 4.6 |

## Prediction vs fact
- Prediction 1 (A p50 / g in [5, 9] ms/MiB for every g): 9.3–27.6 ms/MiB, 0 of 8 in range — **miss**.
- Prediction 2 (p50(64M) / p50(1M) in [40, 80]): 22.0 — **miss**.
- Killer criterion: fired. No repeat: the gates passed, so the run is valid.
- Secondary (not predictions): B p50 below A on every g (zero blocks); warm C 0.023–0.029 ms (< 1 ms); ratio 8.62 →
  8.91 from 1M to 64M; peak RSS above g × 8 + base (base = 4.6 MiB, nbdkit file) on every g: +14 % (64M) … +69 % (8M).

## Invalid attempts and the pilot
`invalid-attempts/` (README there): three runs stopped by harness / method errors, not used; attempt 3 measured
repeat r0 for g = 1M…16M (numbers seen, invalid). `pilot/`: pilot N = 5, 1 repeat (g 1M / 64M) on the real image
was run before the main run in /tmp; numbers seen; the preregistration was not changed after the pilot.

Nothing was sent anywhere; a reply to Richard only by Yakiv's word.
