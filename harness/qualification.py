"""Bind a local correctness receipt to its actual code, configuration and binaries."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from resident_probe import capabilities

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL='cabench-check-v2'
RUNTIME=('check_adapter.py','check_common.sh','check_region.py','resident_probe.py',
         'resident_context.h','resident_fixture.py','qualification.py',
         'verify_context_sources.py','context-ace-sources.json')

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def clean_environment(work):
    env=os.environ.copy()
    env.update(HB_ROOT=str(ROOT),HB_CHECK_WORK=str(work),HB_JOBS='2')
    for key in ('HB_HTSLIB','HB_ZSTD','HB_ACEAPEX','HB_XZ','HB_XZ_BUILD','XZ_DEFAULTS','XZ_OPT',
                'ACEAPEX_BS','LIT_CHUNK','FSE_CHUNK','MIN_MATCH','LIT_LEVEL','LIT_LANES',
                'NO_REP','DIRECT8','FORCED_BIN','ACEAPEX_DUMP','LD_PRELOAD'):
        env.pop(key,None)
    return env

def output(argv,env):
    return subprocess.check_output(list(map(str,argv)),env=env,text=True,timeout=30).strip()

def metadata(adapter,work):
    env=clean_environment(work)
    def call(name): return output(['bash',adapter,'_call',name],env)
    return {'codec':call('codec_name'),'version':call('codec_version'),
            'capabilities':capabilities(adapter,env),
            'constraints':json.loads(call('codec_constraints')),
            'configuration':json.loads(call('codec_configuration'))}

def work_directory(adapter,base):
    adapter=Path(adapter).resolve()
    key=adapter.stem+'-'+hashlib.sha256(str(adapter).encode()).hexdigest()[:10]
    return Path(base).resolve()/key

def snapshot(adapter,work):
    adapter,work=Path(adapter).resolve(),Path(work).resolve()
    env=clean_environment(work)
    def call(name): return output(['bash',adapter,'_call',name],env)
    current=metadata(adapter,work)
    inputs=json.loads(call('codec_inputs'))
    binaries=json.loads(call('codec_build_artifacts'))
    for items in (inputs,binaries):
        if not isinstance(items,list) or any(not isinstance(p,str) or not p for p in items):
            raise ValueError('adapter file declarations must be JSON arrays of paths')
    if current['capabilities']['region']=='available':
        library=Path(call('codec_library')).resolve()
        if library not in [Path(p).resolve() for p in binaries]:
            raise ValueError('native region library missing from build artifact declaration')
    paths=[adapter]+[ROOT/'harness'/p for p in RUNTIME]+[Path(p) for p in inputs+binaries]
    files={str(p.resolve()):digest(p) for p in paths}
    # Capture libraries resolved by the actual loader environment, not package labels.
    linked={}
    for path in binaries:
        p=Path(path)
        with p.open('rb') as stream: magic=stream.read(4)
        if magic!=b'\x7fELF': continue
        run=subprocess.run(['ldd',str(p.resolve())],env=env,text=True,capture_output=True,timeout=30)
        if 'not found' in run.stdout: raise ValueError('unresolved shared library')
        if run.returncode and 'statically linked' not in run.stdout+run.stderr:
            raise ValueError('cannot identify binary shared libraries')
        for name in re.findall(r'(/[^\s]+)\s+\(',run.stdout):
            dep=Path(name).resolve(); linked[str(dep)]=digest(dep)
    sources=[]
    deps=work/'deps'
    for repo in sorted(deps.iterdir()) if deps.exists() else []:
        if not (repo/'.git').exists(): continue
        if output(['git','-C',repo,'status','--porcelain','--untracked-files=no'],env):
            raise ValueError('dirty dependency source')
        subs=output(['git','-C',repo,'submodule','status','--recursive'],env)
        if any(line.startswith(('+','-','U')) for line in subs.splitlines()):
            raise ValueError('submodule differs from pinned revision')
        output(['git','-C',repo,'submodule','foreach','--quiet','--recursive',
                'test -z "$(git status --porcelain --untracked-files=no)"'],env)
        sources.append({'directory':repo.name,'commit':output(['git','-C',repo,'rev-parse','HEAD'],env),
                        'submodules':subs})
    return dict(current,protocol=PROTOCOL,files=files,linked_libraries=linked,sources=sources,
                build_artifacts=binaries,host={'system':platform.system(),'machine':platform.machine()},
                loader_environment={k:env.get(k,'') for k in ('PATH','LD_LIBRARY_PATH','GLIBC_TUNABLES')})

def fingerprint(state):
    return hashlib.sha256(json.dumps(state,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def require_current(adapter,work):
    path=Path(work)/'check.json'
    if not path.is_file(): raise ValueError('no successful --check receipt; run --check first')
    receipt=json.loads(path.read_text())
    if receipt.get('status')!='pass':
        raise ValueError('check receipt is not successful')
    if receipt.get('check_protocol')!=PROTOCOL:
        raise ValueError('receipt predates this qualification protocol; run --check again')
    state=snapshot(adapter,work)
    if receipt.get('qualification')!=state or receipt.get('qualification_sha256')!=fingerprint(state):
        raise ValueError('stale --check receipt: code, build, configuration or environment changed')
    if any(receipt.get(k)!=state[k] for k in ('codec','version','capabilities')):
        raise ValueError('receipt metadata disagrees with qualification')
    cases=receipt.get('cases',[])
    labels={'mixed','one-byte','empty','exact-block','cross-block'}
    if len(cases)!=len(labels) or {c.get('fixture') for c in cases}!=labels:
        raise ValueError('receipt has incomplete fixture evidence')
    for case in cases:
        if case.get('status')=='n/a':
            if (case['fixture']!='empty' or state['constraints'].get('min_input_bytes')!=1
                or case.get('reason')!=state['constraints'].get('min_input_reason')):
                raise ValueError('receipt has an unexplained fixture exclusion')
        elif case.get('status')!='pass' or case.get('full_restore')!='byte-exact':
            raise ValueError('receipt has no verified restoration evidence')
        elif state['capabilities']['region']=='available':
            native=case.get('native',{})
            if (native.get('full_restore')!='byte-exact' or native.get('version')!=state['version']
                or type(native.get('region_checks')) is not int or native['region_checks']<1):
                raise ValueError('receipt has no verified native region evidence')
    return receipt,state
