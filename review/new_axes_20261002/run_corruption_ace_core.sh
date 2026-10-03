#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/../.." && pwd)
WORK=${1:-"$ROOT/.work/axes-20261002"}
mkdir -p "$WORK/source" "$WORK/corruption"
CHR1="$WORK/source/chr1.fa"
if [ -f "$CHR1" ]; then
  :
else
  curl --fail --location --retry 3 https://hgdownload.soe.ucsc.edu/goldenPath/hg38/chromosomes/chr1.fa.gz -o "$WORK/source/chr1.fa.gz"
  gzip -dc "$WORK/source/chr1.fa.gz" > "$CHR1"
fi
printf "%s  %s\n" 9465e0f0df6e2c6eb39729c39cee5465 "$CHR1" | md5sum -c -
head -c 16777216 "$CHR1" > "$WORK/source/chr1-16MiB.fa"
sha256sum "$WORK/source/chr1-16MiB.fa" > "$WORK/source/chr1-16MiB.fa.sha256"
ACE_SHA=${ACE_SHA:-091bb1e75aca7691e8b87db7f0fd8505e74739a0}
export ACE_SHA
bash "$ROOT/review/new_axes_20261002/build_ace_cpu.sh" "$WORK/ace"
{
  uname -a
  lscpu
  printf "scaling_governor "; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || printf "n/a\n"
  printf "scaling_cur_freq_khz "; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || printf "n/a\n"
  zstd --version
  lz4 --version
  bgzip --version
  samtools --version
  gcc --version | head -1
} > "$WORK/corruption/HOST.txt" 2>&1
for adapter in ace-cpu-xxh3 ace-cpu-no-xxh3 zstd-check zstd-no-check lz4-check lz4-no-check bgzip-crc; do
  mkdir -p "$WORK/corruption/$adapter"
  python3 "$ROOT/harness/corruption.py" --adapter "$ROOT/review/new_axes_20261002/adapters/$adapter.json" --input "$WORK/source/chr1-16MiB.fa" --archive "$WORK/corruption/$adapter/clean.archive" --out "$WORK/corruption/$adapter" --memory-mib 2048 --cases 10000
done
python3 "$ROOT/review/new_axes_20261002/render_corruption.py" "$WORK/corruption" > "$WORK/corruption/REPORT.md"
