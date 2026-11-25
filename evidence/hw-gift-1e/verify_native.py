"""Independent post-run HW-GIFT-1e archive proof: decode only, no clocks.

Run after all admitted timing stages finish. Builds a separate direct-frame
decoder/XXH64 oracle against the clean pinned v1.5.7 static library, never an
encoder. Reads every retained output (including excluded started attempts),
restores every frame against source bytes, and checks each seek-table entry.
No experiment modules are imported and no compression entry point is called.
"""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = ROOT/'.work/hw-gift-1e'
WORK = STATE/'independent-native'
PIN = 'f8745da6ff1ad1e7bab384bd1f9d742439278e99'
FULL_BYTES = 100000000
FULL_SHA = '2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8'
ORACLE = b'''#define XXH_NAMESPACE ZSTD_
#include <zstd.h>
#include <xxhash.h>
unsigned audit_version(void) { return ZSTD_versionNumber(); }
unsigned audit_error(size_t n) { return ZSTD_isError(n); }
size_t audit_decode(void *d, size_t dn, const void *s, size_t sn) { return ZSTD_decompress(d,dn,s,sn); }
size_t audit_extent(const void *s, size_t sn) { return ZSTD_findFrameCompressedSize(s,sn); }
unsigned long long audit_xxh64(const void *s, size_t sn) { return XXH64(s,sn,0); }
'''
DOCUMENTS = {}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def packed(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()


def load(path):
    path = Path(path)
    raw = path.read_bytes()
    if path.resolve().is_relative_to(HERE):
        DOCUMENTS[path.resolve().relative_to(HERE).as_posix()] = digest(raw)
    def unique(pairs):
        value = {}
        for key,item in pairs:
            require(key not in value, 'duplicate JSON key: '+key)
            value[key] = item
        return value
    return json.loads(raw,object_pairs_hook=unique)


def ref(item):
    path = (HERE/item['path']).resolve()
    require(path.is_relative_to(HERE) and not path.is_symlink() and file_sha(path) == item['sha256'], 'public evidence reference differs')
    return path


def immutable(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        require(path.read_bytes() == raw, 'retained independent build bytes changed: '+str(path))
    else:
        with path.open('xb') as stream:
            stream.write(raw)


def git(*args, repo):
    return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.PIPE)


def finished_grid():
    decision = load(HERE/'decision.json')
    require(decision['status'] in ('STOP: Kill','PRIMARY COMPLETE'), 'primary timing is incomplete')
    require(decision['search_admitted'] is (decision['P1']['passed'] is True and decision['P2']['passed'] is True), 'search gate differs')
    paths = []
    for core in ('v1.5.4','v1.5.7'):
        for scope in ('full','prefix'):
            for level,g in ((10,256),(10,1024),(3,256)):
                path = HERE/'cells'/core/f'{scope}-L{level}-G{g}.json'
                if decision['Kill']['triggered'] and (core,scope,level,g) != ('v1.5.4','full',10,256):
                    require(not path.exists(), 'timing continued after Kill')
                    continue
                require(path.is_file() and load(path)['status'] == 'COMPLETE', 'main grid timing is incomplete')
                paths.append(path)
    if decision['search_admitted']:
        require((HERE/'search/result.json').is_file() and (HERE/'search/audit.json').is_file(), 'finish admitted search before native correctness work')
        require(load(HERE/'search/audit.json')['status'] == 'PASS', 'search audit did not pass')
        load(HERE/'search/result.json')
    return paths


def rebuild_oracle():
    require(os.name == 'posix' and not os.environ.get('OVH_BENCH_LOCK_HELD'), 'native correctness work must run on Linux outside the benchmark lock')
    setup = load(HERE/'setup.json')
    core = setup['cores']['v1.5.7']
    checkout = Path(core['path']).resolve()
    require(checkout.is_relative_to(STATE.resolve()) and git('rev-parse','HEAD',repo=checkout).decode().strip() == PIN
            and not git('status','--porcelain',repo=checkout).strip(), 'decoder core source pin/cleanliness differs')
    library = checkout/'lib/libzstd.a'
    cli = checkout/'programs/zstd'
    require(file_sha(library) == core['library_sha256'] and file_sha(cli) == core['cli_sha256'], 'pinned decoder static library/CLI differs')
    require(subprocess.check_output([str(cli),'-V'],stderr=subprocess.STDOUT).decode().strip() == core['cli_version']
            and '1.5.7' in core['cli_version'], 'decoder CLI runtime version differs')
    compiler = Path(setup['compiler']['path'])
    require(file_sha(compiler) == setup['compiler']['sha256'], 'oracle compiler differs from recorded compiler')
    headers = {name:file_sha(checkout/'lib'/name) for name in ('zstd.h','common/xxhash.h')}
    for name,expected in headers.items():
        require(expected == core['headers_sha256']['lib/'+name], 'oracle uses different core headers')
    source,binary = WORK/'oracle.c',WORK/'oracle.so'
    command = [str(compiler),'-O3','-fPIC','-fno-lto','-shared','-Wall','-Wextra','-Werror','-Wl,-Bsymbolic',
               '-I'+str(checkout/'lib'),'-I'+str(checkout/'lib/common'),str(source),str(library),'-pthread','-o',str(binary)]
    identity = dict(zstd_commit=PIN,oracle_source_sha256=digest(ORACLE),static_library_sha256=file_sha(library),
                    cli_sha256=file_sha(cli),cli_version=core['cli_version'],headers_sha256=headers,
                    compiler_sha256=file_sha(compiler),command=command)
    receipt = WORK/'build.json'
    if receipt.exists():
        build = load(receipt)
        require(build['identity'] == identity and file_sha(source) == digest(ORACLE)
                and file_sha(binary) == build['binary_sha256'], 'cached independent oracle changed')
        for stream in ('stdout','stderr'):
            require(file_sha(WORK/f'compiler.{stream}') == build[stream+'_sha256'], 'oracle compiler logs differ')
    else:
        require(not binary.exists() and not (WORK/'compiler.stdout').exists() and not (WORK/'compiler.stderr').exists(), 'incomplete oracle build; inspect rather than rebuild')
        immutable(source,ORACLE)
        result = subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        immutable(WORK/'compiler.stdout',result.stdout);immutable(WORK/'compiler.stderr',result.stderr)
        result.check_returncode()
        build = dict(identity=identity,binary_sha256=file_sha(binary),stdout_sha256=digest(result.stdout),stderr_sha256=digest(result.stderr))
        immutable(receipt,packed(build))
    lib = C.CDLL(str(binary),mode=C.RTLD_LOCAL)
    pointer,size = C.c_void_p,C.c_size_t
    for name,args,returns in (('audit_version',[],C.c_uint),('audit_error',[size],C.c_uint),
                              ('audit_decode',[pointer,size,pointer,size],size),('audit_extent',[pointer,size],size),
                              ('audit_xxh64',[pointer,size],C.c_ulonglong)):
        fn = getattr(lib,name);fn.argtypes,fn.restype = args,returns
    require(lib.audit_version() == 10507, 'independent decoder linked the wrong version')
    return lib,dict(build_sha256=file_sha(receipt),**build)


def header(frame):
    require(len(frame) >= 5 and frame[:4] == b'\x28\xb5\x2f\xfd', 'invalid zstd frame magic')
    descriptor,pos = frame[4],5
    require(not descriptor & 8, 'reserved frame-header bit')
    single = bool(descriptor & 32)
    wd = None
    if not single:
        require(len(frame)>pos,'missing window descriptor')
        wd,pos = frame[pos],pos+1
        window = (1 << (10+wd//8))*(8+wd%8)//8
    dictionary_size = (0,1,2,4)[descriptor&3]
    content_size = ((1 if single else 0),2,4,8)[descriptor>>6]
    require(pos+dictionary_size+content_size <= len(frame),'truncated frame header')
    dictionary = int.from_bytes(frame[pos:pos+dictionary_size],'little');pos += dictionary_size
    fcs = int.from_bytes(frame[pos:pos+content_size],'little')+(256 if content_size == 2 else 0) if content_size else None
    pos += content_size
    if single:
        window = fcs
    return dict(descriptor=descriptor,window_descriptor=wd,window_size=window,content_size=fcs,header_size=pos,
                checksum_flag=bool(descriptor&4),dict_id=dictionary,header_hex=frame[:pos].hex())


def decode_archive(lib, data, source, g):
    require(len(data)>=17,'short seekable archive')
    count,descriptor,magic = struct.unpack('<IBI',data[-9:])
    require(count>0 and descriptor == 128 and magic == 0x8F92EAB1,'invalid seek footer/checksums')
    table_bytes = 17+12*count
    table = len(data)-table_bytes
    require(table>=0 and struct.unpack_from('<II',data,table) == (0x184D2A5E,table_bytes-8),'invalid seek table header')
    nonempty = (len(source)+g-1)//g
    empty = count-nonempty
    require(empty in (0,1) and (not empty or len(source)%g == 0),'wrong actual frame count')
    encoded_offset = restored_offset = 0
    restored_sha,first = hashlib.sha256(),None
    for index in range(count):
        cn,dn,checksum = struct.unpack_from('<III',data,table+8+12*index)
        expected = min(g,len(source)-restored_offset)
        require(cn>0 and dn == expected and encoded_offset+cn<=table
                and (dn>0 or empty == 1 and index == count-1 and restored_offset == len(source)), 'invalid actual frame extent')
        frame = data[encoded_offset:encoded_offset+cn]
        wire = header(frame)
        require(wire['dict_id'] == 0 and wire['content_size'] in (None,dn),'unexpected dictionary/content size')
        encoded,decoded = C.create_string_buffer(frame,cn),C.create_string_buffer(dn)
        extent = lib.audit_extent(encoded,cn)
        require(not lib.audit_error(extent) and extent == cn,'entry is not exactly one zstd frame')
        size = lib.audit_decode(decoded,dn,encoded,cn)
        require(not lib.audit_error(size) and size == dn and decoded.raw == source[restored_offset:restored_offset+dn], 'independent decode differs from exact source bytes')
        require((lib.audit_xxh64(decoded,dn)&0xFFFFFFFF) == checksum,'independent seek-table XXH64 mismatch')
        restored_sha.update(decoded.raw)
        if first is None:
            first = dict(sha256=digest(frame),header=wire)
        encoded_offset += cn;restored_offset += dn
    require(encoded_offset == table and restored_offset == len(source) and restored_sha.hexdigest() == digest(source), 'unaccounted compressed/source bytes')
    return dict(frame_count=count,nonempty_frame_count=nonempty,empty_terminal_frames=empty,seek_table_bytes=table_bytes,
                seek_checksums_verified=True,empty_terminal_verified=True,restored_bytes=restored_offset,
                restored_sha256=restored_sha.hexdigest(),first_frame=first)


def collect():
    requests = {}
    for path in sorted(HERE.rglob('*.json')):
        if path.is_relative_to(HERE/'audit'):
            continue
        value = load(path)
        if value.get('schema') in ('hw-gift-1e-cell-v1','hw-gift-1e-search-request-v1') and 'input_path' in value and 'repeats' not in value:
            requests[file_sha(path)] = value
    rows = []
    # Main controls deliberately operate on a shorter and a changed source.
    controls = load(HERE/'method-controls.json')
    for item in controls['cores'].values():
        request = load(ref(item['request']))
        for name,changed in (('positive',False),('negative_changed_input',True)):
            group = item[name]
            require(group['clock_calls'] == 0 and group['input_bytes'] == 262144,'wrong untimed control source')
            for row in group['results']:
                rows.append((row,request,262144,changed,'method-controls.json:'+name))
    for path in sorted(HERE.rglob('*.json')):
        if path.is_relative_to(HERE/'audit'):
            continue
        value = load(path)
        if value.get('schema') not in ('hw-gift-1e-selfcheck-v1','hw-gift-1e-worker-v1','hw-gift-1e-search-worker-v1'):
            continue
        request_sha = value.get('cell_sha256',value.get('request_sha256'))
        require(request_sha in requests,'retained output lacks an exact public request: '+str(path))
        request = requests[request_sha]
        for row in value['results']:
            rows.append((row,request,request['input_bytes'],False,path.relative_to(HERE).as_posix()))
    require(rows,'no retained archive outputs')
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=HERE/'audit/native.json')
    parser.add_argument('--all-attempts',action='store_true',default=True,
                        help='all retained started attempts are always included')
    args = parser.parse_args()
    require(not args.output.exists(),'independent native proof already exists; inspect saved proof instead of rerunning')
    finished_grid()
    rows = collect()
    full_request = load(HERE/'requests/v1.5.4/full-L10-G256.json')
    input_path = Path(full_request['input_path']).resolve()
    require(input_path.is_relative_to(STATE.resolve()) and not input_path.is_symlink(),'source path escapes 1e private state')
    full = input_path.read_bytes()
    require(len(full) == FULL_BYTES and digest(full) == FULL_SHA,'full enwik8 source changed')
    lib,build = rebuild_oracle()
    verified,paths,source_views = {},{},{}
    for row,request,length,changed,origin in rows:
        key = length,changed
        if key not in source_views:
            raw = full[:length]
            if changed:
                raw = bytes([raw[0]^255])+raw[1:]
            source_views[key] = raw,digest(raw)
        raw,source_sha = source_views[key]
        require(len(raw) == length and (changed or length == 262144 or request['input_sha256'] == source_sha),'retained source scope differs')
        require((row.get('decoded_bytes',row.get('restored_bytes')),row.get('decoded_sha256',row.get('restored_sha256'))) == (length,source_sha)
                and row['bit_perfect'] is True,'retained restore metadata differs')
        path = Path(row['archive_path']).resolve()
        require(path.is_relative_to(STATE.resolve()) and not path.is_symlink(),'archive escaped experiment state')
        if str(path) not in paths:
            paths[str(path)] = dict(bytes=path.stat().st_size,sha256=file_sha(path))
        require(paths[str(path)] == dict(bytes=row['archive_bytes'],sha256=row['archive_sha256']),'actual archive identity differs')
        cache_key = row['archive_sha256'],source_sha,request['g']
        if cache_key not in verified:
            proof = decode_archive(lib,path.read_bytes(),raw,request['g'])
            verified[cache_key] = dict(archive_bytes=row['archive_bytes'],archive_sha256=row['archive_sha256'],**proof)
        proof = verified[cache_key]
        for name in ('frame_count','empty_terminal_frames'):
            require(row[name] == proof[name],'retained frame metadata differs: '+origin)
        for name in ('seek_table_bytes','seek_checksums_verified','empty_terminal_verified'):
            if name in row:
                require(row[name] == proof[name],'retained checksum/empty proof differs: '+origin)
        if 'header' in row:
            require(row['header'] == proof['first_frame']['header'],'actual first frame header differs: '+origin)
    result = dict(schema='hw-gift-1e-independent-native-v1',status='PASS',source_sha256=file_sha(__file__),
                  no_clocks=True,measurements_of_time=False,encodings_performed=0,all_attempts=True,
                  setup_sha256=file_sha(HERE/'setup.json'),independent_build=build,
                  archive_references=len(rows),archive_paths_verified=len(paths),unique_archives_verified=len(verified),
                  frame_decodes_verified=sum(p['frame_count'] for p in verified.values()),
                  restored_bytes_verified=sum(p['restored_bytes'] for p in verified.values()),
                  archives=list(verified.values()),archive_paths=paths,documents_sha256=DOCUMENTS)
    immutable(args.output,packed(result))
    print('INDEPENDENT_NATIVE_PASS',file_sha(args.output),len(verified),result['frame_decodes_verified'],flush=True)


if __name__ == '__main__':
    main()
