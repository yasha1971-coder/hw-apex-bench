"""Owned HW-REGION-1 dependencies, frozen corpora and untimed archives.

Import does nothing. All builds/encodings run outside OVH-BENCH on CPU15.
Old checkouts, foreign projects and saved evidence are read only.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = ROOT/'.work/hw-region-1'
PINS = {'aceapex': ('https://github.com/yasha1971-coder/aceapex.git', 'ce6b6740c7aae8a01720d615ae024c181b7d52b6'),
        'zstd': ('https://github.com/meta/zstd.git', 'f8745da6ff1ad1e7bab384bd1f9d742439278e99'),
        'htslib': ('https://github.com/samtools/htslib.git', '4b705e4fada8ee2b6b15746f725ee8ac51631803'),
        'libdeflate': ('https://github.com/ebiggers/libdeflate.git', 'dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f')}
ACE_TAG = '8fd46ca8c0c907cf352f15fb6de062d5531e6489'
MANIFEST = ROOT/'evidence/t2t-regions-20260916/manifest.json'
MANIFEST_SHA = 'c5bc7014ecd0d6c7855e7ad1b01afbd20b8a7f2e55c93c8e78098fa4c049a763'
BUNDLE_SHA = '78f354a13f70e64ac6790af27e2befa98ac132d582a238a3e804201c24ca9808'
BUNDLE_BYTES = 53075428
SOURCES = {'chr1': ('/home/ubuntu/ACE_TRINITY_EVO/LAB/CIVIL5/src_fasta/chr1.fa', 253935557,
                    '04ee6db2e94ccc4daddc168453189d8c17a01454ba67ac0443a73a0401408ee0'),
           'enwik8': ('/home/ubuntu/hw-apex-bench-hw-gift-1b/.work/inputs/enwik8', 100000000,
                      '2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8'),
           'silesia': ('/home/ubuntu/hw-apex-bench-hw-gift-1b/.work/inputs/silesia.tar', 211947520,
                       'a667bac80089b3d04d5496772149e632f0758974b0579d743cd8d6e5e0d63eb2')}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path, algorithm='sha256'):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode()


def load(path):
    return json.loads(Path(path).read_bytes())


def immutable(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == data, 'retained bytes changed: '+str(path))
    else:
        with path.open('xb') as stream:
            stream.write(data)


def git(*args, repo=ROOT):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def provenance():
    require(os.name == 'posix' and not os.environ.get('OVH_BENCH_LOCK_HELD'), 'setup runs on Linux outside benchmark lock')
    os.sched_setaffinity(0, {15})
    require(os.sched_getaffinity(0) == {15}, 'setup requires CPU15')
    require(git('branch', '--show-current').decode().strip() == 'hw-region-1', 'wrong branch')
    first = git('rev-parse', '8108834^{commit}').decode().strip()
    cal = 'evidence/hw-region-1/CALIBRATION.md'
    require(git('show', first+':'+cal) == (HERE/'CALIBRATION.md').read_bytes(), 'original preregistration changed')
    files = [Path(__file__), HERE/'CALIBRATION.md', HERE/'PROTOCOL.md',
             ROOT/'codecs/aceapex.sh', ROOT/'codecs/aceapex_v220.sh', ROOT/'review/matched_g/bgzf_encode_g.c']
    for path in files:
        name = path.relative_to(ROOT).as_posix()
        git('ls-files', '--error-unmatch', '--', name)
        require(not git('status', '--porcelain', '--', name).strip(), 'uncommitted setup input: '+name)
    return dict(calibration_commit=first, source_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in files})


def environment(extra=None):
    blocked = {'ACEAPEX_BS','LIT_CHUNK','FSE_CHUNK','MIN_MATCH','AX_PROFILE','AX_TOK','AX_LIT','AX_ENC',
               'LD_PRELOAD','CFLAGS','CXXFLAGS','CPPFLAGS','LDFLAGS','CC','CXX','MAKEFLAGS','ZSTD_CLEVEL','ZSTD_NBTHREADS','ZSTD_SRC'}
    value = {key: item for key, item in os.environ.items() if key not in blocked
             and not key.startswith(('ACEAPEX_','AX_','LIT_','FSE_'))}
    value.update(extra or {})
    return value


def command(label, argv, *, cwd=None, extra=None, stdout_file=None):
    """Resume only completed commands. ERROR/STARTED/orphan logs stop for review."""
    folder = STATE/'commands'/label
    identity = dict(argv=list(map(str, argv)), cwd=str(cwd or ROOT), environment=extra or {},
                    stdout_file=str(stdout_file) if stdout_file is not None else None)
    receipt = folder/'command.json'
    if receipt.exists():
        old = load(receipt)
        require(old['identity'] == identity and old['status'] == 'COMPLETE', 'unfinished/changed command: '+label)
        for stream in ('stdout','stderr'):
            require(sha(folder/(stream+'.log')) == old[stream+'_sha256'], 'command log changed')
        if stdout_file is not None:
            require(sha(stdout_file) == old['output_sha256'], 'command redirected output changed')
        return old
    require(not folder.exists(), 'orphan command directory: '+label)
    folder.mkdir(parents=True)
    receipt.write_bytes(packed(dict(status='STARTED', identity=identity)))
    require(stdout_file is None or not Path(stdout_file).exists(), 'unrecorded redirected output')
    output = open(stdout_file, 'xb') if stdout_file is not None else subprocess.PIPE
    try:
        result = subprocess.run(identity['argv'], cwd=cwd or ROOT, env=environment(extra),
                                stdout=output, stderr=subprocess.PIPE)
    finally:
        if stdout_file is not None:
            output.close()
    (folder/'stdout.log').write_bytes(result.stdout or b'')
    (folder/'stderr.log').write_bytes(result.stderr)
    value = dict(identity=identity, status='COMPLETE' if result.returncode == 0 else 'ERROR',
                 returncode=result.returncode, stdout_sha256=sha(folder/'stdout.log'), stderr_sha256=sha(folder/'stderr.log'))
    if stdout_file is not None:
        value['output_sha256'] = sha(stdout_file)
    receipt.write_bytes(packed(value))
    result.check_returncode()
    return value


def checkout(name):
    url, commit = PINS[name]
    path = STATE/'deps'/name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        command(name+'-clone', ['git','clone','--no-checkout',url,path])
        command(name+'-checkout', ['git','-C',path,'checkout','--detach',commit])
    require(path.resolve().is_relative_to(STATE.resolve()) and not path.is_symlink(), 'dependency escaped owned state')
    require(git('remote','get-url','origin',repo=path).decode().strip() == url
            and git('rev-parse','HEAD',repo=path).decode().strip() == commit
            and not git('status','--porcelain','--untracked-files=no',repo=path).strip(), 'dependency pin/cleanliness differs: '+name)
    return path


def artifact(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def build_dependencies(identity):
    deps = {name: checkout(name) for name in PINS}
    z, a, h, d = (deps[name] for name in ('zstd','aceapex','htslib','libdeflate'))
    binaries = STATE/'bin'; binaries.mkdir(parents=True, exist_ok=True)
    command('zstd-static', ['make','-j1','-C',z/'lib','libzstd.a','CFLAGS=-O3 -fPIC -fno-lto'])
    command('zstd-cli', ['make','-j1','-C',z/'programs','zstd','CFLAGS=-O3 -fPIC -fno-lto'])
    command('ace-cli', ['make','-j1','-C',a,'ZSTD_CFLAGS=-I'+str(z/'lib'),'ZSTD_LIBS='+str(z/'lib/libzstd.a')])
    command('deflate-configure', ['cmake','-S',d,'-B',STATE/'libdeflate-build','-DCMAKE_BUILD_TYPE=Release',
            '-DCMAKE_POSITION_INDEPENDENT_CODE=ON','-DLIBDEFLATE_BUILD_SHARED_LIB=OFF',
            '-DLIBDEFLATE_BUILD_GZIP=OFF','-DLIBDEFLATE_BUILD_TESTS=OFF'])
    command('deflate-build', ['cmake','--build',STATE/'libdeflate-build','--parallel','1'])
    command('hts-submodules', ['git','-C',h,'submodule','update','--init','--depth','1'])
    command('hts-autoreconf', ['autoreconf','-i'], cwd=h)
    command('hts-configure', ['./configure','--with-libdeflate','--disable-bz2','--disable-lzma',
            '--disable-libcurl','--disable-s3','--disable-gcs','--disable-plugins'], cwd=h,
            extra={'CPPFLAGS':'-I'+str(d),'LDFLAGS':'-L'+str(STATE/'libdeflate-build')})
    command('hts-build', ['make','-j1','lib-static','bgzip','CFLAGS=-O3 -fPIC','PACKAGE_VERSION=1.24'], cwd=h)
    command('bgzf-encoder', ['gcc','-O3','-I'+str(h), ROOT/'review/matched_g/bgzf_encode_g.c',
            h/'libhts.a',STATE/'libdeflate-build/libdeflate.a','-lz','-lm','-pthread','-o',binaries/'bgzf-encode-g'])
    seek = z/'contrib/seekable_format'
    command('seekable-encoder', ['gcc','-O3','-DXXH_NAMESPACE=ZSTD_','-I'+str(z/'lib'),'-I'+str(z/'lib/common'),
            '-I'+str(seek),seek/'examples/seekable_compression.c',seek/'zstdseek_compress.c',z/'lib/libzstd.a',
            '-pthread','-o',binaries/'zstd-seekable-compress'])
    for name, source in (('aceapex',a/'aceapex'),('bgzip',h/'bgzip'),('zstd',z/'programs/zstd')):
        immutable(binaries/name, source.read_bytes()); (binaries/name).chmod(0o755)
    require(git('rev-parse','refs/tags/v2.6.5',repo=a).decode().strip() == ACE_TAG
            and git('rev-parse','refs/tags/v2.6.5^{commit}',repo=a).decode().strip() == PINS['aceapex'][1], 'ACE annotated tag changed')
    records = {}
    libraries = {'zstd':z/'lib/libzstd.a','htslib':h/'libhts.a','libdeflate':STATE/'libdeflate-build/libdeflate.a'}
    for name, path in deps.items():
        require(not git('status','--porcelain','--untracked-files=no',repo=path).strip(), 'build modified dependency source: '+name)
        records[name] = dict(path=str(path), commit=PINS[name][1], url=PINS[name][0], source_clean=True,
                             headers_sha256={p.relative_to(path).as_posix():sha(p) for p in sorted(path.rglob('*.h')) if '.git' not in p.parts})
        if name in libraries:
            records[name].update(library_path=str(libraries[name]),library_sha256=sha(libraries[name]))
    records['aceapex'].update(cli_path=str(binaries/'aceapex'),cli_sha256=sha(binaries/'aceapex'),
        cli_version=subprocess.check_output([str(binaries/'aceapex'),'--version'],stderr=subprocess.STDOUT).decode().strip(),
        annotated_tag_object=ACE_TAG,c99_header_version=re.search(r'ACEAPEX_DECODE_VERSION\s+"([^"]+)"',(a/'c/aceapex_decode.h').read_text()).group(1),
        public_api_version=re.search(r'ACEAPEX_VERSION_STRING\s+"([^"]+)"',(a/'src/aceapex.h').read_text()).group(1))
    records['zstd'].update(cli_path=str(binaries/'zstd'),cli_sha256=sha(binaries/'zstd'),
        cli_version=subprocess.check_output([str(binaries/'zstd'),'-V'],stderr=subprocess.STDOUT).decode().strip())
    records['htslib'].update(cli_path=str(binaries/'bgzip'),cli_sha256=sha(binaries/'bgzip'),
        cli_version=subprocess.check_output([str(binaries/'bgzip'),'--version'],stderr=subprocess.STDOUT).decode().strip(),
        submodules=git('submodule','status','--recursive',repo=h).decode())
    return records, {p.name:artifact(p) for p in sorted(binaries.iterdir())}


def stage_input(source, target, expected_bytes, expected_sha):
    source, target = Path(source), Path(target)
    require(source.is_file() and source.stat().st_size == expected_bytes and sha(source) == expected_sha, 'readonly input identity differs: '+str(source))
    if target.exists():
        require(target.stat().st_size == expected_bytes and sha(target) == expected_sha, 'staged input changed')
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open('rb') as src, target.open('xb') as dst:
            shutil.copyfileobj(src, dst)
    require(sha(target) == expected_sha, 'staged input copy differs')
    return artifact(target)


def recover_windows(manifest):
    """Reconstruct recorded coordinates only; verify the entire gzip/FASTA first."""
    catalog=load(ROOT/'corpora.json')['t2t_chm13v2_0']
    require(catalog['download_bytes']==932696125 and catalog['download_md5']=='9280657210e4161147cbe13b022225b9'
            and catalog['uncompressed_bytes']==3156259565 and catalog['md5']=='cd1e52ce400c027ed0b7ab4b9d613f5a', 'canonical T2T catalog changed')
    expected_url='https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/009/914/755/GCA_009914755.4_T2T-CHM13v2.0/GCA_009914755.4_T2T-CHM13v2.0_genomic.fna.gz'
    require(catalog['url']==expected_url,'T2T source URL changed')
    cached=STATE/'downloads/t2t.fna.gz';cached.parent.mkdir(parents=True,exist_ok=True)
    if not cached.exists():
        partial=cached.with_suffix('.partial');require(not partial.exists(),'partial T2T download retained; inspect before retry')
        with urllib.request.urlopen(expected_url) as response, partial.open('xb') as out: shutil.copyfileobj(response,out)
        require(partial.stat().st_size==932696125 and sha(partial,'md5')==catalog['download_md5'],'downloaded T2T gzip differs')
        partial.rename(cached)
    require(cached.stat().st_size==932696125 and sha(cached,'md5')==catalog['download_md5'],'cached T2T gzip differs')
    receipt=STATE/'corpora/t2t-source.json'
    if receipt.exists():
        value=load(receipt)
        require(value['manifest_sha256']==MANIFEST_SHA and value['compressed_sha256']==sha(cached),'cached T2T source receipt differs')
        for w in manifest['windows']:
            target=STATE/'inputs'/w['file'];require(target.stat().st_size==2097152 and sha(target)==w['input_sha256'],'cached frozen window differs')
        return value
    buffers={w['file']:bytearray() for w in manifest['windows']}
    by_accession={}
    for w in manifest['windows']: by_accession.setdefault(w['accession'],[]).append(w)
    md5,full_sha=hashlib.md5(),hashlib.sha256();expanded=0;accession=None;position=0
    with gzip.open(cached,'rb') as stream:
        for line in stream:
            md5.update(line);full_sha.update(line);expanded+=len(line)
            if line.startswith(b'>'):
                accession=line[1:].split()[0].decode();position=0;continue
            bases=line.rstrip(b'\r\n');end=position+len(bases)
            for w in by_accession.get(accession,[]):
                low,high=max(position,w['start']),min(end,w['end'])
                if low<high: buffers[w['file']].extend(bases[low-position:high-position])
            position=end
    require(expanded==3156259565 and md5.hexdigest()==catalog['md5'],'expanded T2T FASTA/CRC identity differs')
    for w in manifest['windows']:
        data=bytes(buffers[w['file']]);require(len(data)==2097152 and hashlib.sha256(data).hexdigest()==w['input_sha256'],'recovered window differs from frozen manifest')
        immutable(STATE/'inputs'/w['file'],data)
    value=dict(method='fixed manifest coordinates; preserve case; no resampling',url=expected_url,
               compressed_bytes=932696125,compressed_md5=catalog['download_md5'],compressed_sha256=sha(cached),
               expanded_bytes=expanded,expanded_md5=md5.hexdigest(),expanded_sha256=full_sha.hexdigest(),
               gzip_crc_verified=True,manifest_sha256=MANIFEST_SHA,windows_verified=30)
    immutable(receipt,packed(value));return value


def stage_corpora(bundle_path, bundle_url):
    records = {}
    for name, (path, size, digest) in SOURCES.items():
        target = STATE/'inputs'/({'chr1':'chr1.fa','silesia':'silesia.tar'}.get(name,name))
        records[name] = dict(**stage_input(path,target,size,digest),source_readonly=path)
    require(sha(records['chr1']['path'],'md5') == '9465e0f0df6e2c6eb39729c39cee5465', 'chr1 MD5 differs')
    records['chr1']['md5'] = '9465e0f0df6e2c6eb39729c39cee5465'
    manifest_bytes = git('show', 'HEAD:'+MANIFEST.relative_to(ROOT).as_posix())
    require(hashlib.sha256(manifest_bytes).hexdigest() == MANIFEST_SHA, 'canonical frozen T2T manifest differs')
    manifest = json.loads(manifest_bytes)
    require(len(manifest['windows']) == 30 and manifest['window_bytes'] == 2097152, 'frozen window count/size differs')
    cached = STATE/'downloads/t2t-regional-archives-20260916.zip'
    if not bundle_path and not bundle_url and not cached.exists():
        recovery=recover_windows(manifest)
        for index,window in enumerate(manifest['windows']):
            target=STATE/'inputs'/window['file']
            records['t2t-%02d' % index]=dict(**artifact(target),frozen_window=window,parent_manifest_sha256=MANIFEST_SHA)
        return records,dict(method='verified canonical FASTA recovery',source=recovery,manifest_sha256=MANIFEST_SHA)
    if bundle_path:
        stage_input(bundle_path,cached,BUNDLE_BYTES,BUNDLE_SHA)
    elif not cached.exists():
        require(bundle_url, '--bundle PATH or --bundle-url URL is required for the exact frozen bundle')
        cached.parent.mkdir(parents=True,exist_ok=True)
        partial = cached.with_suffix('.partial')
        require(not partial.exists(), 'partial bundle download retained; inspect before retry')
        with urllib.request.urlopen(bundle_url) as response, partial.open('xb') as out:
            shutil.copyfileobj(response,out)
        require(partial.stat().st_size == BUNDLE_BYTES and sha(partial) == BUNDLE_SHA, 'downloaded frozen bundle differs')
        partial.rename(cached)
    require(cached.stat().st_size == BUNDLE_BYTES and sha(cached) == BUNDLE_SHA, 'frozen bundle identity differs')
    with zipfile.ZipFile(cached) as archive:
        for index, window in enumerate(manifest['windows']):
            data = archive.read('windows/'+window['file'])
            require(len(data) == 2097152 and hashlib.sha256(data).hexdigest() == window['input_sha256'], 'frozen window bytes differ')
            target = STATE/'inputs'/window['file']; immutable(target,data)
            records['t2t-%02d' % index] = dict(**artifact(target),frozen_window=window,
                                              parent_manifest_sha256=MANIFEST_SHA,bundle_sha256=BUNDLE_SHA)
    return records, dict(path=str(cached),bytes=BUNDLE_BYTES,sha256=BUNDLE_SHA,manifest_sha256=MANIFEST_SHA)


def prepare(args):
    identity = provenance()
    deps, binaries = build_dependencies(identity)
    inputs, bundle = stage_corpora(args.bundle,args.bundle_url)
    compiler = {name:dict(path=str(Path(shutil.which(name)).resolve()),sha256=sha(Path(shutil.which(name)).resolve()),
                         version=subprocess.check_output([name,'--version']).decode()) for name in ('gcc','g++','make','cmake')}
    cases = {corpus+'-g'+str(g):dict(corpus=corpus,g=g,request_bytes=16384) for corpus in inputs
             for g in ((16384,) if corpus in ('enwik8','silesia') else (4096,16384,65536))}
    value = dict(schema='hw-region-1-setup-v1',measurements_of_time=False,identity=identity,
                 deps=deps,binaries=binaries,inputs=inputs,cases=cases,frozen_bundle=bundle,compiler=compiler,
                 commands={p.parent.name:dict(path=str(p),sha256=sha(p)) for p in sorted((STATE/'commands').glob('*/command.json'))})
    immutable(STATE/'setup.json',packed(value)); immutable(HERE/'setup.json',packed(value))
    expose_logs()
    print('SETUP_PASS',sha(HERE/'setup.json'),len(cases),flush=True)


def expose_logs():
    for path in sorted((STATE/'commands').rglob('*')):
        if path.is_file():
            require(path.suffix in ('.json','.log'), 'unexpected setup command artifact')
            suffix = {'stdout.log':'command.stdout','stderr.log':'command.stderr'}.get(path.name,path.name)
            immutable(HERE/'setup-logs'/path.parent.name/suffix,path.read_bytes())


def archive_case(case_id):
    identity = provenance()
    setup = load(STATE/'setup.json')
    require(setup['identity'] == identity and (HERE/'setup.json').read_bytes() == (STATE/'setup.json').read_bytes(), 'setup source identity changed')
    require(case_id in setup['cases'], 'case outside fixed grid')
    case = setup['cases'][case_id]; source = setup['inputs'][case['corpus']]
    require(sha(source['path']) == source['sha256'], 'case input changed')
    primary = HERE/'archives/chr1-g16384.json'
    if case_id != 'chr1-g16384':
        require(primary.is_file() and (HERE/'method-check.json').is_file()
                and load(HERE/'method-check.json')['status'] == 'PASS', 'primary archives and method gate must precede remaining grid')
    folder = STATE/'archives'/case_id; folder.mkdir(parents=True,exist_ok=True)
    public = HERE/'archives'/(case_id+'.json')
    if public.exists():
        old = load(public)
        for record in old['formats'].values():
            require(sha(record['path']) == record['sha256'] and all(sha(i['path']) == i['sha256'] for i in record['indexes']), 'accepted archive/index changed')
        print('ARCHIVES_REPLAY',case_id,flush=True); return
    bins = STATE/'bin'
    ace_env = {'ACEAPEX_BS':str(case['g']),'LIT_CHUNK':'65536','FSE_CHUNK':'4096'}
    formats = {}
    for codec in ('aceapex','zstd_seekable','bgzip'):
        receipt = folder/(codec+'.json')
        if receipt.exists():
            record=load(receipt)
            require(record['setup_sha256'] == sha(STATE/'setup.json') and sha(record['path']) == record['sha256']
                    and all(sha(i['path']) == i['sha256'] for i in record['indexes']), 'partial completed archive changed')
            formats[codec]=record; continue
        path = folder/({'aceapex':'aceapex.aet','zstd_seekable':'zstd.zst','bgzip':'bgzf.bgz'}[codec])
        require(not path.exists(), 'unrecorded/partial archive; inspect instead of overwriting')
        indexes=[]; effective=min(case['g'],65280) if codec=='bgzip' else case['g']
        if codec=='aceapex':
            argv=[bins/'aceapex','c','--in',source['path'],'--out',path,'--threads','1','--level','2']; extra=ace_env
        elif codec=='bgzip':
            argv=[bins/'bgzf-encode-g',source['path'],path,str(effective)]; extra={}
        else:
            alias=folder/'source'; require(not alias.exists() or alias.resolve()==Path(source['path']).resolve(), 'seekable source alias changed')
            if not alias.exists(): alias.symlink_to(source['path'])
            produced=Path(str(alias)+'.zst'); require(not produced.exists(), 'unrecorded seekable output')
            argv=[bins/'zstd-seekable-compress',alias,str(effective),'3']; extra={}
        execution=command('archive-'+case_id+'-'+codec,argv,extra=extra)
        if codec=='zstd_seekable': produced.rename(path)
        if codec=='bgzip': indexes=[artifact(str(path)+'.gzi')]
        restored=folder/(codec+'.restored')
        if codec=='aceapex':
            restore=[bins/'aceapex','d','--in',path,'--out',restored,'--threads','1']
            command('restore-'+case_id+'-'+codec,restore)
        else:
            restore=[bins/'zstd' if codec=='zstd_seekable' else bins/'bgzip','-d','-c',path]
            command('restore-'+case_id+'-'+codec,restore,stdout_file=restored)
        require(restored.stat().st_size==source['bytes'] and sha(restored)==source['sha256'], 'full restored archive differs from source')
        with open(source['path'],'rb') as left, restored.open('rb') as right:
            while True:
                a,b=left.read(1<<20),right.read(1<<20)
                require(a==b,'byte-for-byte full restoration differs')
                if not a: break
        record=dict(**artifact(path),indexes=indexes,stored_bytes=path.stat().st_size+sum(i['bytes'] for i in indexes),
                    input_sha256=source['sha256'],effective_g=effective,level=2 if codec=='aceapex' else 3 if codec=='zstd_seekable' else 6,
                    command=execution['identity'],environment=extra,bit_perfect=True,restore_sha256=sha(restored),setup_sha256=sha(STATE/'setup.json'))
        immutable(receipt,packed(record)); formats[codec]=record
    immutable(public,packed(dict(schema='hw-region-1-archives-v1',case_id=case_id,**case,input=source,
                                 setup_sha256=sha(STATE/'setup.json'),formats=formats)))
    expose_logs(); print('ARCHIVES_PASS',case_id,sha(public),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','archive'))
    parser.add_argument('--bundle',type=Path); parser.add_argument('--bundle-url')
    parser.add_argument('--case')
    args=parser.parse_args()
    if args.action=='prepare': prepare(args)
    else:
        require(args.case,'--case required'); archive_case(args.case)


if __name__=='__main__':
    main()
