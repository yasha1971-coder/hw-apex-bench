"""Strict one-block baseline and five granularity points, using adapter operations."""
import ctypes as C
import json
import shlex
from pathlib import Path
from resident_probe import Context
from qualification import clean_environment
GRID=(4096,16384,65536,262144,1048576)


def geometry(library,archive,sidecar,size,g):
    ctx=Context(library,archive.read_bytes(),sidecar=sidecar)
    try:
        fn=ctx.lib.hc_geometry
        fn.argtypes=[C.c_void_p]+[C.POINTER(C.c_uint64)]*4;fn.restype=C.c_int
        values=[C.c_uint64() for _ in range(4)]
        if fn(ctx.ptr,*map(C.byref,values))!=0: raise ValueError('geometry rejected')
        units,empty,raw,largest=[v.value for v in values]
        if raw!=size or units-empty!=(size+g-1)//g or largest!=min(g,size):
            raise ValueError('actual geometry differs from requested granularity')
        block=ctx.lib.hc_block_id
        block.argtypes=[C.c_void_p,C.c_uint64];block.restype=C.c_uint64
        for index,offset in enumerate(range(0,size,g)):
            if block(ctx.ptr,offset)!=index or (offset and block(ctx.ptr,offset-1)!=index-1):
                raise ValueError('block boundary differs from granularity')
        # Read across each type of boundary outside timing, including the file tail.
        for off in {0,max(0,size-16384),max(0,min(g,size)-17),max(0,size//2-17)}:
            length=min(16384,size-off)
            n,data=ctx.region(off,length)
            if n!=length: raise ValueError('curve region failed')
            yield (off,data)
        yield {'units':units,'empty_units':empty,'nonempty_units':units-empty,
               'raw_bytes':raw,'largest_unit_bytes':largest}
    finally: ctx.close()


def run_curve(runner,plan):
    from native_execution import digest, execute
    state=runner.prepare(plan);size=runner.original.stat().st_size
    if not size: raise ValueError('c(g) requires nonempty input')
    directory=state['directory']/'cg';directory.mkdir()
    rows=[]
    for label,g in [('whole',max(size,4096))]+[(str(g),g) for g in GRID]:
        arc=directory/('archive-'+label)
        command=['bash',plan['adapter'],'_call','codec_compress',str(runner.original),str(arc),str(g)]
        with (directory/(label+'.log')).open('w') as log:
            execute(command,stdout=log,stderr=log,env=runner.environment(plan),timeout=3600)
            sidecar=runner.call(plan,'codec_sidecar',arc)
            verify=[str(runner.worker),state['library'],str(arc),str(runner.original),'decode',sidecar,'0']
            execute(verify,stdout=log,stderr=log,env=runner.environment(plan),timeout=1800)
        with runner.original.open('rb') as oracle:
            for item in geometry(state['library'],arc,sidecar,size,g):
                if isinstance(item,dict): geo=item
                else:
                    off,data=item;oracle.seek(off)
                    if data!=oracle.read(len(data)): raise ValueError('curve region differs')
        if label=='whole' and geo['nonempty_units']!=1: raise ValueError('baseline is not one whole-file block')
        files=list(map(Path,json.loads(runner.call(plan,'codec_artifacts',arc))))
        if arc not in files or len(set(files))!=len(files): raise ValueError('curve artifacts invalid')
        artifacts={str(p):{'bytes':p.stat().st_size,'sha256':digest(p)} for p in files}
        stored=sum(v['bytes'] for v in artifacts.values())
        row={'label':label,'granularity':g,'configuration':dict(plan['configuration'],granularity=g),
             'archive_bytes':stored,'ratio':size/stored,'geometry':geo,'artifacts':artifacts,
             'command':runner.command(plan,command),'verification_command':runner.command(plan,verify),'verified':'byte-exact'}
        rows.append(row)
        for p in files:p.unlink()
    baseline=rows[0]
    for row in rows[1:]: row['c_g_percent']=100*(1-baseline['archive_bytes']/row['archive_bytes'])
    return {'baseline':baseline,'points':rows[1:],'unit':'percent','varied_parameter':'granularity',
            'formula':'100 * (1 - bytes_whole / bytes_g)',
            'scope':'checked adapter configuration; historical curves at other SHAs/profiles remain distinct',
            'verified':'byte-exact','timings_collected':False}
