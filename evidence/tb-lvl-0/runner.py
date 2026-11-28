# SPDX-License-Identifier: Apache-2.0
"""TB-LVL-0 controller. Import is pure; only explicit CLI actions execute work.

prepare copies the CI artifact and pins sources/input/grid; poll observes once;
step consumes one PASS poll and starts at most one actual native roundtrip.
run repeats that state machine. All codec times come exclusively from TurboBench.
"""
import argparse
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
STATE=ROOT/'.work/tb-lvl-0'
HELPER=ROOT/'evidence/hw-region-2/casefix/ovh_bench.py'
LOCK='/run/lock/ovh-bench.lock'
CAL_COMMIT='fa8a9cf801b2dcf62356b5d9c00c23c680836d21'
TB='4aa97c8c37311e399ea3e7782c18c652c5bdb69f'
ACE='c53f3a04f3dbac8590e46a1f86c5fded1e69e065'
INPUT=Path('/home/aeterna/golden/mixed/silesia.ref.tar')
N=211947520
INPUT_SHA='a667bac80089b3d04d5496772149e632f0758974b0579d743cd8d6e5e0d63eb2'
KNOWN=130490328
POLICY=dict(refuse='2026-11-28T05:25:00+00:00',term='2026-11-28T05:29:40+00:00',kill='2026-11-28T05:29:50+00:00',release='2026-11-28T05:30:00+00:00')
HEADER='dataset\tsize\tcsize\tdtime\tctime\tcodec\tlevel\tparam\tcmem\tdmem\tcstack\tdstack\ttime\terr'
PROFILES={'aceapex_fast':list(range(1,9)),'aceapex':[1,2,3,4],'misa77':list(range(6)),
 'zxc':list(range(1,8)),'lz4':[1,3,9,12],'lzav':[1,2],'minlz':[1,3,7],
 'zstd':[1,3,9,15,19,22],'brotli':[4,6,9,11],'lzma':[9],'bsc':['0e0'],'kanzi':[5,6,7,8]}


def require(ok,message):
    if not ok:raise ValueError(message)


class DeadlineRefusal(ValueError):pass


def packed(value):return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
def load(path):return json.loads(Path(path).read_bytes())
def utc():return datetime.now(timezone.utc)
def stamp(value):
    result=datetime.fromisoformat(value)
    require(result.tzinfo is not None and result.utcoffset()==timedelta(0),'UTC required')
    return result
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda:stream.read(1<<20),b''):h.update(part)
    return h.hexdigest()
def artifact(path):
    path=Path(path).resolve();return dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path))
def ref(path):
    path=Path(path).resolve();require(path.is_relative_to(HERE),'public ref escaped task')
    return dict(path=path.relative_to(HERE).as_posix(),sha256=sha(path))
def deref(value):
    path=(HERE/value['path']).resolve()
    require(path.is_relative_to(HERE) and path.is_file() and sha(path)==value['sha256'],'public reference changed')
    return path
def immutable(path,value):
    path=Path(path);raw=value if isinstance(value,bytes) else packed(value)
    require(path.resolve().is_relative_to(HERE) or path.resolve().is_relative_to(STATE),'output escaped task')
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():require(path.read_bytes()==raw,'retained artifact changed: '+str(path))
    else:
        with path.open('xb') as stream:stream.write(raw)
def replace_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    pending=path.with_name(path.name+'.writing');pending.write_bytes(packed(value));pending.replace(path)


def configuration(codec,level):
    token=str(level);require(codec in PROFILES and token in map(str,PROFILES[codec]),'unsupported native level')
    return dict(id=codec+','+token,codec=codec,level=token,api_level=int(token)+10 if codec=='aceapex_fast' else None)


def canonical_grid():
    return sorted([configuration(c,l) for c,levels in PROFILES.items() for l in levels],key=lambda x:x['id'])


def execution_order(grid,round_number):
    require(round_number in (1,2,3),'round must be 1/2/3');rows=sorted(grid,key=lambda x:x['id'])
    if round_number==2:return list(reversed(rows))
    if round_number==3:
        split=len(rows)//2;return rows[split:]+rows[:split]
    return rows


