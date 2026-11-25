"""Untimed, checkpointed writer investigation; timing is a separate optional stage."""
import argparse
import csv
import ctypes
import difflib
import gzip
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from seekable import parse_archive, parse_header, rewrite_table

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = Path('/home/ubuntu/hw-apex-bench-hw-gift-1b')
STATE = ROOT / '.work/hw-gift-1c'
ZSTD = OLD / '.work/hw-gift-1b/zstd'
INPUTS = OLD / '.work/inputs'
CAL = '65baf466eb399f815afff9235e20e94ea7780421'
PIN = 'f8745da6ff1ad1e7bab384bd1f9d742439278e99'
CASES = [('enwik8-L3',65536),('enwik8-L3',131072),('enwik8-L3',262144),
         ('enwik8-L3',524288),('enwik8-L19',65536),('silesia-L3',65536),
         ('silesia-L3',262144),('silesia-L19',65536)]
BASE = ROOT / 'evidence/hw-gift-1b'


def check(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    return sha(Path(path).read_bytes())


def packed(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()


def save(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    data=packed(value)
    pending=path.with_name(path.name+'.writing')
    with pending.open('wb') as out:
        out.write(data);out.flush();os.fsync(out.fileno())
    pending.replace(path)


def git(*args, repo=ROOT):
    return subprocess.check_output(['git','-C',str(repo),*args])


def command(args, *, cwd=None):
    args=[str(x) for x in args]
    logs=STATE/'commands';logs.mkdir(parents=True,exist_ok=True)
    prefix=logs/f'{len(list(logs.glob("*.json")))+1:04}'
    result=subprocess.run(args,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    prefix.with_suffix('.stdout').write_bytes(result.stdout)
    prefix.with_suffix('.stderr').write_bytes(result.stderr)
    save(prefix.with_suffix('.json'),dict(command=args,cwd=str(cwd) if cwd else None,returncode=result.returncode,
         stdout_sha256=sha(result.stdout),stderr_sha256=sha(result.stderr)))
    result.check_returncode()
    return result.stdout


def preflight():
    check(sys.platform=='linux' and platform.node()=='ace-core','ace-core Linux required')
    check(git('branch','--show-current').decode().strip()=='hw-gift-1c','wrong branch')
    check((HERE/'CALIBRATION.md').read_bytes()==git('show',CAL+':evidence/hw-gift-1c/CALIBRATION.md'),'protocol changed')
    subprocess.run(['git','-C',str(ROOT),'merge-base','--is-ancestor',CAL,'HEAD'],check=True)
    tracked=[str(p.relative_to(ROOT)) for p in HERE.iterdir() if p.suffix in ('.py','.c') or p.name in ('CALIBRATION.md','SOURCE_PATHS.md','.gitattributes')]
    check(not git('status','--porcelain','--',*tracked).strip(),'uncommitted instrument source')
    check(git('rev-parse','HEAD',repo=ZSTD).decode().strip()==PIN,'wrong zstd source')
    check(not git('status','--porcelain',repo=ZSTD).strip(),'original zstd source is dirty')
    import pyzstd
    check(pyzstd.__version__=='0.20.0' and str(pyzstd.zstd_version)=='1.5.7','wrong pyzstd/runtime')
    check(importlib.metadata.version('backports.zstd')=='1.8.0','wrong compression backend')
    install=json.loads((OLD/'.work/hw-gift-1b/install-receipt.json').read_bytes())
    for relative,digest in install['installed_files_sha256'].items():
        check(file_sha(Path(install['installed_files_base'])/relative)==digest,'installed wheel payload changed: '+relative)
    STATE.mkdir(parents=True,exist_ok=True)
    return pyzstd


def compile_probe():
    target=STATE/'frame_probe'
    identity=dict(source_sha256=file_sha(HERE/'frame_probe.c'),static_library_sha256=file_sha(ZSTD/'lib/libzstd.a'))
    receipt=STATE/'frame_probe-build.json'
    if receipt.exists():
        old=json.loads(receipt.read_bytes())
        check(all(old[k]==v for k,v in identity.items()) and file_sha(target)==old['binary_sha256'],'probe build changed')
        return target
    check(not target.exists(),'unrecorded probe binary')
    args=['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(ZSTD/'lib'),str(HERE/'frame_probe.c'),str(ZSTD/'lib/libzstd.a'),'-pthread','-o',str(target)]
    command(args)
    save(receipt,dict(identity,command=args,binary_sha256=file_sha(target)))
    return target


def source_info(chunk):
    src='enwik8' if chunk.startswith('enwik8-') else 'silesia.tar'
    level=int(chunk.rsplit('L',1)[1]);path=INPUTS/src
    old=json.loads((BASE/chunk/'run.json').read_bytes())
    check(path.stat().st_size==old['input_bytes'] and file_sha(path)==old['input_sha256'],'input identity mismatch')
    return path,level


def probe(name, *, level=3,hint=0,chunk=131072,finish='empty'):
    binary=compile_probe();folder=HERE/'controls';folder.mkdir(exist_ok=True)
    source=STATE/'slice-0-262144.bin'
    original=(INPUTS/'enwik8').open('rb').read(262144)
    if source.exists():check(source.read_bytes()==original,'minimal input changed')
    else:source.write_bytes(original)
    out=folder/(name+'.zst');receipt=folder/(name+'.json')
    request=dict(input_offset=0,input_bytes=len(original),input_sha256=sha(original),level=level,hint=hint,chunk=chunk,finish=finish,binary_sha256=file_sha(binary))
    if receipt.exists():
        old=json.loads(receipt.read_bytes());check(old['request']==request and file_sha(out)==old['sha256'],'saved probe changed')
        return old
    check(not out.exists(),'incomplete/unrecorded probe output; inspect rather than rerun')
    args=[str(binary),str(source),str(out),str(level),str(hint),str(chunk),finish]
    result=json.loads(command(args))
    header=parse_header(out.read_bytes())
    check(header==result['header'],'independent header decoders disagree')
    value=dict(request=request,command=args,result=result,sha256=file_sha(out),path=str(out.relative_to(HERE)))
    save(receipt,value)
    return value


def controls():
    preflight();compile_probe()
    a=probe('positive-a');b=probe('positive-b');negative=probe('negative-level4',level=4)
    known=probe('known-fcs',finish='one_end',chunk=262144)
    aa=(HERE/a['path']).read_bytes();bb=(HERE/b['path']).read_bytes();nn=(HERE/negative['path']).read_bytes()
    check(aa==bb,'positive control failed')
    difference=next((i for i,(x,y) in enumerate(zip(aa,nn)) if x!=y),min(len(aa),len(nn)) if len(aa)!=len(nn) else None)
    check(aa!=nn and difference is not None,'negative control failed to detect different level')
    check(known['result']['header']['content_size']==262144,'known-FCS control failed')
    check(all(v['result']['corrupted_magic_error'] for v in (a,b,negative,known)),'corrupted frame did not raise')
    env=dict(protocol_commit=CAL,protocol_sha256=file_sha(HERE/'CALIBRATION.md'),code_commit=git('rev-parse','HEAD').decode().strip(),
             source_sha256={p.name:file_sha(p) for p in HERE.iterdir() if p.suffix in ('.py','.c')},
             zstd_commit=PIN,zstd_source_clean=True,python=platform.python_version(),host=platform.node(),kernel=platform.release(),
             cpu=next(line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),
             correctness_affinity=sorted(os.sched_getaffinity(0)),compiler=command(['cc','--version']).decode().splitlines()[0],
             library_sha256=file_sha(ZSTD/'lib/libzstd.a'),native_reader_sha256=file_sha(OLD/'.work/hw-gift-1b/c-state/libgift.so'),
             original_encoder_sha256=file_sha(ZSTD/'contrib/seekable_format/examples/seekable_compression'),
             pyzstd_version='0.20.0',backports_zstd_version='1.8.0',linked_zstd='1.5.7',measurements_of_time=False)
    save(HERE/'environment.json',env)
    save(HERE/'method-check.json',dict(status='PASS',positive_identical=True,negative_distinguished=True,
         negative_first_difference=difference,known_fcs=262144,corrupt_magic_rejected=True,
         outputs=[a,b,negative,known],environment_sha256=file_sha(HERE/'environment.json')))
    print('METHOD_CONTROLS_PASS',flush=True)


def require_controls():
    value=json.loads((HERE/'method-check.json').read_bytes())
    check(value['status']=='PASS' and value['environment_sha256']==file_sha(HERE/'environment.json'),'method controls missing/changed')
    env=json.loads((HERE/'environment.json').read_bytes())
    for name,digest in env['source_sha256'].items():
        check(file_sha(HERE/name)==digest,'instrument changed after controls; new method check required: '+name)
    for path,key in [(ZSTD/'lib/libzstd.a','library_sha256'),
                     (OLD/'.work/hw-gift-1b/c-state/libgift.so','native_reader_sha256'),
                     (ZSTD/'contrib/seekable_format/examples/seekable_compression','original_encoder_sha256')]:
        check(file_sha(path)==env[key],'compiled dependency changed after method controls')
    for r in value['outputs']:check(file_sha(HERE/r['path'])==r['sha256'],'method control bytes changed')


def identity(chunk,g,kind):
    src,level=source_info(chunk)
    return dict(chunk=chunk,g=g,kind=kind,level=level,input_bytes=src.stat().st_size,input_sha256=file_sha(src))


def check_old_identity(path,chunk,g,kind):
    entries=json.loads((BASE/('c-baseline/'+chunk if kind=='original' else chunk)/'archives.json').read_bytes())
    old=next((r for r in entries if r['g']==g),None)
    if old is not None:
        check(path.stat().st_size==old['bytes'] and file_sha(path)==old['sha256'],'archive does not match saved HW-GIFT-1b: '+kind+' '+chunk+' '+str(g))
    return old is not None


def original_encoder():
    binary=ZSTD/'contrib/seekable_format/examples/seekable_compression'
    old=json.loads((BASE/'c-baseline/enwik8-L3/run.json').read_bytes())
    check(file_sha(binary)==old['host']['encoder_sha256'],'original encoder differs from HW-GIFT-1b')
    return binary


def patched_encoder():
    proof=json.loads((HERE/'minimal-proof.json').read_bytes());check(proof['status']=='PASS','minimal frame proof must pass before patch')
    source=ZSTD/'contrib/seekable_format/zstdseek_compress.c'
    original=source.read_bytes();before=b'ZSTD_c_srcSizeHint, (int)zcs->maxFrameSize'
    check(original.count(before)==1,'expected one-line srcSizeHint call not found')
    modified=original.replace(before,b'ZSTD_c_srcSizeHint, 0')
    patch=''.join(difflib.unified_diff(original.decode().splitlines(True),modified.decode().splitlines(True),
                  fromfile='original/contrib/seekable_format/zstdseek_compress.c',tofile='patched/contrib/seekable_format/zstdseek_compress.c',n=0))
    (HERE/'zstdseek_compress.patch').write_text(patch,encoding='utf-8',newline='')
    copy=STATE/'patched';copy.mkdir(exist_ok=True)
    target=copy/'zstdseek_compress.c'
    if target.exists():check(target.read_bytes()==modified,'patched source changed')
    else:target.write_bytes(modified)
    binary=copy/'seekable_compression';receipt=copy/'build.json'
    if receipt.exists():
        saved=json.loads(receipt.read_bytes());check(saved['source_sha256']==sha(modified) and saved['binary_sha256']==file_sha(binary),'patched build changed')
        return binary
    check(not binary.exists(),'unrecorded patched binary')
    args=['cc','-O3','-g','-DXXH_NAMESPACE=ZSTD_','-I'+str(ZSTD/'contrib/seekable_format'),'-I'+str(ZSTD/'lib'),'-I'+str(ZSTD/'lib/common'),
          str(ZSTD/'contrib/seekable_format/examples/seekable_compression.c'),str(target),
          str(ZSTD/'contrib/seekable_format/zstdseek_decompress.c'),str(ZSTD/'lib/libzstd.a'),'-o',str(binary)]
    command(args)
    save(receipt,dict(command=args,source_sha256=sha(modified),original_source_sha256=sha(original),binary_sha256=file_sha(binary)))
    return binary


def archive(chunk,g,kind):
    source,level=source_info(chunk)
    if kind=='pyzstd':
        existing=OLD/'.work/hw-gift-1b/archives'/chunk/f'archive-{g}.zst'
        if existing.exists():
            check_old_identity(existing,chunk,g,'pyzstd');return existing
    folder=STATE/'archives'/f'{chunk}-{g}'/kind;folder.mkdir(parents=True,exist_ok=True)
    output=folder/(source.name+'.zst');receipt=folder/'complete.json'
    request=identity(chunk,g,kind)
    if receipt.exists():
        old=json.loads(receipt.read_bytes());check(old['request']==request and output.is_file() and file_sha(output)==old['sha256'],'saved archive changed')
        return output
    check(not output.exists(),'unrecorded/partial archive; stop for inspection')
    if kind=='pyzstd':
        import pyzstd
        with source.open('rb') as raw,pyzstd.SeekableZstdFile(output,'wb',level_or_option=level,max_frame_content_size=g) as writer:
            shutil.copyfileobj(raw,writer,length=1<<20)
        args=['pyzstd.SeekableZstdFile',str(source),str(g),str(level),'copyfileobj:1048576']
    else:
        binary=original_encoder() if kind=='original' else patched_encoder()
        link=folder/source.name
        if link.exists():check(link.resolve()==source.resolve(),'input symlink changed')
        else:link.symlink_to(source)
        args=[str(binary),source.name,str(g),str(level)];command(args,cwd=folder)
    old_match=check_old_identity(output,chunk,g,kind) if kind in ('original','pyzstd') else None
    save(receipt,dict(request=request,command=args,path=str(output),bytes=output.stat().st_size,sha256=file_sha(output),matches_saved_1b=old_match))
    return output


def native():
    dll=ctypes.CDLL(str(OLD/'.work/hw-gift-1b/c-state/libgift.so'))
    dll.ZSTD_versionNumber.restype=ctypes.c_uint;check(dll.ZSTD_versionNumber()==10507,'wrong native decoder')
    dll.ZSTD_decompress.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t];dll.ZSTD_decompress.restype=ctypes.c_size_t
    dll.ZSTD_isError.argtypes=[ctypes.c_size_t];dll.ZSTD_isError.restype=ctypes.c_uint
    dll.ZSTD_XXH64.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulonglong];dll.ZSTD_XXH64.restype=ctypes.c_ulonglong
    return dll


def verify_archive(data,source,parsed):
    dll=native();offset=0;digest=hashlib.sha256();checksums=[]
    for f in parsed['frames']:
        frame=data[f['offset']:f['offset']+f['compressed_bytes']]
        encoded=ctypes.create_string_buffer(frame);out=ctypes.create_string_buffer(f['decompressed_bytes'])
        size=dll.ZSTD_decompress(out,len(out),encoded,len(frame))
        check(not dll.ZSTD_isError(size) and size==len(out),'native frame decode failed')
        value=out.raw;check(value==source[offset:offset+size],'restored bytes differ from source')
        checksum=int(dll.ZSTD_XXH64(out,size,0)&0xffffffff);checksums.append(checksum)
        if parsed['checksum_flag']:check(checksum==f['checksum'],'seek-table XXH64 checksum mismatch')
        digest.update(value);offset+=size
    check(offset==len(source) and digest.hexdigest()==sha(source),'complete archive restoration failed')
    return dict(bit_perfect=True,decompressed_bytes=offset,decompressed_sha256=digest.hexdigest(),
                seek_checksums_verified=bool(parsed['checksum_flag']),checksums=checksums)


def inspect():
    preflight();require_controls()
    chunk,g='enwik8-L3',262144
    cp=archive(chunk,g,'original');pp=archive(chunk,g,'pyzstd')
    c,p=cp.read_bytes(),pp.read_bytes();cc,py=parse_archive(c),parse_archive(p)
    source,_=source_info(chunk);raw=source.read_bytes()
    vc,vp=verify_archive(c,raw,cc),verify_archive(p,raw,py)
    check(len(cc['frames'])==len(py['frames']),'different frame geometry')
    rows=[]
    for a,b in zip(cc['frames'],py['frames']):
        check(a['decompressed_bytes']==b['decompressed_bytes'],'frame boundaries differ')
        rows.append(dict(index=a['index'],decompressed_bytes=a['decompressed_bytes'],full=a['decompressed_bytes']==g,
                         original_bytes=a['compressed_bytes'],pyzstd_bytes=b['compressed_bytes'],
                         difference_bytes=b['compressed_bytes']-a['compressed_bytes'],
                         original_sha256=a['sha256'],pyzstd_sha256=b['sha256'],identical=a['sha256']==b['sha256']))
    with (HERE/'frame-comparison.csv').open('w',encoding='utf-8',newline='') as out:
        writer=csv.DictWriter(out,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    full=[r for r in rows if r['full']]
    study=dict(chunk=chunk,g=g,original_archive=dict(path=str(cp),bytes=len(c),sha256=sha(c),recreated_matches_1b=True),
               pyzstd_archive=dict(path=str(pp),bytes=len(p),sha256=sha(p),matches_1b=True),
               original_table={k:v for k,v in cc.items() if k!='frames'},pyzstd_table={k:v for k,v in py.items() if k!='frames'},
               original_header=cc['frames'][0]['header'],pyzstd_header=py['frames'][0]['header'],
               frames=len(rows),full_frames=len(full),full_frames_with_size_gap=sum(r['difference_bytes']!=0 for r in full),
               full_frames_with_byte_gap=sum(not r['identical'] for r in full),tail=rows[-1],
               data_bytes_difference=py['data_bytes']-cc['data_bytes'],archive_bytes_difference=len(p)-len(c),
               original_roundtrip=vc,pyzstd_roundtrip=vp)
    save(HERE/'case-study.json',study)
    cprobe=probe('minimal-contrib',hint=g);pprobe=probe('minimal-pyzstd',hint=0,chunk=g)
    check(cprobe['sha256']==cc['frames'][0]['sha256'],'minimal C output does not reproduce original archive frame 0')
    check(pprobe['sha256']==py['frames'][0]['sha256'],'minimal C output does not reproduce pyzstd archive frame 0')
    cwhole=probe('h2-contrib-whole-continue',hint=g,chunk=g)
    psplit=probe('h2-pyzstd-split-continue',hint=0,chunk=131072)
    h2_same=cwhole['sha256']==cprobe['sha256'] and psplit['sha256']==pprobe['sha256']
    save(HERE/'minimal-proof.json',dict(status='PASS',original_frame_sha256=cprobe['sha256'],pyzstd_frame_sha256=pprobe['sha256'],
          original=cprobe,pyzstd=pprobe,h2_original_whole=cwhole,h2_pyzstd_split=psplit,
          h2_chunking_changes_nothing=h2_same,controls_sha256=file_sha(HERE/'method-check.json'),case_study_sha256=file_sha(HERE/'case-study.json')))
    print('EXACT_MINIMAL_FRAME_PROOF_PASS; H2_UNCHANGED',h2_same,flush=True)


def run_case(key):
    preflight();require_controls();check(json.loads((HERE/'minimal-proof.json').read_bytes())['status']=='PASS','minimal proof missing')
    chunk,g=CASES[key]
    sources={kind:archive(chunk,g,kind) for kind in ('original','pyzstd','patched')}
    data={k:p.read_bytes() for k,p in sources.items()};parsed={k:parse_archive(v) for k,v in data.items()}
    source,_=source_info(chunk);raw=source.read_bytes()
    restored={k:verify_archive(data[k],raw,parsed[k]) for k in sources}
    records=[]
    for frames in zip(*(parsed[k]['frames'] for k in sources)):
        variants=dict(zip(sources,frames));a=variants['pyzstd'];b=variants['patched']
        check(all(f['decompressed_bytes']==a['decompressed_bytes'] for f in frames),'matrix frame boundaries differ')
        check(a['sha256']==b['sha256'],'patched data frame differs from pyzstd')
        records.append(dict(index=a['index'],decompressed_bytes=a['decompressed_bytes'],full=a['decompressed_bytes']==g,variants=variants))
    check(len(records)==parsed['pyzstd']['frame_count']==parsed['original']['frame_count']==parsed['patched']['frame_count'],'matrix frame count differs')
    normalized=rewrite_table(data['patched'],False)
    rebuilt=rewrite_table(data['pyzstd'],True,restored['patched']['checksums'])
    check(normalized==data['pyzstd'] and rebuilt==data['patched'],'seek-table byte-by-byte remainder is unexplained')
    count=len(records);check(len(data['patched'])-len(data['pyzstd'])==4*count,'remaining size delta is not exactly 4 bytes per frame')
    folder=HERE/'cases';folder.mkdir(exist_ok=True);label=f'{chunk}-{g}'
    raw_records=b''.join(packed(r) for r in records)
    path=folder/(label+'.frames.jsonl.gz');path.write_bytes(gzip.compress(raw_records,mtime=0))
    value=dict(case_index=key,chunk=chunk,g=g,frame_count=count,frame_records_file=path.name,frame_records_sha256=file_sha(path),
          environment_sha256=file_sha(HERE/'environment.json'),method_check_sha256=file_sha(HERE/'method-check.json'),
          minimal_proof_sha256=file_sha(HERE/'minimal-proof.json'),execution_commit=git('rev-parse','HEAD').decode().strip(),
          input_bytes=len(raw),input_sha256=sha(raw),archives={k:dict(path=str(sources[k]),bytes=len(v),sha256=sha(v),
             header=parsed[k]['frames'][0]['header'],seek_table_bytes=parsed[k]['seek_table_bytes'],checksum_flag=parsed[k]['checksum_flag'],
             table_header_hex=parsed[k]['table_header_hex'],footer_hex=parsed[k]['footer_hex'],data_bytes=parsed[k]['data_bytes'],
             restored_sha256=restored[k]['decompressed_sha256'],seek_checksums_verified=restored[k]['seek_checksums_verified']) for k,v in data.items()},
          all_patched_frames_identical_to_pyzstd=True,normalized_patched_equals_pyzstd=True,rebuilt_pyzstd_equals_patched=True,
          residual_bytes=4*count,patched_size_difference=len(data['patched'])-len(data['original']),
          original_source_clean=not bool(git('status','--porcelain',repo=ZSTD).strip()))
    save(folder/(label+'.json'),value)
    print('CASE_PASS',label,'original',len(data['original']),'patched',len(data['patched']),'pyzstd',len(data['pyzstd']),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('controls','inspect','case'));parser.add_argument('index',type=int,nargs='?')
    args=parser.parse_args()
    if args.action=='controls':controls()
    elif args.action=='inspect':inspect()
    else:
        check(args.index in range(len(CASES)),'case index 0..7 required');run_case(args.index)


if __name__=='__main__':main()
