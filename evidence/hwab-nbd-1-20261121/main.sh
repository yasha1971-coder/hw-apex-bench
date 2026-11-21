#!/bin/bash
# HWAB-NBD-1c main run on ace-core (prereg yasha-context adc245f + amendments 787a9d6, e49fc1b): gates first, then the probe.
set -uo pipefail
E=/home/aeterna/pubrepo/.wk/hwab-nbd1/evidence/hwab-nbd-1-20261121; R=/tmp/hwab-nbd/run; W=/tmp/hwab-nbd
mkdir -p $R/gates $R/silence
cd /home/aeterna/pubrepo/.wk/hwab-nbd1
# adapter receipts first (pick needs them; as HWAB-ZEEK-1 check/): build and verify, no timing
mkdir -p $R/check
for a in bgzip zstd_seekable xz; do
  bash $E/silence.sh $R/check/silence-$a.json || { echo "STOP: silence gate before check $a"; exit 2; }
  ./run.sh --check codecs/$a.sh > $R/check/check-$a.log 2>&1 || { echo "STOP: check $a failed"; exit 6; }
done
for c in silesia.tar enwik8; do
  bash $E/silence.sh $R/silence/gate-$c.json || { echo "STOP: silence gate before $c"; exit 2; }
  ( time ./run.sh --pick /tmp/hwref/corpus/$c --output-dir $R/gates/$c --g 1M,16M --region-size 4K ) > $R/gates/$c.log 2>&1 \
    || { echo "STOP: pick $c failed"; exit 3; }
done
python3 $E/gates_nbd.py $R/gates evidence/hwab-zeek-1-20261107/r4K || { echo "STOP: gates FAIL - the run is not valid"; exit 4; }
A=""; for g in 1 2 4 8 16 24 32 64; do A="$A --archive $g:$W/fedora45-g${g}M.raw.xz"; done
python3 harness/nbd_xz_probe.py --raw $W/fedora45.raw $A --n 1000 --repeats 5 --seed 20261121 --overhead \
  --out $R/probe --silence "bash $E/silence.sh $R/silence/probe-\$(date +%s%N).json" || { echo "STOP: probe failed"; exit 5; }
echo "ALL DONE"
