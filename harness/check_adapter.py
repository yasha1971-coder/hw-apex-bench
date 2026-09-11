#!/usr/bin/env python3
"""Build and qualify trusted codec adapters on small fixtures, never benchmark."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import tempfile
from resident_probe import capabilities
from qualification import PROTOCOL, clean_environment, snapshot, fingerprint, work_directory

ROOT=Path(__file__).resolve().parents[1]
REQUIRED=('codec_name','codec_version','codec_build','codec_compress','codec_decompress','codec_region','codec_supports')

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def check(adapter, work):
    adapter=adapter.resolve()
    if not adapter.is_file(): raise ValueError('adapter file does not exist')
    work.mkdir(parents=True,exist_ok=True)
    with (work/'check.lock').open('w') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('another check owns this build directory')
        return check_locked(adapter,work)

def check_locked(adapter,work):
    env=clean_environment(work)
    receipt=work/'check.json'; receipt.unlink(missing_ok=True)
    commands=[]
    with (work/'check.log').open('w') as log:
        def run(argv, capture=False, timeout=600):
            argv=list(map(str,argv)); commands.append(shlex.join(argv))
            log.write('+ '+shlex.join(argv)+'\n'); log.flush()
            proc=subprocess.Popen(argv,env=env,stdout=subprocess.PIPE if capture else log,
                                  stderr=log,text=True,cwd=ROOT,start_new_session=True)
            try:
                output,_=proc.communicate(timeout=timeout)
            except (subprocess.TimeoutExpired,KeyboardInterrupt):
                os.killpg(proc.pid,signal.SIGKILL)
                proc.communicate()
                raise
            if proc.returncode: raise RuntimeError(f'command failed ({proc.returncode}): '+shlex.join(argv))
            return output.strip() if capture else None
        def call(op,*args,capture=False):
            return run(['bash',adapter,'_call',op,*args],capture)
        run(['bash','-c','source "$1"; shift; for fn in "$@"; do declare -F "$fn" >/dev/null || exit 2; done','contract',adapter,*REQUIRED])
        name=call('codec_name',capture=True); version=call('codec_version',capture=True)
        axes=capabilities(adapter,env)
        limits=json.loads(call('codec_constraints',capture=True))
        config=json.loads(call('codec_configuration',capture=True))
        g=limits['granularity']; minimum=limits['min_input_bytes']
        if not isinstance(g,int) or not 1<=g<=1048576 or minimum not in (0,1):
            raise ValueError('invalid smoke-test constraints')
        if minimum and not limits.get('min_input_reason'): raise ValueError('input exclusion needs a reason')
        print(f'{name}: build pinned dependencies',flush=True)
        call('codec_build')
        sources=[]
        for repo in sorted((work/'deps').iterdir()) if (work/'deps').exists() else []:
            if not (repo/'.git').exists(): continue
            sha=run(['git','-C',repo,'rev-parse','HEAD'],True)
            if run(['git','-C',repo,'status','--porcelain','--untracked-files=no'],True):
                raise ValueError('build modified tracked dependency source')
            subs=run(['git','-C',repo,'submodule','status','--recursive'],True)
            if any(line.startswith(('+','-','U')) for line in subs.splitlines()):
                raise ValueError('submodule is not at its pinned commit')
            run(['git','-C',repo,'submodule','foreach','--quiet','--recursive',
                 'test -z "$(git status --porcelain --untracked-files=no)"'])
            sources.append(dict(directory=repo.name,commit=sha,submodules=subs))
        library=Path(call('codec_library',capture=True)) if axes['region']=='available' else None
        qualified=snapshot(adapter,work)
        if any(qualified[k]!=v for k,v in [('codec',name),('version',version),('capabilities',axes),('constraints',limits),('configuration',config)]):
            raise ValueError('adapter metadata changed during build')
        cases=[]
        with tempfile.TemporaryDirectory(prefix='fixtures-',dir=work) as td:
            folder=Path(td)
            corpus=folder/'corpus'
            run([sys.executable,ROOT/'harness/resident_fixture.py',corpus])
            payload=corpus.read_bytes()
            fixtures=[('mixed',payload),('one-byte',b'X'),('empty',b''),
                      ('exact-block',bytes(i%251 for i in range(g))),
                      ('cross-block',bytes(i%251 for i in range(3*g+17)))]
            for label,raw in fixtures:
                if len(raw)<minimum:
                    cases.append(dict(fixture=label,status='n/a',reason=limits['min_input_reason']))
                    continue
                source=folder/(label+'.input'); archive=folder/(label+'.archive'); restored=folder/(label+'.restored')
                source.write_bytes(raw)
                call('codec_compress',source,archive,g)
                if source.read_bytes()!=raw: raise ValueError('compressor modified the input')
                artifacts=[Path(p) for p in json.loads(call('codec_artifacts',archive,capture=True))]
                if archive not in artifacts or len(set(artifacts))!=len(artifacts) or any(not p.is_file() for p in artifacts):
                    raise ValueError('incomplete archive artifact list')
                archive_hashes={p.name:digest(p) for p in artifacts}
                call('codec_decompress',archive,restored)
                if restored.read_bytes()!=raw: raise ValueError('CLI full restore differs')
                item=dict(fixture=label,input_bytes=len(raw),input_sha256=digest(source),
                          archive_sha256=digest(archive),artifacts=archive_hashes,
                          full_restore='byte-exact',status='pass')
                if axes['region']=='available':
                    sidecar=call('codec_sidecar',archive,capture=True)
                    argv=[sys.executable,ROOT/'harness/resident_probe.py','--adapter',adapter,'--library',library,
                          '--archive',archive,'--original',source,'--granularity',g]
                    if sidecar: argv+=['--sidecar',sidecar]
                    native=json.loads(run(argv,True,120))
                    if native['version']!=version: raise ValueError('native version differs from declared version')
                    item['native']=native
                    offset=min(max(0,g-1),len(raw)); length=min(2*g+11,len(raw)-offset)
                    out=folder/'region.out'
                    call('codec_region',archive,offset,length,out)
                    if out.read_bytes()!=raw[offset:offset+length]: raise ValueError('shell region differs')
                if {p.name:digest(p) for p in artifacts}!=archive_hashes:
                    raise ValueError('reader changed archive artifacts')
                cases.append(item)
        if snapshot(adapter,work)!=qualified:
            raise ValueError('code or build changed during correctness checks')
        try: replay_adapter=str(adapter.relative_to(ROOT))
        except ValueError: replay_adapter=str(adapter)
        result=dict(status='pass',check_protocol=PROTOCOL,qualification=qualified,
                    qualification_sha256=fingerprint(qualified),codec=name,version=version,adapter_sha256=digest(adapter),
                    command=shlex.join(['./run.sh','--check',replay_adapter]),capabilities=axes,
                    native_library_sha256=digest(library) if library else None,sources=sources,cases=cases,
                    commands=commands,timings_collected=False)
        temp=receipt.with_suffix('.tmp');temp.write_text(json.dumps(result,indent=2)+'\n');temp.replace(receipt)
        count=sum(x.get('native',{}).get('region_checks',0) for x in cases)
        print(f'{name}: PASS; {sum(x["status"]=="pass" for x in cases)} restores; {count} native region checks',flush=True)
        print('Axes: '+', '.join(f'{a}: {s}' for a,s in axes.items()),flush=True)
        print('Receipt: '+str(receipt),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('adapter',nargs='?',type=Path)
    p.add_argument('--work',type=Path,default=ROOT/'.work/adapter-check')
    args=p.parse_args()
    adapters=[args.adapter] if args.adapter else sorted((ROOT/'codecs').glob('*.sh'))
    for adapter in adapters:
        work=work_directory(adapter,args.work)
        try: check(adapter,work)
        except Exception as exc:
            print(f'STOP: {exc}\nBuild/check log: {work/"check.log"}',file=sys.stderr)
            return 1
    return 0

if __name__=='__main__': sys.exit(main())
