"""One-checkpoint-at-a-time HW-REGION-1 controller; no experiment on import."""
import argparse
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
STATE=ROOT/'.work/hw-region-1'
CODECS=('aceapex','zstd_seekable','bgzip')
SIZES=(4096,16384,65536,262144)
SOURCES=('CALIBRATION.md','PROTOCOL.md','run.py','instrument.py','worker.c','native_versions.c',
         'native_constants.c','controls.py','setup.py','model.py','ovh_bench.py')


def check(ok,why):
    if not ok: raise ValueError(why)


def load(path): return json.loads(Path(path).read_bytes())


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()


def packed(value): return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()


def save(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    pending=path.with_name(path.name+'.writing')
    with pending.open('wb') as stream: stream.write(packed(value)); stream.flush(); os.fsync(stream.fileno())
    pending.replace(path)


def ref(path):
    path=Path(path).resolve(); check(path.is_relative_to(HERE),'public path escaped experiment')
    return dict(path=path.relative_to(HERE).as_posix(),sha256=sha(path))


def deref(value):
    check(isinstance(value,dict) and set(value)=={'path','sha256'},'invalid evidence reference')
    path=(HERE/value['path']).resolve()
    check(path.is_relative_to(HERE) and path.is_file() and not path.is_symlink() and sha(path)==value['sha256'],'retained evidence changed: '+value['path'])
    return path


def module(name):
    spec=importlib.util.spec_from_file_location('_region_'+name,HERE/(name+'.py'))
    value=importlib.util.module_from_spec(spec); sys.modules[spec.name]=value; spec.loader.exec_module(value); return value


def source_map():
    check(not {k:v for k,v in os.environ.items() if k.startswith(('AX_','ACEAPEX_','LIT_','FSE_'))},'reader environment must be empty and identical for timed/counter passes')
    names=['evidence/hw-region-1/'+name for name in SOURCES]
    subprocess.run(['git','-C',str(ROOT),'ls-files','--error-unmatch','--',*names],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    check(not subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain','--',*names]).strip(),'all measurement/controller sources must be committed and clean')
    return {name:sha(HERE/name) for name in SOURCES}


def same_sources(value): check(value['source_sha256']==source_map(),'source/protocol cohort changed; do not silently resume')


def invoke(action,*args,script='instrument'):
    command=[sys.executable,'-B',str(HERE/(script+'.py')),*([action] if action else []),*map(str,args)]
    result=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode: sys.stderr.buffer.write(result.stderr); sys.stderr.buffer.flush()
    result.check_returncode()


def ordered_cases():
    values=['chr1-g16384','chr1-g4096','chr1-g65536']
    values += [f't2t-{i:02d}-g{g}' for i in range(30) for g in (4096,16384,65536)]
    values += ['enwik8-g16384','silesia-g16384']
    check(set(values)==set(load(HERE/'setup.json')['cases']) and len(values)==95,'fixed 95-case grid changed')
    return values


def verify_controls(path):
    value=load(path); check(value['status']=='PASS' and value['clock_calls']==0 and value['measurements_of_time'] is False,'untimed controls did not pass')
    for key,name in (('controls_sha256','controls.py'),('instrument_sha256','instrument.py'),('worker_sha256','worker.c'),
                     ('native_build_sha256','native/build.json'),('setup_sha256','setup.json'),('protocol_sha256','PROTOCOL.md'),('calibration_sha256','CALIBRATION.md')):
        check(value[key]==sha(HERE/name),'controls source changed: '+key)
    for item in value['evidence_refs']: deref(item)
    check(set(value['codecs'])==set(CODECS) and all(item['amplification_increased'] is True for item in value['codecs'].values()),'all three boundary controls required')
    return value


def prepared():
    value=load(HERE/'preparation.json'); check(value['status']=='PASS','preparation incomplete')
    same_sources(value); verify_controls(deref(value['controls'])); deref(value['native']); deref(value['setup']); deref(value['policy_controls'])
    verify_outputs_primary(deref(value['outputs_primary'])); return value


def verify_outputs_primary(path):
    value=load(path)
    check(value['schema']=='hw-region-1-output-verification-v1' and value['status']=='PASS' and value['stage']=='primary'
          and value['no_codecs'] is True and value['no_clocks'] is True
          and value['source_sha256']==sha(HERE/'verify_outputs.py') and value['setup_sha256']==sha(HERE/'setup.json'),'independent primary dd+cmp proof missing/changed')
    for name,digest in value['documents_sha256'].items(): deref(dict(path=name,sha256=digest))
    check(value['observation_references']>=14 and all(c['exitcode']==0 for c in value['comparisons']),'primary independent output comparisons incomplete')
    return value


def prepare():
    if (HERE/'preparation.json').exists(): prepared(); print('PREPARATION_VERIFIED_SKIP',flush=True); return 0
    sources=source_map()
    invoke('build')
    if not (HERE/'archives/chr1-g16384.json').exists(): invoke('archive','--case','chr1-g16384',script='setup')
    controls=HERE/'controls.json'
    if not controls.exists(): invoke(None,'--output',controls,script='controls')
    verify_controls(controls)
    outputs=HERE/'audit/outputs-primary.json'; verify_outputs_primary(outputs)
    helper=module('ovh_bench'); cases=[]
    for start,end,foreign,answer in (('1.00','1.00',False,False),('2.00','2.00',False,False),('2.01','0.00',False,True),('0.00','2.01',False,True),('1.00','1.00',True,True)):
        actual=helper.loaded({'loadavg_raw':start+' 0 0 1/1 1'},{'loadavg_raw':end+' 0 0 1/1 1'},{'exceeded':[{'known':True}] if foreign else []})
        check(actual is answer,'known load predicate failed'); cases.append(dict(start=start,end=end,foreign_exceeded=foreign,expected=answer,actual=actual))
    check(helper.foreign_exceeds(10,100,1000000000) is False and helper.foreign_exceeds(11,100,1000000000) is True,'known strict ten-percent boundary failed')
    policy=HERE/'policy-controls.json'; save(policy,dict(schema='hw-region-1-policy-controls-v1',status='PASS',measurements_of_time=False,clock_calls=0,
        helper_sha256=sha(HERE/'ovh_bench.py'),cases=cases,foreign_boundary=dict(hz=100,interval_ns=1000000000,ten_ticks=False,eleven_ticks=True)))
    save(HERE/'preparation.json',dict(schema='hw-region-1-preparation-v1',status='PASS',source_sha256=sources,
        controls=ref(controls),native=ref(HERE/'native/build.json'),setup=ref(HERE/'setup.json'),policy_controls=ref(policy),outputs_primary=ref(outputs),reader_environment={}))
    print('PREPARATION_PASS',flush=True); return 0


def make_request(case,codec):
    path=HERE/'requests'/case/(codec+'.json'); selfcheck=HERE/'selfchecks'/case/(codec+'.json')
    if not path.exists(): invoke('request','--case',HERE/'archives'/(case+'.json'),'--codec',codec,'--output',path)
    value=load(path)
    check(value['case_id']==case and value['codec']==codec and value['instrument_sha256']==sha(HERE/'instrument.py')
          and value['native_build_sha256']==sha(HERE/'native/build.json'),'request identity/source changed')
    if not selfcheck.exists(): invoke('untimed-selfcheck','--request',path,'--output',selfcheck)
    control=load(selfcheck)
    check(control['status']=='PASS' and control['measurements_of_time'] is False and control['clock_calls']==0
          and control['request_sha256']==sha(path) and sha(control['returned']['path'])==control['returned']['sha256'],'saved selfcheck changed')
    return path,selfcheck


def verify_observation(path,request,kind):
    value,asked=load(path),load(request)
    check(value['status']=='PASS' and value['request_sha256']==sha(request)
          and value['instrument_sha256']==sha(HERE/'instrument.py') and value['native_build_sha256']==sha(HERE/'native/build.json'),'observation identity/source differs')
    returned=value['returned']; check(Path(returned['path']).stat().st_size==returned['bytes'] and sha(returned['path'])==returned['sha256'],'returned byte capture changed')
    for field in ('native_stdout','native_stderr'): check(sha(value[field]['path'])==value[field]['sha256'],'native raw stream changed')
    rows=value['rows']; passes=2 if kind=='method' else 1
    check(len(rows)==1000*passes and all(r['verified'] is True for r in rows),'observation sample count/judge differs')
    timed=kind in ('method','latency','constants')
    check(value['measurements_of_time'] is timed and value['clock_calls']==(2*len(rows) if timed else 0),'observation clock scope differs')
    if kind=='constants':
        check(value['frame_bytes']==asked['frame_bytes'] and value['api']=='ZSTD_decompressDCtx','standalone frame/API differs')
        ns=[r['elapsed_ns'] for r in rows]
        check(all(type(n)is int and n>0 for n in ns) and value['p50_ns']==sorted(ns)[499] and value['p99_ns']==sorted(ns)[989],'constant quantiles differ')
    else:
        offsets=load(HERE/asked['trace']['path'])['offsets']
        check(value['codec']==asked['codec'] and value['case_id']==asked['case_id'],'region coordinate changed')
        for i,row in enumerate(rows):
            check((row['pass'],row['query'],row['offset'])==(i//1000,i%1000,offsets[i%1000]) and row['requested_bytes']==16384,'region trace/order differs')
            check(type(row['elapsed_ns'])is int and row['elapsed_ns']>0 if timed else row['elapsed_ns'] is None,'invalid/forbidden timing observation')
            if not timed: check(all(type(row[k])is int and row[k]>=0 for k in ('zstd_calls','zstd_bytes','materialized_bytes','dctx_calls','oneshot_calls','stream_calls')),'counter observation missing')
        if timed:
            for p in range(passes):
                ns=sorted(r['elapsed_ns'] for r in rows if r['pass']==p)
                check(value['quantiles'][p]==dict(pass_id=p,p50_ns=ns[499],p99_ns=ns[989]),'region quantiles differ from raw')
    return value


def worker_command(kind,request,output,frame=None):
    base=['taskset','-c','0',sys.executable,'-B',str(HERE/'instrument.py')]
    if kind=='constants': return base+['constants','--frame',str(frame),'--output',str(output)]
    args=base+['worker','--request',str(request),'--passes','2' if kind=='method' else '1','--output',str(output)]
    return args+['--control-aa'] if kind=='method' else args


def verify_receipt(path,args):
    value=load(path); helper=module('ovh_bench')
    check(value['schema']=='hw-region-1-ovh-v1' and value['command']==args and value['helper_sha256']==sha(HERE/'ovh_bench.py')
          and value['protocol_sha256']==sha(HERE/'PROTOCOL.md') and value['calibration_sha256']==sha(HERE/'CALIBRATION.md')
          and value['status'] in ('CLEAN','LOADED') and value['lock_path']=='/run/lock/ovh-bench.lock','ERROR/unfinished/changed shared-lock attempt')
    check(value['flock_command'][:2]==['flock','/run/lock/ovh-bench.lock'] and value['timed_threads']==1,'blocking flock/T=1 missing')
    check(not value['foreign_cpu_start']['inspection_errors'] and helper.loaded(value['start'],value['end'],value['foreign_cpu_start'])==(value['status']=='LOADED'),'load/foreign classification differs')
    check(value['returncode']==0 if value['command_started'] else value['status']=='LOADED' and value['returncode'] is None,'worker ERROR cannot be a load retry')
    for stream in ('stdout','stderr'): check(sha(Path(str(path)+'.'+stream))==value[stream+'_sha256'],'helper raw stream changed')
    check(sha(path.parent/'worker.stdout')==value['stdout_sha256'],'delivered worker stdout changed')
    return value


def unit(kind,case,codec,request,frame=None):
    path=HERE/'units'/kind/case/(codec+'.json'); sources=source_map()
    if path.exists():
        value=verify_unit(path); return value,path
    helper=module('ovh_bench'); attempts=[]; raw=HERE/'raw'/kind/case/codec
    raw.mkdir(parents=True,exist_ok=True)
    check({p.name for p in raw.iterdir()} <= {'attempt-1','attempt-2','attempt-3'},'unretained fourth attempt')
    value=dict(schema='hw-region-1-unit-v1',kind=kind,case_id=case,codec=codec,request=ref(request),source_sha256=sources,reader_environment={},attempts=attempts,selected=None)
    for number in range(1,4):
        folder=raw/f'attempt-{number}'; folder.mkdir(exist_ok=True)
        result,receipt=folder/'result.json',folder/'ovh-bench.json'; args=worker_command(kind,request,result,frame)
        if receipt.exists(): record=verify_receipt(receipt,args); code=0 if record['status']=='CLEAN' else 77
        else:
            check(not any(folder.iterdir()),'orphan attempt without receipt; inspect instead of retiming')
            code=helper.run_locked(args,receipt,folder/'worker.stdout'); record=verify_receipt(receipt,args)
        check(code in (0,77) and (code==77)==(record['status']=='LOADED'),'fatal worker/status mismatch')
        observation=ref(result) if result.exists() else None
        check(bool(observation)==bool(record['command_started']),'worker-start/result presence differs')
        if observation: verify_observation(result,request,kind)
        attempts.append(dict(attempt=number,status=record['status'],receipt=ref(receipt),observation=observation))
        if record['status']=='CLEAN':
            check(not any((raw/f'attempt-{n}').exists() for n in range(number+1,4)),'CLEAN unit was retaken')
            value.update(status='COMPLETE',selected=observation,selected_receipt=ref(receipt))
            if kind=='method':
                q=load(result)['quantiles']; a,b=q[0]['p50_ns'],q[1]['p50_ns']
                if 20*abs(b-a)>=a: value['status']='METHODFAIL'
            break
    else: value.update(status='BLOCKED: load',ps_top8=record['ps_top8'])
    value.update(attempt_count=len(attempts),retaken=len(attempts)>1,loaded_attempts=sum(a['status']=='LOADED' for a in attempts))
    save(path,value); return value,path


def verify_unit(path):
    value=load(path); check(value['schema']=='hw-region-1-unit-v1' and value['status'] in ('COMPLETE','METHODFAIL','BLOCKED: load'),'unit is incomplete')
    same_sources(value); request=deref(value['request']); attempts=value['attempts']; check(1<=len(attempts)<=3,'retry budget changed')
    raw=HERE/'raw'/value['kind']/value['case_id']/value['codec']
    check({p.name for p in raw.iterdir()}=={f'attempt-{n}' for n in range(1,len(attempts)+1)},'fourth/unretained attempt exists')
    for number,item in enumerate(attempts,1):
        receipt=deref(item['receipt']); frame=load(request).get('frame_bytes')
        args=worker_command(value['kind'],request,receipt.parent/'result.json',frame)
        record=verify_receipt(receipt,args)
        check(item['attempt']==number and item['status']==record['status'] and (number==len(attempts) or item['status']=='LOADED'),'first CLEAN must win')
        if record['command_started']: verify_observation(deref(item['observation']),request,value['kind'])
        else: check(item['observation'] is None,'unstarted attempt has an observation')
    if value['status']=='BLOCKED: load': check(len(attempts)==3 and all(a['status']=='LOADED' for a in attempts) and value['selected'] is None,'BLOCKED requires exactly three LOADED attempts')
    else:
        check(attempts[-1]['status']=='CLEAN' and value['selected']==attempts[-1]['observation'] and value['selected_receipt']==attempts[-1]['receipt'],'selected observation is not first CLEAN')
        observation=load(deref(value['selected']))
        if value['kind']=='method':
            a,b=[q['p50_ns'] for q in observation['quantiles']]
            check(value['status']==('COMPLETE' if 20*abs(b-a)<a else 'METHODFAIL'),'method stability verdict differs')
    check(value['attempt_count']==len(attempts) and value['retaken']==(len(attempts)>1)
          and value['loaded_attempts']==sum(a['status']=='LOADED' for a in attempts),'unit counters changed')
    return value


def method():
    preparation=prepared(); controls=verify_controls(deref(preparation['controls'])); path=HERE/'method-check.json'
    if path.exists():
        value=load(path); same_sources(value)
        for item in value['units'].values(): verify_unit(deref(item))
        print('METHOD_REPLAY',value['status'],flush=True); return 0 if value['status']=='PASS' else 2 if value['status']=='BLOCKED: load' else 1
    result=dict(schema='hw-region-1-method-v1',status='PASS',source_sha256=source_map(),reader_environment={},controls=preparation['controls'],outputs_primary=preparation['outputs_primary'],units={},
                instrument_sha256=sha(HERE/'instrument.py'),native_build_sha256=sha(HERE/'native/build.json'),protocol_sha256=sha(HERE/'PROTOCOL.md'))
    for codec in CODECS:
        request=deref(controls['codecs'][codec]['request'])
        value,unit_path=unit('method','chr1-g16384',codec,request); result['units'][codec]=ref(unit_path)
        if value['status']!='COMPLETE':
            result['status']='BLOCKED: load' if value['status']=='BLOCKED: load' else 'FAIL'; break
    save(path,result); print('METHOD',result['status'],flush=True)
    return 0 if result['status']=='PASS' else 2 if result['status']=='BLOCKED: load' else 1


def method_gate():
    value=load(HERE/'method-check.json'); same_sources(value)
    verify_outputs_primary(deref(value['outputs_primary']))
    check(value['status']=='PASS' and set(value['units'])==set(CODECS),'all three AA gates must pass')
    for item in value['units'].values(): check(verify_unit(deref(item))['status']=='COMPLETE','AA stability gate failed')
    return value


def verify_case(path):
    value=load(path); same_sources(value); check(value['status']=='COMPLETE' and set(value['formats'])==set(CODECS),'case incomplete')
    deref(value['archives'])
    for codec,item in value['formats'].items():
        request=deref(item['request']); check(load(request)['codec']==codec,'case request codec changed')
        check(verify_unit(deref(item['latency_unit']))['status']=='COMPLETE','case latency unit incomplete')
        verify_observation(deref(item['counter']),request,'counter')
    return value


def case(case_id):
    prepared(); method_gate(); order=ordered_cases(); check(case_id in order,'unknown case')
    path=HERE/'cases'/(case_id+'.json')
    if path.exists():
        verify_case(path)
        if (HERE/'model/fit.json').exists() and (case_id=='chr1-g16384' or not primary()['Kill']['triggered']): model_case(case_id)
        print('CASE_REPLAY',case_id,flush=True); return 0
    index=order.index(case_id)
    if index:
        previous=load(HERE/'cases'/(order[index-1]+'.json')); check(previous['status']=='COMPLETE','preceding case must complete/checkpoint first'); same_sources(previous)
    archives=HERE/'archives'/(case_id+'.json')
    if not archives.exists(): invoke('archive','--case',case_id,script='setup')
    descriptor=load(archives); result=dict(schema='hw-region-1-case-v1',status='COMPLETE',case_id=case_id,corpus=descriptor['corpus'],g=descriptor['g'],
        case_index=index,source_sha256=source_map(),reader_environment={},archives=ref(archives),formats={})
    rotation=CODECS[index%3:]+CODECS[:index%3]
    for codec in rotation:
        request,selfcheck=make_request(case_id,codec); observed,unit_path=unit('latency',case_id,codec,request)
        if observed['status']!='COMPLETE': print('CASE_BLOCKED',case_id,codec,flush=True); return 2
        data=verify_observation(deref(observed['selected']),request,'latency')
        counter=HERE/'counters'/case_id/(codec+'.json')
        if not counter.exists(): invoke('counterpass','--request',request,'--output',counter)
        counted=verify_observation(counter,request,'counter'); rows=counted['rows']; archive=descriptor['formats'][codec]
        total=sum(r['materialized_bytes'] for r in rows); zcalls=sum(r['zstd_calls'] for r in rows); zbytes=sum(r['zstd_bytes'] for r in rows)
        result['formats'][codec]=dict(request=ref(request),selfcheck=ref(selfcheck),latency_unit=ref(unit_path),counter=ref(counter),trace=load(request)['trace'],
            p50_ns=data['quantiles'][0]['p50_ns'],p99_ns=data['quantiles'][0]['p99_ns'],
            input_bytes=descriptor['input']['bytes'],stored_bytes=archive['stored_bytes'],effective_g=archive['effective_g'],
            ratio=str(Fraction(descriptor['input']['bytes'],archive['stored_bytes'])),decoded_bytes_total=total,requested_bytes_total=1000*16384,
            amplification=str(Fraction(total,1000*16384)),amplification_p50=str(Fraction(sorted(r['materialized_bytes'] for r in rows)[499],16384)),
            zstd_calls_total=zcalls,zstd_bytes_total=zbytes,zstd_calls_mean=str(Fraction(zcalls,1000)),zstd_bytes_mean=str(Fraction(zbytes,1000)))
    save(path,result)
    if (HERE/'model/fit.json').exists() and (case_id=='chr1-g16384' or not primary()['Kill']['triggered']): model_case(case_id)
    print('CASE_COMPLETE',case_id,flush=True); return 0


def primary():
    value=verify_case(HERE/'cases/chr1-g16384.json'); m=module('model')
    return m.primary_verdict(value['formats']['aceapex']['p50_ns'],value['formats']['zstd_seekable']['p50_ns'])


def constants(frame):
    prepared(); method_gate(); primary(); check(frame in SIZES,'one declared standalone frame required')
    request=HERE/'constants/requests'/(str(frame)+'.json')
    if not request.exists(): invoke('constants','--frame',frame,'--prepare','--output',request)
    value,path=unit('constants','frame-'+str(frame),'zstd',request,frame)
    print('CONSTANT',frame,value['status'],flush=True); return 0 if value['status']=='COMPLETE' else 2


def fit():
    prepared(); primary(); m=module('model'); points=[]; units=[]; observations=[]
    for frame in SIZES:
        path=HERE/'units/constants'/('frame-'+str(frame))/'zstd.json'; value=verify_unit(path)
        check(value['status']=='COMPLETE','all four standalone timing units required')
        observed=load(deref(value['selected'])); points.append((frame,sorted(r['elapsed_ns'] for r in observed['rows'])[499])); units.append(ref(path)); observations.append(value['selected'])
    result=m.fit(points); result.update(status='PASS',source_sha256=source_map(),units=units,observations=observations)
    path=HERE/'model/fit.json'
    if path.exists(): check(load(path)==result,'saved coefficients or calibration inputs changed')
    else: save(path,result)
    model_case('chr1-g16384'); print('FIT_PASS',flush=True); return 0


def model_case(case_id):
    verdict=primary(); case_path=HERE/'cases'/(case_id+'.json'); value=verify_case(case_path)
    fit_path=HERE/'model/fit.json'; coefficients=load(fit_path); same_sources(coefficients)
    path=HERE/'model/cases'/(case_id+'.json'); identity=dict(case_id=case_id,source_sha256=source_map(),fit=ref(fit_path),case=ref(case_path))
    if verdict['Kill']['triggered'] and case_id!='chr1-g16384':
        result=dict(schema='hw-region-1-model-cell-v1',status='NOT TESTED: Kill',**identity)
    else:
        item=value['formats']['aceapex']; timed_unit=verify_unit(deref(item['latency_unit']))
        timed=load(deref(timed_unit['selected'])); counted=load(deref(item['counter']))
        result=module('model').predict(coefficients,timed['rows'],counted['rows'])
        result.update(status='PASS',**identity,timed=timed_unit['selected'],counter=item['counter'])
    if path.exists(): check(load(path)==result,'saved model input/prediction changed')
    else: save(path,result)
    print('MODEL',case_id,result['status'],flush=True); return 0


def decide():
    prepared(); verdict=primary(); order=ordered_cases()
    for name in order: verify_case(HERE/'cases'/(name+'.json'))
    fit_data=load(HERE/'model/fit.json'); same_sources(fit_data)
    modeled=load(HERE/'model/cases/chr1-g16384.json'); same_sources(modeled); check(modeled['status']=='PASS','primary decomposition required')
    target=[name for name in order if not name.startswith(('enwik8-','silesia-'))]
    if verdict['Kill']['triggered']:
        for name in order[1:]:
            path=HERE/'model/cases'/(name+'.json')
            check(not path.exists() or load(path)['status']=='NOT TESTED: Kill','decomposition continued after Kill')
        p2=dict(passed=None,verdict='NOT TESTED: Kill',required_cells=93,modeled_primary_only=True)
    else:
        misses=[]; chr1_misses=[]
        for name in target:
            item=load(HERE/'model/cases'/(name+'.json')); same_sources(item); check(item['status']=='PASS','all 93 P2 cells must be computed')
            if not item['within_twenty_percent']:
                misses.append(dict(case_id=name,relative_error=item['relative_error']))
                if name.startswith('chr1-'): chr1_misses.append(name)
        p2=dict(passed=not misses,verdict='MISS' if misses else 'HIT',required_cells=93,tested_cells=len(target),misses=misses,
                chr1_only=dict(passed=not chr1_misses,verdict='MISS' if chr1_misses else 'HIT',misses=chr1_misses))
    units=[verify_unit(path) for path in sorted((HERE/'units').rglob('*.json'))]
    check(len(units)==292 and all(u['status']=='COMPLETE' for u in units),'final study requires 285+3+4 complete timing units')
    terms=[('calls',Fraction(modeled['calls_term_ns']),Fraction(modeled['calls_share'])),
           ('bytes',Fraction(modeled['bytes_term_ns']),Fraction(modeled['bytes_share'])),('residual',Fraction(modeled['residual_ns']),Fraction(modeled['residual_share']))]
    dominant=max(enumerate(terms),key=lambda row:(abs(row[1][1]),-row[0]))[1]
    result=dict(schema='hw-region-1-decision-v1',status='COMPLETE',source_sha256=source_map(),primary=verdict,P1=verdict['P1'],Kill=verdict['Kill'],outcome=verdict['outcome'],P2=p2,
        P3=dict(passed=modeled['calls_at_least_half'],verdict='HIT' if modeled['calls_at_least_half'] else 'MISS',calls_share=modeled['calls_share']),
        dominant_primary_component=dict(name=dominant[0],term_ns=str(dominant[1]),signed_share=str(dominant[2])),fit=ref(HERE/'model/fit.json'),primary_model=ref(HERE/'model/cases/chr1-g16384.json'),
        counts=dict(logical_units=len(units),attempts=sum(u['attempt_count'] for u in units),retaken=sum(u['retaken'] for u in units),loaded_attempts=sum(u['loaded_attempts'] for u in units),
                    accepted_timing_observations=sum(len(load(deref(u['selected']))['rows']) for u in units),counter_requests=285000))
    save(HERE/'decision.json',result); print('DECISION_COMPLETE',result['outcome'],p2['verdict'],flush=True); return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('action',choices=('prepare','method','case','constants','fit','decide','model'))
    parser.add_argument('--case'); parser.add_argument('--frame',type=int,choices=SIZES); args=parser.parse_args()
    check(sys.platform=='linux','controller runs on the measured Linux host'); STATE.mkdir(parents=True,exist_ok=True)
    import fcntl
    with (STATE/'controller.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.action=='prepare': return prepare()
        if args.action=='method': return method()
        if args.action=='case': check(args.case is not None,'case ID required'); return case(args.case)
        if args.action=='constants': check(args.frame is not None,'one frame required'); return constants(args.frame)
        if args.action=='fit': return fit()
        if args.action=='model': check(args.case is not None,'model requires one case'); return model_case(args.case)
        return decide()


if __name__=='__main__': raise SystemExit(main())
