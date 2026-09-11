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
from resident_probe import AXES
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
    def __init__(self, worker, original, directory, copies=(1,2,4,8), plateau=False, batch_sizes=(100,600,2000,5000)):
        self.worker=Path(worker).resolve()
        self.original=Path(original).resolve()
        self.directory=Path(directory).resolve()
        self.cache={}
        self.copies=copies
        self.plateau=plateau
        self.batch_sizes=batch_sizes

    def environment(self,plan):
        from reader_environment import parameters
        env=clean_environment(plan["work"]);env.update(parameters(plan["configuration"]));return env

    def command(self,plan,argv):
        from reader_environment import parameters
        values=parameters(plan['configuration'])
        return shlex.join(['env',*[k+'='+v for k,v in values.items()],*map(str,argv)] if values else list(map(str,argv)))

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
            execute(command,env=self.environment(plan),stdout=log,stderr=log,
                           check=True,timeout=3600)
        files=[Path(p).resolve() for p in json.loads(self.call(plan,'codec_artifacts',archive))]
        if archive not in files or len(set(files))!=len(files):
            raise ValueError('invalid archive artifact declaration')
        state={'directory':directory,'archive':archive,
               'sidecar':self.call(plan,'codec_sidecar',archive),
               'library':self.call(plan,'codec_library'),
               'artifacts':{str(p):{'bytes':p.stat().st_size,'sha256':digest(p)} for p in files},
               'compress_command':self.command(plan,command)}
        self.cache[key]=state
        return state

    def measure(self,plan,phase):
        state=self.prepare(plan)
        if phase in state: return state[phase]
        raw=state['directory']/(phase+'.jsonl')
        command=[str(self.worker),state['library'],str(state['archive']),str(self.original),phase,state['sidecar']]
        with raw.open('w') as out, (state['directory']/(phase+'.log')).open('w') as log:
            execute(command,stdout=out,stderr=log,check=True,timeout=3600,
                           env=self.environment(plan))
        rows=samples(raw,phase,self.original.stat().st_size)
        # Ensure reads did not mutate archive or mandatory sidecar.
        if any(digest(p)!=v['sha256'] for p,v in state['artifacts'].items()):
            raise ValueError('native reader modified archive artifacts')
        result={'raw_samples':str(raw.relative_to(self.directory)), 'raw_sha256':digest(raw),
                'command':self.command(plan,command),'n_samples':len(rows),'verified':'byte-exact',
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
                           env=self.environment(plan))
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
                'verification_command':self.command(plan,command)}

    def break_even(self,plan):
        region=self.measure(plan,'region')
        decode=self.measure(plan,'decode')
        intersection=decode['full_decode_median_ms']/region['region_p50_ms']
        return {'intersection_requests':intersection,'break_even_N':math.floor(intersection)+1,
                'definition':'first integer N for which N * region p50 exceeds median full decode',
                'model':'independent single calls; excludes preparation and amortization',
                'region':region,'decode':decode,'verified':'byte-exact'}

    def amplification(self,plan):
        state=self.prepare(plan)
        library=self.call(plan,'codec_counter_library')
        raw=state['directory']/'amplification.jsonl'
        command=[str(self.worker),library,str(state['archive']),str(self.original),'amplification',state['sidecar']]
        with raw.open('w') as out, (state['directory']/'amplification.log').open('w') as log:
            execute(command,stdout=out,stderr=log,env=self.environment(plan),timeout=1800)
        rows=[json.loads(line) for line in raw.read_text().splitlines()]
        seed=20260909
        for _ in range(10): seed=(seed*6364136223846793005+1442695040888963407)&((1<<64)-1)
        if len(rows)!=200: raise ValueError('incomplete counter samples')
        for i,r in enumerate(rows):
            seed=(seed*6364136223846793005+1442695040888963407)&((1<<64)-1)
            if (r.get('query')!=i or r.get('byte_offset')!=seed%(self.original.stat().st_size-16384+1)
                or r.get('requested_bytes')!=16384 or r.get('verified') is not True
                or type(r.get('decoded_bytes')) is not int or r['decoded_bytes']<0):
                raise ValueError('invalid counter sample')
        if any(digest(p)!=v['sha256'] for p,v in state['artifacts'].items()):
            raise ValueError('counter reader modified archive')
        return {'value':sum(r['decoded_bytes'] for r in rows)/(200*16384),'unit':'bytes/byte',
                'n_samples':200,'verified':'byte-exact','command':self.command(plan,command),
                'raw_samples':str(raw.relative_to(self.directory)),'raw_sha256':digest(raw),
                'counter_library_sha256':digest(library),'timings_collected':False}

    def c_g(self,plan):
        from adapter_curve import run_curve
        return run_curve(self,plan)

    def h_alpha(self,plan):
        from adapter_profiles import mapped_profiles
        return {'profiles':mapped_profiles(self,plan),'unit':'bits',
                'definition':'Shannon entropy of access counts by request-start block',
                'timings_collected':False}

    def batch(self,plan):
        from adapter_profiles import native_batch
        return native_batch(self,plan)

    def throughput(self,plan,phase):
        from adapter_throughput import run_curve
        return run_curve(self,plan)[phase]

    def handlers(self):
        handlers={phase:(lambda plan,phase=phase:self.measure(plan,phase)) for phase in ('decode','region')}
        handlers.update(ratio=self.ratio,break_even=self.break_even,amplification=self.amplification,h_alpha=self.h_alpha,batch=self.batch,c_g=self.c_g)
        handlers['encode']=lambda plan:self.throughput(plan,'encode')
        if self.plateau: handlers['decode']=lambda plan:self.throughput(plan,'decode')
        from reader_environment import scope
        def scoped(fn):
            def invoke(plan):
                with scope(plan['configuration']):return fn(plan)
            return invoke
        return {axis:scoped(fn) for axis,fn in handlers.items()}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--codec',action='append',required=True)
    p.add_argument('--axis',action='append',choices=sorted(AXES),required=True)
    p.add_argument('--baseline',default='bgzip',help='selected baseline adapter basename')
    p.add_argument('--batch-sizes',default='100,600,2000,5000',help='subset of historical profile counts')
    p.add_argument('--plateau',action='store_true',help='grow encode/decode load; do not use a single-size decode headline')
    p.add_argument('--copies',default='1,2,4,8',help='increasing input multipliers, bounded by 8')
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--work',type=Path,default=ROOT/'.work/adapter-check')
    p.add_argument('--output-dir',type=Path,required=True,help='new directory; never overwrites a run')
    a=p.parse_args()
    try:
        if not a.input.is_file(): raise ValueError('input file missing')
        batch_sizes=tuple(map(int,a.batch_sizes.split(',')))
        if not batch_sizes or len(set(batch_sizes))!=len(batch_sizes) or set(batch_sizes)-{100,600,2000,5000}:
            raise ValueError('invalid batch profile counts')
        copies=tuple(map(int,a.copies.split(',')))
        if not copies or copies[0]!=1 or list(copies)!=sorted(set(copies)) or copies[-1]>8:
            raise ValueError('copies must increase from 1 and not exceed the 8-copy budget')
        adapters=[resolve_adapter(c) for c in a.codec]
        if len(set(adapters))!=len(adapters): raise ValueError('duplicate adapter selection')
        plans=[plan_adapter(c,work_directory(c,a.work),a.axis) for c in adapters]
        needs_region=any(t['action']=='schedule' and t['axis'] in {'region','break_even','amplification'}
                         for plan in plans for t in plan['tasks'])
        if needs_region and a.input.stat().st_size<16384:
            raise ValueError('region requires at least 16384 input bytes')
        needs_profiles=any(t['action']=='schedule' and t['axis'] in {'batch','h_alpha'}
                           for plan in plans for t in plan['tasks'])
        if needs_profiles and a.input.stat().st_size<1024*1024+16384:
            raise ValueError('historical access profiles require at least 1 MiB + 16 KiB')
        a.output_dir.mkdir(parents=True,exist_ok=False)
        directory=a.output_dir.resolve()
        worker=directory/'native-measure'
        sources={str(ROOT/'harness'/name):digest(ROOT/'harness'/name) for name in
                 ('native_measure.c','native_execution.py','axis_planner.py','resident_context.h','adapter_throughput.py','throughput.py','adapter_profiles.py','access_profiles.py','native_batch.c','adapter_curve.py','reader_environment.py','native_results.py','render_native_results.py')}
        build=['gcc','-O3','-std=gnu11','-Wall','-Wextra','-Werror',str(ROOT/'harness/native_measure.c'),'-ldl','-o',str(worker)]
        with (directory/'build.log').open('w') as log:
            execute(build,stdout=log,stderr=log,check=True,timeout=120)
        with (directory/'batch-build.log').open('w') as log:
            execute(['gcc','-O3','-std=gnu11','-Wall','-Wextra','-Werror',str(ROOT/'harness/native_batch.c'),'-ldl','-o',str(directory/'native-batch')],stdout=log,stderr=log,timeout=120)
        input_hash=digest(a.input)
        runner=NativeExecution(worker,a.input,directory,copies,a.plateau,batch_sizes)
        results=[dict(plan=plan,measurements=dispatch_adapter(plan,runner.handlers())) for plan in plans]
        if digest(a.input)!=input_hash: raise ValueError('input changed during measurement')
        if any(digest(path)!=sha for path,sha in sources.items()):
            raise ValueError('measurement source changed during execution')
        manifest={'schema':'cabench-native-samples-v1','status':'pass','published':False,
                  'run_id':datetime.now(timezone.utc).isoformat(),
                  'corpus':str(a.input.resolve()),'corpus_sha256':input_hash,
                  'corpus_md5':digest(a.input,'md5'),
                  'corpus_bytes':a.input.stat().st_size,
                  'host':{'os':platform.platform(),'machine':platform.machine(),
                          'cpu':next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),platform.processor()),
                          'ram_gb':int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:')))/1024**2},
                  'measurement_sources':sources,'worker_sha256':digest(worker),'worker_source_sha256':digest(ROOT/'harness/native_measure.c'),
                  'build_command':shlex.join(build),'compiler':output(['gcc','--version'],os.environ).splitlines()[0],
                  'command':shlex.join(['./run.sh','--measure',*sys.argv[1:]]),
                  'adapters':results}
        from native_results import rows as result_rows
        serialized=result_rows(manifest,a.baseline)
        result_path=directory/'results.jsonl'
        result_path.write_text(''.join(json.dumps(row,sort_keys=True,allow_nan=False)+'\n' for row in serialized))
        from render_native_results import render
        render(result_path,directory/'README.md')
        manifest['results_sha256']=digest(result_path)
        manifest['results_records']=len(serialized)
        tmp=directory/'manifest.tmp'
        tmp.write_text(json.dumps(manifest,indent=2)+'\n'); tmp.replace(directory/'manifest.json')
        for result in results:
            print(result['plan']['codec']+': '+', '.join(m['axis']+' '+('verified' if m['value'] else 'n/a — '+m['reason']) for m in result['measurements']))
        print('Unpublished native samples: '+str(directory/'manifest.json'))
        return 0
    except (ValueError,OSError,KeyError,subprocess.SubprocessError) as exc:
        print('STOP: '+str(exc),file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main())
