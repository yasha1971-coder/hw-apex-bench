"""Adapter-owned encoder commands and common, historical plateau procedure."""
import json
from pathlib import Path
import shlex
import shutil
import statistics
import time
from qualification import clean_environment
from throughput import COPIES, ENCODE_REPEATS, _cv, _plateau


def run_curve(runner,plan):
    from native_execution import digest, execute, samples
    state=runner.prepare(plan)
    if 'throughput' in state: return state['throughput']
    directory=state['directory']/'plateau';directory.mkdir()
    curves={'encode':[],'decode':[]}
    for copies in runner.copies:
        inp=directory/f'input-x{copies}'
        with inp.open('wb') as out:
            for _ in range(copies):
                with runner.original.open('rb') as src: shutil.copyfileobj(src,out,1024*1024)
        size=inp.stat().st_size
        if not size: raise ValueError('throughput requires nonempty input')
        input_sha=digest(inp)
        arc=directory/f'archive-x{copies}'
        commands=[];durations=[];verified=[]
        for rep in range(ENCODE_REPEATS):
            # Command construction and output cleanup are never timed. The adapter
            # returns argv, not a shell command; Python never interpolates shell code.
            spec=json.loads(runner.call(plan,'codec_encode_command',inp,arc,plan['configuration']['granularity']))
            args=spec['argv']
            if not isinstance(args,list) or not args or any(not isinstance(x,str) for x in args):
                raise ValueError('encoder argv must be a nonempty array of strings')
            produced=Path(spec.get('produced',str(arc)))
            for p in {arc,produced,*map(Path,json.loads(runner.call(plan,'codec_artifacts',arc)))}:
                p.unlink(missing_ok=True)
            logpath=directory/f'encode-x{copies}-{rep}.log'
            with logpath.open('w') as log:
                start=time.monotonic()
                if spec.get('stdout_archive',False):
                    with arc.open('wb') as out:
                        execute(args,stdout=out,stderr=log,env=runner.environment(plan),timeout=1800)
                else:
                    execute(args,stdout=log,stderr=log,env=runner.environment(plan),timeout=1800)
                elapsed=(time.monotonic()-start)*1000
            if produced!=arc: produced.replace(arc)
            command=runner.command(plan,args)+(' > '+shlex.quote(str(arc)) if spec.get('stdout_archive',False) else '')
            verify=[str(runner.worker),state['library'],str(arc),str(inp),'decode',runner.call(plan,'codec_sidecar',arc),'0']
            with (directory/f'verify-x{copies}-{rep}.log').open('w') as log:
                execute(verify,stdout=log,stderr=log,env=runner.environment(plan),timeout=1800)
            files=list(map(Path,json.loads(runner.call(plan,'codec_artifacts',arc))))
            if not arc.is_file() or not files or len(set(files))!=len(files) or arc not in files:
                raise ValueError('invalid timed archive artifacts')
            verified.append({'command':runner.command(plan,verify),'artifacts':{str(p):{'bytes':p.stat().st_size,'sha256':digest(p)} for p in files}})
            durations.append(elapsed);commands.append(command)
        if digest(inp)!=input_sha: raise ValueError('encoder changed throughput input')
        rates=[size/ms/1000 for ms in durations]
        common={'copies':copies,'input_bytes':size,'input_sha256':input_sha,'verified':'byte-exact'}
        curves['encode'].append(dict(common,value=size/statistics.median(durations)/1000,
            unit='MB/s',sample_wall_ms=durations,sample_cv=_cv(rates),commands=commands,
            verification=verified,timer='encoder process wall clock; published CLI boundary'))
        raw=directory/f'decode-x{copies}.jsonl'
        command=[str(runner.worker),state['library'],str(arc),str(inp),'decode',runner.call(plan,'codec_sidecar',arc)]
        with raw.open('w') as out, (directory/f'decode-x{copies}.log').open('w') as log:
            execute(command,stdout=out,stderr=log,env=runner.environment(plan),timeout=1800)
        rows=samples(raw,'decode',size);durations=[r['wall_ms'] for r in rows];rates=[size/ms/1000 for ms in durations]
        if any(digest(p)!=v['sha256'] for p,v in verified[-1]['artifacts'].items()):
            raise ValueError('decoder changed throughput archive')
        curves['decode'].append(dict(common,value=size/statistics.median(durations)/1000,
            unit='MB/s',sample_wall_ms=durations,sample_cv=_cv(rates),command=runner.command(plan,command),
            raw_samples=str(raw.relative_to(runner.directory)),raw_sha256=digest(raw),
            timer='resident native callback; one warmup, five samples'))
        for p in files: p.unlink()
        inp.unlink()
        if all(_plateau(c) for c in curves.values()): break
    result={phase:{'value':points[-1]['value'] if _plateau(points) else None,
                   'status':'declared' if _plateau(points) else 'data_edge',
                   'reason':None if _plateau(points) else 'curve not flat by configured data edge',
                   'unit':'MB/s','points':points,'plateau_reached':_plateau(points)}
            for phase,points in curves.items()}
    result['protocol']={'copies':list(runner.copies),'encode_repeats':3,'decode_repeats':5,
                        'plateau_points':3,'median_spread_limit':.05,'sample_cv_limit':.05}
    state['throughput']=result
    return result