def parse_tbb(raw,config,input_bytes=N,dataset='silesia.ref.tar'):
    """One fresh native .tbb row. Native ctime/dtime are seconds, never CSV speed."""
    require(isinstance(raw,bytes),'native .tbb bytes required')
    lines=raw.decode('utf-8').splitlines();require(len(lines)==2 and lines[0]==HEADER,'fresh .tbb must have exact header and exactly one row')
    fields=lines[1].split('\t');require(len(fields)==14,'native .tbb column count differs')
    row=dict(zip(HEADER.split('\t'),fields))
    require(row['dataset']==dataset and row['size']==str(input_bytes),'native input identity differs')
    level,param=('0','e0') if config['codec']=='bsc' and config['level']=='0e0' else (config['level'],'?')
    require((row['codec'],row['level'],row['param'])==(config['codec'],level,param),'native codec/level/parameter differs')
    require(row['err']=='','TurboBench byte-restore error')
    for key in ('size','csize','cmem','dmem','cstack','dstack'):
        require(re.fullmatch(r'[0-9]+',row[key]) is not None,'noninteger native '+key)
    require(int(row['csize'])>0,'empty/failed native archive')
    for key in ('ctime','dtime'):
        require(re.fullmatch(r'[0-9]+\.[0-9]{6}',row[key]) is not None and Decimal(row[key])>0,'native time must be positive seconds with six decimal places')
    return dict(input_bytes=input_bytes,compressed_bytes=int(row['csize']),ctime_seconds=row['ctime'],
                dtime_seconds=row['dtime'],roundtrip=True,native=row)


def native_command(binary,config,input_path=INPUT):
    return ['taskset','-c','0',str(binary),'-e'+config['id'],'-b1073741824B','-B'+str(N)+'B',
            '-i0,0','-C3','-D','-V0','-v0',str(input_path)]


