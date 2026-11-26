"""HW-REGION-1 native preparation and retained per-request observations.

Import performs no build, native call or clock read. Timed readers are the
unchanged repository C readers; counting copies are separate artifacts.
"""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import re
import shutil
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = ROOT/'.work/hw-region-1'
NATIVE = STATE/'native'
CODECS = ('aceapex','zstd_seekable','bgzip')
SIZES = (4096,16384,65536,262144)
LOCK = '/run/lock/ovh-bench.lock'
CALIBRATION = '8108834615cbd651f79f77cb8d81fed24fa269f1'
PINS = {'aceapex':'ce6b6740c7aae8a01720d615ae024c181b7d52b6',
        'zstd':'f8745da6ff1ad1e7bab384bd1f9d742439278e99',
        'htslib':'4b705e4fada8ee2b6b15746f725ee8ac51631803',
        'libdeflate':'dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f'}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def packed(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()


def load(path):
    return json.loads(Path(path).read_bytes())


def immutable(path,data):
    path = Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        require(path.read_bytes() == data,'retained bytes changed: '+str(path))
    else:
        with path.open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())


def save(path,value):
    immutable(path,packed(value))


def git(*args,repo=ROOT):
    return subprocess.check_output(['git','-C',str(repo),*args])


def provenance():
    require(sys.platform == 'linux' and platform.node() == 'ace-core','ace-core Linux required')
    require('AMD EPYC 4344P' in Path('/proc/cpuinfo').read_text(),'declared EPYC host required')
    require(git('branch','--show-current').decode().strip() == 'hw-region-1','wrong experiment branch')
    require(git('show',CALIBRATION+':evidence/hw-region-1/CALIBRATION.md') == (HERE/'CALIBRATION.md').read_bytes(), 'first calibration changed')
    paths = [HERE/name for name in ('CALIBRATION.md','PROTOCOL.md','instrument.py','worker.c','native_versions.c','native_constants.c')]
    paths += [ROOT/'harness/resident_context.h']+[ROOT/'codecs/native'/name for name in ('aceapex_persistent.c','zstd_seekable.c','bgzip.c')]
    for path in paths:
        name = path.relative_to(ROOT).as_posix()
        git('ls-files','--error-unmatch','--',name)
        require(not git('status','--porcelain','--',name).strip(),'uncommitted instrument input: '+name)
    return dict(calibration_commit=CALIBRATION,calibration_sha256=sha(HERE/'CALIBRATION.md'),protocol_sha256=sha(HERE/'PROTOCOL.md'),
                source_sha256={path.relative_to(ROOT).as_posix():sha(path) for path in paths})


def setup():
    value = load(HERE/'setup.json')
    require(value['schema'] == 'hw-region-1-setup-v1' and (HERE/'setup.json').read_bytes() == (STATE/'setup.json').read_bytes(), 'owned setup receipt required')
    for name,pin in PINS.items():
        record = value['deps'][name]; repo = Path(record['path'])
        require(record['commit'] == pin and git('rev-parse','HEAD',repo=repo).decode().strip() == pin
                and not git('status','--porcelain','--untracked-files=no',repo=repo).strip(),'dependency source changed: '+name)
        if 'library_path' in record:
            require(sha(record['library_path']) == record['library_sha256'],'dependency library changed: '+name)
    return value


