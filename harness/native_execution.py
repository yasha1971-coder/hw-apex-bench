#!/usr/bin/env python3
"""Execute qualified resident measurements into a separate, unpublished artifact.

A single input gives decode samples, not a plateau headline. This command never
writes results.jsonl or replaces historical evidence. Failed runs retain logs,
but cannot produce a successful manifest.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shlex
import signal
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from axis_planner import dispatch_adapter, plan_adapter, resolve_adapter
from qualification import ROOT, clean_environment, output, work_directory


def execute(argv, *, stdout, stderr, timeout, env=None, check=True):
    process=subprocess.Popen(argv,stdout=stdout,stderr=stderr,env=env,start_new_session=True)
    try:
        status=process.wait(timeout=timeout)
    except BaseException:
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
        process.wait()
        raise
    if check and status: raise subprocess.CalledProcessError(status,argv)


def digest(path, algorithm='sha256'):
    h=hashlib.new(algorithm)
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def samples(path, phase, size):
    rows=[json.loads(line) for line in Path(path).read_text().splitlines()]
    expected=200 if phase=='region' else 5
    if len(rows)!=expected: raise ValueError('incomplete native samples')
    seed=20260909
    for _ in range(10): seed=(seed*6364136223846793005+1442695040888963407)&((1<<64)-1)
    for i,row in enumerate(rows):
        if row.get('verified') is not True: raise ValueError('unverified native sample')
        timing=row.get('latency_ms' if phase=='region' else 'wall_ms')
        if type(timing) not in (float,int) or not math.isfinite(timing) or timing<=0:
            raise ValueError('invalid native duration')
        if phase=='region':
            seed=(seed*6364136223846793005+1442695040888963407)&((1<<64)-1)
            if (row.get('query')!=i or row.get('requested_bytes')!=16384
                    or row.get('byte_offset')!=seed%(size-16384+1)):
                raise ValueError('native region workload differs')
        elif row.get('repeat')!=i or row.get('verified_bytes')!=size:
            raise ValueError('native decode workload differs')
    return rows


class NativeExecution:
    def __init__(self, worker, original, directory):
        self.worker=Path(worker).resolve()
        self.original=Path(original).resolve()
        self.directory=Path(directory).resolve()
        self.cache={}

    def call(self, plan, operation, *args):
        return output(['bash',plan['adapter'],'_call',operation,*args],clean_environment(plan['work']))

    def prepare(self,plan):
        key=plan['adapter']
        if key in self.cache: return self.cache[key]
        directory=self.directory/Path(plan['work']).name
        directory.mkdir()
        archive=directory/'archive'
        g=plan['configuration']['granularity']
        command=['bash',plan['adapter'],'_call','codec_compress',str(self.original),str(archive),str(g)]
        with (directory/'prepare.log').open('w') as log:
            execute(command,env=clean_environment(plan['work']),stdout=log,stderr=log,
                           check=True,timeout=3600)
        files=[Path(p).resolve() for p in json.loads(self.call(plan,'codec_artifacts',archive))]
        if archive not in files or len(set(files))!=len(files):
            raise ValueError('invalid archive artifact declaration')
        state={'directory':directory,'archive':archive,
               'sidecar':self.call(plan,'codec_sidecar',archive),
               'library':self.call(plan,'codec_library'),
               'artifacts':{str(p):{'bytes':p.stat().st_size,'sha256':digest(p)} for p in files},
               'compress_command':shlex.join(command)}
        self.cache[key]=state
        return state

    def measure(self,plan,phase):
        state=self.prepare(plan)
        if phase in state: return state[phase]
        raw=state['directory']/(phase+'.jsonl')
        command=[str(self.worker),state['library'],str(state['archive']),str(self.original),phase,state['sidecar']]
        with raw.open('w') as out, (state['directory']/(phase+'.log')).open('w') as log:
            execute(command,stdout=out,stderr=log,check=True,timeout=3600,
                           env=clean_environment(plan['work']))
        rows=samples(raw,phase,self.original.stat().st_size)
        # Ensure reads did not mutate archive or mandatory sidecar.
        if any(digest(p)!=v['sha256'] for p,v in state['artifacts'].items()):
            raise ValueError('native reader modified archive artifacts')
        result={'raw_samples':str(raw.relative_to(self.directory)), 'raw_sha256':digest(raw),
                'command':shlex.join(command),'n_samples':len(rows),'verified':'byte-exact',
                'timer':'CLOCK_MONOTONIC; resident context; native callback only',
                'archive_artifacts':state['artifacts'],'compress_command':state['compress_command']}
        if phase=='region':
            ordered=sorted(r['latency_ms'] for r in rows)
            result.update(region_p50_ms=ordered[math.ceil(.50*len(rows))-1],
                          region_p99_ms=ordered[math.ceil(.99*len(rows))-1])
        else:
            median=statistics.median(r['wall_ms'] for r in rows)
            result.update(full_decode_median_ms=median,
                          sample_MB_s=self.original.stat().st_size/1000/median,
                          plateau_status='data_edge',
                          plateau_reason='single input size; a throughput plateau has not been established')
        state[phase]=result
        return result

    def ratio(self,plan):
        state=self.prepare(plan)
        # Verify the archive used for file accounting, even when ratio is selected alone.
        restored=state['directory']/'ratio-restored'
        command=['bash',plan['adapter'],'_call','codec_decompress',str(state['archive']),str(restored)]
        with (state['directory']/'verify.log').open('w') as log:
            execute(command,stdout=log,stderr=log,check=True,timeout=3600,
                           env=clean_environment(plan['work']))
        with restored.open('rb') as actual, self.original.open('rb') as expected:
            while True:
                left=actual.read(1024*1024); right=expected.read(1024*1024)
                if left!=right: raise ValueError('ratio restoration differs')
                if not left: break
        restored.unlink()
        if any(digest(p)!=v['sha256'] for p,v in state['artifacts'].items()):
            raise ValueError('verification changed archive artifacts')
        stored=sum(v['bytes'] for v in state['artifacts'].values())
        if not stored: raise ValueError('zero stored archive size')
        return {'ratio':self.original.stat().st_size/stored,'archive_bytes':stored,
                'archive_artifacts':state['artifacts'],'verified':'byte-exact',
                'n_samples':1,'compress_command':state['compress_command'],
                'verification_command':shlex.join(command)}

    def break_even(self,plan):
        region=self.measure(plan,'region')
        decode=self.measure(plan,'decode')
        intersection=decode['full_decode_median_ms']/region['region_p50_ms']
        return {'intersection_requests':intersection,'break_even_N':math.floor(intersection)+1,
                'definition':'first integer N for which N * region p50 exceeds median full decode',
                'model':'independent single calls; excludes preparation and amortization',
                'region':region,'decode':decode,'verified':'byte-exact'}

    def handlers(self):
        handlers={phase:(lambda plan,phase=phase:self.measure(plan,phase)) for phase in ('decode','region')}
        handlers.update(ratio=self.ratio,break_even=self.break_even)
        return handlers


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--codec',action='append',required=True)
    p.add_argument('--axis',action='append',choices=('ratio','decode','region','break_even'),required=True)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--work',type=Path,default=ROOT/'.work/adapter-check')
    p.add_argument('--output-dir',type=Path,required=True,help='new directory; never overwrites a run')
    a=p.parse_args()
    try:
        if not a.input.is_file(): raise ValueError('input file missing')
        if set(a.axis)&{'region','break_even'} and a.input.stat().st_size<16384:
            raise ValueError('region requires at least 16384 input bytes')
        adapters=[resolve_adapter(c) for c in a.codec]
        if len(set(adapters))!=len(adapters): raise ValueError('duplicate adapter selection')
        plans=[plan_adapter(c,work_directory(c,a.work),a.axis) for c in adapters]
        a.output_dir.mkdir(parents=True,exist_ok=False)
        directory=a.output_dir.resolve()
        worker=directory/'native-measure'
        sources={str(ROOT/'harness'/name):digest(ROOT/'harness'/name) for name in
                 ('native_measure.c','native_execution.py','axis_planner.py','resident_context.h')}
        build=['gcc','-O3','-std=gnu11','-Wall','-Wextra','-Werror',str(ROOT/'harness/native_measure.c'),'-ldl','-o',str(worker)]
        with (directory/'build.log').open('w') as log:
            execute(build,stdout=log,stderr=log,check=True,timeout=120)
        input_hash=digest(a.input)
        runner=NativeExecution(worker,a.input,directory)
        results=[dict(plan=plan,measurements=dispatch_adapter(plan,runner.handlers())) for plan in plans]
        if digest(a.input)!=input_hash: raise ValueError('input changed during measurement')
        if any(digest(path)!=sha for path,sha in sources.items()):
            raise ValueError('measurement source changed during execution')
        manifest={'schema':'cabench-native-samples-v1','status':'pass','published':False,
                  'run_id':datetime.now(timezone.utc).isoformat(),
                  'corpus':str(a.input.resolve()),'corpus_sha256':input_hash,
                  'corpus_md5':digest(a.input,'md5'),
                  'corpus_bytes':a.input.stat().st_size,
                  'host':{'system':platform.platform(),'machine':platform.machine()},
                  'measurement_sources':sources,'worker_sha256':digest(worker),'worker_source_sha256':digest(ROOT/'harness/native_measure.c'),
                  'build_command':shlex.join(build),'compiler':output(['gcc','--version'],os.environ).splitlines()[0],
                  'command':shlex.join(['./run.sh','--measure',*sys.argv[1:]]),
                  'adapters':results}
        tmp=directory/'manifest.tmp'
        tmp.write_text(json.dumps(manifest,indent=2)+'\n'); tmp.replace(directory/'manifest.json')
        for result in results:
            print(result['plan']['codec']+': '+', '.join(m['axis']+' '+('verified' if m['value'] else 'n/a — '+m['reason']) for m in result['measurements']))
        print('Unpublished native samples: '+str(directory/'manifest.json'))
        return 0
    except (ValueError,OSError,KeyError,subprocess.SubprocessError) as exc:
        print('STOP: '+str(exc),file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main())