def observer():
    spec=importlib.util.spec_from_file_location('_tb_admission',HELPER)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def sources():
    names=[HERE/n for n in ('CALIBRATION.md','PROTOCOL.md','GRID_AMENDMENT.md','grid-amendment.json','runner.py','test_runner.py','build_static.py')]+[HELPER]
    require(all(p.is_file() for p in names),'GRID_AMENDMENT.md and committed execution protocol required before timers')
    relative=[p.relative_to(ROOT).as_posix() for p in names]
    subprocess.run(['git','-C',str(ROOT),'ls-files','--error-unmatch','--',*relative],check=True,capture_output=True)
    require(not subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain','--',*relative]).strip(),'execution sources must be committed before timers')
    require(subprocess.check_output(['git','-C',str(ROOT),'show',CAL_COMMIT+':evidence/tb-lvl-0/CALIBRATION.md'])==(HERE/'CALIBRATION.md').read_bytes(),'first calibration changed')
    require(not any(k.startswith(('ACEAPEX_','AX_','LIT_','FSE_')) for k in os.environ),'reader overrides must be absent')
    return {p.relative_to(ROOT).as_posix():sha(p) for p in names}


def prepare(build_dir,input_path=INPUT,mapping_resolved=False):
    source_map=sources();build_dir=Path(build_dir).resolve();build=load(build_dir/'build.json')
    amendment=load(HERE/'grid-amendment.json')
    expected=dict(schema='tb-lvl-0-grid-amendment-v1',status='RESOLVED_BY_SOURCE',mapping_resolved=True,owner_confirmed=False,
        resolved_by='source inspection / ChatGPT',requested_fast_levels=list(range(1,19)),registered_fast_levels=list(range(1,9)),
        api_fast_levels=list(range(11,19)),p2_api_levels=list(range(13,19)),p2_tb_levels=list(range(3,9)),
        registered_configurations=50,registered_main_roundtrips=150)
    require(all(amendment.get(k)==v and type(amendment.get(k)) is type(v) for k,v in expected.items()),'source-derived grid amendment is missing/unresolved/different')
    require(build['status']=='PASS' and build['build_only'] is True and build['benchmark_calls']==0
            and build['static_elf_verified'] is True and build['turbobench_commit']==TB and build['aceapex_override']==ACE,'wrong CI static build/pins')
    require(build['controller_sha256']==sha(HERE/'build_static.py'),'CI builder source differs')
    binary=build_dir/build['binary']['path']
    if not binary.is_file():binary=STATE/'bin/turbobench'
    require(binary.is_file() and binary.stat().st_size==build['binary']['bytes'] and sha(binary)==build['binary']['sha256'],'downloaded/installed binary differs')
    input_path=Path(input_path).resolve();require(input_path in (INPUT,(STATE/'input/silesia.ref.tar').resolve()) and input_path.stat().st_size==N and sha(input_path)==INPUT_SHA,'input path/size/SHA differs')
    staging=None
    if input_path!=INPUT:
        staging=load(HERE/'input-staging.json')
        require(staging['schema']=='tb-lvl-0-input-staging-v1' and staging['source']==dict(path=str(INPUT),bytes=N,sha256=INPUT_SHA)
                and staging['staged']==dict(path=str(input_path),bytes=N,sha256=INPUT_SHA),'staged input proof differs')
    target=STATE/'bin/turbobench';target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():require(sha(target)==build['binary']['sha256'],'retained native binary changed')
    else:shutil.copyfile(binary,target);target.chmod(0o755)
    for file in build_dir.rglob('*'):
        if file.is_file() and file!=binary:
            immutable(HERE/'build'/file.relative_to(build_dir),file.read_bytes())
    controls_path=HERE/'runner-controls.json'
    if controls_path.exists():
        controls=load(controls_path)
        require(controls['status']=='PASS' and controls['source_sha256']=={p:source_map[p] for p in source_map if p.endswith(('runner.py','test_runner.py'))},'runner controls source changed')
        deref(controls['stdout']);deref(controls['stderr'])
    else:
        require(shutil.which('flock') is not None,'flock is required, including isolated supervision controls')
        argv=[sys.executable,'-B','-m','unittest','discover','-s',str(HERE),'-p','test_runner.py','-v']
        checked=subprocess.run(argv,cwd=ROOT,capture_output=True)
        immutable(HERE/'controls.stdout',checked.stdout);immutable(HERE/'controls.stderr',checked.stderr)
        require(checked.returncode==0 and b'skipped' not in checked.stderr,'all runner controls, including Linux fake-worker supervision, must pass without skips')
        immutable(controls_path,dict(schema='tb-lvl-0-runner-controls-v1',status='PASS',native_benchmark_calls=0,synthetic_tests_only=True,
            source_sha256={p:source_map[p] for p in source_map if p.endswith(('runner.py','test_runner.py'))},command=argv,returncode=0,
            stdout=ref(HERE/'controls.stdout'),stderr=ref(HERE/'controls.stderr')))
    identity=dict(source_sha256=source_map,build_manifest_sha256=sha(HERE/'build/build.json'),binary_sha256=sha(target),
                  input_sha256=INPUT_SHA,input_bytes=N,policy=POLICY,
                  input_staging_sha256=sha(HERE/'input-staging.json') if staging else None)
    grid=dict(schema='tb-lvl-0-grid-v1',mapping_resolved=True,owner_confirmed=False,status='RESOLVED_BY_SOURCE',
              amendment=ref(HERE/'GRID_AMENDMENT.md'),amendment_record=ref(HERE/'grid-amendment.json'),
              configurations=canonical_grid(),rounds=3,main_roundtrips=150,
              order={str(r):[c['id'] for c in execution_order(canonical_grid(),r)] for r in (1,2,3)})
    require(len(grid['configurations'])==50,'registered grid must have fifty supported configurations')
    immutable(HERE/'grid.json',grid)
    immutable(HERE/'preparation.json',dict(schema='tb-lvl-0-preparation-v1',status='PASS',identity=identity,grid=ref(HERE/'grid.json'),
              binary=artifact(target),input=artifact(input_path),original_input_path=str(INPUT),build=ref(HERE/'build/build.json'),controls=ref(controls_path),source_commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD']).decode().strip(),no_benchmark_calls=True))
    return status()


def admission():
    require(not (HERE/'ERROR.json').exists(),'retained ERROR stops every later call')
    prep=load(HERE/'preparation.json');identity=prep['identity']
    require(prep['status']=='PASS' and identity['source_sha256']==sources() and identity['policy']==POLICY,'execution source cohort changed')
    require(sha(deref(prep['build']))==identity['build_manifest_sha256'],'build manifest changed')
    controls=load(deref(prep['controls']));require(controls['status']=='PASS' and controls['native_benchmark_calls']==0,'runner controls missing')
    grid=load(deref(prep['grid']));require(grid['mapping_resolved'] is True and grid['owner_confirmed'] is False
        and grid['status']=='RESOLVED_BY_SOURCE' and grid['configurations']==canonical_grid(),'registered grid changed')
    deref(grid['amendment']);deref(grid['amendment_record'])
    require(prep['binary']['sha256']==identity['binary_sha256'] and sha(prep['binary']['path'])==identity['binary_sha256'],'native binary changed')
    actual=Path(prep['input']['path'])
    require(actual in (INPUT,(STATE/'input/silesia.ref.tar').resolve()) and actual.stat().st_size==N
            and prep['original_input_path']==str(INPUT),'input size/path changed')
    if identity['input_staging_sha256'] is not None:
        require(sha(HERE/'input-staging.json')==identity['input_staging_sha256'],'input staging receipt changed')
    return prep,grid


def targets(grid):
    result=[dict(kind='method',round=0,config=configuration('aceapex_fast',1),part='method')]
    for r in (1,2,3):result.extend(dict(kind='main',round=r,config=c,part='round-'+str(r)) for c in execution_order(grid['configurations'],r))
    return result
def unit_path(t):return HERE/'units'/t['part']/(t['config']['id']+'.json')
def raw_path(t):return HERE/'raw'/t['part']/t['config']['id']
def unit_identity(prep,t):return dict(**prep['identity'],config=t['config'],round=t['round'],kind=t['kind'])


def history(prep,t):
    base=raw_path(t);folders=sorted(base.glob('attempt-*')) if base.exists() else []
    require([p.name for p in folders]==['attempt-'+str(i) for i in range(1,len(folders)+1)] and len(folders)<=3,'orphan/fourth actual attempt')
    result=[]
    for n,folder in enumerate(folders,1):
        path=folder/'receipt.json';require(path.exists(),'reserved attempt has no receipt; inspect without retiming')
        receipt=load(path);require(receipt['identity']==unit_identity(prep,t),'attempt source/request changed')
        require(receipt['status'] in ('CLEAN','LOADED','ERROR','DEADLINE'),'unfinished attempt cannot be retimed')
        for stream in ('stdout','stderr'):
            require(sha(folder/stream)==receipt[stream+'_sha256'],'retained native output changed')
        observed=folder/'result.json'
        if receipt['status'] in ('CLEAN','LOADED') and receipt['command_started'] and receipt.get('returncode')==0:
            if not observed.exists():
                parsed=parse_tbb((folder/'native.tbb').read_bytes(),t['config'])
                if t['kind']=='method':require(parsed['compressed_bytes']==KNOWN,'retained method known answer differs')
                immutable(observed,dict(schema='tb-lvl-0-result-v1',identity=receipt['identity'],config=t['config'],round=t['round'],
                    **parsed,raw=ref(folder/'native.tbb'),receipt=ref(path)))
            value=load(observed);require(value['identity']==receipt['identity'] and sha(deref(value['raw']))==receipt['tbb_sha256']
                and deref(value['receipt'])==path,'native result binding changed')
            parsed=parse_tbb(deref(value['raw']).read_bytes(),t['config'])
            require(all(value[k]==parsed[k] for k in ('input_bytes','compressed_bytes','ctime_seconds','dtime_seconds','roundtrip')),'retained raw parse changed')
        else:require(not observed.exists(),'unstarted/failed attempt has a result')
        result.append(dict(attempt=n,status=receipt['status'],receipt=ref(path),result=ref(observed) if observed.exists() else None))
        require(receipt['status']!='CLEAN' or n==len(folders),'first CLEAN was retaken')
    return result


def finish(prep,t):
    path=unit_path(t);records=history(prep,t)
    if path.exists():
        value=load(path);require(value['identity']==unit_identity(prep,t) and value['attempts']==records,'retained unit/attempts changed');deref(value['selected']) if value['selected'] else None;return value
    if not records:return None
    last=records[-1]
    if last['status'] in ('ERROR','DEADLINE'):return dict(status=last['status'])
    if last['status']!='CLEAN' and len(records)<3:return None
    value=dict(schema='tb-lvl-0-unit-v1',kind=t['kind'],round=t['round'],config=t['config'],identity=unit_identity(prep,t),
               status='CLEAN' if last['status']=='CLEAN' else 'BLOCKED: load',attempts=records,selected=last['result'] if last['status']=='CLEAN' else None)
    immutable(path,value);return value


def utc_deadline(now_value=None):return (now_value or utc())>=stamp(POLICY['refuse'])
def poll_paths():
    paths=sorted((HERE/'polls').glob('poll-*.json'))
    require([p.name for p in paths]==[f'poll-{i:06d}.json' for i in range(1,len(paths)+1)],'poll sequence differs')
    return paths
def cooldown():
    dates=[stamp(load(p)['end_utc']) for p in poll_paths() if load(p)['status']=='WAITING']
    dates += [stamp(load(p)['end']['timestamp_utc']) for p in (HERE/'raw').rglob('receipt.json') if load(p)['status']=='LOADED']
    return max(dates)+timedelta(seconds=300) if dates else None
def ready(t):
    paths=poll_paths()
    if not paths:return None
    p=paths[-1];v=load(p)
    return p if v['status']=='PASS' and v['target']==t and not (HERE/'consumptions'/p.name).exists() else None


def status():
    if (HERE/'ERROR.json').exists():return dict(status='ERROR',reason=load(HERE/'ERROR.json')['reason'],next_unit=None)
    if not (HERE/'preparation.json').exists():return dict(status='NEED MAPPING / PREPARATION',next_unit=None)
    prep,grid=admission();accepted=[];next_t=None;state='COMPLETE'
    for t in targets(grid):
        value=finish(prep,t)
        if value is None:state='WAITING';next_t=t;break
        if value['status']!='CLEAN':state=value['status'];next_t=t;break
        accepted.append(ref(unit_path(t)))
    if next_t and utc_deadline():state='DEADLINE'
    due=cooldown();value=dict(schema='tb-lvl-0-run-v1',status=state,identity=prep['identity'],grid=prep['grid'],
        method=accepted[0] if accepted else None,units=accepted[1:],polls=[ref(p) for p in poll_paths()],
        consumptions=[ref(p) for p in sorted((HERE/'consumptions').glob('*.json'))],next_unit=next_t,
        next_poll_utc=due.isoformat() if due and utc()<due else None,deadline=POLICY)
    if next_t and state=='WAITING' and ready(next_t):value['status']='READY'
    replace_json(HERE/'run.json',value);return value


def poll():
    view=status()
    if view['status'] not in ('WAITING','READY') or view['next_poll_utc'] or ready(view['next_unit']):return view
    prep,_=admission();h=observer();value=dict(schema='tb-lvl-0-poll-v1',identity=prep['identity'],target=view['next_unit'],start_utc=utc().isoformat(),status='ERROR',no_native_calls=True)
    try:
        value['start']=h.boundary();value['foreign_cpu_start']=h.cpu_observation();value['end']=h.boundary()
        require(not value['foreign_cpu_start']['inspection_errors'],'uninspectable admission telemetry')
        value['status']='WAITING' if h.loaded(value['start'],value['end'],value['foreign_cpu_start']) else 'PASS'
    except Exception as error:value['error']=str(error)
    value['end_utc']=utc().isoformat();path=HERE/'polls'/f'poll-{len(poll_paths())+1:06d}.json';immutable(path,value)
    if value['status']=='ERROR':immutable(HERE/'ERROR.json',dict(reason=value['error'],poll=ref(path)))
    return status()


def parent_death(expected=None):
    """Linux-only, fail closed when the caller disappears, including fork race."""
    import ctypes
    expected=os.getppid() if expected is None else expected
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(1,signal.SIGKILL,0,0,0)!=0:raise OSError(ctypes.get_errno(),'PR_SET_PDEATHSIG')
    if os.getppid()!=expected:os.kill(os.getpid(),signal.SIGKILL)


def request_policy(request):
    if request.get('synthetic'):
        require(os.environ.get('TB_LVL_0_ALLOW_SYNTHETIC_TESTS')=='1' and request['lock']!=LOCK,'synthetic requests require a separate test lock and explicit test environment')
    else:require(request['policy']==POLICY and request['lock']==LOCK,'fixed deadline/lock changed')
    require(stamp(request['policy']['refuse'])<=stamp(request['policy']['term'])<stamp(request['policy']['kill'])<stamp(request['policy']['release']),'deadline order differs')


def group_members(pgid):
    rows=[]
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:
            raw=(path/'stat').read_text();fields=raw[raw.rindex(')')+2:].split()
            if int(fields[2])==pgid:rows.append(dict(pid=int(path.name),state=fields[0],pgid=pgid,raw_stat=raw))
        except (OSError,ValueError,IndexError):continue
    return rows


def task_observation(pid):
    try:
        tasks=sorted(int(p.name) for p in Path('/proc',str(pid),'task').iterdir() if p.name.isdigit())
        return dict(status='observed',task_ids=tasks,count=len(tasks))
    except OSError:return dict(status='process exited or inaccessible',task_ids=[],count=None)


def watchdog(parent,pgid,done,policy):
    require(os.getpgrp()==pgid and os.getsid(0)==pgid,'watchdog must belong to its newly created owned session')
    signal.signal(signal.SIGTERM,signal.SIG_IGN)
    sent=False
    while True:
        if Path(done).exists():return
        if os.getppid()!=parent:os.killpg(pgid,signal.SIGKILL)
        now_value=utc()
        if now_value>=stamp(policy['kill']):os.killpg(pgid,signal.SIGKILL)
        if not sent and now_value>=stamp(policy['term']):os.killpg(pgid,signal.SIGTERM);sent=True
        time.sleep(.05)


def session(request_path):
    request=load(request_path);request_policy(request)
    require(os.getpid()==os.getpgrp()==os.getsid(0),'owned session is required')
    signal.signal(signal.SIGTERM,lambda *_:None)
    done=Path(request['folder'])/'session.done'
    require(not done.exists() and not (Path(request['folder'])/'session.json').exists(),'owned session was already started; never replay its command')
    watcher=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'_watchdog',str(os.getpid()),str(os.getpgrp()),str(done),json.dumps(request['policy'])],stdin=subprocess.DEVNULL)
    try:
        parent=os.getpid()
        inner=request['command'] if request.get('synthetic') else [sys.executable,'-B',str(Path(__file__).resolve()),'_inside',str(request_path)]
        flock_command=['flock','-F',request['lock'],*inner]
        immutable(Path(request['folder'])/'session.json',dict(schema='tb-lvl-0-session-v1',request_sha256=sha(request_path),
            pid=parent,pgid=os.getpgrp(),session_id=os.getsid(0),parent_pid=os.getppid(),watchdog_pid=watcher.pid,
            flock_command=flock_command,policy=request['policy'],started_utc=utc().isoformat(),parent_death_signal='SIGKILL'))
        proc=subprocess.Popen(flock_command,stdin=subprocess.DEVNULL,preexec_fn=lambda:parent_death(parent))
        while proc.poll() is None:
            if watcher.poll() is not None:os.killpg(os.getpgrp(),signal.SIGKILL)
            time.sleep(.05)
        code=proc.wait()
    finally:
        done.write_bytes(b'done\n');watcher.wait(timeout=2)
    return code


def inside(request_path):
    request=load(request_path);request_policy(request);signal.signal(signal.SIGTERM,lambda *_:None)
    folder=Path(request['folder']);h=observer();record=dict(schema='tb-lvl-0-receipt-v1',identity=request['identity'],
        target=request['target'],request_sha256=sha(request_path),lock_path=request['lock'],policy=request['policy'],
        helper_sha256=sha(HELPER),waiting_since_utc=request['waiting_since_utc'],command=request['command'],
        status='ERROR',command_started=False,returncode=None)
    output=errors=b'';parsed_result=None
    record.update(pid=os.getpid(),pgid=os.getpgrp(),session_id=os.getsid(0),parent_pid=os.getppid(),parent_death_signal='SIGKILL')
    record['worker_environment']={'GOMAXPROCS':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
    out=(folder/'stdout').open('xb');err=(folder/'stderr').open('xb')
    try:
        inode=Path(request['lock']).stat().st_ino;held=[]
        for line in Path('/proc/locks').read_text().splitlines():
            fields=line.split()
            if len(fields)>=6 and fields[1:4]==['FLOCK','ADVISORY','WRITE'] and fields[4]==str(os.getpid()) and int(fields[5].rsplit(':',1)[-1])==inode:held.append(line)
        require(len(held)==1,'native entry must hold its own external flock-F descriptor')
        record['flock_lock_record']=held[0]
        if utc()>=stamp(request['policy']['refuse']):raise DeadlineRefusal('new attempt refused at cutoff')
        record['foreign_cpu_start']=h.cpu_observation();record['start']=h.boundary()
        require(not record['foreign_cpu_start']['inspection_errors'],'uninspectable admission telemetry')
        if not h.loaded(record['start'],record['start'],record['foreign_cpu_start']):
            if utc()>=stamp(request['policy']['refuse']):raise DeadlineRefusal('new native call refused at cutoff')
            cwd=Path(request['cwd']);require(cwd.is_dir() and not any(cwd.iterdir()),'round cwd must be fresh and empty')
            record['command_started']=True;expected_parent=os.getpid()
            child=subprocess.Popen(request['command'],cwd=cwd,stdin=subprocess.DEVNULL,stdout=out,stderr=err,
                preexec_fn=lambda:parent_death(expected_parent),env=dict(os.environ,**record['worker_environment']))
            record['worker_pid']=child.pid
            immutable(folder/'worker-started.json',dict(pid=child.pid,pgid=os.getpgrp(),utc=utc().isoformat()))
            observed_tasks=[task_observation(child.pid)]
            while child.poll() is None:
                time.sleep(.1);observed_tasks.append(task_observation(child.pid))
            record['returncode']=child.wait()
            record['worker_tasks']=dict(start=observed_tasks[0],end=observed_tasks[-1],
                maximum_observed=max((x['count'] for x in observed_tasks if x['count'] is not None),default=None),
                observational_only=True,samples=observed_tasks)
        record['end']=h.boundary();delta=h.other_cpu_delta(record['start'],record['end'])
        record['start']['other_cpu_delta']=record['end']['other_cpu_delta']=delta
        if record['command_started'] and record['returncode']!=0:
            record['status']='DEADLINE' if record['returncode'] in (-signal.SIGTERM,-signal.SIGKILL) and utc()>=stamp(request['policy']['term']) else 'ERROR'
        elif record['command_started']:
            native=Path(request['cwd'])/'silesia.ref.tar.tbb'
            immutable(folder/'native.tbb',native.read_bytes());record['tbb_sha256']=sha(folder/'native.tbb')
            parsed=parse_tbb(native.read_bytes(),request['target']['config'])
            if request['target']['kind']=='method':require(parsed['compressed_bytes']==KNOWN,'known-answer size mismatch')
            parsed_result=dict(schema='tb-lvl-0-result-v1',identity=request['identity'],config=request['target']['config'],
                round=request['target']['round'],**parsed,raw=ref(folder/'native.tbb'))
            if utc()>=stamp(request['policy']['term']):record['status']='DEADLINE';parsed_result=None
            else:record['status']='LOADED' if h.loaded(record['start'],record['end'],record['foreign_cpu_start']) else 'CLEAN'
        else:record['status']='LOADED'
        if record['status']=='LOADED':
            record['ps_command']='ps -eo pid,user,pcpu,comm --sort=-pcpu | head -8'
            record['ps_top8']=subprocess.check_output(['bash','-c',record['ps_command']],text=True)
    except DeadlineRefusal as error:record.update(status='DEADLINE',error=str(error))
    except Exception as error:record.update(status='ERROR',error=str(error))
    finally:out.close();err.close()
    record.update(stdout_sha256=sha(folder/'stdout'),stderr_sha256=sha(folder/'stderr'))
    immutable(folder/'receipt.json',record)
    if parsed_result is not None:
        immutable(folder/'result.json',dict(**parsed_result,receipt=ref(folder/'receipt.json')))
    return 0 if record['status']=='CLEAN' else 77 if record['status']=='LOADED' else 2


def step():
    view=status()
    if view['status'] not in ('WAITING','READY') or view['next_poll_utc']:return view
    t=view['next_unit'];passed=ready(t)
    if passed is None:return view
    prep,_=admission();require(sha(prep['input']['path'])==INPUT_SHA,'source input changed before actual attempt')
    require(not utc_deadline(),'new actual attempt refused at cutoff')
    records=history(prep,t);number=len(records)+1;require(number<=3,'no fourth actual attempt')
    folder=raw_path(t)/('attempt-'+str(number));require(not folder.exists(),'orphan attempt cannot be overwritten')
    folder.mkdir(parents=True);cwd=folder/'cwd';cwd.mkdir()
    request=dict(schema='tb-lvl-0-request-v1',identity=unit_identity(prep,t),target=t,folder=str(folder),cwd=str(cwd),
        command=native_command(prep['binary']['path'],t['config'],prep['input']['path']),policy=POLICY,lock=LOCK,synthetic=False,waiting_since_utc=utc().isoformat())
    immutable(folder/'request.json',request)
    immutable(HERE/'consumptions'/passed.name,dict(schema='tb-lvl-0-consumption-v1',identity=prep['identity'],target=t,
        attempt=number,poll=ref(passed),request=ref(folder/'request.json'),receipt_path=(folder/'receipt.json').relative_to(HERE).as_posix(),committed_before_attempt_utc=utc().isoformat()))
    expected_parent=os.getpid()
    child=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'_session',str(folder/'request.json')],
        start_new_session=True,stdin=subprocess.DEVNULL,preexec_fn=lambda:parent_death(expected_parent))
    code=child.wait()
    members=group_members(child.pid)
    immutable(folder/'supervision.json',dict(schema='tb-lvl-0-supervision-v1',request=ref(folder/'request.json'),session=ref(folder/'session.json') if (folder/'session.json').exists() else None,
        session_pid=child.pid,pgid=child.pid,session_id=child.pid,session_returncode=code,reaped_utc=utc().isoformat(),
        members_after_session_reap=members,live_group_empty=not any(m['state']!='Z' for m in members),policy=POLICY,
        deadline_release_met=utc()<stamp(POLICY['release'])))
    require(not any(m['state']!='Z' for m in members),'owned group still has live members after supervisor reap')
    if not (folder/'receipt.json').exists():
        for stream in ('stdout','stderr'):
            if not (folder/stream).exists():immutable(folder/stream,b'')
        immutable(folder/'receipt.json',dict(schema='tb-lvl-0-receipt-v1',identity=request['identity'],target=t,status='DEADLINE' if utc()>=stamp(POLICY['term']) else 'ERROR',
            command_started=None,returncode=None,session_returncode=code,reaped_utc=utc().isoformat(),
            error='owned session ended without a final receipt; native start is unknown',stdout_sha256=sha(folder/'stdout'),stderr_sha256=sha(folder/'stderr'),policy=POLICY))
    receipt=load(folder/'receipt.json')
    if receipt['status']=='ERROR':immutable(HERE/'ERROR.json',dict(reason=receipt.get('error','native error'),receipt=ref(folder/'receipt.json')))
    finish(prep,t);return status()


