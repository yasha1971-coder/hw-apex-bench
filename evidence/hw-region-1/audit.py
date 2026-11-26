"""Independent HW-REGION-1 saved-data controller; no codecs or clocks.

Only retained bytes/receipts and read-only Git preregistration objects are read.
No experiment module is imported. Missing phase artifacts mean INCOMPLETE.
"""
import argparse
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import random
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CALIBRATION = '8108834615cbd651f79f77cb8d81fed24fa269f1'
BASE = 'e8aa8488310d8cb7d5793f2e49a707c67f80b689'
SIGNATURE = "[written by ChatGPT (AI) at the author's request; checked by the author]"
LOCK = '/run/lock/ovh-bench.lock'
CODECS = ('aceapex','zstd_seekable','bgzip')
GRIDS = (4096,16384,65536)
SIZES = (4096,16384,65536,262144)
R,N,WARMUPS = 16384,1000,12
PINS = {'aceapex':'ce6b6740c7aae8a01720d615ae024c181b7d52b6',
        'zstd':'f8745da6ff1ad1e7bab384bd1f9d742439278e99',
        'htslib':'4b705e4fada8ee2b6b15746f725ee8ac51631803',
        'libdeflate':'dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f'}
INPUTS = {'chr1':(253935557,'04ee6db2e94ccc4daddc168453189d8c17a01454ba67ac0443a73a0401408ee0'),
          'enwik8':(100000000,'2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8'),
          'silesia':(211947520,'a667bac80089b3d04d5496772149e632f0758974b0579d743cd8d6e5e0d63eb2')}
MANIFEST = 'evidence/t2t-regions-20260916/manifest.json'
MANIFEST_SHA = 'c5bc7014ecd0d6c7855e7ad1b01afbd20b8a7f2e55c93c8e78098fa4c049a763'
BUNDLE_SHA = '78f354a13f70e64ac6790af27e2befa98ac132d582a238a3e804201c24ca9808'
SOURCE_BINDINGS = {}
PRIVATE_CHECKED,PRIVATE_UNAVAILABLE = set(),set()
HOST = None
RETURNED_CHECKED = set()
OBSERVATIONS = {}
UNITS = {}
SOURCES = ('CALIBRATION.md','PROTOCOL.md','run.py','instrument.py','worker.c','native_versions.c',
           'native_constants.c','controls.py','setup.py','model.py','ovh_bench.py')


class Incomplete(ValueError):
    pass


def check(ok, reason):
    if not ok:
        raise ValueError(reason)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def valid_sha(value):
    return isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value)


