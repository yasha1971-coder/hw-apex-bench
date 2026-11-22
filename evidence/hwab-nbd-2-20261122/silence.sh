#!/bin/bash
# silence gate (as HWAB-ZEEK-1 pick1.sh): wait for load1 < 0.3, then capture_silence must PASS. silence.sh <json out>
# A capture is a 1 s sample: a short burst of another process (on ace-core: other Claude Code sessions, ~12 % for a
# moment) fails it. So the gate waits for a PASS: up to 40 captures 15 s apart; thresholds unchanged; every attempt
# is kept in the JSON. No PASS in 40 -> exit 1 (STOP).
cd /home/aeterna/pubrepo/.wk/hwab-nbd2
until awk "BEGIN{exit !($(cut -d' ' -f1 /proc/loadavg)<0.3)}"; do sleep 15; done
python3 -c "
import sys,json,time; sys.path.insert(0,'.')
from review.axis3.verdict_data import capture_silence
tries=[]
for i in range(40):
    r=capture_silence('/home/aeterna'); tries.append({'status':r['status'],'reasons':r['reasons'],'load1':r['snapshot']['load1'],
        'foreign':[p for p in r['snapshot']['processes'] if p['cpu_percent']>=10 and not p['own_process']]})
    if r['status']=='PASS': break
    time.sleep(15)
r['attempts']=tries; json.dump(r,open('$1','w'),indent=1)
print('silence', r['status'], r['reasons'], 'load1', r['snapshot']['load1'], 'attempts', len(tries)); sys.exit(0 if r['status']=='PASS' else 1)"