def command(label,args):
    folder = NATIVE/'commands'/label
    identity = list(map(str,args)); receipt = folder/'command.json'
    if receipt.exists():
        old = load(receipt)
        require(old['status'] == 'COMPLETE' and old['command'] == identity,'unfinished/changed native command: '+label)
        for stream in ('stdout','stderr'):
            require(sha(folder/stream) == old[stream+'_sha256'],'native build log changed')
        return old
    require(not folder.exists(),'orphan native command: '+label)
    folder.mkdir(parents=True); save(receipt,dict(status='STARTED',command=identity))
    result = subprocess.run(identity,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    (folder/'stdout').write_bytes(result.stdout); (folder/'stderr').write_bytes(result.stderr)
    old = dict(status='COMPLETE' if result.returncode == 0 else 'ERROR',command=identity,returncode=result.returncode,
               stdout_sha256=sha(folder/'stdout'),stderr_sha256=sha(folder/'stderr'))
    receipt.write_bytes(packed(old)); result.check_returncode(); return old


ACE_PREFIX = r'''
#include <stdint.h>
static uint64_t region_materialized,region_calls,region_zbytes,region_dc,region_one;
void hc_count_reset(void *p){(void)p;region_materialized=region_calls=region_zbytes=region_dc=region_one=0;}
uint64_t hc_count_bytes(void *p){(void)p;return region_materialized;}
uint64_t hc_count_zstd_calls(void *p){(void)p;return region_calls;}
uint64_t hc_count_zstd_bytes(void *p){(void)p;return region_zbytes;}
uint64_t hc_count_dctx_calls(void *p){(void)p;return region_dc;}
uint64_t hc_count_oneshot_calls(void *p){(void)p;return region_one;}
uint64_t hc_count_stream_calls(void *p){(void)p;return 0;}
/* These bodies precede macro redirection. Internal libzstd calls therefore do
 * not recursively enter these counters: one ACE API invocation is one call. */
static size_t region_decompress(void *d,size_t nd,const void *s,size_t ns){
    size_t r=ZSTD_decompress(d,nd,s,ns);region_calls++;region_one++;if(!ZSTD_isError(r))region_zbytes+=r;return r;}
static size_t region_decompress_dctx(ZSTD_DCtx *x,void *d,size_t nd,const void *s,size_t ns){
    size_t r=ZSTD_decompressDCtx(x,d,nd,s,ns);region_calls++;region_dc++;if(!ZSTD_isError(r))region_zbytes+=r;return r;}
int64_t hc_counter_probe(const void *s,size_t ns,void *d,size_t nd,int api){
    if(api==0){if(ns>nd)return -1;memcpy(d,s,ns);return (int64_t)ns;}
    size_t r;
    if(api==1){ZSTD_DCtx *x=ZSTD_createDCtx();if(!x)return -1;r=region_decompress_dctx(x,d,nd,s,ns);ZSTD_freeDCtx(x);}
    else if(api==2)r=region_decompress(d,nd,s,ns);else return -1;
    return ZSTD_isError(r)?-1:(int64_t)r;}
#define ZSTD_decompress region_decompress
#define ZSTD_decompressDCtx region_decompress_dctx
'''

BGZF_COUNTER = r'''
#include <stdint.h>
#include <stddef.h>
#include <zlib.h>
#include <libdeflate.h>
static uint64_t region_bytes;
void hc_count_reset(void *p){(void)p;region_bytes=0;}
uint64_t hc_count_bytes(void *p){(void)p;return region_bytes;}
uint64_t hc_count_zstd_calls(void *p){(void)p;return 0;}
uint64_t hc_count_zstd_bytes(void *p){(void)p;return 0;}
uint64_t hc_count_dctx_calls(void *p){(void)p;return 0;}
uint64_t hc_count_oneshot_calls(void *p){(void)p;return 0;}
uint64_t hc_count_stream_calls(void *p){(void)p;return 0;}
int __real_inflate(z_streamp,int);
int __wrap_inflate(z_streamp s,int flush){uLong before=s->total_out;int r=__real_inflate(s,flush);region_bytes+=(uint64_t)(s->total_out-before);return r;}
enum libdeflate_result __real_libdeflate_deflate_decompress(struct libdeflate_decompressor*,const void*,size_t,void*,size_t,size_t*);
enum libdeflate_result __wrap_libdeflate_deflate_decompress(struct libdeflate_decompressor *d,const void *s,size_t ns,void *out,size_t nd,size_t *actual){
    size_t got=0;enum libdeflate_result r=__real_libdeflate_deflate_decompress(d,s,ns,out,nd,&got);
    if(r==LIBDEFLATE_SUCCESS)region_bytes+=got;if(actual)*actual=got;return r;}
'''

ZSTD_COUNTER = r'''
#include <stdint.h>
#include <zstd.h>
void region_decoded_reset(void);
uint64_t region_decoded_bytes(void);
static uint64_t region_calls;
void hc_count_reset(void *p){(void)p;region_calls=0;region_decoded_reset();}
uint64_t hc_count_bytes(void *p){(void)p;return region_decoded_bytes();}
uint64_t hc_count_zstd_bytes(void *p){(void)p;return region_decoded_bytes();}
uint64_t hc_count_zstd_calls(void *p){(void)p;return region_calls;}
uint64_t hc_count_dctx_calls(void *p){(void)p;return 0;}
uint64_t hc_count_oneshot_calls(void *p){(void)p;return 0;}
uint64_t hc_count_stream_calls(void *p){(void)p;return region_calls;}
size_t __real_ZSTD_decompressStream(ZSTD_DStream*,ZSTD_outBuffer*,ZSTD_inBuffer*);
size_t __wrap_ZSTD_decompressStream(ZSTD_DStream *x,ZSTD_outBuffer *d,ZSTD_inBuffer *s){region_calls++;return __real_ZSTD_decompressStream(x,d,s);}
'''


def replace_once(text,old,new):
    require(text.count(old) == 1,'pinned counter hook changed: '+old)
    return text.replace(old,new)


def expose_native(value):
    save(HERE/'native/build.json',value)
    for path in (NATIVE/'commands').glob('*/*'):
        if path.is_file():
            name='command.'+path.name if path.name in ('stdout','stderr') else path.name
            immutable(HERE/'native'/path.parent.name/name,path.read_bytes())


def build():
    require(not os.environ.get('OVH_BENCH_LOCK_HELD'),'build outside OVH-BENCH')
    sources,prepared = provenance(),setup()
    deps = {name:Path(record['path']) for name,record in prepared['deps'].items()}
    libs = {name:Path(prepared['deps'][name]['library_path']) for name in ('zstd','htslib','libdeflate')}
    identity = dict(provenance=sources,setup_sha256=sha(HERE/'setup.json'),counter_templates_sha256={
        'ace':digest(ACE_PREFIX.encode()),'zstd':digest(ZSTD_COUNTER.encode()),'bgzf':digest(BGZF_COUNTER.encode())})
    receipt = NATIVE/'build.json'
    if receipt.exists():
        old=load(receipt); require(old['identity']==identity,'native build cohort changed')
        for item in old['artifacts'].values(): require(sha(item['path'])==item['sha256'],'native artifact changed')
        for item in old['sources'].values(): require(sha(item['path'])==item['sha256'],'native counting source changed')
        expose_native(old)
        return old
    NATIVE.mkdir(parents=True,exist_ok=True)
    generated = NATIVE/'sources'; generated.mkdir(exist_ok=True)
    ace=(deps['aceapex']/'c/aceapex_decode.c').read_text()
    ace=replace_once(ace,'#include <zstd.h>\n','#include <zstd.h>\n'+ACE_PREFIX)
    marker='        if(!cur_chunk(c,i,b,raw)){ *err=ACEAPEX_ERR_DATA; return 0; }\n        c->cc[slot].idx=i; c->cc[slot].raw=raw; }'
    ace=replace_once(ace,marker,'        if(!cur_chunk(c,i,b,raw)){ *err=ACEAPEX_ERR_DATA; return 0; }\n        region_materialized += raw;\n        c->cc[slot].idx=i; c->cc[slot].raw=raw; }')
    immutable(generated/'aceapex_decode_count.c',ace.encode())
    immutable(generated/'bgzf_count.c',BGZF_COUNTER.encode()); immutable(generated/'zstd_count.c',ZSTD_COUNTER.encode())
    counter_zstd=NATIVE/'counter-zstd'
    if not counter_zstd.exists():
        shutil.copytree(deps['zstd'],counter_zstd,ignore=shutil.ignore_patterns('.git','obj','*.o','*.a','*.so*'))
    relative=Path('lib/decompress/zstd_decompress.c')
    ztext=(deps['zstd']/relative).read_text()
    ztext='#include <stdint.h>\nstatic uint64_t region_reconstructed;\nvoid region_decoded_reset(void){region_reconstructed=0;}\nuint64_t region_decoded_bytes(void){return region_reconstructed;}\n'+ztext
    ztext=replace_once(ztext,'        FORWARD_IF_ERROR(decodedSize, "Block decompression failure");','        FORWARD_IF_ERROR(decodedSize, "Block decompression failure");\n        region_reconstructed += decodedSize;')
    ztext=replace_once(ztext,'            dctx->decodedSize += rSize;','            region_reconstructed += rSize;\n            dctx->decodedSize += rSize;')
    target=counter_zstd/relative
    if target.read_bytes() == (deps['zstd']/relative).read_bytes(): target.write_text(ztext,encoding='utf-8',newline='\n')
    else: require(target.read_text()==ztext,'private counted zstd source changed')
    command('zstd-count-static',['make','-C',counter_zstd/'lib','-j1','libzstd.a','CFLAGS=-O3 -fPIC -fno-lto'])
    common=['gcc','-O3','-fPIC','-fno-lto','-shared','-Wall','-Wextra','-Wl,-Bsymbolic','-I'+str(ROOT/'harness')]
    zflags=['-DXXH_NAMESPACE=ZSTD_','-I'+str(deps['zstd']/'lib'),'-I'+str(deps['zstd']/'lib/common'),'-I'+str(deps['zstd']/'contrib/seekable_format')]
    artifacts={}
    for codec in CODECS:
        for kind in ('timed','count'):
            output=NATIVE/(codec+'-'+kind+'.so')
            wrapper=ROOT/'codecs/native'/('aceapex_persistent.c' if codec=='aceapex' else codec+'.c')
            if codec=='aceapex':
                source=generated/'aceapex_decode_count.c' if kind=='count' else deps['aceapex']/'c/aceapex_decode.c'
                args=common+['-std=c99','-I'+str(deps['aceapex']/'c'),*zflags,'-DHB_ACE_VERSION="aceapex-v2.6.5@'+PINS['aceapex']+'"',
                             wrapper,source,HERE/'native_versions.c',libs['zstd'],'-pthread','-o',output]
            elif codec=='zstd_seekable':
                extra=[generated/'zstd_count.c','-Wl,--wrap=ZSTD_decompressStream'] if kind=='count' else []
                library=counter_zstd/'lib/libzstd.a' if kind=='count' else libs['zstd']
                args=common+zflags+[wrapper,deps['zstd']/'contrib/seekable_format/zstdseek_decompress.c',HERE/'native_versions.c',*extra,library,'-pthread','-o',output]
            else:
                extra=[generated/'bgzf_count.c','-Wl,--wrap=inflate','-Wl,--wrap=libdeflate_deflate_decompress'] if kind=='count' else []
                args=common+['-I'+str(deps['htslib']),'-I'+str(deps['libdeflate']),wrapper,*extra,libs['htslib'],libs['libdeflate'],'-lz','-lm','-pthread','-o',output]
            command(codec+'-'+kind,args)
            artifacts[codec+'-'+kind]=dict(path=str(output),sha256=sha(output))
    constants=NATIVE/'zstd-constants.so'
    command('constants-lib',common+zflags+[HERE/'native_constants.c',libs['zstd'],'-o',constants])
    worker=NATIVE/'worker'
    command('worker',['gcc','-O3','-std=c11','-Wall','-Wextra','-I'+str(ROOT/'harness'),HERE/'worker.c','-ldl','-o',worker])
    artifacts.update(constants=dict(path=str(constants),sha256=sha(constants)),worker=dict(path=str(worker),sha256=sha(worker)))
    paths=[generated/'aceapex_decode_count.c',generated/'bgzf_count.c',generated/'zstd_count.c',counter_zstd/relative]
    result=dict(schema='hw-region-1-native-v1',identity=identity,artifacts=artifacts,
                sources={p.name:dict(path=str(p),sha256=sha(p)) for p in paths},
                commands={p.parent.name:load(p) for p in sorted((NATIVE/'commands').glob('*/command.json'))},
                compiler=subprocess.check_output(['gcc','--version']).decode(),timed_readers_unchanged=True)
    save(receipt,result); expose_native(result)
    return result


def native_receipt():
    value=load(NATIVE/'build.json')
    require(value['schema']=='hw-region-1-native-v1' and value['identity']['provenance']==provenance()
            and value['identity']['setup_sha256']==sha(HERE/'setup.json'),'native preparation changed')
    require((HERE/'native/build.json').read_bytes()==(NATIVE/'build.json').read_bytes(),'public/private native receipt differs')
    for record in value['artifacts'].values(): require(sha(record['path'])==record['sha256'],'native artifact changed')
    return value


def traces(corpus,source):
    require(source['bytes']>=16384,'source smaller than request')
    seed=20261126+int(source['sha256'],16)
    rng=random.Random(seed)
    warmups=[rng.randrange(source['bytes']-16384+1) for _ in range(12)]
    offsets=[rng.randrange(source['bytes']-16384+1) for _ in range(1000)]
    folder=STATE/'traces'/corpus
    warm=folder/'warmups.bin'; trace=folder/'requests.bin'
    immutable(warm,b''.join(struct.pack('<Q',off) for off in warmups))
    immutable(trace,b''.join(struct.pack('<Q',off) for off in offsets))
    value=dict(schema='hw-region-1-trace-v1',corpus=corpus,input_bytes=source['bytes'],input_sha256=source['sha256'],
               seed_integer=str(seed),seed_rule='20261126 + int(input_sha256,16)',request_bytes=16384,
               warmup_offsets=warmups,offsets=offsets,encoding='uint64 little endian',
               warmups=dict(path=str(warm),bytes=warm.stat().st_size,sha256=sha(warm)),
               requests=dict(path=str(trace),bytes=trace.stat().st_size,sha256=sha(trace)))
    public=HERE/'traces'/(corpus+'.json'); save(public,value)
    return public,value


def request(case_path,codec):
    require(codec in CODECS,'unknown codec')
    case_path=Path(case_path)
    if not case_path.is_file(): case_path=HERE/'archives'/(str(case_path)+'.json')
    case_path=case_path.resolve(); require(case_path.is_relative_to((HERE/'archives').resolve()),'case manifest escaped experiment')
    prepared,native=setup(),native_receipt(); case=load(case_path)
    require(case['schema']=='hw-region-1-archives-v1' and case['setup_sha256']==sha(HERE/'setup.json')
            and case['case_id'] in prepared['cases'],'archive case not admitted')
    source=case['input']; archive=case['formats'][codec]
    require(source==prepared['inputs'][case['corpus']] and sha(source['path'])==source['sha256'],'source identity changed')
    require(sha(archive['path'])==archive['sha256'] and Path(archive['path']).stat().st_size==archive['bytes']
            and archive['bit_perfect'] is True,'archive changed/not restored')
    for index in archive['indexes']: require(sha(index['path'])==index['sha256'],'archive index changed')
    require(archive['stored_bytes']==archive['bytes']+sum(i['bytes'] for i in archive['indexes']),'stored archive/index size differs')
    if codec=='aceapex':
        with Path(archive['path']).open('rb') as stream: header=stream.read(28)
        require(header[:8]==b'ACEPX2\0\0' and struct.unpack_from('<I',header,8)[0]==2
                and struct.unpack_from('<I',header,20)[0]==case['g'],'only pinned interactive four-stream archives admitted')
    trace_path,trace=traces(case['corpus'],source)
    value=dict(schema='hw-region-1-request-v1',case_id=case['case_id'],codec=codec,corpus=case['corpus'],g=case['g'],
               effective_g=archive['effective_g'],request_bytes=16384,queries=1000,warmups=12,input=source,archive=archive,
               case_manifest=dict(path=case_path.relative_to(HERE).as_posix(),sha256=sha(case_path)),
               trace=dict(path=trace_path.relative_to(HERE).as_posix(),sha256=sha(trace_path)),trace_files=dict(warmups=trace['warmups'],requests=trace['requests']),
               setup_sha256=sha(HERE/'setup.json'),native_build_sha256=sha(HERE/'native/build.json'),
               calibration_sha256=sha(HERE/'CALIBRATION.md'),protocol_sha256=sha(HERE/'PROTOCOL.md'),
               instrument_sha256=sha(__file__),worker_sha256=sha(HERE/'worker.c'),
               timed_library=native['artifacts'][codec+'-timed'],counter_library=native['artifacts'][codec+'-count'])
    value['request_id']=case['case_id']+'-'+codec+'-'+digest(packed(value))[:16]
    return value


def validate_request(value):
    require(value['schema']=='hw-region-1-request-v1' and value['codec'] in CODECS,'invalid region request')
    original=dict(value); supplied=original.pop('request_id')
    require(supplied==value['case_id']+'-'+value['codec']+'-'+digest(packed(original))[:16],'request identity changed')
    native=native_receipt()
    require(value['setup_sha256']==sha(HERE/'setup.json') and value['native_build_sha256']==sha(HERE/'native/build.json')
            and value['instrument_sha256']==sha(__file__) and value['worker_sha256']==sha(HERE/'worker.c')
            and value['calibration_sha256']==sha(HERE/'CALIBRATION.md') and value['protocol_sha256']==sha(HERE/'PROTOCOL.md'),'request/source cohort changed')
    require(value['queries']==1000 and value['warmups']==12 and value['request_bytes']==16384,'request workload changed')
    for record in (value['input'],value['archive'],*value['archive']['indexes'],*value['trace_files'].values(),value['timed_library'],value['counter_library']):
        require(sha(record['path'])==record['sha256'],'request artifact changed')
    require(sha(HERE/value['case_manifest']['path'])==value['case_manifest']['sha256']
            and sha(HERE/value['trace']['path'])==value['trace']['sha256'],'request public case/trace changed')
    require(value['timed_library']==native['artifacts'][value['codec']+'-timed']
            and value['counter_library']==native['artifacts'][value['codec']+'-count'],'request selected another reader binary')
    return value


def private_stage(output,kind):
    output=Path(output).resolve(); require(output.is_relative_to(ROOT.resolve()) and not output.exists(),'output must be new and experiment-owned')
    stage=STATE/'observations'/digest(str(output).encode())/kind
    require(not stage.exists(),'unfinished native observation needs inspection; do not retime')
    stage.mkdir(parents=True)
    return output,stage


def run_native(args,stage):
    proc=subprocess.run(list(map(str,args)),stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=ROOT)
    immutable(stage/'native.stdout',proc.stdout); immutable(stage/'native.stderr',proc.stderr)
    if proc.returncode:
        sys.stderr.buffer.write(proc.stderr); sys.stderr.buffer.flush()
    proc.check_returncode()
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


def output_evidence(path,rows):
    raw=Path(path).read_bytes()
    require(len(raw)==16384*len(rows),'native returned-output capture length differs')
    for i,row in enumerate(rows):
        require(row['verified'] is True and row['requested_bytes']==16384,'native region was not verified')
        row['returned_sha256']=digest(raw[i*16384:(i+1)*16384])
    # Keep every stage's output path while deduplicating identical captures.
    canonical=STATE/'returned'/(digest(raw)+'.bin'); canonical.parent.mkdir(parents=True,exist_ok=True)
    if not canonical.exists():
        try: os.link(path,canonical)
        except FileExistsError: pass
    require(sha(canonical)==digest(raw),'content-addressed returned capture changed')
    if os.stat(path).st_ino!=os.stat(canonical).st_ino:
        Path(path).unlink(); os.link(canonical,path)
    return dict(path=str(path),bytes=len(raw),sha256=digest(raw),content_addressed_path=str(canonical))


def observe(value,mode,output,passes=1,offsets=None):
    validate_request(value)
    output,stage=private_stage(output,mode)
    warm=value['trace_files']['warmups']['path']; trace=value['trace_files']['requests']['path']
    if offsets is not None:
        require(mode=='probe' and 1<=len(offsets)<=5000 and all(type(o)is int and 0<=o<=value['input']['bytes']-16384 for o in offsets),'invalid fresh-handle probe offsets')
        warm=stage/'warmups.bin'; trace=stage/'requests.bin'
        immutable(warm,b''); immutable(trace,b''.join(struct.pack('<Q',o) for o in offsets))
    library=value['counter_library'] if mode in ('counter','probe') else value['timed_library']
    indexes=value['archive']['indexes']; sidecar=indexes[0]['path'] if indexes else ''
    require(value['codec']!='bgzip' or len(indexes)==1,'BGZF needs exactly one retained gzi')
    prefix=stage/'native'
    args=[NATIVE/'worker','region',mode,library['path'],value['archive']['path'],value['input']['path'],sidecar,warm,trace,prefix,str(passes)]
    rows=run_native(args,stage)
    n=len(offsets) if offsets is not None else 1000
    require(len(rows)==n*passes,'native sample count changed')
    expected=offsets if offsets is not None else load(HERE/value['trace']['path'])['offsets']
    for i,row in enumerate(rows):
        require((row['pass'],row['query'],row['offset'])==(i//n,i%n,expected[i%n]),'native request order/offset changed')
        if mode=='latency': require(type(row['elapsed_ns'])is int and row['elapsed_ns']>0,'invalid native interval')
        else: require(row['elapsed_ns'] is None,'untimed native pass read a timing clock')
    if mode=='counter' and value['codec']=='aceapex':
        require(all(row['oneshot_calls']==0 and row['stream_calls']==0 and row['zstd_calls']==row['dctx_calls'] for row in rows),
                'METHOD MISMATCH: ACE actual API mixture differs from standalone reused DCtx calibration')
    returned=output_evidence(Path(str(prefix)+'.regions.bin'),rows)
    result=dict(schema='hw-region-1-observation-v1',status='PASS',mode=mode,request_id=value['request_id'],
                request_sha256=digest(packed(value)),codec=value['codec'],case_id=value['case_id'],corpus=value['corpus'],g=value['g'],
                effective_g=value['effective_g'],passes=passes,queries_per_pass=n,warmups=0 if offsets is not None else 12,
                measurements_of_time=mode=='latency',clock_calls=2*len(rows) if mode=='latency' else 0,
                input_sha256=value['input']['sha256'],archive_sha256=value['archive']['sha256'],trace_sha256=value['trace']['sha256'],
                native_build_sha256=value['native_build_sha256'],instrument_sha256=value['instrument_sha256'],
                native_command=list(map(str,args)),native_stdout=dict(path=str(stage/'native.stdout'),sha256=sha(stage/'native.stdout')),
                native_stderr=dict(path=str(stage/'native.stderr'),sha256=sha(stage/'native.stderr')),returned=returned,rows=rows)
    if mode=='latency':
        result['quantiles']=[dict(pass_id=p,p50_ns=sorted(r['elapsed_ns'] for r in rows if r['pass']==p)[499],
                                 p99_ns=sorted(r['elapsed_ns'] for r in rows if r['pass']==p)[989]) for p in range(passes)]
    save(output,result); return result


def worker(value,output,passes=1,control_aa=False,method_check=None):
    require(os.environ.get('OVH_BENCH_LOCK_HELD')==LOCK and os.sched_getaffinity(0)=={0},'timing requires shared external lock and CPU0')
    if control_aa:
        require(passes==2 and value['case_id']=='chr1-g16384','AA is exactly two primary passes')
    else:
        require(passes==1,'production cell is exactly one pass')
        gate=load(method_check or HERE/'method-check.json')
        require(gate['status']=='PASS' and gate['instrument_sha256']==sha(__file__)
                and gate['native_build_sha256']==sha(HERE/'native/build.json')
                and gate['protocol_sha256']==sha(HERE/'PROTOCOL.md'),'all three method gates must pass before main timing')
    return observe(value,'latency',output,passes)


def counterpass(value,output):
    return observe(value,'counter',output)


def counter_probe(value,offsets,output):
    return observe(value,'probe',output,offsets=list(offsets))


def constants_library():
    native=native_receipt(); lib=C.CDLL(native['artifacts']['constants']['path'],mode=C.RTLD_LOCAL)
    for name,args,returns in (
        ('region_zstd_version_number',[],C.c_uint),('region_compress_bound',[C.c_size_t],C.c_size_t),
        ('region_compress',[C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t],C.c_size_t),('region_is_error',[C.c_size_t],C.c_uint)):
        fn=getattr(lib,name); fn.argtypes=args; fn.restype=returns
    require(lib.region_zstd_version_number()==10507,'standalone linked library must be zstd 1.5.7')
    return lib,native


def prepare_constant(frame):
    require(frame in SIZES and not os.environ.get('OVH_BENCH_LOCK_HELD'),'prepare a declared frame outside OVH lock')
    source=setup()['inputs']['chr1']; native=native_receipt()
    require(sha(source['path'])==source['sha256'],'constant parent input changed')
    folder=STATE/'constants'/str(frame); request_path=folder/'request.json'
    if request_path.exists():
        value=load(request_path)
        require(value['native_build_sha256']==sha(HERE/'native/build.json') and value['instrument_sha256']==sha(__file__)
                and value['parent_input_sha256']==source['sha256'],'constant preparation cohort changed')
        for key in ('plaintext','compressed'): require(sha(value[key]['path'])==value[key]['sha256'],'constant frame changed')
        save(HERE/'constants/requests'/(str(frame)+'.json'),value); return value
    require(not folder.exists(),'interrupted frame preparation; inspect instead of re-encoding')
    folder.mkdir(parents=True)
    with Path(source['path']).open('rb') as stream: raw=stream.read(frame)
    require(len(raw)==frame,'short constant plaintext')
    lib,_=constants_library(); src=C.create_string_buffer(raw,len(raw)); cap=lib.region_compress_bound(len(raw)); dst=C.create_string_buffer(cap)
    n=lib.region_compress(dst,cap,src,len(raw)); require(not lib.region_is_error(n) and 0<n<=cap,'constant frame compression failed')
    plaintext,compressed=folder/'plaintext.bin',folder/'frame.zst'
    immutable(plaintext,raw); immutable(compressed,dst.raw[:n])
    artifact=lambda p:dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
    value=dict(schema='hw-region-1-constant-request-v1',frame_bytes=frame,level=3,api='ZSTD_decompressDCtx',
               dctx_policy='one persistent DCtx per standalone pass; 12 warmups; 1000 individual frame decodes',
               parent_input_sha256=source['sha256'],plaintext=artifact(plaintext),compressed=artifact(compressed),
               library=native['artifacts']['constants'],native_build_sha256=sha(HERE/'native/build.json'),
               setup_sha256=sha(HERE/'setup.json'),instrument_sha256=sha(__file__),worker_sha256=sha(HERE/'worker.c'),
               calibration_sha256=sha(HERE/'CALIBRATION.md'),protocol_sha256=sha(HERE/'PROTOCOL.md'),linked_zstd_version=10507)
    save(request_path,value); save(HERE/'constants/requests'/(str(frame)+'.json'),value); return value


def constants(frame,output):
    require(frame in SIZES and os.environ.get('OVH_BENCH_LOCK_HELD')==LOCK and os.sched_getaffinity(0)=={0}, 'standalone timing requires one frame and OVH lock/CPU0')
    value=load(STATE/'constants'/str(frame)/'request.json')
    native_receipt()
    require(value['native_build_sha256']==sha(HERE/'native/build.json') and value['instrument_sha256']==sha(__file__)
            and value['protocol_sha256']==sha(HERE/'PROTOCOL.md'),'constant request cohort changed')
    for key in ('plaintext','compressed','library'): require(sha(value[key]['path'])==value[key]['sha256'],'constant artifact changed')
    output,stage=private_stage(output,'constants-'+str(frame)); prefix=stage/'native'
    args=[NATIVE/'worker','constants',value['library']['path'],value['plaintext']['path'],value['compressed']['path'],prefix]
    rows=run_native(args,stage)
    require(len(rows)==1000 and all(row['query']==i and row['verified'] is True and row['decoded_bytes']==frame
                                   and type(row['elapsed_ns'])is int and row['elapsed_ns']>0 for i,row in enumerate(rows)),'invalid standalone samples')
    decoded=Path(str(prefix)+'.decoded.bin')
    require(sha(decoded)==value['plaintext']['sha256'],'standalone captured plaintext differs')
    times=sorted(row['elapsed_ns'] for row in rows)
    result=dict(schema='hw-region-1-constant-observation-v1',status='PASS',frame_bytes=frame,request_sha256=digest(packed(value)),
                measurements_of_time=True,clock_calls=2000,warmups=12,queries=1000,api=value['api'],linked_zstd_version=10507,
                plaintext=value['plaintext'],compressed=value['compressed'],library=value['library'],
                native_build_sha256=value['native_build_sha256'],instrument_sha256=sha(__file__),protocol_sha256=value['protocol_sha256'],
                returned=dict(path=str(decoded),bytes=frame,sha256=sha(decoded)),native_command=list(map(str,args)),
                native_stdout=dict(path=str(stage/'native.stdout'),sha256=sha(stage/'native.stdout')),
                native_stderr=dict(path=str(stage/'native.stderr'),sha256=sha(stage/'native.stderr')),
                p50_ns=times[499],p99_ns=times[989],rows=rows)
    save(output,result); return result


def counter_known_answer():
    prepared=prepare_constant(4096)
    path=HERE/'controls/counter-known.json'
    identity=dict(instrument_sha256=sha(__file__),native_build_sha256=sha(HERE/'native/build.json'),constant_request_sha256=digest(packed(prepared)))
    if path.exists():
        old=load(path); require(old['identity']==identity and old['status']=='PASS','counter known-answer cohort changed'); return old
    record=native_receipt()['artifacts']['aceapex-count']; lib=C.CDLL(record['path'],mode=C.RTLD_LOCAL)
    lib.hc_count_reset.argtypes=[C.c_void_p]; lib.hc_count_reset.restype=None
    for name in ('hc_count_zstd_calls','hc_count_zstd_bytes','hc_count_dctx_calls','hc_count_oneshot_calls'):
        fn=getattr(lib,name); fn.argtypes=[C.c_void_p]; fn.restype=C.c_uint64
    lib.hc_counter_probe.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t,C.c_int]; lib.hc_counter_probe.restype=C.c_int64
    raw=Path(prepared['plaintext']['path']).read_bytes(); frame=Path(prepared['compressed']['path']).read_bytes(); rows=[]
    for api,label in ((1,'DCtx one frame'),(2,'one-shot one frame'),(0,'plain-copy API bypass')):
        src=raw if api==0 else frame; source=C.create_string_buffer(src,len(src)); out=C.create_string_buffer(len(raw))
        lib.hc_count_reset(None); n=lib.hc_counter_probe(source,len(src),out,len(raw),api)
        require(n==len(raw) and out.raw==raw,'counter known-answer native restoration failed')
        calls,byte_count=lib.hc_count_zstd_calls(None),lib.hc_count_zstd_bytes(None)
        require((calls,byte_count)==((0,0) if api==0 else (1,len(raw))),'counter known-answer actual call/output count differs')
        rows.append(dict(control=label,actual_zstd_calls=calls,actual_zstd_output_bytes=byte_count,
                         dctx_calls=lib.hc_count_dctx_calls(None),oneshot_calls=lib.hc_count_oneshot_calls(None),restored_sha256=digest(out.raw)))
    result=dict(schema='hw-region-1-counter-known-v1',status='PASS',identity=identity,clock_calls=0,measurements_of_time=False,rows=rows)
    save(path,result); return result


def native_error_controls(value):
    lib=C.CDLL(value['timed_library']['path'],mode=C.RTLD_LOCAL)
    for name,args,returns in (('hc_open',[C.c_void_p,C.c_size_t,C.c_char_p,C.c_uint64],C.c_void_p),
                              ('hc_region',[C.c_void_p,C.c_uint64,C.c_void_p,C.c_size_t],C.c_int64),('hc_close',[C.c_void_p],None)):
        fn=getattr(lib,name); fn.argtypes=args; fn.restype=returns
    lib.hc_version.argtypes=[]; lib.hc_version.restype=C.c_char_p
    versions=dict(reader_version=lib.hc_version().decode(),linked_zstd_version=None,linked_zstd_version_number=None)
    if value['codec'] in ('aceapex','zstd_seekable'):
        lib.region_zstd_version_number.argtypes=[]; lib.region_zstd_version_number.restype=C.c_uint
        lib.region_zstd_version_string.argtypes=[]; lib.region_zstd_version_string.restype=C.c_char_p
        versions.update(linked_zstd_version=lib.region_zstd_version_string().decode(),linked_zstd_version_number=lib.region_zstd_version_number())
        require(versions['linked_zstd_version_number']==10507 and versions['linked_zstd_version']=='1.5.7','actually linked reader zstd version differs')
    if value['codec']=='aceapex':
        header=Path(setup()['deps']['aceapex']['path'])/'c/aceapex_decode.h'
        matched=re.search(r'#define\s+ACEAPEX_DECODE_VERSION\s+"([^"]+)"',header.read_text())
        require(matched is not None,'C99 decoder header version marker missing')
        versions['literal_c99_header_version']=matched.group(1)
    raw=Path(value['archive']['path']).read_bytes(); archive=C.create_string_buffer(raw,len(raw)); dst=C.create_string_buffer(16384)
    indexes=value['archive']['indexes']; side=indexes[0]['path'].encode() if indexes else None
    ctx=lib.hc_open(archive,len(raw),side,(1<<64)-1); require(ctx,'known valid context rejected')
    try:
        for off,length in ((value['input']['bytes']+1,0),(value['input']['bytes'],1),((1<<64)-1,1)):
            require(lib.hc_region(ctx,off,dst,length)<0,'invalid range accepted')
    finally: lib.hc_close(ctx)
    changed=bytes([raw[0]^255])+raw[1:]; damaged=C.create_string_buffer(changed,len(changed)); ctx=lib.hc_open(damaged,len(changed),side,(1<<64)-1)
    if ctx:
        try: require(lib.hc_region(ctx,0,dst,16384)<0,'corrupt magic silently decoded')
        finally: lib.hc_close(ctx)
    return dict(invalid_ranges_rejected=3,corrupt_magic_rejected=True,versions=versions)


def untimed_selfcheck(value,output):
    require(not os.environ.get('OVH_BENCH_LOCK_HELD'),'correctness controls run outside benchmark lock')
    output=Path(output)
    if output.exists():
        old=load(output); validate_request(value)
        require(old['status']=='PASS' and old['request_sha256']==digest(packed(value))
                and old['instrument_sha256']==sha(__file__) and sha(old['returned']['path'])==old['returned']['sha256'], 'saved selfcheck changed')
        return old
    result=observe(value,'check',output.with_name(output.name+'.regions.json'))
    error_controls=native_error_controls(value)
    known=counter_known_answer() if value['codec']=='aceapex' else None
    result.update(schema='hw-region-1-selfcheck-v1',status='PASS',**error_controls,
                  counter_known_sha256=sha(HERE/'controls/counter-known.json') if known else None)
    save(output,result); return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('build','request','untimed-selfcheck','worker','counterpass','counter-known','constants'))
    parser.add_argument('--case'); parser.add_argument('--codec',choices=CODECS); parser.add_argument('--request',type=Path)
    parser.add_argument('--output',type=Path); parser.add_argument('--passes',type=int,default=1)
    parser.add_argument('--control-aa',action='store_true'); parser.add_argument('--method-check',type=Path)
    parser.add_argument('--frame',type=int,choices=SIZES); parser.add_argument('--prepare',action='store_true')
    args=parser.parse_args()
    if args.action=='build': result=build()
    elif args.action=='request':
        result=request(args.case,args.codec)
        if args.output: save(args.output,result)
    elif args.action=='constants':
        require(args.frame is not None,'constants requires one --frame')
        result=prepare_constant(args.frame) if args.prepare else constants(args.frame,args.output)
        if args.prepare and args.output: save(args.output,result)
    elif args.action=='counter-known': result=counter_known_answer()
    else:
        require(args.request is not None and args.output is not None,'observation requires --request and --output')
        value=load(args.request)
        if args.action=='untimed-selfcheck': result=untimed_selfcheck(value,args.output)
        elif args.action=='counterpass': result=counterpass(value,args.output)
        else: result=worker(value,args.output,args.passes,args.control_aa,args.method_check)
    print(json.dumps(dict(status=result.get('status','PASS'),schema=result['schema'],output=str(args.output) if args.output else None),sort_keys=True),flush=True)


if __name__=='__main__':
    main()
