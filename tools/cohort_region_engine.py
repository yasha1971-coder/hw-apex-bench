"""Axis 4 v1.1 canonical cohort-region judge."""
import hashlib,time
from pathlib import Path
def storage_bytes(paths):
    p=[Path(x).resolve(strict=True) for x in paths]
    if len(set(p))!=len(p): raise ValueError('duplicate storage path')
    return sum(x.stat().st_size for x in p)
def run_cohort(reader,groups,assemblies,storage_paths,*,clock=time.perf_counter_ns):
    if reader.scope!='cpu-in-process' or reader.decoder_threads!=1: raise ValueError('one-thread in-process reader required')
    if not groups or not assemblies or len(set(assemblies))!=len(assemblies): raise ValueError('bad cohort')
    for g in groups:
        if set(g)!=set(assemblies): raise ValueError('query does not cover cohort')
        for a,w in g.items():
            if w.assembly!=a or w.start0<0 or w.end0<=w.start0: raise ValueError('bad canonical mapping')
    stored=storage_bytes(storage_paths);raw=[];total=0
    for gid,g in enumerate(groups):
        t0=clock()
        for a in assemblies:
            w=g[a]
            try:
                ans=reader.fetch(a,w.contig,w.start0,w.end0);sha=hashlib.sha256(ans.upper()).hexdigest()
                if len(ans)!=w.length or sha!=w.sha256: raise ValueError('SHA mismatch')
                raw.append({'group_id':gid,'assembly':a,'canonical':w.canonical(),'translated':reader.translated(w) if hasattr(reader,'translated') else w.canonical(),'sha256':sha,'status':'PASS'})
            except Exception as exc:
                raw.append({'group_id':gid,'assembly':a,'status':'FAILED','error':str(exc)});return {'axis':4,'status':'FAILED','seconds':None,'stored_bytes':stored},raw
        t1=clock()
        if t1<=t0: raise ValueError('nonpositive interval')
        total+=t1-t0
    return {'axis':4,'status':'PASS','seconds':total/1e9,'stored_bytes':stored,'verified':len(groups)*len(assemblies)},raw
