# SPDX-License-Identifier: Apache-2.0
"""Independent TB-LVL-0 audit of retained public bytes; no native code or clocks."""
import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT/'evidence/hw-region-2/casefix'
CAL = 'fa8a9cf801b2dcf62356b5d9c00c23c680836d21'
TB = '4aa97c8c37311e399ea3e7782c18c652c5bdb69f'
ACE = 'c53f3a04f3dbac8590e46a1f86c5fded1e69e065'
N = 211947520
INPUT_SHA = 'a667bac80089b3d04d5496772149e632f0758974b0579d743cd8d6e5e0d63eb2'
LOCK = '/run/lock/ovh-bench.lock'
POLICY = dict(refuse='2026-11-28T05:25:00+00:00',term='2026-11-28T05:29:40+00:00',
              kill='2026-11-28T05:29:50+00:00',release='2026-11-28T05:30:00+00:00')
PROFILES = {'aceapex_fast':list(range(1,9)),'aceapex':[1,2,3,4],'misa77':list(range(6)),
 'zxc':list(range(1,8)),'lz4':[1,3,9,12],'lzav':[1,2],'minlz':[1,3,7],
 'zstd':[1,3,9,15,19,22],'brotli':[4,6,9,11],'lzma':[9],'bsc':['0e0'],'kanzi':[5,6,7,8]}
PINS = dict(aceapex='022af6126de42e63450a45557676ba30bfd6caa9',brotli='717514a67b3f8abf53365d4471a102a60fff8ef5',
 **{'kanzi-cpp':'388ca03cf3a13e5456629a6781616c4c96f8fd4a'},libbsc='6542faafd0c235975e77e219c77f8227f770fe91',
 lz4='00bf3522fdb94a9d0e69c1d4db7eed77343f7a60',lzav='5a60cfd78e6f6dd8347a905d520b8d03ff5ea2f4',
 lzma='44809544b95bbf2dccec75d954657ff76fc349ff',minlz='ede3d8ebed44161c62b50a22491274d182ced777',
 misa77='d5293cfa4fd59526d26a8702a42a1139a5d4e0df',zstd='e50cdb0d407f5db512ed377fbee6c9ba473fea8e',zxc='69d1fae484b44b7ab612d8a9b1a5a023b9021c1b')
HEADER_PINS = {'zlib':'a28e8d5acad59823917e4e556a87584a803ac15e'}
AUXILIARY_PINS = {'Turbo-Range-Coder':'092b08c425394b118dd068e7c7778f51fad99fcf'}
HEADER = 'dataset size csize dtime ctime codec level param cmem dmem cstack dstack time err'.split()
BINDINGS = {}


class Incomplete(ValueError):
    pass


def require(ok, message):
    if not ok: raise ValueError(message)