def main():
    if len(sys.argv)>1 and sys.argv[1].startswith('_'):
        action=sys.argv[1]
        if action=='_watchdog':watchdog(int(sys.argv[2]),int(sys.argv[3]),sys.argv[4],json.loads(sys.argv[5]));return 0
        return session(Path(sys.argv[2])) if action=='_session' else inside(Path(sys.argv[2]))
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare','poll','step','status','run'))
    parser.add_argument('--build-dir',type=Path);parser.add_argument('--input',type=Path,default=INPUT)
    parser.add_argument('--mapping-resolved',action='store_true');args=parser.parse_args()
    require(sys.platform=='linux' and not os.environ.get('OVH_BENCH_LOCK_HELD'),'Linux controller outside benchmark lock required')
    parent_death();os.sched_setaffinity(0,{15})
    import fcntl
    STATE.mkdir(parents=True,exist_ok=True)
    with (STATE/'controller.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.action=='prepare':value=prepare(args.build_dir,args.input,args.mapping_resolved)
        elif args.action=='poll':value=poll()
        elif args.action=='step':value=step()
        elif args.action=='status':value=status()
        else:
            while True:
                value=poll()
                if value['status'] not in ('WAITING','READY'):break
                value=step()
                print(json.dumps(dict(status=value['status'],next_unit=value.get('next_unit'))),flush=True)
                if value['status'] not in ('WAITING','READY'):break
                time.sleep(min(30,max(1,(stamp(value['next_poll_utc'])-utc()).total_seconds())) if value.get('next_poll_utc') else 1)
    print(json.dumps(value,sort_keys=True));return 0 if value['status'] in ('COMPLETE','WAITING','READY') else 2


if __name__=='__main__':raise SystemExit(main())
