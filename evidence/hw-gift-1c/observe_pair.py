"""Prepare receipts, then select one CLEAN pair under the shared OVH lock."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

import timing as pair

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PUBLIC=HERE/'timing'
sys.path.insert(0,str(ROOT/'evidence/hw-gift-1b'))
import ovh_bench


def check(ok,message):
    if not ok:raise ValueError(message)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def immutable_copy(source,dest):
    data=source.read_bytes();dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():check(dest.read_bytes()==data,'published timing receipt changed')
    else:dest.write_bytes(data)


def prepare():
    value=pair.selfcheck()
    check(value['status']=='PASS' and value['clock_calls']==0,'untimed selfcheck did not pass')
    immutable_copy(pair.STATE/'build.json',PUBLIC/'native-build.json')
    immutable_copy(pair.STATE/'selfcheck.json',PUBLIC/'selfcheck.json')
    print('UNTIMED_NATIVE_SELFCHECK_PASS',flush=True)


def run():
    saved=pair.build(allow_create=False)
    check(saved['request']['protocol_sha256']==sha(HERE/'TIMING_PROTOCOL.md'),'timing policy changed')
    own=str(Path(__file__).resolve().relative_to(ROOT))
    check(not pair.study.git('status','--porcelain','--',own).strip(),'uncommitted pair orchestrator')
    check(sha(pair.STATE/'build.json')==sha(PUBLIC/'native-build.json') and
          sha(pair.STATE/'selfcheck.json')==sha(PUBLIC/'selfcheck.json'),'publish selfcheck before timed observation')
    summary_path=PUBLIC/'observation.json'
    if summary_path.exists():
        old=json.loads(summary_path.read_bytes())
        for item in old['attempts']:
            check(sha(PUBLIC/item['receipt_path'])==item['receipt_sha256'],'saved timing receipt changed')
            if item['result_path']:check(sha(PUBLIC/item['result_path'])==item['result_sha256'],'saved timed result changed')
        print('TIMING_REPLAY_WITHOUT_MEASUREMENT',old['status'],flush=True)
        return 0 if old['status']=='CLEAN' else 2
    check(0 in os.sched_getaffinity(0),'CPU 0 is unavailable')
    os.sched_setaffinity(0,{0})
    attempts=[];selected=None
    for number in range(1,4):
        folder=PUBLIC/f'attempt-{number:03}';folder.mkdir(parents=True,exist_ok=True)
        receipt=folder/'ovh-bench.json';result=folder/'pair.json'
        command=[sys.executable,'-B',str(HERE/'timing.py'),'worker','--output',str(result)]
        code=ovh_bench.run_locked(command,receipt,stdout_path=folder/'worker.stdout')
        record=json.loads(receipt.read_bytes())
        item=dict(attempt=number,status=record['status'],receipt_path=receipt.relative_to(PUBLIC).as_posix(),
                  receipt_sha256=sha(receipt),result_path=result.relative_to(PUBLIC).as_posix() if result.exists() else None,
                  result_sha256=sha(result) if result.exists() else None)
        attempts.append(item)
        check(code in (0,77) and record['status'] in ('CLEAN','LOADED'),'fatal worker/byte error; retained, never retried as load')
        if record['status']=='CLEAN':
            check(code==0 and result.exists(),'CLEAN pair has no complete result')
            selected=item['result_path'];break
        check(code==77,'LOADED helper exit mismatch')
    status='CLEAN' if selected else 'BLOCKED: load'
    summary=dict(status=status,selected_result=selected,attempts=attempts,logical_pairs=1,
                 retaken_pairs=int(len(attempts)>1),loaded_attempts=sum(a['status']=='LOADED' for a in attempts),
                 maximum_attempts=3,load1_threshold='2.0',decision='loadavg only; no elapsed-time gate',
                 native_build_sha256=sha(PUBLIC/'native-build.json'),selfcheck_sha256=sha(PUBLIC/'selfcheck.json'),
                 protocol_sha256=sha(HERE/'TIMING_PROTOCOL.md'),orchestrator_sha256=sha(__file__),
                 ovh_bench_sha256=sha(ROOT/'evidence/hw-gift-1b/ovh_bench.py'))
    pair.save(summary_path,summary)
    print('TIMING_PAIR_COMPLETE',status,'attempts',len(attempts),flush=True)
    return 0 if selected else 2


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare','run'))
    args=parser.parse_args();return prepare() if args.action=='prepare' else run()


if __name__=='__main__':raise SystemExit(main())
