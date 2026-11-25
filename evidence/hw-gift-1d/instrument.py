"""Resident native grid instrument. No compilation or measurement on import.

evaluate() returns {results: [...], clock_calls, input_bytes, input_sha256,
control_override}. Each slot is retained separately, including original/original
method pairs. Only timed_worker() admits production or method-control timing.
"""
import argparse
import ast
import ctypes as ct
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = ROOT / '.work/hw-gift-1d'
OLD = Path('/home/ubuntu/hw-apex-bench-hw-gift-1b')
ZSTD = OLD / '.work/hw-gift-1b/zstd'
INPUTS = OLD / '.work/inputs'
PIN = 'f8745da6ff1ad1e7bab384bd1f9d742439278e99'
FRAMES = (256, 1024, 4096, 16384, 65536, 262144, 524288)
LEVELS = (3, 10, 19)
CORPORA = {'enwik8': (100000000, '2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8'),
           'silesia.tar': (211947520, 'a667bac80089b3d04d5496772149e632f0758974b0579d743cd8d6e5e0d63eb2')}
LOCK = '/run/lock/ovh-bench.lock'
TELEMETRY = b'\nsize_t probe_context_bytes(const ZSTD_seekable_CStream *ctx) { return ZSTD_sizeof_CCtx(ctx->cstream); }\n'


