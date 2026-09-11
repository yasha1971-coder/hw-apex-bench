"""Shared access traces, codec-owned block mapping, and native batch dispatch."""
import collections
import ctypes as C
import json
import math
from pathlib import Path
import shlex
import statistics
from access_profiles import traces, SIZES, PROFILES
from resident_probe import Context
from qualification import clean_environment


def mapped_profiles(runner,plan):
    from native_execution import digest
    state=runner.prepare(plan)
    if 'profiles' in state: return state['profiles']
    all_traces,_=traces(runner.original.stat().st_size)
    directory=state['directory']/'profiles';directory.mkdir()
    ctx=Context(state['library'],state['archive'].read_bytes(),sidecar=state['sidecar'])
    try:
        fn=ctx.lib.hc_block_id;fn.argtypes=[C.c_void_p,C.c_uint64];fn.restype=C.c_uint64
        rows=[]
        for name in PROFILES:
            for count in runner.batch_sizes:
                offsets=all_traces[name,count]
                ids=[fn(ctx.ptr,off) for off in offsets]
                if any(x==(1<<64)-1 for x in ids): raise ValueError('block mapping rejected a valid offset')
                counts=collections.Counter(ids)
                h=-math.fsum((n/count)*math.log2(n/count) for n in counts.values())
                path=directory/f'{name}-{count}.ranges'
                path.write_text(''.join(f'{off} 16384\n' for off in offsets))
                rows.append({'profile':name,'count':count,'H_alpha_bits':h,'distinct_start_blocks':len(counts),
                    'trace':str(path.relative_to(runner.directory)),'trace_sha256':digest(path),
                    'block_ids_sha256':__import__('hashlib').sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest(),
                    'block_distribution':dict(sorted(counts.items()))})
        state['profiles']=rows;return rows
    finally: ctx.close()


def native_batch(runner,plan):
    from native_execution import digest, execute
    state=runner.prepare(plan);rows=[]
    for profile in mapped_profiles(runner,plan):
        name,count=profile['profile'],profile['count']
        raw=state['directory']/f'batch-{name}-{count}.jsonl'
        command=[str(runner.directory/'native-batch'),state['library'],str(state['archive']),str(runner.original),
                 state['sidecar'],str(runner.directory/profile['trace']),str(count),'batch']
        with raw.open('w') as out, raw.with_suffix('.log').open('w') as log:
            execute(command,stdout=out,stderr=log,env=runner.environment(plan),timeout=1800)
        points=[json.loads(line) for line in raw.read_text().splitlines()]
        expected={(rep,method) for rep in range(3) for method in ('loop','batch')}
        if (len(points)!=6 or {(p.get('repeat'),p.get('method')) for p in points}!=expected
            or any(p.get('verified') is not True or p.get('n')!=count or not math.isfinite(p.get('wall_ms',0)) or p['wall_ms']<=0 for p in points)):
            raise ValueError('invalid native batch samples')
        medians={m:statistics.median(p['wall_ms'] for p in points if p['method']==m) for m in ('loop','batch')}
        rows.append(dict(profile,threads=1,loop_ranges_s=count*1000/medians['loop'],
            batch_ranges_s=count*1000/medians['batch'],speedup=medians['loop']/medians['batch'],
            raw_samples=str(raw.relative_to(runner.directory)),raw_sha256=digest(raw),
            command=runner.command(plan,command),verified='byte-exact',n_samples=3))
    if any(digest(p)!=v['sha256'] for p,v in state['artifacts'].items()):
        raise ValueError('profile reader modified archive')
    return {'profiles':rows,'threads':1,'verified':'byte-exact'}
