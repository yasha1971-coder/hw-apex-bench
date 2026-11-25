"""Independent HW-GIFT-1c correctness audit. No clocks or benchmark timing.

This script imports neither run.py nor seekable.py. It rebuilds the retained
minimal C program and permits only its two 256 KiB correctness encodings.
All full archives are read without modification and decoded independently.
"""
import csv
import ctypes as C
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess

ROOT = Path('/home/ubuntu/hw-apex-bench-hw-gift-1c')
OLD = Path('/home/ubuntu/hw-apex-bench-hw-gift-1b')
P = ROOT / 'evidence/hw-gift-1c'
REVIEW = ROOT / '.work/review'
ZSTD = OLD / '.work/hw-gift-1b/zstd'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def load(path):
    return json.loads(Path(path).read_bytes())


def header(frame):
    require(frame[:4] == b'\x28\xb5\x2f\xfd' and len(frame) >= 5, 'bad frame header')
    d = frame[4]
    require(not d & 8, 'reserved frame header bit')
    single = bool(d & 32)
    pos = 5
    wd = None
    if not single:
        require(len(frame) > pos, 'missing window byte')
        wd = frame[pos]
        pos += 1
        window = (1 << (10 + wd//8)) * (8 + wd%8) // 8
    dictionary_bytes = (0, 1, 2, 4)[d & 3]
    fcs_bytes = ((1 if single else 0), 2, 4, 8)[d >> 6]
    require(pos + dictionary_bytes + fcs_bytes <= len(frame), 'short frame header')
    dictionary = int.from_bytes(frame[pos:pos+dictionary_bytes], 'little')
    pos += dictionary_bytes
    fcs = None
    if fcs_bytes:
        fcs = int.from_bytes(frame[pos:pos+fcs_bytes], 'little') + (256 if fcs_bytes == 2 else 0)
        pos += fcs_bytes
    if single:
        window = fcs
    return dict(descriptor=d, window_descriptor=wd, window_size=window,
                content_size=fcs, header_size=pos, checksum_flag=bool(d & 4),
                dict_id=dictionary, header_hex=frame[:pos].hex())


def archive(data):
    require(len(data) >= 17, 'short archive')
    count, descriptor, magic = struct.unpack('<IBI', data[-9:])
    require(magic == 0x8f92eab1 and not descriptor & 0x7c, 'bad seekable footer')
    checksum = bool(descriptor & 128)
    width = 12 if checksum else 8
    table_bytes = 17 + count*width
    offset_table = len(data) - table_bytes
    require(offset_table >= 0, 'seek table beyond archive')
    skip_magic, skip_size = struct.unpack_from('<II', data, offset_table)
    require(skip_magic == 0x184d2a5e and skip_size == table_bytes-8, 'bad seek table header')
    frames, offset = [], 0
    for index in range(count):
        pos = offset_table + 8 + index*width
        compressed, decompressed = struct.unpack_from('<II', data, pos)
        require(compressed > 0 and decompressed > 0 and offset+compressed <= offset_table, 'invalid frame extent')
        frame = data[offset:offset+compressed]
        entry = dict(index=index, offset=offset, compressed_bytes=compressed,
                     decompressed_bytes=decompressed,
                     checksum=struct.unpack_from('<I', data, pos+8)[0] if checksum else None,
                     sha256=sha(frame), header=header(frame))
        frames.append(entry)
        offset += compressed
    require(offset == offset_table, 'unaccounted data bytes')
    return dict(frames=frames, frame_count=count, checksum_flag=checksum,
                seek_table_bytes=table_bytes, data_bytes=offset_table, descriptor=descriptor)


def table(data, parsed, checksum, hashes):
    width = 12 if checksum else 8
    pieces = []
    for f, digest in zip(parsed['frames'], hashes):
        value = struct.pack('<II', f['compressed_bytes'], f['decompressed_bytes'])
        if checksum:
            value += struct.pack('<I', digest)
        pieces.append(value)
    descriptor = (parsed['descriptor'] & 3) | (128 if checksum else 0)
    body = b''.join(pieces) + struct.pack('<IBI', parsed['frame_count'], descriptor, 0x8f92eab1)
    require(len(body) == parsed['frame_count']*width+9, 'table construction accounting')
    return data[:parsed['data_bytes']] + struct.pack('<II', 0x184d2a5e, len(body)) + body


def native_decoder():
    path = OLD / '.work/hw-gift-1b/c-state/libgift.so'
    env = load(P/'environment.json')
    require(sha(path.read_bytes()) == env['native_reader_sha256'], 'native decoder binary changed')
    lib = C.CDLL(str(path))
    lib.ZSTD_versionNumber.restype = C.c_uint
    require(lib.ZSTD_versionNumber() == 10507, 'wrong native zstd version')
    for name, args, result in (
        ('ZSTD_decompress', [C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t], C.c_size_t),
        ('ZSTD_findFrameCompressedSize', [C.c_void_p,C.c_size_t], C.c_size_t),
        ('ZSTD_isError', [C.c_size_t], C.c_uint),
        ('ZSTD_XXH64', [C.c_void_p,C.c_size_t,C.c_ulonglong], C.c_ulonglong)):
        fn = getattr(lib,name)
        fn.argtypes, fn.restype = args, result
    return lib


def decode_all(lib, data, parsed, source):
    hashes, offset, digest = [], 0, hashlib.sha256()
    for f in parsed['frames']:
        frame = data[f['offset']:f['offset']+f['compressed_bytes']]
        encoded = C.create_string_buffer(frame)
        extent = lib.ZSTD_findFrameCompressedSize(encoded, len(frame))
        require(not lib.ZSTD_isError(extent) and extent == len(frame), 'entry is not exactly one native frame')
        decoded = C.create_string_buffer(f['decompressed_bytes'])
        length = lib.ZSTD_decompress(decoded, len(decoded), encoded, len(frame))
        require(not lib.ZSTD_isError(length) and length == len(decoded), 'native decode error or wrong decoded size')
        raw = decoded.raw
        require(raw == source[offset:offset+length], 'restored bytes differ from input')
        low = int(lib.ZSTD_XXH64(decoded, length, 0) & 0xffffffff)
        if parsed['checksum_flag']:
            require(low == f['checksum'], 'seek-table XXH64 entry mismatch')
        hashes.append(low)
        offset += length
        digest.update(raw)
    require(offset == len(source) and digest.hexdigest() == sha(source), 'complete restoration mismatch')
    return hashes, dict(bit_perfect=True, source_bytes=offset, source_sha256=digest.hexdigest(),
                       seek_checksums_verified=parsed['checksum_flag'], frame_count=len(hashes))


def rebuild_minimal():
    REVIEW.mkdir(parents=True, exist_ok=True)
    binary = REVIEW/'independent-frame-probe'
    build = REVIEW/'independent-build.json'
    source = P/'frame_probe.c'
    library = ZSTD/'lib/libzstd.a'
    identity = dict(source_sha256=sha(source.read_bytes()), library_sha256=sha(library.read_bytes()))
    if build.exists():
        saved = load(build)
        require(all(saved[k] == v for k,v in identity.items()) and saved['binary_sha256'] == sha(binary.read_bytes()), 'review build changed')
    else:
        require(not binary.exists(), 'unrecorded review binary')
        command = ['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(ZSTD/'lib'),str(source),str(library),'-pthread','-o',str(binary)]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        (REVIEW/'build.stdout').write_bytes(result.stdout)
        (REVIEW/'build.stderr').write_bytes(result.stderr)
        build.write_bytes(packed(dict(identity,command=command,binary_sha256=sha(binary.read_bytes()))))
    input_path = REVIEW/'independent-slice.bin'
    raw = (OLD/'.work/inputs/enwik8').open('rb').read(262144)
    require(len(raw) == 262144 and sha(raw) == '0cdfd008d5327addbf5b118b4a8d616a8cc2971627727b10bfb20e97920881e7', 'minimal slice mismatch')
    if input_path.exists():
        require(input_path.read_bytes() == raw, 'review slice changed')
    else:
        input_path.write_bytes(raw)
    outputs = {}
    for name, hint, chunk in (('contrib',262144,131072),('pyzstd',0,262144)):
        target, receipt = REVIEW/(name+'.zst'), REVIEW/(name+'.json')
        command = [str(binary),str(input_path),str(target),'3',str(hint),str(chunk),'empty']
        if receipt.exists():
            saved = load(receipt)
            require(saved['command'] == command and saved['sha256'] == sha(target.read_bytes()), 'review minimal output changed')
        else:
            require(not target.exists(), 'incomplete minimal output: do not re-encode')
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            (REVIEW/(name+'.stdout')).write_bytes(result.stdout)
            (REVIEW/(name+'.stderr')).write_bytes(result.stderr)
            saved = dict(command=command,result=json.loads(result.stdout),sha256=sha(target.read_bytes()))
            receipt.write_bytes(packed(saved))
        outputs[name] = dict(sha256=sha(target.read_bytes()),bytes=target.stat().st_size,header=header(target.read_bytes()))
    return outputs


def main():
    minimal = rebuild_minimal()
    lib = native_decoder()
    records = sorted((load(path) for path in (P/'cases').glob('*.json')), key=lambda r:r['case_index'])
    require([r['case_index'] for r in records] == list(range(8)), 'incomplete eight-case matrix')
    source_cache, summaries, differing_512 = {}, [], []
    total_archives = total_frames = 0
    for case in records:
        chunk, g = case['chunk'], case['g']
        source_name = 'enwik8' if chunk.startswith('enwik8-') else 'silesia.tar'
        if source_name not in source_cache:
            source_cache[source_name] = (OLD/'.work/inputs'/source_name).read_bytes()
        source = source_cache[source_name]
        require(len(source) == case['input_bytes'] and sha(source) == case['input_sha256'], 'input receipt mismatch')
        frame_file = P/'cases'/case['frame_records_file']
        require(sha(frame_file.read_bytes()) == case['frame_records_sha256'], 'frame record file hash mismatch')
        evidence = [json.loads(line) for line in gzip.decompress(frame_file.read_bytes()).splitlines()]
        data, parsed, checksums, restoration = {}, {}, {}, {}
        for kind in ('original','pyzstd','patched'):
            ref = case['archives'][kind]
            data[kind] = Path(ref['path']).read_bytes()
            require(len(data[kind]) == ref['bytes'] and sha(data[kind]) == ref['sha256'], 'actual archive SHA or size mismatch')
            parsed[kind] = archive(data[kind])
            require(parsed[kind]['frame_count'] == len(evidence) == case['frame_count'], 'frame count mismatch')
            require(parsed[kind]['seek_table_bytes'] == ref['seek_table_bytes'] and parsed[kind]['data_bytes'] == ref['data_bytes'], 'table receipt accounting mismatch')
            for i,f in enumerate(parsed[kind]['frames']):
                require(f == evidence[i]['variants'][kind], 'independent parsed frame/header differs from retained raw record')
            checksums[kind], restoration[kind] = decode_all(lib,data[kind],parsed[kind],source)
            if kind in ('original','pyzstd'):
                inventory = ROOT/'evidence/hw-gift-1b'/('c-baseline' if kind=='original' else '')/chunk/'archives.json'
                old = [a for a in load(inventory) if a['g'] == g]
                if old:
                    require(old[0]['bytes'] == len(data[kind]) and old[0]['sha256'] == sha(data[kind]), 'reference does not reproduce accepted 1b archive')
            total_archives += 1
            total_frames += parsed[kind]['frame_count']
        for i, (p, fixed) in enumerate(zip(parsed['pyzstd']['frames'],parsed['patched']['frames'])):
            pa = data['pyzstd'][p['offset']:p['offset']+p['compressed_bytes']]
            fa = data['patched'][fixed['offset']:fixed['offset']+fixed['compressed_bytes']]
            require(pa == fa, 'patched frame not byte-identical to pyzstd')
        require(table(data['patched'],parsed['patched'],False,checksums['patched']) == data['pyzstd'], 'removing table checksum does not reproduce pyzstd archive')
        require(table(data['pyzstd'],parsed['pyzstd'],True,checksums['pyzstd']) == data['patched'], 'adding table checksums does not reproduce patched archive')
        count = parsed['original']['frame_count']
        require(len(data['patched'])-len(data['pyzstd']) == 4*count, 'unexplained archive remainder')
        if chunk == 'enwik8-L3' and g == 262144:
            for name,kind in (('contrib','original'),('pyzstd','pyzstd')):
                f = parsed[kind]['frames'][0]
                actual = data[kind][f['offset']:f['offset']+f['compressed_bytes']]
                require((REVIEW/(name+'.zst')).read_bytes() == actual, 'independently re-encoded minimal frame differs from actual archive frame 0')
        if chunk == 'enwik8-L3' and g == 524288:
            for original, py in zip(parsed['original']['frames'],parsed['pyzstd']['frames']):
                a = data['original'][original['offset']:original['offset']+original['compressed_bytes']]
                b = data['pyzstd'][py['offset']:py['offset']+py['compressed_bytes']]
                require(len(a) == len(b), '512 KiB frame lengths differ')
                positions = [j for j,(x,y) in enumerate(zip(a,b)) if x != y]
                require(positions == [5], '512 KiB data frames differ beyond the window-descriptor byte')
                differing_512.append(dict(index=original['index'],decompressed_bytes=original['decompressed_bytes'],compressed_bytes=len(a),
                                          positions=positions,original_byte=a[5],pyzstd_byte=b[5],
                                          original_window=original['header']['window_size'],pyzstd_window=py['header']['window_size']))
            require(len(differing_512) == 191, 'unexpected 512 KiB frame count')
        summary = dict(case_index=case['case_index'],chunk=chunk,g=g,frame_count=count,
                       original_bytes=len(data['original']),patched_bytes=len(data['patched']),pyzstd_bytes=len(data['pyzstd']),
                       patched_minus_original=len(data['patched'])-len(data['original']),
                       pyzstd_minus_original_data=parsed['pyzstd']['data_bytes']-parsed['original']['data_bytes'],
                       residual_bytes=len(data['patched'])-len(data['pyzstd']),
                       patched_frames_byte_identical_to_pyzstd=count,restoration=restoration,
                       archive_sha256={kind:sha(raw) for kind,raw in data.items()})
        summaries.append(summary)
        print('INDEPENDENT_CASE_PASS',case['case_index'],chunk,g,count,flush=True)
    result = dict(status='PASS',no_clocks=True,minimal_encodings_authorized=2,minimal=minimal,
                  archives_verified=total_archives,frame_decodes_verified=total_frames,cases=summaries,
                  frame_512_byte_differences=differing_512,
                  source_sha256=sha(Path(__file__).read_bytes()),native_decoder_sha256=sha((OLD/'.work/hw-gift-1b/c-state/libgift.so').read_bytes()),
                  observed_head=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip())
    (REVIEW/'independent-audit.json').write_bytes(packed(result))
    with (REVIEW/'independent-cases.csv').open('w',encoding='utf-8',newline='') as stream:
        fields=['case_index','chunk','g','frame_count','original_bytes','patched_bytes','pyzstd_bytes','patched_minus_original','pyzstd_minus_original_data','residual_bytes']
        writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');writer.writeheader()
        writer.writerows({k:r[k] for k in fields} for r in summaries)
    print('INDEPENDENT_AUDIT_PASS',sha((REVIEW/'independent-audit.json').read_bytes()),total_archives,total_frames,flush=True)


if __name__ == '__main__':
    main()