def check(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def immutable(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        check(path.read_bytes() == data, 'saved bytes changed: ' + str(path))
    else:
        with path.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())


def save(path, value):
    immutable(path, packed(value))


def git(*args, repo=ROOT):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def committed(path):
    relative = Path(path).relative_to(ROOT).as_posix()
    check(Path(path).is_file(), 'missing committed protocol: ' + relative)
    check(not git('status', '--porcelain', '--', relative).strip(), 'uncommitted protocol: ' + relative)
    commit = git('log', '-1', '--format=%H', '--', relative).decode().strip()
    check(len(commit) == 40 and git('show', f'{commit}:{relative}') == Path(path).read_bytes(), 'protocol is not committed')
    return dict(commit=commit, sha256=file_sha(path))


def bridge_source():
    path = ROOT / 'evidence/hw-gift-1c/timing.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    values = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == 'BRIDGE' for t in node.targets)]
    check(len(values) == 1 and isinstance(values[0], str), '1c native bridge literal changed')
    return values[0].encode()


def admission():
    check(sys.platform == 'linux' and platform.node() == 'ace-core', 'ace-core Linux required')
    check(git('branch', '--show-current').decode().strip() == 'hw-gift-1d', 'wrong branch')
    check(not git('status', '--porcelain', '--', 'evidence/hw-gift-1d/instrument.py').strip(), 'uncommitted instrument')
    protocol = committed(HERE / 'CALIBRATION.md')
    check(git('rev-parse', 'HEAD', repo=ZSTD).decode().strip() == PIN
          and not git('status', '--porcelain', repo=ZSTD).strip(), 'pinned zstd source changed')
    return protocol


def build(threshold=None, allow_create=True):
    """Base and conditional receipts are separate; adding C never changes A/B."""
    protocol = admission()
    upstream = ZSTD / 'contrib/seekable_format'
    original = (upstream / 'zstdseek_compress.c').read_bytes()
    before = b'ZSTD_c_srcSizeHint, (int)zcs->maxFrameSize'
    check(original.count(before) == 1, 'srcSizeHint patch location changed')
    bridge = bridge_source()
    if threshold is None:
        folder = STATE / 'native/base'
        texts = {'original': original, 'nohint': original.replace(before, b'ZSTD_c_srcSizeHint, 0')}
        conditional_protocol, base_sha = None, None
    else:
        check(type(threshold) is int and 1024 <= threshold <= 65536, 'conditional X must be between 1 and 64 KiB')
        build(allow_create=allow_create)
        base_sha = file_sha(STATE / 'native/base/build.json')
        conditional_protocol = committed(HERE / 'CONDITIONAL_PROTOCOL.md')
        folder = STATE / f'native/conditional-{threshold}'
        replacement = f'ZSTD_c_srcSizeHint, zcs->maxFrameSize < {threshold} ? (int)zcs->maxFrameSize : 0'.encode()
        texts = {'conditional': original.replace(before, replacement)}
    payload = {'bridge.c': bridge, 'decompress.c': (upstream / 'zstdseek_decompress.c').read_bytes()}
    payload.update({variant + '-compress.c': text + TELEMETRY for variant, text in texts.items()})
    identity = dict(protocol=protocol, instrument_sha256=file_sha(__file__), zstd_commit=PIN,
                    static_library_sha256=file_sha(ZSTD / 'lib/libzstd.a'),
                    source_sha256={name: sha(value) for name, value in payload.items()},
                    upstream_compress_sha256=sha(original), telemetry_sha256=sha(TELEMETRY),
                    bridge_source_sha256=file_sha(ROOT / 'evidence/hw-gift-1c/timing.py'),
                    threshold=threshold, conditional_protocol=conditional_protocol, base_build_sha256=base_sha)
    receipt = folder / 'build.json'
    if receipt.exists():
        saved = json.loads(receipt.read_bytes())
        check(saved['identity'] == identity, 'native build identity changed')
        for name, expected in identity['source_sha256'].items():
            check(file_sha(folder / name) == expected, 'native source copy changed')
        for variant, info in saved['libraries'].items():
            check(file_sha(folder / f'{variant}.so') == info['sha256'], 'native library changed')
        return saved
    check(allow_create and not os.environ.get('OVH_BENCH_LOCK_HELD'), 'build libraries outside the benchmark lock first')
    folder.mkdir(parents=True, exist_ok=True)
    check(not any(folder.glob('*.so')), 'unrecorded native build; inspect before retrying')
    for name, data in payload.items():
        immutable(folder / name, data)
    libraries = {}
    for variant in texts:
        output = folder / f'{variant}.so'
        args = ['cc', '-O3', '-fPIC', '-shared', '-Wall', '-Wextra', '-Werror', '-Wl,-Bsymbolic',
                '-DXXH_NAMESPACE=ZSTD_', '-I' + str(upstream), '-I' + str(ZSTD / 'lib'),
                '-I' + str(ZSTD / 'lib/common'), str(folder / 'bridge.c'), str(folder / f'{variant}-compress.c'),
                str(folder / 'decompress.c'), str(ZSTD / 'lib/libzstd.a'), '-pthread', '-o', str(output)]
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        immutable(folder / f'{variant}-build.stdout', result.stdout)
        immutable(folder / f'{variant}-build.stderr', result.stderr)
        result.check_returncode()
        libraries[variant] = dict(path=str(output), sha256=file_sha(output), command=args)
    value = dict(schema='hw-gift-1d-native-v1', identity=identity, libraries=libraries,
                 compiler=subprocess.check_output(['cc', '--version']).decode().splitlines()[0])
    save(receipt, value)
    return value


def request(corpus, L, G, variants=('original', 'nohint'), threshold=None):
    check(corpus in CORPORA and type(L) is int and L in LEVELS and type(G) is int and G in FRAMES, 'cell outside the fixed grid')
    variants = list(variants)
    check(variants and len(variants) == len(set(variants)) and set(variants) <= {'original', 'nohint', 'conditional'}, 'invalid cell variants')
    build()
    conditional = build(threshold) if 'conditional' in variants else None
    check(conditional is not None or threshold is None, 'X applies only to conditional cells')
    source = INPUTS / corpus
    raw = source.read_bytes()
    full_size, full_sha = CORPORA[corpus]
    check(len(raw) == full_size and sha(raw) == full_sha, 'full corpus identity changed')
    prefix = 16 << 20 if G in (256, 1024) else None
    if prefix is not None:
        raw = raw[:prefix]
    input_sha = sha(raw)
    frozen = STATE / 'inputs' / f'{input_sha}.bin'
    immutable(frozen, raw)
    protocol = committed(HERE / 'CALIBRATION.md')
    value = dict(schema='hw-gift-1d-cell-v1', corpus=corpus, level=L, g=G, variants=variants,
                 threshold=threshold, input_path=str(frozen), input_bytes=len(raw), input_sha256=input_sha,
                 full_corpus_bytes=full_size, full_corpus_sha256=full_sha, prefix_bytes=prefix,
                 protocol_commit=protocol['commit'], protocol_sha256=protocol['sha256'],
                 instrument_sha256=file_sha(__file__), base_build_sha256=file_sha(STATE / 'native/base/build.json'),
                 conditional_build_sha256=file_sha(STATE / f'native/conditional-{threshold}/build.json') if conditional else None)
    label = 'enwik8' if corpus == 'enwik8' else 'silesia'
    value['cell_id'] = f'{label}-L{L}-G{G}-' + sha(packed(value))[:16]
    return value


def validate_cell(cell):
    check(cell['schema'] == 'hw-gift-1d-cell-v1' and cell['corpus'] in CORPORA
          and cell['level'] in LEVELS and cell['g'] in FRAMES, 'invalid grid cell')
    check(cell['instrument_sha256'] == file_sha(__file__), 'cell instrument changed')
    base = build(allow_create=False)
    check(file_sha(STATE / 'native/base/build.json') == cell['base_build_sha256'], 'cell native base changed')
    check(cell['protocol_commit'] == base['identity']['protocol']['commit']
          and cell['protocol_sha256'] == base['identity']['protocol']['sha256'], 'cell preregistration changed')
    full_size, full_sha = CORPORA[cell['corpus']]
    prefix = 16 << 20 if cell['g'] in (256, 1024) else None
    check((cell['full_corpus_bytes'], cell['full_corpus_sha256'], cell['prefix_bytes'], cell['input_bytes'])
          == (full_size, full_sha, prefix, prefix or full_size), 'cell input scope changed')
    frozen = Path(cell['input_path']).resolve()
    check(frozen.is_relative_to((STATE / 'inputs').resolve()), 'frozen input escaped private state')
    original = dict(cell)
    supplied_id = original.pop('cell_id')
    label = 'enwik8' if cell['corpus'] == 'enwik8' else 'silesia'
    check(supplied_id == f"{label}-L{cell['level']}-G{cell['g']}-" + sha(packed(original))[:16], 'cell identity changed')
    if 'conditional' in cell['variants']:
        build(cell['threshold'], allow_create=False)
        check(file_sha(STATE / f"native/conditional-{cell['threshold']}/build.json") == cell['conditional_build_sha256'], 'conditional cell build changed')
    return cell


def load(variant, threshold=None):
    folder = STATE / (f'native/conditional-{threshold}' if variant == 'conditional' else 'native/base')
    lib = ct.CDLL(str(folder / f'{variant}.so'), mode=ct.RTLD_LOCAL)
    ptr, size = ct.c_void_p, ct.c_size_t
    methods = {'ZSTD_versionNumber': ([], ct.c_uint), 'ZSTD_isError': ([size], ct.c_uint),
               'ZSTD_getErrorName': ([size], ct.c_char_p), 'ZSTD_decompress': ([ptr, size, ptr, size], size),
               'ZSTD_seekable_createCStream': ([], ptr), 'ZSTD_seekable_initCStream': ([ptr, ct.c_int, ct.c_int, ct.c_uint], size),
               'ZSTD_seekable_freeCStream': ([ptr], size), 'probe_encode': ([ptr, ptr, size, ptr, size], size),
               'probe_context_bytes': ([ptr], size), 'ZSTD_seekable_create': ([], ptr),
               'ZSTD_seekable_free': ([ptr], size), 'ZSTD_seekable_initBuff': ([ptr, ptr, size], size),
               'ZSTD_seekable_decompress': ([ptr, ptr, size, ct.c_ulonglong], size)}
    for name, (arguments, returns) in methods.items():
        fn = getattr(lib, name)
        fn.argtypes, fn.restype = arguments, returns
    check(lib.ZSTD_versionNumber() == 10507, 'wrong native zstd version')
    return lib


def native_check(lib, code):
    check(not lib.ZSTD_isError(code), lib.ZSTD_getErrorName(code).decode())


def header(data):
    spec = importlib.util.spec_from_file_location('_gift1d_seekable', ROOT / 'evidence/hw-gift-1c/seekable.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    count, descriptor, magic = struct.unpack_from('<IBI', data, len(data) - 9)
    check(magic == 0x8F92EAB1 and descriptor == 128 and count > 0, 'archive seek table or checksum flag changed')
    table_bytes = 17 + count * 12
    check(len(data) >= table_bytes and struct.unpack_from('<I', data, len(data) - table_bytes)[0] == 0x184D2A5E,
          'invalid complete seek table')
    return module.parse_header(data), count, table_bytes


def evaluate(cell, order, clock=None, decode=False, input_override=None):
    """Native calls only inside intervals; every produced archive is restored."""
    validate_cell(cell)
    order = list(order)
    check(order and all(v in cell['variants'] for v in order), 'order contains a variant outside this cell')
    if clock is not None:
        check(os.environ.get('OVH_BENCH_LOCK_HELD') == LOCK and os.sched_getaffinity(0) == {0}, 'timing requires OVH lock and CPU 0')
    check(input_override is None or clock is None, 'changed-input controls must be untimed')
    raw = Path(cell['input_path']).read_bytes() if input_override is None else bytes(input_override)
    if input_override is None:
        check(len(raw) == cell['input_bytes'] and sha(raw) == cell['input_sha256'], 'frozen input changed')
    check(raw, 'empty probe input')
    input_sha = sha(raw)
    source = ct.create_string_buffer(raw, len(raw))
    capacity = 2 * len(raw) + 17 + 12 * ((len(raw) + cell['g'] - 1) // cell['g']) + (1 << 20)
    slots, results, calls = [], [], 0
    try:
        for index, variant in enumerate(order):
            lib = load(variant, cell['threshold'])
            encoded, restored = ct.create_string_buffer(capacity), ct.create_string_buffer(len(raw))
            ct.memset(encoded, 0xA5, capacity)
            ct.memset(restored, 0xA5, len(raw))
            encoder = lib.ZSTD_seekable_createCStream()
            check(bool(encoder), 'fresh encoder creation failed')
            native_check(lib, lib.ZSTD_seekable_initCStream(encoder, cell['level'], 1, cell['g']))
            slots.append(dict(slot=index, variant=variant, lib=lib, encoder=encoder, decoder=None,
                              encoded=encoded, restored=restored, compression_ns=None, decode_ns=None))
        # All A/B/C encoder contexts and buffers are ready before the first clock.
        for slot in slots:
            if clock is not None:
                start = clock(); calls += 1
            length = slot['lib'].probe_encode(slot['encoder'], source, len(raw), slot['encoded'], capacity)
            if clock is not None:
                slot['compression_ns'] = clock() - start; calls += 1
            native_check(slot['lib'], length)
            check(length <= capacity, 'native encoder exceeded capacity')
            slot['length'] = length
        for slot in slots:
            slot['decoder'] = slot['lib'].ZSTD_seekable_create()
            check(bool(slot['decoder']), 'fresh decoder creation failed')
            native_check(slot['lib'], slot['lib'].ZSTD_seekable_initBuff(slot['decoder'], slot['encoded'], slot['length']))
        for slot in slots:
            if clock is not None and decode:
                start = clock(); calls += 1
            length = slot['lib'].ZSTD_seekable_decompress(slot['decoder'], slot['restored'], len(raw), 0)
            if clock is not None and decode:
                slot['decode_ns'] = clock() - start; calls += 1
            native_check(slot['lib'], length)
            restored = ct.string_at(slot['restored'], length)
            check(length == len(raw) and restored == raw, 'native archive restore differs')
            data = ct.string_at(slot['encoded'], slot['length'])
            digest = sha(data)
            wire, frame_count, table_bytes = header(data)
            library = (STATE / (f"native/conditional-{cell['threshold']}" if slot['variant'] == 'conditional' else 'native/base') / f"{slot['variant']}.so")
            key = sha(packed(dict(input_sha256=input_sha, level=cell['level'], g=cell['g'],
                                 variant=slot['variant'], library_sha256=file_sha(library))))
            cache = STATE / ('controls' if input_override is not None else 'archives') / f'{key}.zst'
            immutable(cache, data)
            result = dict(slot=slot['slot'], variant=slot['variant'], compression_ns=slot['compression_ns'],
                          decode_ns=slot['decode_ns'], archive_bytes=len(data), archive_sha256=digest,
                          archive_path=str(cache), decoded_bytes=length, decoded_sha256=sha(restored),
                          bit_perfect=True, context_bytes=slot['lib'].probe_context_bytes(slot['encoder']),
                          header=wire, frame_count=frame_count, seek_table_bytes=table_bytes, seek_checksum_flag=True)
            if clock is not None:
                check(type(result['compression_ns']) is int and result['compression_ns'] > 0, 'invalid compression interval')
                if decode:
                    check(type(result['decode_ns']) is int and result['decode_ns'] > 0, 'invalid decode interval')
            results.append(result)
    finally:
        for slot in slots:
            if slot['decoder']:
                slot['lib'].ZSTD_seekable_free(slot['decoder'])
            slot['lib'].ZSTD_seekable_freeCStream(slot['encoder'])
    return dict(results=results, clock_calls=calls, input_bytes=len(raw), input_sha256=input_sha,
                control_override=input_override is not None)


def cell_sha(cell):
    return sha(packed(cell))


def selfcheck_path(cell):
    return STATE / 'cells' / cell['cell_id'] / 'selfcheck.json'


def untimed_selfcheck(cell):
    validate_cell(cell)
    path = selfcheck_path(cell)
    if path.exists():
        old = json.loads(path.read_bytes())
        check(old['status'] == 'PASS' and old['cell_sha256'] == cell_sha(cell) and old['clock_calls'] == 0,
              'saved untimed selfcheck changed')
        for result in old['results']:
            check(file_sha(result['archive_path']) == result['archive_sha256'], 'saved selfcheck archive changed')
        return old
    value = evaluate(cell, cell['variants'], clock=None)
    known = cell['corpus'] == 'enwik8' and cell['level'] == 3 and cell['g'] == 262144
    if known:
        previous = json.loads((ROOT / 'evidence/hw-gift-1c/cases/enwik8-L3-262144.json').read_bytes())
        for result in value['results']:
            variant = 'original' if result['variant'] == 'original' else 'patched'
            # The conditional writer selects exactly one of the two policies.
            if result['variant'] == 'conditional' and cell['g'] < cell['threshold']:
                variant = 'original'
            expected = previous['archives'][variant]
            check((result['archive_bytes'], result['archive_sha256']) == (expected['bytes'], expected['sha256']),
                  'known HW-GIFT-1c archive is not reproduced')
    result = dict(schema='hw-gift-1d-selfcheck-v1', status='PASS', measurements_of_time=False,
                  cell_id=cell['cell_id'], cell_sha256=cell_sha(cell), clock_calls=0,
                  known_1c_checked=known, results=value['results'])
    save(path, result)
    return result


def timed_worker(cell, pair_index, order=('original', 'nohint'), decode=False,
                 method=False, method_check=None, output=None):
    validate_cell(cell)
    check(type(pair_index) is int and 0 <= pair_index < 5, 'pair index must be 0..4')
    check(os.environ.get('OVH_BENCH_LOCK_HELD') == LOCK and os.sched_getaffinity(0) == {0}, 'worker requires the shared OVH lock and CPU 0')
    control_path = selfcheck_path(cell)
    check(control_path.exists(), 'untimed cell selfcheck must pass before timing')
    control = untimed_selfcheck(cell)  # Saved receipt path never encodes again.
    order = list(order)
    if method:
        check(cell['corpus'] == 'enwik8' and cell['level'] == 3 and cell['g'] == 262144
              and order == ['original', 'original'], 'only the predefined AA timing control bypasses the main gate')
    else:
        check(len(order) in (2, 3) and sorted(order) == sorted(cell['variants']), 'production order must contain each cell variant once')
        gate = json.loads(Path(method_check or HERE / 'method-check.json').read_bytes())
        check(gate['status'] == 'PASS' and gate['protocol_sha256'] == cell['protocol_sha256']
              and gate['instrument_sha256'] == cell['instrument_sha256'], 'method controls must pass before the main grid')
    if output is not None:
        output = Path(output).resolve()
        check(output.is_relative_to(ROOT.resolve()) and not output.exists(), 'worker output must be new and inside this checkout')
    import time
    result = evaluate(cell, order, clock=time.perf_counter_ns, decode=decode)
    expected = {r['variant']: (r['archive_bytes'], r['archive_sha256']) for r in control['results']}
    for row in result['results']:
        check((row['archive_bytes'], row['archive_sha256']) == expected[row['variant']], 'timed archive differs from first untimed cell manifest')
    result.update(schema='hw-gift-1d-worker-v1', cell_id=cell['cell_id'], cell_sha256=cell_sha(cell),
                  pair_index=pair_index, order=order, decode_timed=bool(decode), method_control=bool(method),
                  measurements_of_time=True, protocol_sha256=cell['protocol_sha256'],
                  instrument_sha256=cell['instrument_sha256'], selfcheck_sha256=file_sha(control_path),
                  cpu_affinity=[0], lock_path=LOCK,
                  timer_scope='native API loops only; init/prefault/hash/byte validation outside; first-use codec workspace allocation inside')
    if output is not None:
        save(output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'request', 'selfcheck', 'worker'))
    parser.add_argument('--cell', type=Path)
    parser.add_argument('--corpus', choices=CORPORA)
    parser.add_argument('--level', type=int)
    parser.add_argument('--frame', type=int)
    parser.add_argument('--variants', default='original,nohint')
    parser.add_argument('--threshold', type=int)
    parser.add_argument('--pair', type=int)
    parser.add_argument('--order', default='original,nohint')
    parser.add_argument('--decode', action='store_true')
    parser.add_argument('--method', action='store_true')
    parser.add_argument('--method-check', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.action == 'build':
        value = build(args.threshold)
    elif args.action == 'request':
        value = request(args.corpus, args.level, args.frame, args.variants.split(','), args.threshold)
        if args.output:
            save(args.output, value)
    else:
        check(args.cell is not None, '--cell is required')
        cell = json.loads(args.cell.read_bytes())
        if args.action == 'selfcheck':
            value = untimed_selfcheck(cell)
            if args.output:
                save(args.output, value)
        else:
            value = timed_worker(cell, args.pair, args.order.split(','), args.decode, args.method, args.method_check, args.output)
    print(json.dumps(value, sort_keys=True, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    main()
