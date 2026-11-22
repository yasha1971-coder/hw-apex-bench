# HWAB-NBD-2b — compressed qcow2 (zstd, zlib) through qemu-nbd: cold 4 KiB read cost (2026-11-22, ace-core)

Follow-up of HWAB-NBD-1c (nbdkit-xz-filter): the same image, the same reads, the qcow2 compression formats.
Preregistration: yasha-context HW-APEX-BENCH/CALIBRATION.md 695f63c (predictions P1, P2), amendment d946992 (support
and ceiling fields only, predictions unchanged), both written before the run.
Run: scripts/run_template.sh of the aceapex repository (STATUS, watchdog, PID wait), `main.sh`, 22:56–23:10 UTC.
One machine: ace-core, AMD EPYC 4344P, Ubuntu 22.04. This evidence holds the qcow2 rows and the NBD overhead only; the
run script of the session went on to a measurement that is not part of this repository.

## Tools (`run/versions.txt`)
qemu-img / qemu-nbd 6.2.0 (Ubuntu 1:6.2+dfsg-2ubuntu6.31, an old release; current qemu may differ), libzstd 1.4.8,
zlib 1.2.11, nbdkit 1.24.1, libnbd 1.10.5 (python3-libnbd), liblzma 5.2.5 (gates), /usr/bin/time -v for peak RSS.

## Test image
Fedora 45 Cloud Base raw, 5 368 709 120 B, sha256 0b3aae677ecde8d27e1c43c154877faca5cec2172d519bb3556d8b17fe314f92
(`image/fedora45.raw.sha256`; the image of HWAB-NBD-1c, see its README). qcow2 images (`image/qcow2.sha256`):
`qemu-img convert -c -O qcow2 -o compression_type=zstd|zlib` with the default cluster (64 KiB): zstd 669 450 240 B
(convert 2.1 s), zlib 659 816 448 B (26.6 s). Data clusters (>= 1 non-zero byte), computed from the raw image before
the reads: 13 653 of 81 920.

## Method (harness/nbd_qcow2_probe.py, tests/test_nbd_qcow2_probe.py)
`qemu-nbd -r -f qcow2 -k <socket> <image>` (read-only; cache and aio at their defaults), a fresh server per (image,
repeat); libnbd client, 4 KiB reads, the plan of HWAB-NBD-1c at cluster granularity: A cold — a uniformly drawn data
cluster not among the last 8 clusters read; C warm — right after each A read, another 4 KiB in the same cluster.
N = 1 000 per series, seed 20261122, 5 repeats; per repeat p50 / p99, table = median of the 5. Every answer compared
with the raw image (SHA-256): 0 mismatches in 15 (image, repeat) runs. The images are in the page cache (the first
repeat reads them; later repeats as well). NBD overhead: `nbdkit file` on the raw image, same plan.
Silence gate (`silence.sh`) before every check, pick and (image, repeat): 20 PASS (3 check + 2 pick + 15 probe).
The harness test builds a synthetic image, checks the data map and 0 mismatches for both formats, and a negative
control (a raw image with one changed byte in every 4 KiB of data) must give mismatches and exit 1.

## Gates (before any comparison with the prediction) — PASS
- adapter receipts `--check` bgzip, zstd_seekable, xz: PASS (`run/check/`);
- `./run.sh --pick --g 1M,16M --region-size 4K`, xz rows against HWAB-ZEEK-1 r4K (`run/gates/gates.json`):
  silesia_tar 1M / 16M and enwik8 1M / 16M — ratio and archive SHA-256 equal 4/4, p50 −1.35 %, +0.40 %, +0.94 %,
  −0.44 % (tolerance 10 %). Archives of the gate runs are not kept here (as HWAB-NBD-1c).

## Result (`table.md`, `predictions.json`)

| image | file B | ratio | A p50 cold ms | A p99 ms | C p50 warm ms | C p99 ms | peak RSS MiB |
|---|---|---|---|---|---|---|---|
| qcow2 zstd (64 KiB) | 669 450 240 | 8.020 | 0.0407 | 0.1172 | 0.0344 | 0.1027 | 9.3 |
| qcow2 zlib (64 KiB) | 659 816 448 | 8.137 | 0.1597 | 0.2369 | 0.1533 | 0.2264 | 9.0 |
| nbdkit file on raw (NBD overhead) | 5 368 709 120 | 1 | 0.0139 | 0.0235 | 0.0139 | 0.0208 | 4.7 |

For scale, HWAB-NBD-1c (same image, nbdkit-xz-filter): cold A p50 27.1 ms at 1 MiB xz blocks, 275.5 ms at Fedora's
24 MiB, at ratios 8.62–8.89.

## Prediction vs fact
- P1 (qcow2-zstd cold p50 in [0.05, 0.5] ms): 0.0407 ms — **miss** (below the range; per repeat 0.036–0.043).
- P2 (qcow2-zlib cold p50 in [0.1, 1.0] ms and above qcow2-zstd): 0.160 ms, ×3.9 qcow2-zstd — **hit**.
- No repeat: the gates passed, the run is valid.
- Secondary (not predictions): warm C is close to cold A for both formats (zstd 0.034 vs 0.041, zlib 0.153 vs 0.160):
  a second read in the same cluster still decompresses it (qemu 6.2); NBD overhead 0.014 ms is a third of the zstd
  cold read.

Nothing was sent anywhere.