def packed(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()


def unique(pairs):
    result={}
    for key,value in pairs:
        require(key not in result,'duplicate JSON key: '+key);result[key]=value
    return result


def read(path):
    path=Path(path).resolve()
    require(path.is_relative_to(ROOT) and not path.is_relative_to(ROOT/'.work'),'public repository files only')
    if not path.is_file(): raise Incomplete('missing saved evidence: '+str(path.relative_to(ROOT)))
    raw=path.read_bytes();value=hashlib.sha256(raw).hexdigest();name=path.relative_to(ROOT).as_posix()
    require(BINDINGS.setdefault(name,value)==value,'file changed during audit: '+name)
    return raw


def sha(path): return hashlib.sha256(read(path)).hexdigest()
def load(path): return json.loads(read(path),object_pairs_hook=unique)


def reference(value, base=HERE):
    require(type(value) is dict and type(value.get('path')) is str and not Path(value['path']).is_absolute(),'relative public ref required')
    path=(base/value['path']).resolve();require(path.is_relative_to(base.resolve()),'reference escaped its base')
    raw=read(path);require(hashlib.sha256(raw).hexdigest()==value['sha256'],'reference SHA differs: '+value['path'])
    if 'bytes' in value:require(type(value['bytes']) is int and len(raw)==value['bytes'],'artifact length differs')
    return path


def stamp(value):
    date=datetime.fromisoformat(value)
    require(date.tzinfo is not None and date.utcoffset()==timedelta(0),'literal UTC timestamp required')
    return date


def positive(value):
    require(type(value) in (str,int,Fraction),'exact rational required')
    result=Fraction(value);require(result>0,'nonpositive exact quantity');return result


def grid(resolved=True):
    result=[]
    profiles=dict(PROFILES)
    if not resolved:profiles['aceapex_fast']=list(range(1,19))
    for codec,levels in profiles.items():
        for level in levels:
            level=str(level);result.append(dict(id=codec+','+level,codec=codec,level=level,
                                               api_level=int(level)+10 if codec=='aceapex_fast' and resolved else None))
    return sorted(result,key=lambda row:row['id'])


def ordered(configs, number):
    result=sorted(configs,key=lambda row:row['id'])
    if number==2:return result[::-1]
    if number==3:return result[len(result)//2:]+result[:len(result)//2]
    return result


def native(raw, config):
    lines=raw.decode('utf-8').splitlines()
    require(len(lines)==2 and lines[0].split('\t')==HEADER,'fresh exact native header/one row required')
    fields=lines[1].split('\t');require(len(fields)==14,'wrong native table width')
    row=dict(zip(HEADER,fields))
    require(row['dataset']=='silesia.ref.tar' and row['codec']==config['codec'] and row['size']==str(N),'native source/codec differs')
    expected=('0','e0') if config['id']=='bsc,0e0' else (config['level'],'?')
    require((row['level'],row['param'])==expected and row['err']=='','native selection or byte check failed')
    for name in ('size','csize','cmem','dmem','cstack','dstack'):
        require(re.fullmatch(r'[0-9]+',row[name]) is not None,'native integer malformed')
    require(int(row['csize'])>0,'zero native archive')
    for name in ('ctime','dtime'):
        require(re.fullmatch(r'[0-9]+\.[0-9]{6}',row[name]) is not None,'native six-decimal seconds required');positive(row[name])
    return dict(input_bytes=N,compressed_bytes=int(row['csize']),ctime_seconds=row['ctime'],dtime_seconds=row['dtime'],roundtrip=True,native=row)


def elf(raw):
    require(len(raw)>=64 and raw[:7]==b'\x7fELF\x02\x01\x01','little-endian ELF64 required')
    h=struct.unpack_from('<16sHHIQQQIHHHHHH',raw)
    require(h[1] in (2,3) and h[2]==62 and h[8]==64 and h[9]==56 and h[10]>0,'wrong x86-64 executable header')
    require(h[5]+h[9]*h[10]<=len(raw),'truncated ELF program headers')
    dynamic=0
    for index in range(h[10]):
        p=struct.unpack_from('<IIQQQQQQ',raw,h[5]+index*56)
        require(p[0]!=3,'ELF PT_INTERP exists')
        if p[0] in (1,2):require(p[2]+p[5]<=len(raw),'truncated ELF segment')
        if p[0]==2:
            dynamic+=1;require(p[5]%16==0,'bad ELF dynamic size')
            for at in range(p[2],p[2]+p[5],16):
                tag,value=struct.unpack_from('<qQ',raw,at)
                require(tag!=1,'ELF DT_NEEDED exists')
                if tag==0:break
    return dict(machine='x86_64',program_headers=h[10],dynamic_segments=dynamic,PT_INTERP=False,DT_NEEDED=False)


def median_rows(selected, configs):
    rows=[]
    for config in configs:
        rounds=selected.get(config['id'],[])
        if len(rounds)!=3:continue
        require(sorted(r['round'] for r in rounds)==[1,2,3],'duplicate/missing external round')
        normalized=[]
        for r in sorted(rounds,key=lambda item:item['round']):
            c,d=positive(r['ctime_seconds']),positive(r['dtime_seconds'])
            normalized.append(dict(round=r['round'],compressed_bytes=r['compressed_bytes'],ctime_seconds=str(c),dtime_seconds=str(d),
                                   C_MB_s=str(Fraction(N,1000000)/c),D_MB_s=str(Fraction(N,1000000)/d)))
        sizes=sorted(r['compressed_bytes'] for r in normalized)
        c=sorted(Fraction(r['C_MB_s']) for r in normalized);d=sorted(Fraction(r['D_MB_s']) for r in normalized)
        rows.append(dict(**config,input_bytes=N,compressed_bytes=sizes[1],archive_percent=str(Fraction(100*sizes[1],N)),
                         C_MB_s=str(c[1]),D_MB_s=str(d[1]),size_min=sizes[0],size_max=sizes[2],
                         C_min=str(c[0]),C_max=str(c[2]),D_min=str(d[0]),D_max=str(d[2]),rounds=normalized))
    return rows


def mathematics(rows, mapping=True, owner_confirmed=False):
    configs=grid(mapping);complete=mapping and len(rows)==len(configs)
    def witnesses(pool,row,axis):
        return sorted(x['id'] for x in pool if x['compressed_bytes']<row['compressed_bytes'] and Fraction(x[axis+'_MB_s'])>Fraction(row[axis+'_MB_s']))
    fronts={axis:{r['id']:witnesses(rows,r,axis) for r in rows} for axis in ('C','D')}
    bands=[]
    for index in range(21):
        members=[r for r in rows if (20 if r['compressed_bytes']>N else min(20*r['compressed_bytes']//N,19))==index]
        names=sorted(r['id'] for r in members)
        bands.append(dict(index=index,label='>100%' if index==20 else '['+str(index*5)+','+str(index*5+5)+(']%' if index==19 else ')%'),
            status='POPULATED' if members else 'EMPTY',configurations=names,
            local_front_D=sorted(r['id'] for r in members if not witnesses(members,r,'D')),
            global_front_D_members=sorted(r['id'] for r in members if not fronts['D'][r['id']])))
    nearest=[];ace=[r for r in rows if r['codec'] in ('aceapex','aceapex_fast')]
    for m in sorted((r for r in rows if r['codec']=='misa77'),key=lambda r:int(r['level'])):
        if not ace:
            nearest.append(dict(misa77=m['id'],status='UNAVAILABLE',reason='no complete ACE median is available'));continue
        a=min(ace,key=lambda r:(abs(r['compressed_bytes']-m['compressed_bytes']),-Fraction(r['D_MB_s']),r['compressed_bytes'],r['id']))
        gap=a['compressed_bytes']-m['compressed_bytes'];speed=Fraction(a['D_MB_s'])-Fraction(m['D_MB_s'])
        nearest.append(dict(misa77=m['id'],ACE=a['id'],absolute_byte_gap=abs(gap),signed_byte_gap=gap,
            signed_archive_gap_pp=str(Fraction(100*gap,N)),signed_archive_gap_percent_of_misa=str(Fraction(100*gap,m['compressed_bytes'])),
            misa_D_MB_s=m['D_MB_s'],ACE_D_MB_s=a['D_MB_s'],signed_D_gap_MB_s=str(speed),signed_D_gap_percent_of_misa=str(100*speed/Fraction(m['D_MB_s']))))
    forecast={p:dict(verdict='NOT TESTED',passed=None,reason='registered grid/mapping is incomplete') for p in ('P1','P2')}
    if complete:
        references=[r for r in rows if r['codec'] in ('zstd','brotli','lzma')]
        eligible=[r for r in rows if r['codec']=='aceapex' and 27*N<=100*r['compressed_bytes']<=33*N]
        p1={r['id']:witnesses(references,r,'D') for r in eligible}
        fast=[r for r in rows if r['codec']=='aceapex_fast' and 13<=r['api_level']<=18]
        require(len(references)==11 and len(fast)==6,'forecast reference universe differs')
        p2={r['id']:witnesses(rows,r,'C') for r in fast};yes1=any(not v for v in p1.values());yes2=all(p2.values())
        forecast=dict(P1=dict(passed=yes1,verdict='HIT' if yes1 else 'MISS',probability='75%',eligible_defaults=sorted(p1),
            undominated_defaults=sorted(k for k,v in p1.items() if not v),D_dominators_within_named_11=p1,reference_configs=sorted(r['id'] for r in references)),
            P2=dict(passed=yes2,verdict='HIT' if yes2 else 'MISS',probability='55%',universal_API_levels=list(range(13,19)),C_dominators_within_registered_grid=p2))
    present={r['id'] for r in rows};wanted={r['id'] for r in configs}
    return dict(grid_complete=complete,mapping_resolved=mapping,owner_confirmed=owner_confirmed,requested_configurations=60,requested_main_roundtrips=180,
        registered_configurations=50 if mapping else None,registered_main_roundtrips=150 if mapping else None,
        completed_configurations=len(rows),missing_configurations=sorted(wanted-present),input_bytes=N,input_sha256=INPUT_SHA,
        rows=rows,global_front_D=sorted(k for k,v in fronts['D'].items() if not v),global_D_dominators=fronts['D'],
        separate_front_C=sorted(k for k,v in fronts['C'].items() if not v),separate_C_dominators=fronts['C'],frontiers_provisional=not complete,
        density_bands=bands,nearest_ACE_to_misa77=nearest,nearest_provisional=not complete,forecasts=forecast)


def build_evidence():
    base=HERE/'build';value=load(base/'build.json')
    require(value['schema']=='tb-lvl-0-static-build-v1' and value['status']=='PASS' and value['build_only'] is True
            and value['benchmark_calls']==0 and value['static_elf_verified'] is True,'successful build-only artifact required')
    require(value['turbobench_commit']==TB and value['aceapex_override']==ACE and value['controller_sha256']==sha(HERE/'build_static.py'),'build source pins/controller differ')
    require(value['fixed_architecture']=='-march=x86-64-v3 -mtune=generic' and value['go']['version']=='go1.27.4','compiler target/Go version differ')
    pins=dict(PINS,**HEADER_PINS,**AUXILIARY_PINS)
    sources=value['selected_sources']
    require(set(sources)==set(pins) and value['header_only_dependencies']==['zlib']
            and value['auxiliary_dependencies']=={'Turbo-Range-Coder':'upstream makefile supplies libsais and libsais16 for BSC/BCM'},
            'codec/header/auxiliary source roles differ')
    for name,pin in pins.items():require(sources[name]['upstream_gitlink']==pin and sources[name]['commit']==(ACE if name=='aceapex' else pin),'codec/header gitlink changed: '+name)
    require(sources['zlib']['url']=='https://github.com/madler/zlib.git' and 'zlib' not in value['requested_profiles'],
            'mandatory zlib headers became a measured dependency')
    require(sources['Turbo-Range-Coder']['url']=='https://github.com/powturbo/Turbo-Range-Coder.git'
            and value['requested_profiles']==PROFILES,'auxiliary dependency changed the registered profiles')
    for name,digest in value['repository_sources'].items():require(sha(ROOT/name)==digest,'CI repository source changed')
    require(value['make_argv'][0]=='make' and all(x in value['make_argv'] for x in ('STATIC=1','OPENMP=0','ZLIB=0','CC=gcc-14','CXX=g++-14','CXL=g++-14','MARCH=-march=x86-64-v3 -mtune=generic')),'build/link/header-only flags differ')
    for command in value['commands']:
        require(command['returncode']==0,'successful artifact contains a failed build command')
        for stream in ('stdout','stderr'):reference(command[stream],base)
    commands=[r['argv'] for r in value['commands']]
    require(['go','mod','download','-json','all'] in commands and ['go','mod','verify'] in commands
            and ['go','build','-mod=readonly','-buildmode=c-archive','-o','libmlz.a','.'] in commands,'pinned readonly Go resolution not proved')
    for row in value['commands']:
        if Path(row['argv'][0]).name=='turbobench':require(row['argv'][1:] in (['-l1'],['-l2']),'CI codec benchmark was invoked')
    registry=[r for r in value['commands'] if Path(r['argv'][0]).name=='turbobench' and r['argv'][1:]==['-l1']]
    require(len(registry)==1,'one enabled machine registry listing required')
    listing=read(reference(registry[0]['stdout'],base)).decode()
    specs={parts[0]:parts[1] for line in listing.splitlines() if len(parts:=line.split(None,1))==2 and parts[0] in PROFILES}
    require(set(specs)==set(PROFILES),'machine registry lacks a required compiled codec')
    for codec,levels in PROFILES.items():
        supported={int(x) for x in specs[codec].split('/',1)[0].split(',') if re.fullmatch('-?[0-9]+',x)}
        require(all(int(re.match('-?[0-9]+',str(x))[0]) in supported for x in levels)
                and (codec!='bsc' or 'e0' in specs[codec]),'compiled level/parameter missing')
    require(set(value['validated_profiles'])==set(PROFILES),'enabled profile set differs')
    for codec,requested in PROFILES.items():require(value['validated_profiles'][codec]['requested']==requested,'requested build levels differ')
    for key in ('source_selection','source_git_diff','submodules'):reference(value[key],base)
    selection=load(reference(value['source_selection'],base));known={r['path']:r['commit'] for r in value['upstream_gitlinks']}
    unused=sorted(set(known)-set(pins));require(selection['unselected_absent']==unused,'sparse source selection differs')
    require(selection['index_gitlinks']=={k:dict(mode='160000',stage='0',commit=v) for k,v in known.items()},'source index differs from upstream tree')
    flags=selection['index_flags'];require({k for k,v in flags.items() if v.upper()=='S'}==set(unused) and all(v.isupper() for v in flags.values()),'selected source hidden by index flags')
    patch=read(reference(value['source_git_diff'],base)).decode()
    require(patch.count('diff --git ')==1 and 'diff --git a/aceapex b/aceapex' in patch
            and '-Subproject commit '+PINS['aceapex'] in patch and '+Subproject commit '+ACE in patch and '-dirty' not in patch,'unexpected codec source patch')
    raw=gzip.decompress(read(base/'turbobench.gz'))
    require(len(raw)==value['binary']['bytes'] and hashlib.sha256(raw).hexdigest()==value['binary']['sha256'],'retained ELF differs from CI artifact')
    proof=elf(raw)
    for name in ('go.mod','go.sum','origin.json','SHA256SUMS'):read(base/name)
    origin=load(base/'origin.json')
    require(origin['schema']=='tb-lvl-0-actions-artifact-v1' and origin['status']=='PASS' and origin['benchmark_calls']==0
            and origin['repository']=='yasha1971-coder/hw-apex-bench' and origin['head_sha']==value['repository_commit']
            and origin['artifact_name']=='tb-lvl-0-static-'+origin['head_sha'] and type(origin['run_id']) is int and origin['run_id']>0
            and re.fullmatch('[0-9a-f]{64}',origin['artifact_zip_sha256']) is not None
            and origin['url']=='https://github.com/yasha1971-coder/hw-apex-bench/actions/runs/'+str(origin['run_id']), 'Actions artifact origin differs')
    sums=read(base/'SHA256SUMS').decode()
    require(sums==value['binary']['sha256']+'  turbobench\n'+sha(base/'build.json')+'  build.json\n','CI SHA256SUMS differs')
    require('github.com/minio/minlz v1.3.1' in read(base/'go.mod').decode(),'actual minlz module changed')
    for name in ('go_mod','go_sum'):reference(value['go'][name],base)
    for item in value['cmake_configuration']:reference(item,base)
    return value,proof


class Evidence:
    def __init__(self):
        self.host=None;self.attempts=[];self.seen_receipts=set();self.units=[];self.polls=[]
        spec=importlib.util.spec_from_file_location('_tb_independent_raw_telemetry',BASE/'audit.py')
        sha(BASE/'audit.py');self.telemetry=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.telemetry)

    def boundary(self,value):
        require(value['hostname']=='ace-core' and 'AMD EPYC 4344P' in value['cpu'] and value['pinned_core']==0
                and value['timed_threads']==1 and type(value['nproc']) is int and value['nproc']>0
                and value['date_u'] and value['kernel'] and value['governor'],'wrong host/core/thread metadata')
        fields=value['loadavg_raw'].split();require(len(fields)==5,'literal /proc/loadavg required')
        load1=Decimal(fields[0]);require(load1.is_finite() and load1>=0 and Decimal(value['load1_minus_T'])==load1-1,'load arithmetic differs')
        signature={k:value[k] for k in ('hostname','cpu','kernel','governor','pinned_core','host_logical_cpus')}
        if self.host is None:self.host=signature
        require(self.host==signature,'host/kernel/governor changed')
        stamp(value['timestamp_utc']);return load1

    def prepare(self):
        self.build,self.elf=build_evidence();self.prep=load(HERE/'preparation.json');p=self.prep;i=p['identity']
        require(p['schema']=='tb-lvl-0-preparation-v1' and p['status']=='PASS' and p['no_benchmark_calls'] is True
                and i['policy']==POLICY and i['input_bytes']==N and i['input_sha256']==INPUT_SHA,'preparation/input/policy differs')
        require(reference(p['build'])==HERE/'build/build.json' and i['build_manifest_sha256']==p['build']['sha256']
                and p['binary']['sha256']==i['binary_sha256']==self.build['binary']['sha256']
                and p['binary']['bytes']==self.build['binary']['bytes'],'binary/build coupling differs')
        require(p['input']['bytes']==N and p['input']['sha256']==INPUT_SHA
                and p['original_input_path']=='/home/aeterna/golden/mixed/silesia.ref.tar','original input identity differs')
        if i.get('input_staging_sha256') is not None:
            staging=load(HERE/'input-staging.json')
            require(sha(HERE/'input-staging.json')==i['input_staging_sha256'] and staging['schema']=='tb-lvl-0-input-staging-v1'
                    and staging['source']==dict(path=p['original_input_path'],bytes=N,sha256=INPUT_SHA)
                    and staging['staged']==p['input'] and p['input']['path'].endswith('/.work/tb-lvl-0/input/silesia.ref.tar'),'staged input bytes/path differ')
        else:require(p['input']['path']==p['original_input_path'],'unregistered alternate input')
        source_names={f'evidence/tb-lvl-0/{n}' for n in ('CALIBRATION.md','PROTOCOL.md','GRID_AMENDMENT.md','grid-amendment.json','runner.py','test_runner.py','build_static.py')}
        source_names.add('evidence/hw-region-2/casefix/ovh_bench.py')
        require(set(i['source_sha256'])==source_names,'execution source cohort differs')
        for name,digest in i['source_sha256'].items():require(sha(ROOT/name)==digest,'execution source changed')
        controls=load(reference(p['controls']))
        expected={k:v for k,v in i['source_sha256'].items() if k.endswith(('runner.py','test_runner.py'))}
        require(controls['schema']=='tb-lvl-0-runner-controls-v1' and controls['status']=='PASS' and controls['native_benchmark_calls']==0
                and controls['synthetic_tests_only'] is True and controls['returncode']==0 and controls['source_sha256']==expected,'controller controls missing/changed')
        reference(controls['stdout']);stderr=read(reference(controls['stderr'])).decode()
        count=re.search(r'Ran ([0-9]+) tests? in ',stderr)
        tests=len(re.findall(r'^    def test_',read(HERE/'test_runner.py').decode(),re.M))
        require(count is not None and int(count[1])==tests and '\nOK\n' in stderr and 'skipped' not in stderr.lower(),'controller tests skipped/failed/missing')
        sha(HERE/'analysis.py');sha(Path(__file__))
        g=load(reference(p['grid']));self.grid=g
        require(g['schema']=='tb-lvl-0-grid-v1' and g['mapping_resolved'] is True and g['owner_confirmed'] is False
                and g['status']=='RESOLVED_BY_SOURCE' and g['configurations']==grid()
                and g['rounds']==3 and g['main_roundtrips']==150
                and g['order']=={str(r):[c['id'] for c in ordered(grid(),r)] for r in (1,2,3)}
                and reference(g['amendment'])==HERE/'GRID_AMENDMENT.md','registered grid/order/amendment differs')
        amendment=load(reference(g['amendment_record']))
        required=dict(schema='tb-lvl-0-grid-amendment-v1',status='RESOLVED_BY_SOURCE',mapping_resolved=True,owner_confirmed=False,
            resolved_by='source inspection / ChatGPT',requested_fast_levels=list(range(1,19)),registered_fast_levels=list(range(1,9)),
            api_fast_levels=list(range(11,19)),p2_api_levels=list(range(13,19)),p2_tb_levels=list(range(3,9)),
            registered_configurations=50,registered_main_roundtrips=150)
        require(reference(g['amendment_record'])==HERE/'grid-amendment.json'
                and all(type(amendment.get(k)) is type(v) and amendment.get(k)==v for k,v in required.items()),
                'source-derived resolution changed or falsely claims owner confirmation')
        self.run=load(HERE/'run.json')
        require(self.run['schema']=='tb-lvl-0-run-v1' and self.run['identity']==i
                and self.run['grid']==p['grid'] and self.run['deadline']==POLICY,'run/preparation changed')
        return p

    def supervision(self,folder,request,receipt):
        value=load(folder/'supervision.json')
        require(value['schema']=='tb-lvl-0-supervision-v1' and reference(value['request'])==folder/'request.json'
                and value['policy']==POLICY and value['session_pid']==value['pgid']==value['session_id']
                and type(value['session_pid']) is int and value['session_pid']>0,'owned process-group identity differs')
        reaped=stamp(value['reaped_utc']);release=stamp(POLICY['release'])
        require(value['deadline_release_met'] is (reaped<release) and reaped<release,'own process group was not reaped before release')
        members=value['members_after_session_reap']
        for row in members:
            raw=row['raw_stat'];tail=raw[raw.rindex(')')+2:].split()
            require(int(raw[:raw.index('(')].strip())==row['pid'] and tail[0]==row['state'] and int(tail[2])==row['pgid']==value['pgid'],
                    'post-reap group observation differs from /proc bytes')
        require(value['live_group_empty'] is True and all(r['state']=='Z' for r in members),'own session left live children/lock waiters')
        if value['session'] is not None:
            session=load(reference(value['session']))
            require(session['schema']=='tb-lvl-0-session-v1' and session['request_sha256']==sha(folder/'request.json')
                    and session['pid']==session['pgid']==session['session_id']==value['session_pid'] and session['policy']==POLICY
                    and session['parent_death_signal']=='SIGKILL' and session['watchdog_pid']!=session['pid'],'watchdog/session binding differs')
            argv=session['flock_command']
            require(argv[:3]==['flock','-F',LOCK] and argv[4]=='-B' and argv[5].endswith('/evidence/tb-lvl-0/runner.py')
                    and argv[6]=='_inside' and argv[7]==request['folder']+'/request.json' and len(argv)==8,'not the fixed blocking flock child')
            require(stamp(request['waiting_since_utc'])<=stamp(session['started_utc'])<=reaped,'session chronology differs')
        else:require(receipt['status'] in ('ERROR','DEADLINE'),'healthy attempt has no session proof')
        return value

    def attempt(self,folder,target,number):
        p=self.prep;identity=dict(**p['identity'],config=target['config'],round=target['round'],kind=target['kind'])
        request=load(folder/'request.json');record=load(folder/'receipt.json');self.seen_receipts.add(folder/'receipt.json')
        require(request['schema']=='tb-lvl-0-request-v1' and request['identity']==identity and request['target']==target
                and request['policy']==POLICY and request['lock']==LOCK and request['synthetic'] is False,'actual request identity differs')
        require(request['folder'].endswith('/evidence/tb-lvl-0/'+folder.relative_to(HERE).as_posix())
                and request['cwd']==request['folder']+'/cwd','round cwd is not a unique fresh attempt directory')
        command=['taskset','-c','0',p['binary']['path'],'-e'+target['config']['id'],'-b1073741824B','-B'+str(N)+'B',
                 '-i0,0','-C3','-D','-V0','-v0',p['input']['path']]
        require(request['command']==command and stamp(request['waiting_since_utc'])<stamp(POLICY['refuse']),'single-call/byte oracle/selection/cutoff differs')
        require(record['schema']=='tb-lvl-0-receipt-v1' and record['identity']==identity and record['target']==target
                and record['policy']==POLICY and record['status'] in ('CLEAN','LOADED','ERROR','DEADLINE'),'receipt identity/status differs')
        for stream in ('stdout','stderr'):require(sha(folder/stream)==record[stream+'_sha256'],'native stream changed')
        healthy=record['status'] in ('CLEAN','LOADED');parsed=None
        if healthy:
            require(record['request_sha256']==sha(folder/'request.json') and record['helper_sha256']==sha(BASE/'ovh_bench.py')
                    and record['lock_path']==LOCK and record['command']==command,'receipt helper/request/command differs')
            flock=record['flock_lock_record'].split()
            require(len(flock)>=6 and flock[1:4]==['FLOCK','ADVISORY','WRITE'] and flock[4]==str(record['pid'])
                    and int(flock[5].rsplit(':',1)[-1])>0,'actual kernel flock owner record differs')
            high=self.telemetry.foreign_cpu(record['foreign_cpu_start'])
            start,end=self.boundary(record['start']),self.boundary(record['end']);self.telemetry.other_cores(record['start'],record['end'])
            require(stamp(record['waiting_since_utc'])<=stamp(record['start']['timestamp_utc'])<=stamp(record['end']['timestamp_utc'])<stamp(POLICY['term']),
                    'healthy native chronology exceeds fixed deadline')
            loaded=high or start>2 or end>2
            require(loaded is (record['status']=='LOADED') and record['command_started'] is (not high and start<=2),
                    'status/start selection differs from raw load/foreign threshold')
            require(record['returncode']==0 and type(record['returncode']) is int if record['command_started'] else record['returncode'] is None,
                    'native error cannot be retried as environmental load')
            if record['status']=='LOADED':require(record['ps_top8'] and record['ps_command']=='ps -eo pid,user,pcpu,comm --sort=-pcpu | head -8','LOADED process capture missing')
            if record['command_started']:
                require(stamp(record['start']['timestamp_utc'])<stamp(POLICY['refuse']),'new native call after refusal')
                require(record['worker_environment']=={'GOMAXPROCS':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'},'worker thread environment differs')
                started=load(folder/'worker-started.json')
                require(started['pid']==record['worker_pid'] and started['pgid']==record['pgid'] and stamp(started['utc'])<stamp(POLICY['refuse']),
                        'native start/affinity/PG proof differs')
                tasks=record['worker_tasks'];counts=[]
                for sample in tasks['samples']:
                    require(sample['count'] is None or sample['count']==len(sample['task_ids'])==len(set(sample['task_ids'])),'task count observation differs')
                    if sample['count'] is not None:counts.append(sample['count'])
                require(tasks['observational_only'] is True and tasks['maximum_observed']==max(counts,default=None),'task observation summary differs')
        result_path=folder/'result.json'
        if result_path.exists():
            require(record['command_started'] is True and record['returncode']==0,'failed/unstarted attempt supplied a numeric result')
            value=load(result_path);native_path=reference(value['raw'])
            require(native_path==folder/'native.tbb' and record['tbb_sha256']==value['raw']['sha256'] and reference(value['receipt'])==folder/'receipt.json','native result/raw/receipt swapped')
            parsed=native(read(native_path),target['config'])
            require(value['schema']=='tb-lvl-0-result-v1' and value['identity']==identity and value['config']==target['config']
                    and value['round']==target['round'] and all(value[k]==v for k,v in parsed.items()),'native result parse differs')
            if target['kind']=='method':require(parsed['compressed_bytes']==130490328,'method known-answer size mismatch')
        elif healthy:require(record['command_started'] is False and not (folder/'native.tbb').exists(),'healthy started pass lacks a byte-verified native result')
        supervision=self.supervision(folder,request,record)
        if healthy:
            require(record['pgid']==record['session_id']==supervision['pgid'] and record['parent_death_signal']=='SIGKILL','native flocker escaped owned group')
            expected_code=0 if record['status']=='CLEAN' else 77
            require(supervision['session_returncode']==expected_code,'session/receipt return code differs')
            require(read(folder/'session.done')==b'done\n','healthy session did not finish and join its watchdog')
        for artifact in folder.rglob('*'):
            if artifact.is_file():read(artifact)
        row=dict(target=target,number=number,folder=folder,request=request,receipt=record,parsed=parsed,supervision=supervision)
        self.attempts.append(row);return row

    def unit(self,target):
        folder=HERE/'raw'/target['part']/target['config']['id'];path=HERE/'units'/target['part']/(target['config']['id']+'.json')
        attempts=sorted(folder.glob('attempt-*')) if folder.exists() else []
        require([p.name for p in attempts]==['attempt-'+str(i) for i in range(1,len(attempts)+1)] and len(attempts)<=3,'missing/orphan/fourth actual attempt')
        if not attempts:
            require(not path.exists(),'unit exists without raw attempt');return None
        history=[];records=[]
        for number,attempt in enumerate(attempts,1):
            if records:require(records[-1]['receipt']['status']=='LOADED','CLEAN/fatal attempt was repeated')
            row=self.attempt(attempt,target,number);records.append(row)
            history.append(dict(attempt=number,status=row['receipt']['status'],receipt=dict(path=(attempt/'receipt.json').relative_to(HERE).as_posix(),sha256=sha(attempt/'receipt.json')),
                result=dict(path=(attempt/'result.json').relative_to(HERE).as_posix(),sha256=sha(attempt/'result.json')) if row['parsed'] is not None else None))
        winner=records[-1] if records[-1]['receipt']['status']=='CLEAN' else None
        if path.exists():
            value=load(path);self.units.append(path)
            require(value['schema']=='tb-lvl-0-unit-v1' and value['identity']==records[0]['request']['identity']
                    and value['config']==target['config'] and value['kind']==target['kind'] and value['round']==target['round']
                    and value['attempts']==history,'unit/request/attempt history differs')
            if winner:require(value['status']=='CLEAN' and value['selected']==history[-1]['result'],'not first-CLEAN selection')
            else:require(value['status']=='BLOCKED: load' and len(records)==3 and all(r['receipt']['status']=='LOADED' for r in records)
                         and value['selected'] is None,'blocked unit is not exactly three LOADED')
        else:require(winner is None,'CLEAN result not checkpointed in unit manifest')
        return dict(winner=winner,records=records,path=path)

    def registration(self):
        record=load(HERE/'preregistration.json');receipt=load(reference(record['github_receipt']))
        raw=read(HERE/'CALIBRATION.md');blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        require(record['schema']=='tb-lvl-0-preregistration-v1' and record['first_commit']==receipt['sha']==CAL
                and record['calibration_sha256']==hashlib.sha256(raw).hexdigest() and record['calibration_blob_sha']==blob
                and record['changed_files']==['evidence/tb-lvl-0/CALIBRATION.md'],'first-only calibration differs')
        files=receipt['files']
        require(len(files)==1 and files[0]['filename']==record['changed_files'][0] and files[0]['status']=='added'
                and files[0]['sha']==blob and stamp(receipt['commit']['committer']['date'])==stamp(record['first_commit_utc']),
                'saved GitHub first-commit metadata differs')
        for item in self.attempts:
            require(stamp(item['request']['waiting_since_utc'])>stamp(record['first_commit_utc']),'attempt predates calibration')

    def polling(self):
        paths=sorted((HERE/'polls').glob('poll-*.json'))
        require([p.name for p in paths]==[f'poll-{i:06d}.json' for i in range(1,len(paths)+1)],'poll sequence has a gap')
        previous=None;polls={}
        for path in paths:
            value=load(path);self.polls.append(value);polls[path]=value
            require(value['schema']=='tb-lvl-0-poll-v1' and value['identity']==self.prep['identity'] and value['no_native_calls'] is True
                    and value['status'] in ('PASS','WAITING','ERROR'),'poll identity/status differs')
            start,end=stamp(value['start_utc']),stamp(value['end_utc'])
            require(start<=end and (previous is None or start>=previous),'poll chronology regressed')
            earlier=[r for r in self.attempts if stamp(r['request']['waiting_since_utc'])<=start]
            if earlier:
                require(start>=max(stamp(r['supervision']['reaped_utc']) for r in earlier),'observation overlapped an unfinished actual attempt')
                require(all(r['receipt']['status'] not in ('ERROR','DEADLINE') for r in earlier),'poll after fatal/deadline attempt')
            completed={(r['target']['part'],r['target']['config']['id']) for r in earlier if r['receipt']['status']=='CLEAN'}
            current=next((t for t in self.planned if (t['part'],t['config']['id']) not in completed),None)
            require(current is not None and value['target']==current,'admission target skipped/reordered an unfinished unit')
            require(sum(r['target']==current and r['receipt']['status']=='LOADED' for r in earlier)<3,'observation after exhausted three-attempt budget')
            waits=[stamp(v['end_utc']) for p,v in polls.items() if p!=path and v['status']=='WAITING']
            waits += [stamp(r['receipt']['end']['timestamp_utc']) for r in earlier if r['receipt']['status']=='LOADED']
            if waits:require(start>=max(waits)+timedelta(seconds=300),'admission poll bypassed the 300-second wait')
            if value['status']=='ERROR':require(path==paths[-1] and value.get('error') and (HERE/'ERROR.json').exists(),'inspection ERROR was not terminal')
            else:
                high=self.telemetry.foreign_cpu(value['foreign_cpu_start']);loads=[self.boundary(value[k]) for k in ('start','end')]
                require((high or max(loads)>2) is (value['status']=='WAITING'),'observational admission differs from raw telemetry')
            previous=end
        consumed={};actual={row['folder']/'request.json':row for row in self.attempts}
        for path in sorted((HERE/'consumptions').glob('*.json')):
            item=load(path);poll_path=reference(item['poll']);poll=polls.get(poll_path)
            require(poll is not None and poll['status']=='PASS' and poll_path.name==path.name and poll_path not in consumed,
                    'attempt did not consume a unique PASS poll')
            request_path=reference(item['request']);row=actual.get(request_path)
            require(row is not None and item['schema']=='tb-lvl-0-consumption-v1' and item['identity']==self.prep['identity']
                    and item['target']==poll['target']==row['target'] and item['attempt']==row['number']
                    and item['receipt_path']==(row['folder']/'receipt.json').relative_to(HERE).as_posix(),'poll/request/attempt binding differs')
            time=stamp(item['committed_before_attempt_utc'])
            require(stamp(poll['end_utc'])<=time and stamp(row['request']['waiting_since_utc'])<=time
                    and time<=stamp(row['supervision']['reaped_utc']),'PASS consumption was not committed around this attempt')
            if row['receipt'].get('start'):require(time<=stamp(row['receipt']['start']['timestamp_utc']),'admission consumption occurred after native admission')
            preceding=[p for p in paths if stamp(polls[p]['end_utc'])<=time]
            require(preceding and preceding[-1]==poll_path,'stale PASS poll was reused after another observation')
            consumed[poll_path]=request_path
        require(set(consumed.values())==set(actual),'actual attempt lacks one-to-one pre-admission consumption')
        unused=[p for p in paths if polls[p]['status']=='PASS' and p not in consumed]
        require(not unused or unused==[paths[-1]] and polls[unused[0]]['target']==self.run['next_unit'],'unused PASS poll was superseded')
        require(self.run['polls']==[dict(path=p.relative_to(HERE).as_posix(),sha256=sha(p)) for p in paths],'run poll inventory differs')
        expected=[dict(path=p.relative_to(HERE).as_posix(),sha256=sha(p)) for p in sorted((HERE/'consumptions').glob('*.json'))]
        require(self.run['consumptions']==expected,'run consumption inventory differs')
        return dict(polls=len(paths),waiting_polls=sum(v['status']=='WAITING' for v in polls.values()),consumed_passing_polls=len(consumed))

    def all(self):
        self.prepare();configs=grid();planned=[dict(kind='method',round=0,config=next(c for c in configs if c['id']=='aceapex_fast,1'),part='method')]
        for number in (1,2,3):planned.extend(dict(kind='main',round=number,config=c,part='round-'+str(number)) for c in ordered(configs,number))
        self.planned=planned
        selected={};accepted=[];next_target=None;stopped=False;last_end=None;method=None
        for target in planned:
            if stopped:
                require(not (HERE/'raw'/target['part']/target['config']['id']).exists()
                        and not (HERE/'units'/target['part']/(target['config']['id']+'.json')).exists(),'future target ran after an incomplete/fatal predecessor')
                continue
            value=self.unit(target)
            if value is not None:
                first=stamp(value['records'][0]['request']['waiting_since_utc'])
                if last_end is not None:require(first>=last_end,'next roundtrip preceded prior process-group reap')
                last_end=stamp(value['records'][-1]['supervision']['reaped_utc'])
            if value is None or value['winner'] is None:
                stopped=True;next_target=target;continue
            winner=value['winner'];accepted.append(dict(path=value['path'].relative_to(HERE).as_posix(),sha256=sha(value['path'])))
            if target['kind']=='method':method=winner['parsed']
            else:selected.setdefault(target['config']['id'],[]).append(dict(**winner['parsed'],round=target['round']))
        require(self.run['method']==(accepted[0] if accepted else None) and self.run['units']==accepted[1:]
                and self.run['next_unit']==next_target,'accepted execution prefix/next target differs from raw evidence')
        require(set((HERE/'units').rglob('*.json'))==set(self.units)
                and set((HERE/'raw').rglob('receipt.json'))==self.seen_receipts,'orphan or hidden timing unit/receipt')
        require({p for p in (HERE/'raw').glob('*/*') if p.is_dir()}==
                {r['folder'].parent for r in self.attempts},'unaccounted raw request directory')
        require(not self.run['units'] or method is not None and method['compressed_bytes']==130490328,'main timing lacks the exact preceding known answer')
        self.registration();polls=self.polling();rows=median_rows(selected,configs);math=mathematics(rows,True,False)
        require(not math['grid_complete'] or self.run['status']=='COMPLETE' and len(accepted)==151,'complete mathematical grid lacks complete clean execution')
        completion='COMPLETE' if math['grid_complete'] else self.run['status']
        if self.attempts and self.attempts[-1]['receipt']['status'] in ('ERROR','DEADLINE'):
            completion=self.attempts[-1]['receipt']['status']
        if (HERE/'ERROR.json').exists():
            error=load(HERE/'ERROR.json');require(error.get('reason'),'latched ERROR has no reason')
            if 'receipt' in error:reference(error['receipt'])
            if 'poll' in error:reference(error['poll'])
            require(not math['grid_complete'],'complete grid cannot hide a latched ERROR');completion='ERROR'
        counts=dict(accepted_units=len(accepted),accepted_main_roundtrips=max(0,len(accepted)-1),actual_attempts=len(self.attempts),
                    logical_units_started=len({(r['target']['part'],r['target']['config']['id']) for r in self.attempts}),
                    loaded_attempts=sum(r['receipt']['status']=='LOADED' for r in self.attempts),
                    retaken_units=sum(r['number']==2 for r in self.attempts),**polls)
        return dict(status='PASS',completion=completion,grid_complete=math['grid_complete'],
            analysis=math,analysis_sha256=hashlib.sha256(packed(math)).hexdigest(),counts=counts,host=self.host,ELF=self.elf,
            method_known_answer=method['compressed_bytes'] if method else None,
            excluded_attempts=[dict(target=r['target'],attempt=r['number'],status=r['receipt']['status'],command_started=r['receipt']['command_started'],
                receipt=dict(path=(r['folder']/'receipt.json').relative_to(HERE).as_posix(),sha256=sha(r['folder']/'receipt.json')))
                for r in self.attempts if r['receipt']['status']!='CLEAN'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=HERE/'audit.json');args=parser.parse_args()
    output=args.output.resolve();require(output.parent==HERE and output.suffix=='.json','audit output must stay in task directory')
    value=dict(schema='tb-lvl-0-independent-audit-v1',saved_data_only=True,no_codecs=True,no_clocks=True,no_git=True,
               private_paths_required=False,source_binding_base='repository')
    try:value.update(Evidence().all())
    except Incomplete as error:value.update(status='INCOMPLETE',completion='INCOMPLETE',reason=str(error))
    except (ValueError,KeyError,IndexError,TypeError,OSError,struct.error,StopIteration,UnicodeError,zlib.error,EOFError) as error:
        value.update(status='FAIL',completion='INCOMPLETE',reason=type(error).__name__+': '+str(error))
    value['source_bindings']=[dict(path=k,sha256=v) for k,v in sorted(BINDINGS.items())]
    output.write_bytes(packed(value))
    print(json.dumps({k:value[k] for k in ('status','completion','reason','counts','method_known_answer') if k in value},sort_keys=True))
    return 0 if value['status']=='PASS' else 2 if value['status']=='INCOMPLETE' else 1


if __name__=='__main__':raise SystemExit(main())
