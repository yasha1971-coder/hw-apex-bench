#!/usr/bin/env python3
"""FASTA-only .2bit operations, distinct from generic original-byte axes.

seq-reader-build prepares only the pinned reader and its one-line casefix.
seq-build retains case with the original Apache-2.0 writer. seq-fetch uses a
source-bound standalone or study DSO, never autobuilds and performs no timing.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/'evidence/hw-region-2'
CASEFIX=STUDY/'casefix'
REF='58e20daa898a6fc338eae82e5d2ef7108d4fc07f'
DEFAULT_BUILD=ROOT/'.work/twobit-sequence/build.json'
BEFORE=b"            if(seq[pos] != 'N') seq[pos] = tolower(seq[pos]);"
AFTER=b'            seq[pos] = tolower(seq[pos]);'
AXES=('ratio','encode','decode','region','amplification','c_g','batch','h_alpha','break_even')
REASON='FASTA sequence/base-coordinate domain; generic axes require exact original-file bytes and byte coordinates'


def require(ok,why):
    if not ok: raise ValueError(why)


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1<<20),b''):
            digest.update(chunk)
    return digest.hexdigest()


def load(path): return json.loads(Path(path).read_bytes())


def configuration():
    return dict(input_domain='fasta-sequence',coordinate_domain='base',interval='zero-based half-open',
                storeMasked=1,case_preserving=True,lib2bit_commit=REF,
                patch='softMask: lowercase every masked base, including N',
                patch_path='evidence/hw-region-2/lib2bit-casefix.patch',
                generic_byte_qualification=False,native_interface='coordinate ABI 1, not hc ABI 2',
                fetch_limit_bases=16384,writer_license='Apache-2.0',reader_license='MIT',
                known_limit='pinned lib2bit exact-end mmap reads may fail; no padding, clamping or EOF patch is applied')


def writer_module():
    path=STUDY/'writer.py'
    spec=importlib.util.spec_from_file_location('_twobit_original_writer',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


def immutable(path,raw):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists(): require(path.read_bytes()==raw,'existing artifact differs: '+str(path))
    else:
        with path.open('xb') as stream: stream.write(raw)


def seq_build(fasta,output):
    w=writer_module();w.self_test()
    sequence,fai,source=w.parse_fasta(fasta)
    data,table=w.encode_twobit(fai['name'],sequence)
    restored,parsed=w.decode_twobit(data,store_masked=True)
    require(restored==sequence and parsed['name']==fai['name'],'case-preserving structural roundtrip failed')
    folder=Path(output).resolve();archive=folder/'sequence.2bit'
    metadata=dict(schema='cabench-twobit-sequence-v1',configuration=configuration(),
                  adapter_source_sha256=sha(__file__),writer_source_sha256=sha(STUDY/'writer.py'),
                  source_fasta=source,sequence=dict(name=fai['name'],bytes=len(sequence),sha256=hashlib.sha256(sequence).hexdigest()),
                  archive=dict(path=str(archive),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()),
                  tables=table,structural_check='case-preserving sequence equality; not original FASTA byte restoration',
                  timings_collected=False)
    immutable(archive,data)
    immutable(folder/'metadata.json',(json.dumps(metadata,sort_keys=True,separators=(',',':'))+'\n').encode())
    return metadata


def artifact(path):
    path=Path(path).resolve()
    return dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path))


def verify_artifact(value):
    path=Path(value['path'])
    require(path.is_file() and path.stat().st_size==value['bytes'] and sha(path)==value['sha256'],'retained reader artifact changed: '+str(path))
    return path


def standalone_reader(build,receipt):
    require(build.get('status')=='PASS' and build.get('lib2bit_commit')==REF,'standalone reader pin/status differs')
    files={key:verify_artifact(value) for key,value in build['artifacts'].items()}
    old,new=files['original_source'].read_bytes(),files['casefix_source'].read_bytes()
    require(old.count(BEFORE)==1 and new==old.replace(BEFORE,AFTER),'standalone reader exceeds the one-line casefix')
    for name in ('native.c','coordinate.h'):
        require(build['native_source_sha256'][name]==sha(CASEFIX/name),'standalone coordinate source differs: '+name)
    require(files['native_source'].read_bytes()==(CASEFIX/'native.c').read_bytes()
            and files['coordinate_header'].read_bytes()==(CASEFIX/'coordinate.h').read_bytes(),'standalone copied ABI differs')
    require(build['source_sha256']['evidence/hw-region-2/lib2bit-casefix.patch']==sha(STUDY/'lib2bit-casefix.patch'),'standalone allowed patch pin differs')
    for command in build['commands']:
        require(command['returncode']==0,'standalone build command failed')
        verify_artifact(command['stdout']);verify_artifact(command['stderr'])
    commands={c['label']:c for c in build['commands']}
    require(Path(commands['source-head']['stdout']['path']).read_text().strip()==REF,'standalone source checkout pin differs')
    require(old==Path(commands['source-content']['stdout']['path']).read_bytes()
            and files['header'].read_bytes()==Path(commands['source-header']['stdout']['path']).read_bytes(),'standalone source differs from pinned Git blobs')
    require(not Path(commands['source-before']['stdout']['path']).read_bytes().strip()
            and not Path(commands['source-after']['stdout']['path']).read_bytes().strip(),'standalone source cleanliness log differs')
    require(build['source_clean_before'] is True and build['source_clean_after'] is True,'standalone dependency was not clean')
    return files['library'],receipt


def seq_reader_build(workdir,source_tree=None):
    """Build in owned state, reading a clean pin; never edit dependency sources."""
    import difflib
    import shutil
    import subprocess
    work=Path(workdir).resolve();receipt=work/'build.json'
    if receipt.exists():
        value=load(receipt);standalone_reader(value,receipt);return value
    require(not work.exists() or not any(work.iterdir()),'unfinished reader build; inspect it or select a new WORKDIR')
    source=Path(source_tree).resolve() if source_tree else work/'deps/lib2bit'
    require(not work.is_relative_to(source),'reader outputs must be outside the clean source tree')
    work.mkdir(parents=True,exist_ok=True);commands=[]
    def command(label,argv):
        folder=work/'commands'/label;folder.mkdir(parents=True)
        run=subprocess.run(list(map(str,argv)),stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=work)
        immutable(folder/'stdout',run.stdout);immutable(folder/'stderr',run.stderr)
        commands.append(dict(label=label,argv=list(map(str,argv)),cwd=str(work),returncode=run.returncode,stdout=artifact(folder/'stdout'),stderr=artifact(folder/'stderr')))
        require(run.returncode==0,'reader build command failed; inspect '+str(folder))
        return run.stdout
    if source_tree is None:
        command('clone',['git','clone','--no-checkout','https://github.com/dpryan79/lib2bit.git',source])
        command('checkout',['git','-C',source,'checkout','--detach',REF])
    require((source/'.git').exists(),'source-tree must be an actual clean Git checkout')
    require(command('source-head',['git','-C',source,'rev-parse','HEAD']).decode().strip()==REF,'reader source revision differs')
    require(not command('source-before',['git','-C',source,'status','--porcelain']).strip(),'reader source tree must be clean')
    old=(source/'2bit.c').read_bytes();header=(source/'2bit.h').read_bytes()
    require(old==command('source-content',['git','-C',source,'show',REF+':2bit.c'])
            and header==command('source-header',['git','-C',source,'show',REF+':2bit.h']),'working sources differ from pinned Git blobs')
    require(old.count(BEFORE)==1,'allowed softMask line is not unique in pinned source')
    patched=old.replace(BEFORE,AFTER)
    source_files={'original_source':work/'original-2bit.c','casefix_source':work/'casefix-2bit.c','header':work/'2bit.h','reader_license':work/'lib2bit-LICENSE',
                  'native_source':work/'coordinate-native.c','coordinate_header':work/'coordinate.h','patch':work/'casefix.patch'}
    immutable(source_files['original_source'],old);immutable(source_files['casefix_source'],patched);immutable(source_files['header'],header)
    license_path=next((source/name for name in ('LICENSE','LICENSE.txt') if (source/name).is_file()),None)
    require(license_path is not None,'pinned reader license missing')
    immutable(source_files['reader_license'],license_path.read_bytes())
    immutable(source_files['native_source'],(CASEFIX/'native.c').read_bytes());immutable(source_files['coordinate_header'],(CASEFIX/'coordinate.h').read_bytes())
    patch=''.join(difflib.unified_diff(old.decode().splitlines(keepends=True),patched.decode().splitlines(keepends=True),fromfile='a/2bit.c',tofile='b/2bit.c')).encode()
    immutable(source_files['patch'],patch)
    compiler_path=shutil.which('gcc');require(compiler_path is not None,'gcc is required for seq-reader-build')
    compiler_path=Path(compiler_path).resolve()
    compiler=dict(executable=artifact(compiler_path),version=command('compiler-version',[compiler_path,'--version']).decode().strip())
    library=work/'twobit-casefix.so'
    argv=[compiler_path,'-O3','-std=c11','-D_GNU_SOURCE','-fPIC','-fno-lto','-shared','-Wall','-Wextra','-Wl,-Bsymbolic',
          '-DCOORD_TWOBIT','-DCOORD_STORE_MASKED=1','-DCOORD_ORIGINAL=0','-I'+str(work),source_files['native_source'],source_files['casefix_source'],'-o',library]
    command('reader-compile',argv)
    require(not command('source-after',['git','-C',source,'status','--porcelain']).strip(),'reader build modified dependency source')
    require((source/'2bit.c').read_bytes()==old and (source/'2bit.h').read_bytes()==header,'reader source changed during build')
    value=dict(schema='cabench-twobit-reader-v1',status='PASS',lib2bit_commit=REF,source_tree=str(source),source_clean_before=True,source_clean_after=True,
               source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in (Path(__file__).resolve(),STUDY/'lib2bit-casefix.patch')},
               native_source_sha256={name:sha(CASEFIX/name) for name in ('native.c','coordinate.h')},
               casefix=dict(replacements=1,old_line=BEFORE.decode(),new_line=AFTER.decode()),compiler=compiler,commands=commands,
               artifacts={key:artifact(path) for key,path in source_files.items()}|{'library':artifact(library)},timings_collected=False)
    immutable(receipt,(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode())
    standalone_reader(value,receipt);return value


def coordinate_library(build_path):
    """Verify retained setup, the one allowed patch, sources and DSO hash."""
    build_path=Path(build_path).resolve()
    require(build_path.is_file(),'sequence reader is not built; run seq-reader-build WORKDIR, then pass --native-build WORKDIR/build.json')
    build=load(build_path)
    if build.get('schema')=='cabench-twobit-reader-v1':return standalone_reader(build,build_path)
    require(build.get('schema')=='hw-region-2-casefix-native-v1' and build.get('status')=='PASS','completed coordinate build receipt required')
    setup_path=CASEFIX/'setup.json';setup=load(setup_path)
    lib=setup['lib2bit'];require(lib['commit']==REF,'lib2bit source pin differs')
    original=lib['variants']['original'];fixed=lib['variants']['casefix']
    for variant in (original,fixed):
        require(sha(variant['source_path'])==variant['source_sha256'] and sha(variant['library_path'])==variant['library_sha256'],
                'retained lib2bit source/library differs')
    old=Path(original['source_path']).read_bytes();new=Path(fixed['source_path']).read_bytes()
    require(old.count(BEFORE)==1 and new==old.replace(BEFORE,AFTER),'casefix differs from the single allowed softMask line')
    identity=build.get('identity',build)
    require(build.get('setup_sha256',identity.get('setup_sha256'))==sha(setup_path),'native/setup binding differs')
    sources=build.get('source_sha256',identity.get('source_sha256',{}))
    require(isinstance(sources,dict),'native source bindings absent')
    for name in ('coordinate.h','native.c'):
        candidates=(name,'evidence/hw-region-2/casefix/'+name,str((CASEFIX/name).resolve()))
        require(any(sources.get(key)==sha(CASEFIX/name) for key in candidates),'coordinate source not bound: '+name)
    require(sources.get('evidence/hw-region-2/lib2bit-casefix.patch')==sha(STUDY/'lib2bit-casefix.patch'),'allowed patch not bound by native build')
    artifacts=build['artifacts'];dsos=artifacts.get('dsos',artifacts)
    row=dsos['twobit_casefix_mask1']
    require(sha(row['path'])==row['sha256'],'coordinate DSO differs')
    return Path(row['path']).resolve(),build_path


def seq_fetch(archive,chrom,start,length,output,build_path):
    require(type(start)is int and type(length)is int and start>=0 and 1<=length<=16384,'fetch needs 1..16384 bases at a nonnegative start')
    archive=Path(archive).resolve();meta=load(archive.parent/'metadata.json')
    require(meta['schema']=='cabench-twobit-sequence-v1' and meta['configuration']==configuration(),'sequence metadata/domain differs')
    require(archive.stat().st_size==meta['archive']['bytes'] and sha(archive)==meta['archive']['sha256'],'archive differs from structural proof')
    require(chrom==meta['sequence']['name'] and length<=meta['sequence']['bytes']-start,'sequence coordinates outside chromosome')
    library,receipt=coordinate_library(build_path)
    import ctypes as C
    class Config(C.Structure):
        _fields_=[('archive_path',C.c_char_p),('archive_data',C.c_void_p),('archive_bytes',C.c_size_t),
                  ('fai_path',C.c_char_p),('gzi_path',C.c_char_p),('chrom',C.c_char_p),
                  ('sequence_bases',C.c_uint64),('reference_fasta_bytes',C.c_uint64),('max_query_bases',C.c_size_t)]
    lib=C.CDLL(str(library),mode=C.RTLD_LOCAL)
    for name,args,result in (('coordinate_abi',[],C.c_uint),('coordinate_semantics',[],C.c_uint),('coordinate_uses_memory_archive',[],C.c_uint),
                             ('coordinate_open',[C.POINTER(Config)],C.c_void_p),('coordinate_read',[C.c_void_p,C.c_uint64,C.c_size_t],C.c_void_p),
                             ('coordinate_close',[C.c_void_p],None)):
        fn=getattr(lib,name);fn.argtypes=args;fn.restype=result
    require(lib.coordinate_abi()==1 and lib.coordinate_semantics()==0 and lib.coordinate_uses_memory_archive()==0,'library is not the equivalent masked coordinate row')
    cfg=Config(str(archive).encode(),None,archive.stat().st_size,b'-',b'-',chrom.encode(),meta['sequence']['bytes'],meta['source_fasta']['bytes'],16384)
    context=lib.coordinate_open(C.byref(cfg));require(context,'coordinate open failed')
    pointer=None
    try:
        pointer=lib.coordinate_read(context,start,length);require(pointer,'coordinate read failed (no EOF workaround or clamping is applied)')
        raw=C.string_at(pointer,length);require(C.string_at(pointer+length,1)==b'\0','coordinate string length differs')
    finally:
        if pointer:
            # Coordinate API explicitly returns the process C allocator's malloc.
            runtime=C.CDLL(None);runtime.free.argtypes=[C.c_void_p];runtime.free.restype=None;runtime.free(pointer)
        lib.coordinate_close(context)
    immutable(output,raw)
    return dict(status='PASS',input_domain='fasta-sequence',coordinate_domain='base',chrom=chrom,start0=start,length=length,
                output_sha256=hashlib.sha256(raw).hexdigest(),native_build_sha256=sha(receipt),timings_collected=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    for name in ('configuration','unavailable','inputs'):sub.add_parser(name)
    rb=sub.add_parser('seq-reader-build');rb.add_argument('workdir',type=Path,nargs='?',default=DEFAULT_BUILD.parent);rb.add_argument('--source-tree',type=Path)
    b=sub.add_parser('seq-build');b.add_argument('fasta',type=Path);b.add_argument('output_directory',type=Path)
    f=sub.add_parser('seq-fetch');f.add_argument('archive',type=Path);f.add_argument('chrom');f.add_argument('start',type=int);f.add_argument('length',type=int);f.add_argument('output',type=Path)
    f.add_argument('--native-build',type=Path,default=DEFAULT_BUILD)
    a=parser.parse_args()
    if a.action=='configuration':result=configuration()
    elif a.action=='unavailable':result=dict.fromkeys(AXES,REASON)
    elif a.action=='inputs':result=[str(Path(__file__).resolve()),str(STUDY/'writer.py'),str(STUDY/'lib2bit-casefix.patch'),str(CASEFIX/'coordinate.h'),str(CASEFIX/'native.c')]
    elif a.action=='seq-reader-build':result=seq_reader_build(a.workdir,a.source_tree)
    elif a.action=='seq-build':result=seq_build(a.fasta,a.output_directory)
    else:result=seq_fetch(a.archive,a.chrom,a.start,a.length,a.output,a.native_build)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError) as error:
        print('STOP: '+str(error),file=sys.stderr);raise SystemExit(2)
