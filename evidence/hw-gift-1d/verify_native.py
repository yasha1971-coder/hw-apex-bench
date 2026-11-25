"""Independent post-grid correctness audit; no clocks or benchmark imports.

Run only after timing ends. Rebuilds a separate decoder and the retained 1c
probe; permits exactly two cached 256 KiB correctness encodings. All production
archives are read only. --all-attempts also inspects retained LOADED outputs.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = ROOT / '.work/hw-gift-1d'
WORK = STATE / 'independent'
OLD = Path('/home/ubuntu/hw-apex-bench-hw-gift-1b')
ZSTD = OLD / '.work/hw-gift-1b/zstd'
PIN = 'f8745da6ff1ad1e7bab384bd1f9d742439278e99'
CORPORA = {'enwik8': (100000000, '2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8'),
           'silesia.tar': (211947520, 'a667bac80089b3d04d5496772149e632f0758974b0579d743cd8d6e5e0d63eb2')}
KNOWN = {'original': '3cab61b1c4cec5296d5ff271d162bbbd3ef730604c00a8833a4dac211db461e6',
         'nohint': 'bf72723ed208c90b32be0400bb1a611201f32555ca98d6f6261395614f2ec2c2'}
ORACLE = b'''#define XXH_NAMESPACE ZSTD_
#include <zstd.h>
#include <xxhash.h>
unsigned audit_version(void) { return ZSTD_versionNumber(); }
unsigned audit_error(size_t n) { return ZSTD_isError(n); }
size_t audit_decode(void *d, size_t dn, const void *s, size_t sn) { return ZSTD_decompress(d,dn,s,sn); }
size_t audit_extent(const void *s, size_t sn) { return ZSTD_findFrameCompressedSize(s,sn); }
unsigned long long audit_xxh64(const void *s, size_t sn) { return XXH64(s,sn,0); }
'''


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def load(path):
    return json.loads(Path(path).read_bytes())


def immutable(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == data, 'saved audit bytes changed: ' + str(path))
    else:
        with path.open('xb') as stream:
            stream.write(data)


def ref(value):
    path = (HERE / value['path']).resolve()
    require(path.is_relative_to(HERE) and path.is_file() and not path.is_symlink(), 'invalid evidence reference')
    require(file_sha(path) == value['sha256'], 'evidence reference changed: ' + str(path))
    return path


def header(data):
    require(len(data) >= 5 and data[:4] == b'\x28\xb5\x2f\xfd', 'bad frame magic')
    d, pos = data[4], 5
    require(not d & 8, 'reserved header bit')
    single, wd = bool(d & 32), None
    if not single:
        require(len(data) > pos, 'missing window byte')
        wd, pos = data[pos], pos + 1
        window = (1 << (10 + wd // 8)) * (8 + wd % 8) // 8
    dictionary_bytes = (0, 1, 2, 4)[d & 3]
    fcs_bytes = ((1 if single else 0), 2, 4, 8)[d >> 6]
    require(pos + dictionary_bytes + fcs_bytes <= len(data), 'short header')
    dictionary = int.from_bytes(data[pos:pos + dictionary_bytes], 'little')
    pos += dictionary_bytes
    fcs = int.from_bytes(data[pos:pos + fcs_bytes], 'little') + (256 if fcs_bytes == 2 else 0) if fcs_bytes else None
    pos += fcs_bytes
    if single:
        window = fcs
    return dict(descriptor=d, window_descriptor=wd, window_size=window, content_size=fcs,
                header_size=pos, checksum_flag=bool(d & 4), dict_id=dictionary, header_hex=data[:pos].hex())


def decode_archive(lib, data, source, g):
    require(len(data) >= 17, 'short seekable archive')
    count, descriptor, magic = struct.unpack('<IBI', data[-9:])
    require(count > 0 and descriptor == 128 and magic == 0x8F92EAB1, 'invalid seek footer or absent checksums')
    table_bytes = 17 + 12 * count
    table = len(data) - table_bytes
    require(table >= 0 and struct.unpack_from('<II', data, table) == (0x184D2A5E, table_bytes - 8), 'invalid seek table header')
    nonempty_count = (len(source) + g - 1) // g
    # The contrib example can close a fresh, empty session after its final
    # exact-size frame. This is a real indexed zstd frame, not padding: retain
    # and validate its compressed bytes, zero-byte restore and XXH64 entry.
    allowed_counts = {nonempty_count}
    if len(source) % g == 0:
        allowed_counts.add(nonempty_count + 1)
    require(count in allowed_counts, 'wrong frame count for input/frame grid')
    empty_terminal_frames = int(count == nonempty_count + 1)
    encoded_offset = restored_offset = 0
    digest, first = hashlib.sha256(), None
    for index in range(count):
        cn, dn, checksum = struct.unpack_from('<III', data, table + 8 + 12 * index)
        expected_size = min(g, len(source) - restored_offset)
        require(cn > 0 and dn == expected_size and encoded_offset + cn <= table
                and (dn > 0 or (empty_terminal_frames == 1 and index == count - 1 and restored_offset == len(source))),
                'invalid seek entry extent')
        frame = data[encoded_offset:encoded_offset + cn]
        wire = header(frame)
        require(wire['dict_id'] == 0 and wire['content_size'] in (None, dn), 'unexpected dictionary/content size')
        encoded, decoded = C.create_string_buffer(frame, cn), C.create_string_buffer(dn)
        extent = lib.audit_extent(encoded, cn)
        require(not lib.audit_error(extent) and extent == cn, 'entry is not exactly one complete frame')
        size = lib.audit_decode(decoded, dn, encoded, cn)
        require(not lib.audit_error(size) and size == dn, 'independent frame decoder failed')
        raw = decoded.raw
        require(raw == source[restored_offset:restored_offset + dn], 'restored source byte mismatch')
        require((lib.audit_xxh64(decoded, dn) & 0xFFFFFFFF) == checksum, 'seek-table XXH64 mismatch')
        digest.update(raw)
        if first is None:
            first = dict(sha256=sha(frame), header=wire)
        encoded_offset += cn
        restored_offset += dn
    require(encoded_offset == table and restored_offset == len(source) and digest.hexdigest() == sha(source),
            'unaccounted archive/source bytes or restored SHA mismatch')
    return dict(frame_count=count, nonempty_frame_count=nonempty_count, empty_terminal_frames=empty_terminal_frames,
                restored_bytes=restored_offset, restored_sha256=digest.hexdigest(),
                seek_table_bytes=table_bytes, seek_checksums_verified=True, first_frame=first)


def source_and_build_pins():
    require(subprocess.check_output(['git', '-C', str(ZSTD), 'rev-parse', 'HEAD']).decode().strip() == PIN
            and not subprocess.check_output(['git', '-C', str(ZSTD), 'status', '--porcelain']).strip(), 'pinned upstream tree changed')
    preparation = load(HERE / 'preparation.json')
    for name, expected in preparation['provenance']['source_hashes'].items():
        require(file_sha(HERE / name) == expected, 'experiment source snapshot changed: ' + name)
    ref(preparation['base_build'])
    receipts = {}
    for public in sorted((HERE / 'native').glob('*/build.json')):
        private = STATE / 'native' / public.parent.name / 'build.json'
        require(public.read_bytes() == private.read_bytes(), 'public/private build receipt differs')
        build = load(public)
        identity, folder = build['identity'], private.parent
        require(identity['zstd_commit'] == PIN and identity['static_library_sha256'] == file_sha(ZSTD / 'lib/libzstd.a'), 'static codec build pin differs')
        for name, expected in identity['source_sha256'].items():
            require(file_sha(folder / name) == expected, 'production native source changed: ' + name)
        for variant, library in build['libraries'].items():
            require(file_sha(folder / (variant + '.so')) == library['sha256'], 'production native binary changed')
        protocol = identity.get('conditional_protocol')
        if protocol:
            require(file_sha(HERE / 'CONDITIONAL_PROTOCOL.md') == protocol['sha256'], 'conditional protocol changed')
        receipts[public.parent.name] = dict(sha256=file_sha(public), identity=identity, libraries=build['libraries'])
    require('base' in receipts, 'base build unavailable')
    return dict(preparation_sha256=file_sha(HERE / 'preparation.json'), native_builds=receipts)


def rebuild_oracle():
    WORK.mkdir(parents=True, exist_ok=True)
    probe = ROOT / 'evidence/hw-gift-1c/frame_probe.c'
    environment = load(ROOT / 'evidence/hw-gift-1c/environment.json')
    static = ZSTD / 'lib/libzstd.a'
    require(environment['zstd_commit'] == PIN and environment['source_sha256']['frame_probe.c'] == file_sha(probe)
            and environment['library_sha256'] == file_sha(static), 'independent probe/library pin differs from 1c')
    immutable(WORK / 'oracle.c', ORACLE)
    commands = [ ['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-I' + str(ZSTD / 'lib'), str(probe), str(static), '-pthread', '-o', str(WORK / 'frame_probe')],
                 ['cc', '-O2', '-fPIC', '-shared', '-Wall', '-Wextra', '-Werror', '-Wl,-Bsymbolic', '-I' + str(ZSTD / 'lib'), '-I' + str(ZSTD / 'lib/common'), str(WORK / 'oracle.c'), str(static), '-pthread', '-o', str(WORK / 'oracle.so')] ]
    identity = dict(probe_source_sha256=file_sha(probe), oracle_source_sha256=sha(ORACLE),
                    static_library_sha256=file_sha(static), zstd_commit=PIN, commands=commands)
    build_path = WORK / 'build.json'
    if build_path.exists():
        saved = load(build_path)
        require(saved['identity'] == identity, 'independent rebuild identity changed')
        for name, expected in saved['binaries'].items():
            require(file_sha(WORK / name) == expected, 'independent binary changed')
    else:
        require(not (WORK / 'oracle.so').exists() and not (WORK / 'frame_probe').exists(), 'incomplete independent build; inspect manually')
        for name, command in zip(('probe', 'oracle'), commands):
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            immutable(WORK / (name + '-build.stdout'), result.stdout)
            immutable(WORK / (name + '-build.stderr'), result.stderr)
            result.check_returncode()
        immutable(build_path, packed(dict(identity=identity, binaries={name: file_sha(WORK / name) for name in ('frame_probe', 'oracle.so')})))
    lib = C.CDLL(str(WORK / 'oracle.so'))
    for name, arguments, returns in (('audit_version', [], C.c_uint), ('audit_error', [C.c_size_t], C.c_uint),
            ('audit_decode', [C.c_void_p, C.c_size_t, C.c_void_p, C.c_size_t], C.c_size_t),
            ('audit_extent', [C.c_void_p, C.c_size_t], C.c_size_t), ('audit_xxh64', [C.c_void_p, C.c_size_t], C.c_ulonglong)):
        method = getattr(lib, name)
        method.argtypes, method.restype = arguments, returns
    require(lib.audit_version() == 10507, 'independent decoder is not zstd 1.5.7')
    return lib, dict(build_sha256=file_sha(build_path), **load(build_path))


def tiny_proof(raw):
    raw = raw[:262144]
    require(sha(raw) == '0cdfd008d5327addbf5b118b4a8d616a8cc2971627727b10bfb20e97920881e7', 'known-answer slice changed')
    immutable(WORK / 'slice.bin', raw)
    outputs = {}
    for variant, hint in (('original', 262144), ('nohint', 0)):
        target, receipt = WORK / (variant + '.zst'), WORK / (variant + '.json')
        command = [str(WORK / 'frame_probe'), str(WORK / 'slice.bin'), str(target), '3', str(hint), '131072', 'empty']
        if receipt.exists():
            saved = load(receipt)
            require(saved['command'] == command and saved['sha256'] == file_sha(target), 'cached tiny proof changed')
        else:
            require(not target.exists(), 'incomplete tiny proof; do not re-encode')
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            immutable(WORK / (variant + '.stdout'), result.stdout)
            immutable(WORK / (variant + '.stderr'), result.stderr)
            result.check_returncode()
            saved = dict(command=command, result=json.loads(result.stdout), sha256=file_sha(target))
            immutable(receipt, packed(saved))
        require(saved['sha256'] == KNOWN[variant] and saved['result']['roundtrip'] is True
                and saved['result']['corrupted_magic_error'] is True, 'independent tiny known answer failed')
        outputs[variant] = saved
    return outputs


def collect(all_attempts):
    requests = {file_sha(path): load(path) for path in (HERE / 'requests').rglob('*.json')}
    rows, documents = [], {}

    def add(path, cell=None, changed=False):
        value = load(path)
        documents[str(path.relative_to(HERE))] = file_sha(path)
        if cell is None:
            require(value['cell_sha256'] in requests, 'result lacks a retained request')
            cell = requests[value['cell_sha256']]
        require(value.get('status', 'PASS') == 'PASS' and value.get('clock_calls', 0) >= 0, 'invalid archive document')
        for row in value['results']:
            rows.append((row, cell, changed, str(path.relative_to(HERE))))

    method = load(HERE / 'method-controls.json')
    method_cell = requests[method['cell_sha256']]
    for name in ('positive', 'known_answer', 'negative_changed_input'):
        for row in method[name]['results']:
            rows.append((row, method_cell, name == 'negative_changed_input', 'method-controls.json:' + name))
    documents['method-controls.json'] = file_sha(HERE / 'method-controls.json')
    for path in sorted((HERE / 'selfchecks').rglob('*.json')):
        add(path)
    cell_paths = sorted((HERE / 'cells').rglob('*.json')) + [HERE / 'method-check.json']
    for path in cell_paths:
        cell = load(path)
        documents[str(path.relative_to(HERE))] = file_sha(path)
        request = ref(dict(path=cell['request_path'], sha256=cell['request_sha256']))
        ref(dict(path=cell['selfcheck_path'], sha256=cell['selfcheck_sha256']))
        for repeat in cell['repeats']:
            add(ref(repeat['selected_result']), load(request))
    if all_attempts:
        for path in sorted((HERE / 'raw').rglob('result.json')):
            add(path)
    require(rows, 'no retained archive results')
    return rows, documents


def same_file_bytes(a, b):
    if Path(a) == Path(b):
        return True  # Every distinct actual path was already SHA/size checked.
    with Path(a).open('rb') as left, Path(b).open('rb') as right:
        while True:
            x, y = left.read(1 << 20), right.read(1 << 20)
            if x != y:
                return False
            if not x:
                return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'audit/native.json')
    parser.add_argument('--all-attempts', action='store_true')
    args = parser.parse_args()
    pins = source_and_build_pins()
    source = {}
    for name, (size, digest) in CORPORA.items():
        data = (OLD / '.work/inputs' / name).read_bytes()
        require(len(data) == size and sha(data) == digest, 'full source corpus changed: ' + name)
        source[name] = data
    lib, build = rebuild_oracle()
    minimal = tiny_proof(source['enwik8'])
    rows, documents = collect(args.all_attempts)
    verified, paths, groups, source_views = {}, {}, {}, {}
    for row, cell, changed, origin in rows:
        source_key = (cell['corpus'], cell['input_bytes'], changed)
        if source_key not in source_views:
            raw = source[cell['corpus']][:cell['input_bytes']]
            require(len(raw) == cell['input_bytes'] and sha(raw) == cell['input_sha256'], 'cell prefix input changed')
            if changed:
                raw = bytes([raw[0] ^ 255]) + raw[1:]
            source_views[source_key] = (raw, sha(raw))
        raw, source_sha = source_views[source_key]
        if not changed:
            require(source_sha == cell['input_sha256'], 'request source identity differs')
        require((cell['full_corpus_bytes'], cell['full_corpus_sha256']) == CORPORA[cell['corpus']], 'cell full corpus differs')
        require(cell['input_bytes'] == ((16 << 20) if cell['g'] in (256, 1024) else len(source[cell['corpus']])), 'unexpected input prefix')
        require(row['decoded_bytes'] == len(raw) and row['decoded_sha256'] == source_sha, 'retained restored source SHA differs')
        path = Path(row['archive_path']).resolve()
        require(path.is_relative_to(STATE) and not path.is_symlink(), 'archive path escaped experiment state')
        if str(path) not in paths:
            paths[str(path)] = dict(sha256=file_sha(path), bytes=path.stat().st_size)
        require(paths[str(path)] == dict(sha256=row['archive_sha256'], bytes=row['archive_bytes']), 'actual archive identity differs')
        key = (row['archive_sha256'], source_sha, cell['g'])
        if key not in verified:
            proof = decode_archive(lib, path.read_bytes(), raw, cell['g'])
            verified[key] = dict(archive_sha256=key[0], archive_bytes=row['archive_bytes'], **proof)
        proof = verified[key]
        require(proof['frame_count'] == row['frame_count'] and proof['seek_table_bytes'] == row['seek_table_bytes']
                and proof['first_frame']['header'] == row['header'] and row['seek_checksum_flag'] is True, 'parsed archive metadata differs')
        if not changed:
            group = groups.setdefault((cell['corpus'], cell['level'], cell['g']), {})
            old = group.setdefault(row['variant'], (path, cell.get('threshold')))
            require(same_file_bytes(old[0], path), 'same variant changed bytes between retained observations')
            if cell['corpus'] == 'enwik8' and cell['level'] == 3 and cell['g'] == 262144 and row['variant'] in KNOWN:
                require(proof['first_frame']['sha256'] == KNOWN[row['variant']], 'production frame 0 differs from independent tiny proof')
    conditional = []
    for (corpus, level, g), variants in sorted(groups.items()):
        if 'conditional' in variants:
            path, threshold = variants['conditional']
            selected = 'original' if g < threshold else 'nohint'
            require(selected in variants and same_file_bytes(path, variants[selected][0]), 'conditional bytes differ from selected policy')
            conditional.append(dict(corpus=corpus, level=level, g=g, threshold=threshold, selected=selected, bytes_equal=True))
    result = dict(schema='hw-gift-1d-independent-native-v1', status='PASS', no_clocks=True,
                  measurements_of_time=False, all_attempts=args.all_attempts, minimal_encodings_authorized=2,
                  source_sha256=file_sha(__file__), pins=pins, independent_build=build, tiny_probe=minimal,
                  archive_references=len(rows), archive_paths_verified=len(paths), unique_archives_verified=len(verified),
                  frame_decodes_verified=sum(p['frame_count'] for p in verified.values()),
                  restored_bytes_verified=sum(p['restored_bytes'] for p in verified.values()),
                  archives=list(verified.values()), archive_paths=paths, documents_sha256=documents,
                  conditional_policy_byte_checks=conditional)
    immutable(args.output, packed(result))
    print('INDEPENDENT_NATIVE_PASS', file_sha(args.output), len(verified), result['frame_decodes_verified'], flush=True)


if __name__ == '__main__':
    main()