def packed(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()


def bind(path, digest):
    path = Path(path).resolve()
    if path.is_relative_to(ROOT.resolve()) and not path.is_relative_to((ROOT/'.work').resolve()):
        import os
        name = os.path.relpath(path,HERE).replace('\\','/')
        check(SOURCE_BINDINGS.setdefault(name,digest)==digest, 'evidence changed while being audited: '+name)


def sha(path):
    path=Path(path)
    if not path.is_file():
        raise Incomplete('missing evidence: '+str(path))
    with path.open('rb') as stream:
        result=hashlib.file_digest(stream,'sha256').hexdigest()
    bind(path,result)
    return result


def unique(pairs):
    value={}
    for key,item in pairs:
        check(key not in value,'duplicate JSON key: '+key)
        value[key]=item
    return value


def load(path):
    path=Path(path)
    if not path.is_file():
        raise Incomplete('missing evidence: '+str(path))
    raw=path.read_bytes();bind(path,hashlib.sha256(raw).hexdigest())
    return json.loads(raw,object_pairs_hook=unique)


def public(name):
    check(isinstance(name,str) and name,'missing public path')
    path=(HERE/name).resolve()
    check(path.is_relative_to(HERE.resolve()),'public path escapes this experiment')
    return path


def file_ref(value):
    check(isinstance(value,dict) and {'path','sha256'} <= value.keys() and valid_sha(value['sha256']), 'invalid public reference')
    path=public(value['path'])
    check(sha(path)==value['sha256'],'referenced bytes changed: '+value['path'])
    if 'bytes' in value:
        check(integer(value['bytes']) and path.stat().st_size==value['bytes'],'public byte count changed')
    return path


def json_ref(value):
    return load(file_ref(value))


def rows_ref(value):
    path=file_ref(value)
    return [json.loads(line,object_pairs_hook=unique) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def private(value):
    check(isinstance(value,dict) and isinstance(value.get('path'),str) and valid_sha(value.get('sha256')), 'invalid private artifact')
    path=Path(value['path'])
    if not path.is_file():
        PRIVATE_UNAVAILABLE.add(value['path']);return False
    if 'bytes' in value:
        check(integer(value['bytes']) and path.stat().st_size==value['bytes'],'private artifact size changed')
    identity=value['path'],value['sha256']
    if identity not in PRIVATE_CHECKED:
        check(sha(path)==value['sha256'],'private artifact SHA changed: '+str(path))
        PRIVATE_CHECKED.add(identity)
    return True


def git_bytes(path, commit='HEAD'):
    return subprocess.check_output(['git','-C',str(ROOT),'show',commit+':'+path],stderr=subprocess.PIPE)


def source_hash(name):
    path=ROOT/name
    raw=git_bytes(name)
    digest=hashlib.sha256(raw).hexdigest()
    # Canonical tracked source bytes avoid Windows CRLF conversion of old
    # adapters; measured Linux builds and Git objects use these same bytes.
    bind(path,digest)
    return digest


def quantile(values, numerator):
    check(len(values)==N and all(integer(v,1) for v in values),'exactly 1000 positive integer latency samples required')
    return sorted(values)[(N*numerator+99)//100-1]


def nnls(points):
    """Exact global fit; this function receives only standalone-zstd points."""
    check(len(points)==4 and sorted(x for x,y in points)==list(SIZES)
          and all(integer(x,1) and integer(y,1) for x,y in points),'four frozen standalone calibration points required')
    points=sorted(points)
    n=len(points);sx=sum(x for x,y in points);sy=sum(y for x,y in points)
    sxx=sum(x*x for x,y in points);sxy=sum(x*y for x,y in points)
    denominator=n*sxx-sx*sx
    a,b=Fraction(sxx*sy-sx*sxy,denominator),Fraction(n*sxy-sx*sy,denominator)
    candidates=[(Fraction(0),max(Fraction(sxy,sxx),0)),(max(Fraction(sy,n),0),Fraction(0)),(Fraction(0),Fraction(0))]
    if a>=0 and b>=0:
        candidates.append((a,b))
    def score(pair):
        c,d=pair
        return sum((Fraction(y)-c-d*x)**2 for x,y in points),c,d
    a,b=min(candidates,key=score)
    return dict(c_call=str(a),c_byte=str(b),squared_residual_sum=str(score((a,b))[0]),
                points=[dict(bytes=x,p50_ns=y,predicted_ns=str(a+b*x),residual_ns=str(Fraction(y)-a-b*x)) for x,y in points])


def predict(latency_rows, counter_rows, coefficients):
    check(len(latency_rows)==len(counter_rows)==N,'model needs all 1000 paired latency/work samples')
    a,b=Fraction(coefficients['c_call']),Fraction(coefficients['c_byte'])
    values=[]
    for query,(timed,work) in enumerate(zip(latency_rows,counter_rows)):
        check(timed['query']==work['query']==query and timed['offset']==work['offset'], 'model trace/query pairing differs')
        calls,decoded=work['zstd_calls'],work['zstd_bytes']
        check(integer(calls) and integer(decoded),'model work counters must be measured nonnegative integers')
        values.append((calls*a+decoded*b,query,calls*a,decoded*b))
    estimate,query,calls,decoded=sorted(values,key=lambda v:(v[0],v[1]))[499]
    measured=quantile([r['elapsed_ns'] for r in latency_rows],50)
    residual=Fraction(measured)-estimate
    terms={'calls':calls,'bytes':decoded,'residual':residual}
    check(sum(terms.values())==measured,'additive representative terms do not sum to measured p50')
    return dict(measured_p50_ns=measured,predicted_p50_ns=str(estimate),representative_query=query,
                terms_ns={k:str(v) for k,v in terms.items()},shares={k:str(v/measured) for k,v in terms.items()},
                signed_relative_error=str((estimate-measured)/measured),within_20_percent=5*abs(estimate-measured)<=measured,
                calls_at_least_half=2*calls>=measured,
                largest_absolute_component=min(terms,key=lambda k:(-abs(terms[k]),k)))


def process_rows(rows):
    result={}
    check(isinstance(rows,list),'missing raw process table')
    for row in rows:
        pid=row['pid'];check(integer(pid,1) and pid not in result,'invalid/duplicate raw PID')
        raw=row['raw_stat'];left,right=raw.index('('),raw.rindex(')');fields=raw[right+2:].split()
        check(int(raw[:left].strip())==pid and row['comm']==raw[left+1:right] and row['state']==fields[0]
              and row['ppid']==int(fields[1]) and row['ticks']==int(fields[11])+int(fields[12])
              and row['start_ticks']==int(fields[19]) and integer(row['uid']), 'process telemetry differs from raw /proc/stat')
        result[pid]=row
    return result


def foreign_cpu(value):
    check(integer(value['interval_ns'],1000000000) and integer(value['hz'],1),'foreign CPU interval must be at least one second')
    before,after=process_rows(value['before']),process_rows(value['after'])
    excluded=value['excluded_ancestry']
    check(isinstance(excluded,list) and excluded==sorted(set(excluded)) and all(integer(p) for p in excluded), 'invalid observer ancestry')
    # Validate that the excluded set is one observer's before/after ancestry,
    # without relying on comm names or exempting all sessions of a user.
    def ancestry(pid,table):
        seen=set()
        while pid in table and pid not in seen:
            seen.add(pid);pid=table[pid]['ppid']
        seen.add(pid);return seen
    leaves=[pid for pid in after if pid in excluded and not any(r['ppid']==pid and other in excluded for other,r in after.items())]
    check(any(ancestry(pid,before)|ancestry(pid,after)==set(excluded) for pid in leaves),'excluded processes are not an explicit controlling ancestry')
    expected=[]
    with localcontext() as ctx:
        ctx.prec=28
        for pid,row in sorted(after.items()):
            if pid in excluded:
                continue
            old=before.get(pid);same=old is not None and old['start_ticks']==row['start_ticks']
            delta=row['ticks']-(old['ticks'] if same else 0)
            check(integer(delta),'process CPU counter regressed')
            high=10*delta*1000000000>value['hz']*value['interval_ns']
            expected.append(dict(pid=pid,start_ticks=row['start_ticks'],uid=row['uid'],comm=row['comm'],ticks_delta=delta,
                                 observed_since_birth=not same,percent_one_cpu=str(Decimal(100)*delta*1000000000/(value['hz']*value['interval_ns'])),
                                 exceeds_ten_percent=high))
    check(value['live_processes']==expected and value['exceeded']==[r for r in expected if r['exceeds_ten_percent']]
          and value['exited_pids']==sorted(set(before)-set(after)),'foreign CPU classification differs from raw ticks')
    check(isinstance(value['inspection_errors'],list) and not value['inspection_errors'],'uninspectable live-process telemetry')
    return bool(value['exceeded'])


def cpu_delta(start,end):
    def parse(raw):
        result={}
        for line in raw.splitlines():
            f=line.split()
            if f and f[0].startswith('cpu') and f[0][3:].isdigit():
                check(len(f)>=9 and f[0] not in result and all(v.isdigit() for v in f[1:9]),'invalid CPU raw counters')
                result[f[0]]=list(map(int,f[1:9]))
        check('cpu0' in result,'missing pinned CPU accounting');return result
    first,last=parse(start['proc_stat_raw']),parse(end['proc_stat_raw'])
    check(first.keys()==last.keys(),'CPU accounting set changed')
    result={}
    with localcontext() as ctx:
        ctx.prec=28
        for name in first:
            if name=='cpu0':continue
            delta=[b-a for a,b in zip(first[name],last[name])]
            check(min(delta)>=0,'CPU accounting regressed')
            total=sum(delta);busy=total-delta[3]-delta[4]
            result[name]=dict(total_jiffies=total,busy_jiffies=busy,idle_jiffies=delta[3],iowait_jiffies=delta[4],
                              busy_percent=str(Decimal(100)*busy/total) if total else None)
    expected=dict(pinned_core=0,observational_only=True,cpus=result)
    check(start['other_cpu_delta']==end['other_cpu_delta']==expected,'other-core observation differs from raw ticks')


def receipt(value,status):
    global HOST
    check(value.get('schema')=='hw-region-1-ovh-v1' and value.get('status')==status and status in ('CLEAN','LOADED'), 'unfinished/ERROR load attempt')
    check(value.get('lock_path')==LOCK and value.get('timed_threads')==1 and value.get('foreign_cpu_percent_threshold')=='10.0'
          and value.get('helper_sha256')==sha(HERE/'ovh_bench.py') and value.get('protocol_sha256')==sha(HERE/'PROTOCOL.md')
          and value.get('calibration_sha256')==sha(HERE/'CALIBRATION.md'),'wrong new-study helper/policy/source')
    argv,command=value['flock_command'],value['command']
    check(isinstance(argv,list) and len(argv)>=6 and argv[:2]==['flock',LOCK] and argv[3]=='-B' and argv[5]=='_inside'
          and isinstance(command,list) and command and argv[-len(command):]==command,'blocking external flock/command missing')
    foreign=foreign_cpu(value['foreign_cpu_start'])
    loads=[]
    for boundary in (value['start'],value['end']):
        check(boundary['hostname']=='ace-core' and 'AMD EPYC 4344P' in boundary['cpu'] and boundary['pinned_core']==0
              and boundary['timed_threads']==1 and integer(boundary['nproc'],1) and boundary['date_u'],'wrong host/core/literal boundary')
        signature=tuple(boundary[k] for k in ('hostname','cpu','kernel','governor','pinned_core','host_logical_cpus'))
        if HOST is None:HOST=signature
        check(signature==HOST,'host/kernel/governor changed between timing units')
        raw=boundary['loadavg_raw'];check(isinstance(raw,str) and len(raw.split())==5,'missing literal load average')
        number=Decimal(raw.split()[0]);check(number.is_finite() and number>=0,'invalid load1')
        check(Decimal(boundary['load1_minus_T'])==number-1,'load1 minus T differs')
        loads.append(number)
    loaded=foreign or any(n-1>Decimal('1.0') for n in loads)
    check(loaded==(status=='LOADED'),'LOADED differs from exact load/T/foreign predicates')
    check(value['command_started'] is (not foreign and loads[0]-1<=Decimal('1.0')),'worker start differs from admission')
    check((type(value['returncode']) is int and value['returncode']==0) if value['command_started'] else value['returncode'] is None,
          'worker error cannot be a load-only retry')
    cpu_delta(value['start'],value['end'])
    if status=='LOADED':
        check(value.get('ps_command')=='ps -eo pid,user,pcpu,comm --sort=-pcpu | head -8'
              and isinstance(value.get('ps_top8'),str) and value['ps_top8'],'missing LOADED ps top eight')


def verify_setup():
    value=load(HERE/'setup.json')
    check(value.get('schema')=='hw-region-1-setup-v1' and value.get('measurements_of_time') is False, 'wrong setup schema/timing scope')
    identity=value['identity']
    check(identity['calibration_commit']==CALIBRATION and git_bytes('evidence/hw-region-1/CALIBRATION.md',CALIBRATION)==(HERE/'CALIBRATION.md').read_bytes(),
          'first literal preregistration changed')
    for name in ('PROTOCOL.md','SOURCE_PATHS.md'):
        path=HERE/name;check(path.read_text(encoding='utf-8').splitlines()[0]==SIGNATURE,'required author signature absent: '+name);sha(path)
    for name,digest in identity['source_sha256'].items():
        check(source_hash(name)==digest,'setup source changed: '+name)
    old=git_bytes('codecs/aceapex.sh',BASE)
    check(git_bytes('codecs/aceapex_v220.sh')==old,'retained v2.2.0 adapter differs from accepted original')
    expected=old.replace(b'ACE_REF=0a143cd64b35a802835f18c361f981968edf25a1',b'ACE_REF='+PINS['aceapex'].encode())
    expected=expected.replace(b'ACE_LABEL=aceapex-v2.2.0-interactive',b'ACE_LABEL=aceapex-v2.6.5-interactive')
    expected=expected.replace(b'ACE_VERSION=aceapex-v2.2.0@0a143cd64b35a802835f18c361f981968edf25a1',b'ACE_VERSION=aceapex-v2.6.5@'+PINS['aceapex'].encode())
    check(git_bytes('codecs/aceapex.sh')==expected,'active adapter changed beyond requested release pin/label/version')
    check(set(value['deps'])==set(PINS),'setup omitted a dependency')
    for name,pin in PINS.items():
        item=value['deps'][name]
        check(item['commit']==pin and item['source_clean'] is True and item['headers_sha256'],'dependency source/header pin differs: '+name)
        if 'library_path' in item:private(dict(path=item['library_path'],sha256=item['library_sha256']))
        if 'cli_path' in item:private(dict(path=item['cli_path'],sha256=item['cli_sha256']))
    ace=value['deps']['aceapex']
    check(ace['annotated_tag_object']=='8fd46ca8c0c907cf352f15fb6de062d5531e6489'
          and ace['public_api_version']=='2.6.5' and ace['c99_header_version']=='2.6.4'
          and isinstance(ace['cli_version'],str) and ace['cli_version'],'ACE release versus literal linked header identity differs')
    check('1.5.7' in value['deps']['zstd']['cli_version'] and '1.24' in value['deps']['htslib']['cli_version'],'baseline CLI version differs')
    for item in value['binaries'].values():private(item)
    manifest_bytes=git_bytes(MANIFEST)
    check(hashlib.sha256(manifest_bytes).hexdigest()==MANIFEST_SHA,'historical window manifest bytes changed')
    manifest=json.loads(manifest_bytes,object_pairs_hook=unique)
    check(manifest['seed']==20260916 and manifest['window_bytes']==2097152 and len(manifest['windows'])==30,'frozen window selection changed')
    expected_inputs=dict(INPUTS)
    for index,window in enumerate(manifest['windows']):
        name=f't2t-{index:02d}';expected_inputs[name]=(2097152,window['input_sha256'])
        item=value['inputs'][name]
        check(item['frozen_window']==window and item['parent_manifest_sha256']==MANIFEST_SHA,'window origin/coordinates changed')
    check(set(value['inputs'])==set(expected_inputs) and len(value['inputs'])==33,'setup omitted/added a corpus')
    for name,(size,digest) in expected_inputs.items():
        item=value['inputs'][name]
        check(item['bytes']==size and item['sha256']==digest,'corpus bytes/full SHA differs: '+name);private(item)
    check(value['inputs']['chr1']['md5']=='9465e0f0df6e2c6eb39729c39cee5465','chr1 full MD5 differs')
    source=value['frozen_bundle']
    check(source['manifest_sha256']==MANIFEST_SHA,'T2T acquisition uses a different manifest')
    if source.get('method')=='verified canonical FASTA recovery':
        recovered=source['source']
        check(recovered['compressed_bytes']==932696125 and recovered['compressed_md5']=='9280657210e4161147cbe13b022225b9'
              and recovered['expanded_bytes']==3156259565 and recovered['expanded_md5']=='cd1e52ce400c027ed0b7ab4b9d613f5a'
              and recovered['gzip_crc_verified'] is True and recovered['windows_verified']==30
              and recovered['manifest_sha256']==MANIFEST_SHA,'canonical T2T recovery is incomplete')
    else:
        check(source['sha256']==BUNDLE_SHA and source['bytes']==53075428,'frozen ZIP differs')
    cases={f'{name}-g{g}':dict(corpus=name,g=g,request_bytes=R) for name in expected_inputs
           for g in ((16384,) if name in ('enwik8','silesia') else GRIDS)}
    check(value['cases']==cases and len(cases)==95,'setup does not contain the exact 95 planned archive cases')
    for label,reference in value['commands'].items():
        path=HERE/'setup-logs'/label/'command.json'
        check(sha(path)==reference['sha256'],'setup command receipt changed')
        command=load(path)
        check(command['status']=='COMPLETE' and command['returncode']==0,'setup command failed')
        for stream in ('stdout','stderr'):
            check(sha(path.parent/('command.'+stream))==command[stream+'_sha256'],'setup command log changed')
    return value


def verify_archives(case_id,setup):
    value=load(HERE/'archives'/(case_id+'.json'))
    check(value.get('schema')=='hw-region-1-archives-v1' and value['case_id']==case_id and case_id in setup['cases'], 'archive case is outside planned grid')
    case=setup['cases'][case_id];source=setup['inputs'][case['corpus']]
    check(all(value[k]==v for k,v in case.items()) and value['input']==source and value['setup_sha256']==sha(HERE/'setup.json'), 'archive case input/setup changed')
    check(set(value['formats'])==set(CODECS),'archive case omitted a codec')
    for codec,item in value['formats'].items():
        effective=min(case['g'],65280) if codec=='bgzip' else case['g']
        check(item['effective_g']==effective and item['input_sha256']==source['sha256'] and item['bit_perfect'] is True
              and item['restore_sha256']==source['sha256'] and item['setup_sha256']==value['setup_sha256'], 'archive effective geometry/restore differs')
        check(item['stored_bytes']==item['bytes']+sum(index['bytes'] for index in item['indexes']) and integer(item['stored_bytes'],1), 'complete archive/index accounting differs')
        check(len(item['indexes'])==(1 if codec=='bgzip' else 0),'required sidecar omitted or invented')
        for index in item['indexes']:
            check(index['path']==item['path']+'.gzi' and integer(index['bytes'],8),'wrong required BGZF sidecar');private(index)
        check(item['level']=={'aceapex':2,'zstd_seekable':3,'bgzip':6}[codec],'codec level changed')
        expected_env={'ACEAPEX_BS':str(case['g']),'LIT_CHUNK':'65536','FSE_CHUNK':'4096'} if codec=='aceapex' else {}
        check(item['environment']==expected_env and item['command']['environment']==expected_env,'interactive encoder environment changed')
        argv=item['command']['argv']
        if codec=='aceapex':
            check(argv[-4:]==['--threads','1','--level','2'],'ACE encoder thread/level changed')
        private(item)
    return value


def expected_trace(source):
    generator=random.Random(20261126+int(source['sha256'],16))
    values=[generator.randrange(source['bytes']-R+1) for _ in range(N+WARMUPS)]
    return values[:WARMUPS],values[WARMUPS:]


def verify_native_build():
    value=load(HERE/'native/build.json')
    check(value.get('schema')=='hw-region-1-native-v1' and value.get('timed_readers_unchanged') is True,'native instrument source scope differs')
    identity=value['identity'];provenance=identity['provenance']
    check(identity['setup_sha256']==sha(HERE/'setup.json') and provenance['calibration_commit']==CALIBRATION
          and provenance['calibration_sha256']==sha(HERE/'CALIBRATION.md') and provenance['protocol_sha256']==sha(HERE/'PROTOCOL.md'), 'native build source/preregistration changed')
    for name,digest in provenance['source_sha256'].items():
        check(source_hash(name)==digest,'native timed source changed: '+name)
    expected={codec+'-'+kind for codec in CODECS for kind in ('timed','count')}|{'constants','worker'}
    check(set(value['artifacts'])==expected,'missing native timed/counter/API artifact')
    for item in value['artifacts'].values():private(item)
    for item in value['sources'].values():private(item)
    for label,command in value['commands'].items():
        check(command['status']=='COMPLETE' and command['returncode']==0,'native build command failed')
        path=HERE/'native'/label/'command.json'
        check(load(path)==command,'public native command receipt changed')
        for stream in ('stdout','stderr'):
            check(sha(path.parent/('command.'+stream))==command[stream+'_sha256'],'native build logs changed')
    return value


def verify_trace(value,source):
    warm,offsets=expected_trace(source)
    check(value.get('schema')=='hw-region-1-trace-v1' and value['input_bytes']==source['bytes']
          and value['input_sha256']==source['sha256'] and value['request_bytes']==R
          and value['seed_integer']==str(20261126+int(source['sha256'],16))
          and value['seed_rule']=='20261126 + int(input_sha256,16)' and value['encoding']=='uint64 little endian'
          and value['warmup_offsets']==warm and value['offsets']==offsets,'trace differs from frozen uniform seed/workload')
    for key,values in (('warmups',warm),('requests',offsets)):
        raw=b''.join(struct.pack('<Q',off) for off in values)
        check(value[key]['bytes']==len(raw) and value[key]['sha256']==hashlib.sha256(raw).hexdigest(),'binary trace identity differs')
        private(value[key])
    return value


def verify_request(value,setup,native):
    check(value.get('schema')=='hw-region-1-request-v1' and value['case_id'] in setup['cases'] and value['codec'] in CODECS,'request outside fixed grid')
    case=setup['cases'][value['case_id']]
    check(value['corpus']==case['corpus'] and value['g']==case['g'] and value['request_bytes']==R
          and value['queries']==N and value['warmups']==WARMUPS and value['input']==setup['inputs'][value['corpus']], 'request input/size differs')
    archive=verify_archives(value['case_id'],setup)
    check(value['archive']==archive['formats'][value['codec']] and value['effective_g']==value['archive']['effective_g']
          and file_ref(value['case_manifest'])==HERE/'archives'/(value['case_id']+'.json'),'request changed archive/index selection')
    trace=json_ref(value['trace']);verify_trace(trace,value['input'])
    check(trace['corpus']==value['corpus'] and value['trace_files']=={k:trace[k] for k in ('warmups','requests')},'request reuses another trace')
    for key,name in (('setup_sha256','setup.json'),('native_build_sha256','native/build.json'),('instrument_sha256','instrument.py'),
                     ('worker_sha256','worker.c'),('calibration_sha256','CALIBRATION.md'),('protocol_sha256','PROTOCOL.md')):
        check(value[key]==sha(HERE/name),'request source binding differs: '+name)
    check(value['timed_library']==native['artifacts'][value['codec']+'-timed']
          and value['counter_library']==native['artifacts'][value['codec']+'-count'],'request swaps a timed/counter reader')
    raw=dict(value);supplied=raw.pop('request_id')
    check(supplied==value['case_id']+'-'+value['codec']+'-'+hashlib.sha256(packed(raw)).hexdigest()[:16],'request identity differs')
    return trace


def verify_returned(record,rows,source):
    check(record['bytes']==len(rows)*R and valid_sha(record['sha256']),'returned capture length/identity differs')
    if not private(record):return
    key=record['sha256'],source['sha256'],tuple(r['offset'] for r in rows)
    if key in RETURNED_CHECKED:return
    original=Path(source['path'])
    if not original.is_file():return
    with Path(record['path']).open('rb') as returned,original.open('rb') as input_stream:
        for row in rows:
            data=returned.read(R)
            check(len(data)==R and hashlib.sha256(data).hexdigest()==row['returned_sha256'],'captured returned row SHA differs')
            input_stream.seek(row['offset'])
            check(data==input_stream.read(R),'captured returned bytes differ from exact source slice')
        check(returned.read(1)==b'','unaccounted returned bytes')
    RETURNED_CHECKED.add(key)


def verify_observation(value,request,mode,passes=1,probe_offsets=None):
    schema='hw-region-1-selfcheck-v1' if value.get('schema')=='hw-region-1-selfcheck-v1' else 'hw-region-1-observation-v1'
    check(value.get('schema')==schema and value.get('status')=='PASS' and value['mode']==mode and value['passes']==passes,
          'native observation mode/status differs')
    query_count=len(probe_offsets) if probe_offsets is not None else N
    check(value['queries_per_pass']==query_count and value['warmups']==(0 if probe_offsets is not None else WARMUPS)
          and value['measurements_of_time'] is (mode=='latency') and value['clock_calls']==(2*query_count*passes if mode=='latency' else 0),
          'native observation clock/workload scope differs')
    for key in ('request_id','codec','case_id','corpus','g','effective_g','native_build_sha256','instrument_sha256'):
        check(value[key]==request[key],'observation request/source differs: '+key)
    check(value['request_sha256']==hashlib.sha256(packed(request)).hexdigest()
          and value['input_sha256']==request['input']['sha256'] and value['archive_sha256']==request['archive']['sha256']
          and value['trace_sha256']==request['trace']['sha256'],'observation data/trace identity differs')
    trace=json_ref(request['trace'])
    expected=probe_offsets if probe_offsets is not None else trace['offsets']
    rows=value['rows'];check(len(rows)==query_count*passes,'native observation lost raw samples')
    counted=mode in ('counter','probe')
    fields=('zstd_calls','zstd_bytes','materialized_bytes','dctx_calls','oneshot_calls','stream_calls')
    for i,row in enumerate(rows):
        check(row['schema']=='hw-region-1-native-row-v1' and (row['pass'],row['query'],row['offset'])==(i//query_count,i%query_count,expected[i%query_count])
              and row['requested_bytes']==R and row['verified'] is True and valid_sha(row['returned_sha256']),'raw region identity/verification differs')
        check(integer(row['elapsed_ns'],1) if mode=='latency' else row['elapsed_ns'] is None,'wrong per-query clock scope')
        check(all(integer(row[k]) for k in fields) if counted else all(row[k] is None for k in fields),'counter sample type differs')
        if counted:
            check(row['zstd_calls']==row['dctx_calls']+row['oneshot_calls']+row['stream_calls']
                  and (row['zstd_calls']>0 or row['zstd_bytes']==0),'API counters double-count or invent decoded output')
            if request['codec']=='aceapex':
                check(row['oneshot_calls']==row['stream_calls']==0 and row['dctx_calls']==row['zstd_calls'],'ACE API differs from persistent DCtx calibration')
            elif request['codec']=='bgzip':
                check(row['zstd_calls']==row['zstd_bytes']==0,'BGZF invents zstd work')
    if mode=='latency':
        quantiles=[dict(pass_id=p,p50_ns=quantile([r['elapsed_ns'] for r in rows if r['pass']==p],50),
                        p99_ns=quantile([r['elapsed_ns'] for r in rows if r['pass']==p],99)) for p in range(passes)]
        check(value['quantiles']==quantiles,'reported p50/p99 differ from exact raw nearest rank')
    verify_returned(value['returned'],rows,request['input'])
    for key in ('native_stdout','native_stderr'):private(value[key])
    stdout=Path(value['native_stdout']['path'])
    if stdout.is_file():
        native_rows=[json.loads(line,object_pairs_hook=unique) for line in stdout.read_text().splitlines() if line.strip()]
        check(native_rows==[{k:v for k,v in row.items() if k!='returned_sha256'} for row in rows],'native stdout and retained rows differ')
    library=request['counter_library'] if counted else request['timed_library']
    command=value['native_command']
    worker=load(HERE/'native/build.json')['artifacts']['worker']
    check(len(command)==11 and command[0]==worker['path'] and command[1:3]==['region',mode] and command[3:6]==[library['path'],request['archive']['path'],request['input']['path']]
          and command[6]==(request['archive']['indexes'][0]['path'] if request['archive']['indexes'] else '') and command[10]==str(passes),
          'native callback command/library changed')
    if probe_offsets is None:
        check(command[7:9]==[request['trace_files']['warmups']['path'],request['trace_files']['requests']['path']],'native worker uses different trace bytes')
    if schema=='hw-region-1-selfcheck-v1':
        check(mode=='check' and value['invalid_ranges_rejected']==3 and value['corrupt_magic_rejected'] is True,'negative range/corruption controls failed')
        versions=value['versions'];check(isinstance(versions['reader_version'],str) and versions['reader_version'],'reader version is missing')
        if request['codec'] in ('aceapex','zstd_seekable'):
            check(versions['linked_zstd_version_number']==10507 and versions['linked_zstd_version']=='1.5.7','actually linked zstd differs')
        if request['codec']=='aceapex':
            check(versions['literal_c99_header_version']=='2.6.4' and PINS['aceapex'] in versions['reader_version'],'ACE tag/C99 header versions are misattributed')
            check(value['counter_known_sha256']==sha(HERE/'controls/counter-known.json'),'known counter fixture changed')
    return rows


def verify_constant_request(value,native):
    size=value['frame_bytes']
    check(value.get('schema')=='hw-region-1-constant-request-v1' and size in SIZES and value['level']==3 and value['api']=='ZSTD_decompressDCtx'
          and value['parent_input_sha256']==INPUTS['chr1'][1] and value['linked_zstd_version']==10507,'standalone constant input/API differs')
    for key,name in (('setup_sha256','setup.json'),('native_build_sha256','native/build.json'),('instrument_sha256','instrument.py'),
                     ('worker_sha256','worker.c'),('calibration_sha256','CALIBRATION.md'),('protocol_sha256','PROTOCOL.md')):
        check(value[key]==sha(HERE/name),'constant request source changed: '+name)
    check(value['plaintext']['bytes']==size and value['library']==native['artifacts']['constants'],'constant library/plaintext scope changed')
    for key in ('plaintext','compressed','library'):private(value[key])
    source=load(HERE/'setup.json')['inputs']['chr1']
    if Path(source['path']).is_file():
        with Path(source['path']).open('rb') as stream:raw=stream.read(size)
        check(hashlib.sha256(raw).hexdigest()==value['plaintext']['sha256'],'constant is not the declared chr1 byte prefix')
    return size


def verify_constant_observation(value,request):
    size=request['frame_bytes'];rows=value['rows']
    check(value.get('schema')=='hw-region-1-constant-observation-v1' and value.get('status')=='PASS' and value['frame_bytes']==size
          and value['request_sha256']==hashlib.sha256(packed(request)).hexdigest() and value['measurements_of_time'] is True
          and value['clock_calls']==2000 and value['warmups']==12 and value['queries']==1000 and value['api']==request['api']
          and value['linked_zstd_version']==10507 and len(rows)==N,'standalone timing scope differs')
    for key in ('plaintext','compressed','library','native_build_sha256','instrument_sha256','protocol_sha256'):
        check(value[key]==request[key],'constant observation source changed: '+key)
    for i,row in enumerate(rows):
        check(row['query']==i and row['decoded_bytes']==size and row['verified'] is True and integer(row['elapsed_ns'],1),'invalid standalone raw row')
    times=[r['elapsed_ns'] for r in rows]
    check(value['p50_ns']==quantile(times,50) and value['p99_ns']==quantile(times,99),'standalone quantile differs')
    check(value['returned']['bytes']==size and value['returned']['sha256']==request['plaintext']['sha256'],'standalone returned bytes differ')
    for key in ('returned','native_stdout','native_stderr'):private(value[key])
    worker=load(HERE/'native/build.json')['artifacts']['worker']
    check(len(value['native_command'])==6 and value['native_command'][:5]==[worker['path'],'constants',request['library']['path'],
          request['plaintext']['path'],request['compressed']['path']],'standalone native command/API differs')
    if Path(value['native_stdout']['path']).is_file():
        raw=[json.loads(line,object_pairs_hook=unique) for line in Path(value['native_stdout']['path']).read_text().splitlines() if line.strip()]
        check(raw==rows,'standalone native stdout differs')
    return size,value['p50_ns']


def boundary_from_bytes(codec,data,size):
    """Derive the FIRST usable native boundary without inspecting counters."""
    if codec=='aceapex':
        check(data[:8]==b'ACEPX2\0\0' and struct.unpack_from('<I',data,8)[0]==2,'control ACE format differs')
        decoded,g,count=struct.unpack_from('<QII',data,12)
        check(decoded==size and g==R and count==(size+R-1)//R,'control ACE geometry differs')
        lengths=struct.unpack_from('<4Q',data,36);position=68+64*count;streams=[]
        check(position+sum(lengths)<=len(data),'control ACE streams escape archive')
        for i,length in enumerate(lengths):
            stream=data[position:position+length];position+=length
            if len(stream)<8:
                streams.append(dict(size=0,chunk=0,count=0));continue
            word=struct.unpack_from('<Q',stream)[0]
            if i==0 and word&(1<<62):
                amount=word&~((1<<62)|(1<<61)|(1<<60))
                chunk=struct.unpack_from('<Q',stream,8)[0] if word&(1<<61) else (amount+3)//4
                number=(amount+chunk-1)//chunk if word&(1<<61) and chunk else 4
                header=16 if word&(1<<61) else 8
            else:
                amount=word&((1<<48)-1);field=(word>>48)&0x7fff
                chunk=field*4096 if field else 524288;number=(amount+chunk-1)//chunk;header=8
            check(chunk>0 and header+8*number<=len(stream),'control entropy geometry differs')
            streams.append(dict(size=amount,chunk=chunk,count=number))
        def chunks(index):
            row=struct.unpack_from('<8Q',data,68+64*index);answer=[]
            for stream,start,length in zip(streams,row[:4],row[4:]):
                check(start+length<=stream['size'],'control outer block escapes entropy stream')
                answer.append(set(range(start//stream['chunk'],(start+length-1)//stream['chunk']+1)) if length else set())
            return answer
        for index in range(count-1):
            if (index+2)*R>size:break
            before,after=chunks(index),chunks(index+1)
            added=[sorted(b-a) for a,b in zip(before,after)]
            if any(added):
                return dict(codec=codec,rule='first adjacent outer blocks adding an actual decoded entropy chunk',block_index=index,
                            boundary=(index+1)*R,aligned_offset=index*R,crossing_offset=index*R+1,next_miss_offset=(index+1)*R,
                            streams=streams,aligned_chunks=[sorted(a) for a in before],next_block_chunks=[sorted(a) for a in after],
                            new_chunks=added,request_bytes=R)
    elif codec=='zstd_seekable':
        count,flags,magic=struct.unpack('<IBI',data[-9:]);table=len(data)-17-12*count
        check(count>1 and flags==128 and magic==0x8f92eab1 and table>=0
              and struct.unpack_from('<II',data,table)==(0x184d2a5e,12*count+9),'control seek table differs')
        offset=compressed=0
        for index in range(count-1):
            cn,dn,crc=struct.unpack_from('<III',data,table+8+12*index)
            check(cn>0 and compressed+cn<=table,'control frame escapes archive')
            following=struct.unpack_from('<I',data,table+8+12*(index+1)+4)[0]
            if dn>=R and following>0 and offset+dn+1<=size:
                return dict(codec=codec,rule='first native frame boundary with an R-byte preceding span',unit_index=index,
                            boundary=offset+dn,aligned_offset=offset+dn-R,crossing_offset=offset+dn-R+1,
                            preceding_decoded_bytes=dn,next_decoded_bytes=following,request_bytes=R)
            compressed+=cn;offset+=dn
    else:
        position=offset=0;blocks=[]
        while position<len(data):
            check(len(data)-position>=26 and data[position:position+4]==b'\x1f\x8b\x08\x04','control BGZF header differs')
            cn=struct.unpack_from('<H',data,position+16)[0]+1
            check(cn>=26 and position+cn<=len(data),'control BGZF extent differs')
            dn=struct.unpack_from('<I',data,position+cn-4)[0];blocks.append((offset,dn));offset+=dn;position+=cn
        check(offset==size and blocks[-1][1]==0,'control BGZF decompressed extent/EOF differs')
        for index,((start,dn),(_,following)) in enumerate(zip(blocks,blocks[1:])):
            if dn>=R and following>0:
                return dict(codec=codec,rule='first actual BGZF boundary with an R-byte preceding span',unit_index=index,
                            boundary=start+dn,aligned_offset=start+dn-R,crossing_offset=start+dn-R+1,
                            preceding_decoded_bytes=dn,next_decoded_bytes=following,request_bytes=R)
    raise ValueError('no first usable actual boundary: '+codec)


def verify_controls(setup,native):
    value=load(HERE/'controls.json')
    check(value.get('schema')=='hw-region-1-controls-v1' and value.get('status')=='PASS' and value['clock_calls']==0
          and value['measurements_of_time'] is False and value['case_id']=='chr1-g16384' and set(value['codecs'])==set(CODECS),
          'untimed method controls incomplete')
    identity={key:sha(HERE/name) for key,name in (('controls_sha256','controls.py'),('instrument_sha256','instrument.py'),
              ('worker_sha256','worker.c'),('native_build_sha256','native/build.json'),('setup_sha256','setup.json'),
              ('protocol_sha256','PROTOCOL.md'),('calibration_sha256','CALIBRATION.md'))}
    check(value['identity']==identity and all(value[k]==v for k,v in identity.items()),'control source cohort changed')
    references=[];answers={}
    for name in CODECS:
        item=value['codecs'][name];request=json_ref(item['request']);verify_request(request,setup,native)
        check(request['case_id']=='chr1-g16384' and request['codec']==name,'control request coordinate differs')
        verify_observation(json_ref(item['selfcheck']),request,'check')
        plan=json_ref(item['boundary_plan'])
        check(plan['codec']==name and plan['request_bytes']==R and plan['crossing_offset']==plan['aligned_offset']+1
              and plan['boundary']==plan['aligned_offset']+R and 0<=plan['aligned_offset']<setup['inputs']['chr1']['bytes']-2*R,
              'boundary control does not cross the same-sized actual boundary')
        if Path(request['archive']['path']).is_file():
            check(plan==boundary_from_bytes(name,Path(request['archive']['path']).read_bytes(),request['input']['bytes']),
                  'boundary was not selected by the first-native-boundary metadata rule')
        aligned=verify_observation(json_ref(item['aligned']),request,'probe',probe_offsets=[plan['aligned_offset']])[0]
        crossing=verify_observation(json_ref(item['crossing']),request,'probe',probe_offsets=[plan['crossing_offset']])[0]
        check(0<aligned['materialized_bytes']<crossing['materialized_bytes'] and item['request_bytes']==R
              and item['amplification_increased'] is True and item['aligned_materialized_bytes']==aligned['materialized_bytes']
              and item['crossing_materialized_bytes']==crossing['materialized_bytes'],'actual amplification negative control failed')
        references.extend(item[key] for key in ('request','selfcheck','boundary_plan','aligned','crossing'))
        if name=='aceapex':
            hit=verify_observation(json_ref(item['cache_hit']),request,'probe',probe_offsets=[plan['aligned_offset']]*2)
            misses=verify_observation(json_ref(item['two_misses']),request,'probe',probe_offsets=[plan['aligned_offset'],plan['next_miss_offset']])
            check(hit[0]['materialized_bytes']>0 and hit[1]['materialized_bytes']==hit[1]['zstd_calls']==hit[1]['zstd_bytes']==0
                  and all(row['materialized_bytes']>0 for row in misses),'persistent cache hit/two-miss control failed')
            references.extend(item[key] for key in ('cache_hit','two_misses'))
        answers[name]=dict(aligned_materialized_bytes=aligned['materialized_bytes'],crossing_materialized_bytes=crossing['materialized_bytes'])
    known=json_ref(value['counter_known']);request=load(HERE/'constants/requests/4096.json');verify_constant_request(request,native)
    check(known.get('schema')=='hw-region-1-counter-known-v1' and known.get('status')=='PASS' and known['clock_calls']==0
          and known['measurements_of_time'] is False and known['identity']==dict(instrument_sha256=sha(HERE/'instrument.py'),
          native_build_sha256=sha(HERE/'native/build.json'),constant_request_sha256=sha(HERE/'constants/requests/4096.json')),
          'API counter known answer/source failed')
    expected=[]
    for label,calls,amount,dctx,oneshot in (('DCtx one frame',1,4096,1,0),('one-shot one frame',1,4096,0,1),('plain-copy API bypass',0,0,0,0)):
        expected.append(dict(control=label,actual_zstd_calls=calls,actual_zstd_output_bytes=amount,dctx_calls=dctx,oneshot_calls=oneshot,
                             restored_sha256=request['plaintext']['sha256']))
    check(known['rows']==expected,'one frame did not produce exactly one API call / true decoded bytes / zero bypass')
    references.append(value['counter_known'])
    check(value['evidence_refs']==references,'unretained or omitted control evidence')
    return dict(status='PASS',codecs=answers,counter_known='PASS',cache='PASS')


def sources(value):
    expected={name:sha(HERE/name) for name in SOURCES}
    check(value.get('source_sha256')==expected,'controller/source cohort changed')


def verify_preparation():
    value=load(HERE/'preparation.json')
    check(value.get('schema')=='hw-region-1-preparation-v1' and value.get('status')=='PASS','preparation not complete')
    sources(value);check(value['reader_environment']=={},'reader environment contains codec tuning')
    for key,name in (('setup','setup.json'),('native','native/build.json'),('controls','controls.json'),('policy_controls','policy-controls.json'),
                     ('outputs_primary','audit/outputs-primary.json')):
        check(file_ref(value[key])==HERE/name,'preparation reference points elsewhere')
    policy=json_ref(value['policy_controls'])
    check(policy.get('schema')=='hw-region-1-policy-controls-v1' and policy.get('status')=='PASS'
          and policy['measurements_of_time'] is False and policy['clock_calls']==0
          and policy['helper_sha256']==sha(HERE/'ovh_bench.py'),'load-policy control source/status differs')
    cases=[]
    for start,end,foreign,answer in (('1.00','1.00',False,False),('2.00','2.00',False,False),('2.01','0.00',False,True),
                                   ('0.00','2.01',False,True),('1.00','1.00',True,True)):
        calculated=foreign or any(Decimal(x)-1>1 for x in (start,end))
        check(calculated is answer,'independent load boundary math failed')
        cases.append(dict(start=start,end=end,foreign_exceeded=foreign,expected=answer,actual=answer))
    check(policy['cases']==cases and policy['foreign_boundary']==dict(hz=100,interval_ns=1000000000,ten_ticks=False,eleven_ticks=True),
          'strict load 2.00/2.01 or foreign 10/11-percent controls changed')
    return value


def observed_ref(reference,request,mode,passes=1):
    path=file_ref(reference);value=load(path)
    verify_observation(value,request,mode,passes)
    OBSERVATIONS[path.relative_to(HERE).as_posix()]=dict(sha256=reference['sha256'],rows=len(value['rows']),
        returned_sha256=value['returned']['sha256'],mode=mode)
    return value


def remote_public_path(text,name):
    return isinstance(text,str) and text.startswith('/') and text.endswith('/evidence/hw-region-1/'+name)


def verify_unit(path,setup,native):
    path=Path(path);value=load(path)
    check(value.get('schema')=='hw-region-1-unit-v1' and value.get('status') in ('COMPLETE','METHODFAIL','BLOCKED: load')
          and value.get('kind') in ('method','latency','constants'),'timing unit incomplete/unknown')
    sources(value);check(value['reader_environment']=={},'timed reader environment contains codec tuning')
    kind,case,codec=value['kind'],value['case_id'],value['codec']
    check(path==HERE/'units'/kind/case/(codec+'.json'),'unit location and identity differ')
    request_path=file_ref(value['request']);request=load(request_path)
    if kind=='constants':
        size=verify_constant_request(request,native)
        check(case=='frame-'+str(size) and codec=='zstd' and request_path==HERE/'constants/requests'/(str(size)+'.json'),
              'standalone unit coordinate changed')
    else:
        verify_request(request,setup,native)
        check(request['case_id']==case and request['codec']==codec,'unit swaps a region request')
        if kind=='method':check(case=='chr1-g16384','AA control must use primary dataset/geometry')
    attempts=value['attempts'];check(isinstance(attempts,list) and 1<=len(attempts)<=3,'unit exceeds three attempts')
    folder=HERE/'raw'/kind/case/codec
    check(folder.is_dir() and {p.name for p in folder.iterdir()}=={f'attempt-{i}' for i in range(1,len(attempts)+1)},
          'fourth/unretained raw attempt exists')
    selected=None
    for number,item in enumerate(attempts,1):
        check(item['attempt']==number and item['status'] in ('CLEAN','LOADED') and (number==len(attempts) or item['status']=='LOADED'),
              'first CLEAN was retaken or non-load attempt retried')
        receipt_path=file_ref(item['receipt']);record=load(receipt_path)
        check(receipt_path==folder/f'attempt-{number}'/'ovh-bench.json','attempt receipt moved/swapped')
        receipt(record,item['status'])
        for stream in ('stdout','stderr'):
            check(sha(Path(str(receipt_path)+'.'+stream))==record[stream+'_sha256'],'helper raw stream changed')
        check(sha(receipt_path.parent/'worker.stdout')==record['stdout_sha256'],'delivered worker stdout differs')
        invocation_command=record['command']
        check(invocation_command[:3]==['taskset','-c','0'],'actual timed worker was not pinned to CPU0')
        command=invocation_command[3:];result_name=(receipt_path.parent/'result.json').relative_to(HERE).as_posix()
        check(len(command)>=8 and command[1]=='-B' and remote_public_path(command[2],'instrument.py'),'receipt invokes different instrument')
        if kind=='constants':
            check(len(command)==8 and command[3:6]==['constants','--frame',str(size)] and command[6]=='--output'
                  and remote_public_path(command[7],result_name),'standalone worker command changed')
        else:
            suffix=['--control-aa'] if kind=='method' else []
            check(len(command)==10+len(suffix) and command[3:5]==['worker','--request']
                  and remote_public_path(command[5],value['request']['path']) and command[6:9]==['--passes','2' if kind=='method' else '1','--output']
                  and remote_public_path(command[9],result_name) and command[10:]==suffix,'region/AA worker command changed')
        invocation=record['flock_command']
        check(remote_public_path(invocation[4],'ovh_bench.py') and invocation[6]=='--receipt'
              and remote_public_path(invocation[7],item['receipt']['path']) and invocation[8]=='--' and invocation[9:]==invocation_command,
              'blocking flock receipt/command binding changed')
        result_path=receipt_path.parent/'result.json'
        check(bool(item['observation']) is record['command_started'] and result_path.exists() is record['command_started'],
              'worker result differs from actual start')
        if item['observation']:
            check(file_ref(item['observation'])==result_path,'attempt selected another raw result')
            observation=load(result_path)
            if kind=='constants':verify_constant_observation(observation,request)
            else:observed_ref(item['observation'],request,'latency',2 if kind=='method' else 1)
            if item['status']=='CLEAN':selected=observation
    check(value['attempt_count']==len(attempts) and value['retaken'] is (len(attempts)>1)
          and value['loaded_attempts']==sum(a['status']=='LOADED' for a in attempts),'timing unit counters differ')
    if selected is None:
        check(value['status']=='BLOCKED: load' and len(attempts)==3 and value['selected'] is None
              and all(a['status']=='LOADED' for a in attempts) and value['ps_top8']==record['ps_top8'],'BLOCKED is not exactly three retained LOADED attempts')
        raise Incomplete('BLOCKED: load at '+kind+'/'+case+'/'+codec)
    check(value['selected']==attempts[-1]['observation'] and value['selected_receipt']==attempts[-1]['receipt'],'winner is not the first CLEAN result')
    expected_status='COMPLETE'
    if kind=='method':
        first,second=[q['p50_ns'] for q in selected['quantiles']]
        if 20*abs(second-first)>=first:expected_status='METHODFAIL'
    check(value['status']==expected_status,'method verdict differs from strict raw five-percent rule')
    if expected_status!='COMPLETE':raise ValueError('AA METHODFAIL: '+codec)
    name=path.relative_to(HERE).as_posix()
    UNITS[name]=dict(kind=kind,attempts=len(attempts),retaken=len(attempts)>1,loaded=value['loaded_attempts'],rows=len(selected['rows']))
    return value,selected,request


def verify_method(setup,native):
    verify_preparation();value=load(HERE/'method-check.json');sources(value)
    check(value.get('schema')=='hw-region-1-method-v1' and value.get('status')=='PASS' and set(value['units'])==set(CODECS),
          'all three primary AA method gates required')
    check(file_ref(value['controls'])==HERE/'controls.json','AA controls binding differs')
    check(value['reader_environment']=={} and file_ref(value['outputs_primary'])==HERE/'audit/outputs-primary.json','AA reader environment/output proof differs')
    for key,name in (('instrument_sha256','instrument.py'),('native_build_sha256','native/build.json'),('protocol_sha256','PROTOCOL.md')):
        check(value[key]==sha(HERE/name),'AA source cohort changed')
    answers={}
    for codec in CODECS:
        path=file_ref(value['units'][codec]);unit,observation,request=verify_unit(path,setup,native)
        check(unit['kind']=='method' and unit['case_id']=='chr1-g16384' and unit['codec']==codec,'AA gate coordinate differs')
        first,second=[q['p50_ns'] for q in observation['quantiles']]
        check(20*abs(second-first)<first,'AA instability must stop, never select a faster repeat')
        answers[codec]=dict(first_p50_ns=first,second_p50_ns=second,relative_difference=str(Fraction(abs(second-first),first)),
                            queries=2000,passed=True)
    return answers


def ordered_cases():
    return ['chr1-g16384','chr1-g4096','chr1-g65536']+[f't2t-{i:02d}-g{g}' for i in range(30) for g in GRIDS]+['enwik8-g16384','silesia-g16384']


def verify_case(case_id,setup,native):
    path=HERE/'cases'/(case_id+'.json');value=load(path);sources(value)
    case=setup['cases'][case_id];index=ordered_cases().index(case_id)
    check(value.get('schema')=='hw-region-1-case-v1' and value.get('status')=='COMPLETE' and value['case_id']==case_id
          and value['corpus']==case['corpus'] and value['g']==case['g'] and value['case_index']==index and set(value['formats'])==set(CODECS),
          'case coordinate/completion differs')
    check(file_ref(value['archives'])==HERE/'archives'/(case_id+'.json'),'case archive reference differs')
    check(value['reader_environment']=={},'case reader environment contains codec tuning')
    archives=verify_archives(case_id,setup);answer={}
    for codec in CODECS:
        item=value['formats'][codec];request=json_ref(item['request']);verify_request(request,setup,native)
        check(request['codec']==codec and request['case_id']==case_id,'case swaps request coordinate')
        observed_ref(item['selfcheck'],request,'check')
        unit,timed,unit_request=verify_unit(file_ref(item['latency_unit']),setup,native)
        check(unit['kind']=='latency' and unit_request==request,'case swaps selected latency unit')
        counted=observed_ref(item['counter'],request,'counter');rows=counted['rows'];source=setup['inputs'][case['corpus']]
        archive=archives['formats'][codec];total=sum(r['materialized_bytes'] for r in rows)
        calls=sum(r['zstd_calls'] for r in rows);decoded=sum(r['zstd_bytes'] for r in rows)
        expected=dict(trace=request['trace'],p50_ns=quantile([r['elapsed_ns'] for r in timed['rows']],50),
                      p99_ns=quantile([r['elapsed_ns'] for r in timed['rows']],99),input_bytes=source['bytes'],stored_bytes=archive['stored_bytes'],
                      effective_g=archive['effective_g'],ratio=str(Fraction(source['bytes'],archive['stored_bytes'])),decoded_bytes_total=total,
                      requested_bytes_total=N*R,amplification=str(Fraction(total,N*R)),amplification_p50=str(Fraction(sorted(r['materialized_bytes'] for r in rows)[499],R)),
                      zstd_calls_total=calls,zstd_bytes_total=decoded,zstd_calls_mean=str(Fraction(calls,N)),zstd_bytes_mean=str(Fraction(decoded,N)))
        check(all(item[k]==v for k,v in expected.items()),'case summary arithmetic differs from unrounded integer raw samples: '+case_id+'/'+codec)
        # A byte-identical return trace is an independent cross-format identity.
        check(timed['returned']['sha256']==counted['returned']['sha256'],'timed/counter returned trace differs')
        answer[codec]=dict(summary=expected,timed=timed,counted=counted,unit=unit)
    check(len({v['timed']['returned']['sha256'] for v in answer.values()})==1,'formats return different source slices')
    return answer


def primary_verdict(case):
    ace,zstd=case['aceapex']['summary']['p50_ns'],case['zstd_seekable']['summary']['p50_ns']
    ratio=Fraction(ace,zstd);passed=Fraction(7,5)<=ratio<=Fraction(11,5)
    return dict(schema='hw-region-1-primary-v1',ACE_p50_ns=ace,zstd_p50_ns=zstd,ratio=str(ratio),P1=dict(passed=passed,verdict='HIT' if passed else 'MISS'),
                Kill=dict(triggered=10*ace<11*zstd),outcome='a' if 10*ace<=11*zstd else 'b')


def verify_fit(setup,native):
    value=load(HERE/'model/fit.json');sources(value)
    check(value.get('schema')=='hw-region-1-model-fit-v1' and value.get('status')=='PASS','four-point fit missing/incomplete')
    points=[];units=[];observations=[]
    for size in SIZES:
        path=HERE/'units/constants'/('frame-'+str(size))/'zstd.json'
        unit,observation,request=verify_unit(path,setup,native)
        check(unit['kind']=='constants' and request['frame_bytes']==size,'fit uses a non-standalone-zstd point')
        points.append((size,quantile([r['elapsed_ns'] for r in observation['rows']],50)))
        units.append(dict(path=path.relative_to(HERE).as_posix(),sha256=sha(path)));observations.append(unit['selected'])
    expected=nnls(points)
    expected_points=[dict(decoded_bytes=p['bytes'],observed_median_ns=p['p50_ns'],predicted_ns=p['predicted_ns'],residual_ns=p['residual_ns'])
                     for p in expected['points']]
    check(value['units']==units and value['observations']==observations and value['points']==expected_points
          and value['c_call_ns']==expected['c_call'] and value['c_byte_ns']==expected['c_byte']
          and value['squared_error_ns2']==expected['squared_residual_sum'],'fit differs from independent exact NNLS on all four medians')
    return expected


def model_projection(case,coefficients):
    timed,counted=case['aceapex']['timed']['rows'],case['aceapex']['counted']['rows']
    value=predict(timed,counted,coefficients);query=value['representative_query'];work=counted[query]
    return dict(schema='hw-region-1-model-cell-v1',observed_p50_ns=value['measured_p50_ns'],predicted_p50_ns=value['predicted_p50_ns'],
                representative_query=query,representative_zstd_calls=work['zstd_calls'],representative_zstd_output_bytes=work['zstd_bytes'],
                calls_term_ns=value['terms_ns']['calls'],bytes_term_ns=value['terms_ns']['bytes'],residual_ns=value['terms_ns']['residual'],
                calls_share=value['shares']['calls'],bytes_share=value['shares']['bytes'],residual_share=value['shares']['residual'],
                relative_error=str(abs(Fraction(value['signed_relative_error']))),within_twenty_percent=value['within_20_percent'],
                calls_at_least_half=value['calls_at_least_half'])


def verify_model_case(case_id,case,coefficients,killed):
    path=HERE/'model/cases'/(case_id+'.json')
    if killed and case_id!='chr1-g16384' and not path.exists():return None
    value=load(path);sources(value)
    check(value['case_id']==case_id and file_ref(value['fit'])==HERE/'model/fit.json'
          and file_ref(value['case'])==HERE/'cases'/(case_id+'.json'),'prediction input references changed')
    if killed and case_id!='chr1-g16384':
        check(value.get('schema')=='hw-region-1-model-cell-v1' and value.get('status')=='NOT TESTED: Kill'
              and not any(k in value for k in ('predicted_p50_ns','calls_term_ns','bytes_term_ns','residual_ns')),
              'model decomposition continued after Kill')
        return None
    expected=model_projection(case,coefficients)
    check(value.get('status')=='PASS' and all(value.get(k)==v for k,v in expected.items()),'model differs from independent per-query rank-500 arithmetic: '+case_id)
    item=load(HERE/'cases'/(case_id+'.json'))['formats']['aceapex']
    check(value['timed']==case['aceapex']['unit']['selected'] and value['counter']==item['counter'],'model swaps timed/counter observations')
    return expected


def counters():
    return dict(logical_units=len(UNITS),attempts=sum(v['attempts'] for v in UNITS.values()),retaken=sum(v['retaken'] for v in UNITS.values()),
                loaded_attempts=sum(v['loaded'] for v in UNITS.values()),accepted_timing_observations=sum(v['rows'] for v in UNITS.values()),counter_requests=285000)


def verify_decision(primary,models,coefficients):
    value=load(HERE/'decision.json');sources(value)
    check(value.get('schema')=='hw-region-1-decision-v1' and value.get('status')=='COMPLETE'
          and value['primary']==primary and value['P1']==primary['P1'] and value['Kill']==primary['Kill'] and value['outcome']==primary['outcome'],
          'primary P1/Kill/outcome decision differs from exact raw medians')
    target=[name for name in ordered_cases() if not name.startswith(('enwik8-','silesia-'))]
    check(len(target)==93,'independent P2 grid is not all 93 ACE targets')
    if primary['Kill']['triggered']:
        p2=dict(passed=None,verdict='NOT TESTED: Kill',required_cells=93,modeled_primary_only=True)
    else:
        misses=[dict(case_id=name,relative_error=models[name]['relative_error']) for name in target if not models[name]['within_twenty_percent']]
        chr1_misses=[item['case_id'] for item in misses if item['case_id'].startswith('chr1-')]
        p2=dict(passed=not misses,verdict='MISS' if misses else 'HIT',required_cells=93,tested_cells=93,misses=misses,
                chr1_only=dict(passed=not chr1_misses,verdict='MISS' if chr1_misses else 'HIT',misses=chr1_misses))
    main=models['chr1-g16384'];p3=dict(passed=main['calls_at_least_half'],verdict='HIT' if main['calls_at_least_half'] else 'MISS',calls_share=main['calls_share'])
    terms=[('calls',Fraction(main['calls_term_ns']),Fraction(main['calls_share'])),('bytes',Fraction(main['bytes_term_ns']),Fraction(main['bytes_share'])),
           ('residual',Fraction(main['residual_ns']),Fraction(main['residual_share']))]
    # Resolve exact ties by the protocol's listed component order.
    dominant=max(enumerate(terms),key=lambda x:(abs(x[1][1]),-x[0]))[1]
    dominant=dict(name=dominant[0],term_ns=str(dominant[1]),signed_share=str(dominant[2]))
    expected_units={f'units/latency/{case}/{codec}.json' for case in ordered_cases() for codec in CODECS}
    expected_units|={f'units/method/chr1-g16384/{codec}.json' for codec in CODECS}
    expected_units|={f'units/constants/frame-{size}/zstd.json' for size in SIZES}
    check(set(UNITS)==expected_units and {p.relative_to(HERE).as_posix() for p in (HERE/'units').rglob('*.json')}==expected_units,
          'final timing-unit coverage differs from 285 cells + 3 AA + 4 constants')
    count=counters()
    check(count['logical_units']==292 and count['accepted_timing_observations']==295000,'fixed observation count differs')
    check(value['P2']==p2 and value['P3']==p3 and value['dominant_primary_component']==dominant and value['counts']==count,
          'P2/P3, signed dominant component, or trial counters differ')
    check(file_ref(value['fit'])==HERE/'model/fit.json' and file_ref(value['primary_model'])==HERE/'model/cases/chr1-g16384.json','decision model binding differs')
    return dict(P1=primary['P1'],P2=p2,P3=p3,Kill=primary['Kill'],outcome=primary['outcome'],dominant_primary_component=dominant)


def verify_outputs(stage):
    name='audit/outputs-final.json' if stage=='all' else 'audit/outputs-primary.json'
    path=HERE/name;value=load(path)
    check(value.get('schema')=='hw-region-1-output-verification-v1' and value.get('status')=='PASS' and value.get('stage')==('all' if stage=='all' else 'primary')
          and value['no_codecs'] is True and value['no_clocks'] is True and value['source_sha256']==sha(HERE/'verify_outputs.py')
          and value['setup_sha256']==sha(HERE/'setup.json'),'independent GNU dd+cmp proof missing/stale')
    check('coreutils' in value['gnu_versions']['dd'] and 'GNU' in value['gnu_versions']['cmp'],'output proof uses different tools')
    documents=value['documents_sha256'];captures=value['captures']
    check(len(captures)==len(documents)==value['observation_references'] and value['returned_regions']==sum(c['rows'] for c in captures),
          'independent output proof counts differ')
    check(len({c['document'] for c in captures})==len(captures),'duplicate output proof capture')
    comparisons={}
    for item in value['comparisons']:
        identity=item['identity'];key=(identity['expected_sha256'],identity['actual_sha256'])
        check(key not in comparisons and key[0]==key[1] and item['exitcode']==0 and item['command'][:2]==['cmp','--']
              and item['stdout_sha256']==item['stderr_sha256']==hashlib.sha256(b'').hexdigest(),'GNU cmp proof does not show exact equality')
        comparisons[key]=item
    check(len(comparisons)==value['unique_region_comparisons'],'comparison count differs')
    expected={}
    for item in value['expected']:
        digest=item['sha256'];check(digest not in expected and valid_sha(digest),'duplicate/invalid dd expectation')
        private(item);expected[digest]=item
        if 'identity' in item:
            identity=item['identity'];offsets=identity['offsets']
            check(identity['request_bytes']==R and identity['input_sha256'] in {v['sha256'] for v in load(HERE/'setup.json')['inputs'].values()}
                  and identity['offsets_sha256']==hashlib.sha256(b''.join(struct.pack('<Q',o) for o in offsets)).hexdigest()
                  and item['bytes']==len(offsets)*R and item['dd_exitcodes']==[0]*len(offsets)
                  and item['dd_command_template']==['dd','if=SOURCE','bs=1M','iflag=skip_bytes,count_bytes','skip=OFFSET','count=16384','status=none']
                  and item['dd_stderr_sha256']==hashlib.sha256(b'').hexdigest(),'independent dd trace proof differs')
        else:
            check(item['repetitions']==2 and valid_sha(item['base_sha256']) and item['bytes']==2*N*R,'AA double expectation differs')
    check(len(expected)==value['unique_expected'],'dd expectation count differs')
    for capture in captures:
        document=capture['document'];record=load(file_ref(dict(path=document,sha256=documents[document])))
        check(record['schema'] in ('hw-region-1-observation-v1','hw-region-1-selfcheck-v1') and record['status']=='PASS'
              and len(record['rows'])==capture['rows'] and record['returned']['bytes']==capture['bytes']
              and record['returned']['sha256']==capture['sha256']==capture['expected_sha256']
              and (capture['expected_sha256'],capture['sha256']) in comparisons and capture['expected_sha256'] in expected,
              'output proof capture differs from retained rows/returned bytes')
    # Include every retained result, including observations excluded by LOADED.
    required=set()
    for p in (HERE/'controls').glob('*.json'):
        candidate=load(p)
        if candidate.get('schema')=='hw-region-1-observation-v1':required.add(p.relative_to(HERE).as_posix())
    for p in (HERE/'selfchecks').rglob('*.json'):
        candidate=load(p)
        if candidate.get('schema') in ('hw-region-1-observation-v1','hw-region-1-selfcheck-v1'):
            if stage=='all' or candidate['case_id']=='chr1-g16384':required.add(p.relative_to(HERE).as_posix())
    if stage=='all':required|=set(OBSERVATIONS)
    check(required<=documents.keys(),'dd+cmp proof omits a retained selfcheck/control/CLEAN/LOADED returned capture')
    return dict(path=name,sha256=sha(path),source_sha256=value['source_sha256'],observation_references=value['observation_references'],
                returned_regions=value['returned_regions'],unique_region_comparisons=value['unique_region_comparisons'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('setup','method','primary','all'),required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=dict(schema='hw-region-1-independent-audit-v1',stage=args.stage,saved_data_only=True,no_codecs=True,no_clocks=True)
    try:
        sha(HERE/'audit.py');setup=verify_setup();result['setup']=dict(corpora=33,cases=95,calibration_commit=CALIBRATION)
        if args.stage!='setup' or (HERE/'native/build.json').exists():
            native=verify_native_build();result['native_build_sha256']=sha(HERE/'native/build.json')
            if args.stage!='setup' or (HERE/'controls.json').exists():result['controls']=verify_controls(setup,native)
        if args.stage!='setup':
            result['method']=verify_method(setup,native);result['output_proof_primary']=verify_outputs('primary')
        if args.stage in ('primary','all'):
            first=verify_case('chr1-g16384',setup,native);primary=primary_verdict(first);result['primary']=primary
        if args.stage=='all':
            check(set((HERE/'cases').glob('*.json'))=={HERE/'cases'/(name+'.json') for name in ordered_cases()},'full 95-case summary grid differs')
            coefficients=verify_fit(setup,native);result['fit']=coefficients;models={}
            for name in ordered_cases():
                case=first if name=='chr1-g16384' else verify_case(name,setup,native)
                models[name]=verify_model_case(name,case,coefficients,primary['Kill']['triggered'])
            result['literal_verdicts']=verify_decision(primary,models,coefficients)
            result['models']={k:v for k,v in models.items() if v is not None}
            result['output_proof_final']=verify_outputs('all')
            for p in HERE.glob('*.py'):sha(p)
        result.update(status='PASS',counts=counters(),host=HOST,private_artifacts_checked=len(PRIVATE_CHECKED),
                      private_artifacts_unavailable=len(PRIVATE_UNAVAILABLE),private_bytes_verified_on_this_host=not PRIVATE_UNAVAILABLE)
    except Incomplete as error:
        result.update(status='INCOMPLETE',reason=str(error))
    except (ValueError,KeyError,TypeError,IndexError,struct.error,subprocess.CalledProcessError) as error:
        result.update(status='FAIL',reason=f'{type(error).__name__}: {error}')
    result['source_bindings']=[dict(path=k,sha256=v) for k,v in sorted(SOURCE_BINDINGS.items())]
    raw=packed(result)
    if args.output:
        output=args.output.resolve();check(output.is_relative_to((HERE/'audit').resolve()),'audit output must stay in audit/')
        output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(raw)
    print(raw.decode(),end='')
    return 0 if result['status']=='PASS' else 2 if result['status']=='INCOMPLETE' else 1


if __name__=='__main__':raise SystemExit(main())
