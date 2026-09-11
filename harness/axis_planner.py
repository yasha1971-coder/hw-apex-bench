#!/usr/bin/env python3
"""Plan adapter axes from current correctness receipts; never run measurements."""
import argparse
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import sys
from qualification import ROOT, digest, require_current, work_directory
from resident_probe import AXES

@contextmanager
def qualification_lock(work):
    work=Path(work)
    if not work.is_dir(): raise ValueError('no checked build directory; run --check first')
    with (work/'check.lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_SH|fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('adapter build/check is in progress')
        yield

def plan_adapter(adapter,work,axes):
    adapter=Path(adapter).resolve()
    if not axes or len(set(axes))!=len(axes) or set(axes)-AXES:
        raise ValueError('unknown, duplicate or empty axis selection')
    with qualification_lock(work):
        receipt,state=require_current(adapter,work)
        tasks=[]
        for axis in sorted(axes):
            capability=state['capabilities'][axis]
            supported=capability=='available'
            tasks.append({'axis':axis,'action':'schedule' if supported else 'skip',
                          'status':'eligible' if supported else 'n/a',
                          'reason':None if supported else capability.removeprefix('n/a — ')})
        return {'codec':state['codec'],'version':state['version'],
                'adapter':str(adapter),'work':str(Path(work).resolve()),
                'configuration':state['configuration'],
                'qualification_sha256':receipt['qualification_sha256'],
                'receipt_sha256':digest(Path(work)/'check.json'),'tasks':tasks}

def dispatch_adapter(plan,handlers):
    """Dispatch qualified axes to supplied backends; this function does not time calls.

    Validate the whole adapter before invoking any handler. Unsupported axes never
    reach a handler. Missing implementation is a blocking error, not codec n/a.
    Hold the checked-build lock for the entire call sequence and recheck state.
    """
    adapter,work=Path(plan['adapter']),Path(plan['work'])
    with qualification_lock(work):
        current=plan_adapter(adapter,work,[t['axis'] for t in plan['tasks']])
        if current!=plan: raise ValueError('plan is stale or modified; create a new plan')
        required=[t['axis'] for t in plan['tasks'] if t['action']=='schedule']
        missing=[axis for axis in required if not callable(handlers.get(axis))]
        if missing: raise ValueError('measurement backend not connected: '+', '.join(missing))
        outputs=[]
        for task in plan['tasks']:
            if task['action']=='skip':
                outputs.append(dict(task,value=None))
            else:
                # The backend receives explicit checked adapter/configuration context.
                value=handlers[task['axis']](plan)
                outputs.append(dict(task,value=value))
        if plan_adapter(adapter,work,[t['axis'] for t in plan['tasks']])!=plan:
            raise ValueError('checked state changed during dispatch; discard results')
        return outputs

def resolve_adapter(value):
    path=Path(value)
    if path.is_file(): return path.resolve()
    path=ROOT/'codecs'/(value+'.sh')
    if path.is_file(): return path.resolve()
    raise ValueError('unknown adapter: '+value)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--codec',action='append',help='adapter file or basename; repeatable')
    p.add_argument('--axis',action='append',choices=sorted(AXES),help='repeatable; default all nine axes')
    p.add_argument('--work',type=Path,default=ROOT/'.work/adapter-check')
    p.add_argument('--output',type=Path,default=ROOT/'.work/axes.plan.json')
    a=p.parse_args()
    try:
        if not a.output.name.endswith('.plan.json'):
            raise ValueError('plan output must end in .plan.json; it is not results.jsonl')
        adapters=[resolve_adapter(c) for c in a.codec] if a.codec else sorted((ROOT/'codecs').glob('*.sh'))
        if len(set(map(str,adapters)))!=len(adapters): raise ValueError('duplicate adapter selection')
        rows=[plan_adapter(c,work_directory(c,a.work),a.axis or sorted(AXES)) for c in adapters]
        plan={'schema':'cabench-axis-plan-v1','mode':'planning-only','timings_collected':False,
              'note':'eligible means correctness-qualified; measurement backends are not connected by this command',
              'adapters':rows}
        a.output.parent.mkdir(parents=True,exist_ok=True)
        # One completed plan, no partial output if any adapter fails eligibility.
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w',dir=a.output.parent,delete=False) as f:
            f.write(json.dumps(plan,indent=2)+'\n'); temp=Path(f.name)
        temp.replace(a.output)
        for row in rows:
            print(row['codec']+': '+', '.join(t['axis']+': '+(t['status'] if t['reason'] is None else 'n/a — '+t['reason']) for t in row['tasks']))
        print('Plan only; no measurements: '+str(a.output))
        return 0
    except (ValueError,OSError,KeyError) as exc:
        print('STOP: '+str(exc),file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main())
