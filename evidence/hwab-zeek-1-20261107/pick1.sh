#!/bin/bash
# one pick run under the silence gate: pick1.sh CORPUS_FILE OUTDIR [pick args...]
cd /home/aeterna/pubrepo/.wk/hwab-pick2
C=$1; O=$2; shift 2; mkdir -p "$(dirname "$O")"
until awk "BEGIN{exit !($(cut -d' ' -f1 /proc/loadavg)<0.3)}"; do sleep 15; done
python3 -c "
import sys,json; sys.path.insert(0,'.')
from review.axis3.verdict_data import capture_silence
r=capture_silence('/home/aeterna'); json.dump(r,open('$O.silence.json','w'),indent=1)
print('$(basename $O) silence', r['status'], r['reasons'], 'load1', r['snapshot']['load1']); sys.exit(0 if r['status']=='PASS' else 1)" || { echo "$(basename $O) GATE FAILED"; exit 2; }
( time ./run.sh --pick /tmp/hwref/corpus/$C --output-dir $O "$@" ) > $O.log 2>&1
echo "$(basename $O) pick rc $? load1_after $(cut -d' ' -f1 /proc/loadavg)"
