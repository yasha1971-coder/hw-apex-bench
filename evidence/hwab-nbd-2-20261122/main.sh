#!/bin/bash
# HWAB-NBD-2b main run on ace-core (prereg yasha-context 695f63c): gates first (as HWAB-NBD-1: xz 1M / 16M on silesia_tar
# and enwik8 against HWAB-ZEEK-1 r4K), then 4 KiB reads of compressed qcow2 (zstd, zlib) through qemu-nbd -> libnbd and
# the NBD overhead (nbdkit file on the raw image), 1 000 x 5, every answer checked against the raw image.
set -uo pipefail
E=/home/aeterna/pubrepo/.wk/hwab-nbd2/evidence/hwab-nbd-2-20261122; R=/tmp/hwab-nbd2/run; W=/tmp/hwab-nbd2
mkdir -p $R/gates $R/silence $R/check
cd /home/aeterna/pubrepo/.wk/hwab-nbd2
{ qemu-img --version | head -1; qemu-nbd --version | head -1; nbdkit --version; python3 -c "import nbd; print('libnbd', nbd.NBD().get_version())"
  dpkg-query -W -f='${Package} ${Version}\n' liblzma5 qemu-utils qemu-block-extra libzstd1 zlib1g 2>/dev/null; sha256sum /tmp/hwab-nbd/fedora45.raw; } > $R/versions.txt
grep -q 0b3aae677ecde8d27e1c43c154877faca5cec2172d519bb3556d8b17fe314f92 $R/versions.txt || { echo "STOP: raw sha256"; exit 7; }
for a in bgzip zstd_seekable xz; do
  bash $E/silence.sh $R/check/silence-$a.json || { echo "STOP: silence gate before check $a"; exit 2; }
  ./run.sh --check codecs/$a.sh > $R/check/check-$a.log 2>&1 || { echo "STOP: check $a failed"; exit 6; }
done
for c in silesia.tar enwik8; do
  bash $E/silence.sh $R/silence/gate-$c.json || { echo "STOP: silence gate before $c"; exit 2; }
  ( time ./run.sh --pick /tmp/hwref/corpus/$c --output-dir $R/gates/$c --g 1M,16M --region-size 4K ) > $R/gates/$c.log 2>&1 \
    || { echo "STOP: pick $c failed"; exit 3; }
done
python3 evidence/hwab-nbd-1-20261121/gates_nbd.py $R/gates evidence/hwab-zeek-1-20261107/r4K || { echo "STOP: gates FAIL - the run is not valid"; exit 4; }
python3 harness/nbd_qcow2_probe.py --raw /tmp/hwab-nbd/fedora45.raw --image qcow2-zstd:$W/fedora45-zstd.qcow2 --image qcow2-zlib:$W/fedora45-zlib.qcow2 \
  --n 1000 --repeats 5 --seed 20261122 --overhead --out $R/probe --silence "bash $E/silence.sh $R/silence/probe-\$(date +%s%N).json" \
  || { echo "STOP: probe failed"; exit 5; }
echo "ALL DONE"
