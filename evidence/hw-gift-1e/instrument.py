"""HW-GIFT-1e resident native instrument; import performs no native operation.

A adds the PR #3544 assert and hint setter to the frozen v1.5.4 seekable
writer; B is that unmodified writer, with the setter absent. Both core versions
use the same writer/header/decoder/bridge bytes. Only native encode loops are
timed; every output is fully restored after all compression intervals.
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
import shutil
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = ROOT / '.work/hw-gift-1e'
CORES = STATE / 'cores'
FROZEN = STATE / 'frozen'
INPUTS = Path('/home/ubuntu/hw-apex-bench-hw-gift-1b/.work/inputs')
PINS = {'v1.5.4': '945f27758c0fd67b636103a38dbf050266c6b90a',
        'v1.5.7': 'f8745da6ff1ad1e7bab384bd1f9d742439278e99'}
VERSIONS = {'v1.5.4': 10504, 'v1.5.7': 10507}
CALIBRATION_COMMIT = '8b1fba61c325a4020dbad165a058d91848f9f914'
FULL_BYTES = 100000000
FULL_SHA256 = '2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8'
PREFIX_BYTES = 16 << 20
CASES = ((10, 256), (10, 1024), (3, 256))
LOCK = '/run/lock/ovh-bench.lock'
VARIANTS = ('A', 'B')
HINT_LINES = (b'    assert(zcs->maxFrameSize < INT_MAX);\n'
              b'    ZSTD_CCtx_setParameter(zcs->cstream, ZSTD_c_srcSizeHint, (int)zcs->maxFrameSize);\n')


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
    check(Path(path).is_file(), 'missing protocol: ' + relative)
    check(not git('status', '--porcelain', '--', relative).strip(), 'uncommitted protocol: ' + relative)
    commit = git('log', '-1', '--format=%H', '--', relative).decode().strip()
    check(len(commit) == 40 and git('show', f'{commit}:{relative}') == Path(path).read_bytes(), 'protocol is not committed')
    return dict(commit=commit, sha256=file_sha(path))


def bridge_source():
    path = ROOT / 'evidence/hw-gift-1c/timing.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    values = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == 'BRIDGE' for t in node.targets)]
    check(len(values) == 1 and isinstance(values[0], str), 'known native bridge literal changed')
    return values[0].encode()


def admission():
    check(sys.platform == 'linux' and platform.node() == 'ace-core', 'ace-core Linux required')
    check('AMD EPYC 4344P' in Path('/proc/cpuinfo').read_text(), 'declared AMD EPYC 4344P required')
    check(git('branch', '--show-current').decode().strip() == 'hw-gift-1e', 'wrong branch')
    instrument = 'evidence/hw-gift-1e/instrument.py'
    check(not git('status', '--porcelain', '--', instrument).strip(), 'instrument must be committed before preparation')
    calibration = committed(HERE / 'CALIBRATION.md')
    check(git('show', f'{CALIBRATION_COMMIT}:evidence/hw-gift-1e/CALIBRATION.md')
          == (HERE / 'CALIBRATION.md').read_bytes(), 'first preregistration bytes changed')
    execution = committed(HERE / 'PROTOCOL.md')
    return dict(calibration=calibration, execution_protocol=execution)


def writer_payloads():
    """Prove frozen B is tagged v1.5.4 and A is exactly the two-line patch."""
    upstream = 'contrib/seekable_format/'
    base = CORES / 'v1.5.4'
    original = (FROZEN / 'B-compress.c').read_bytes()
    decoder = (FROZEN / 'decompress.c').read_bytes()
    header = (FROZEN / 'zstd_seekable.h').read_bytes()
    for name, data in (('zstdseek_compress.c', original), ('zstdseek_decompress.c', decoder), ('zstd_seekable.h', header)):
        check(data == git('show', PINS['v1.5.4'] + ':' + upstream + name, repo=base), 'frozen v1.5.4 source changed: ' + name)
    check(b'ZSTD_c_srcSizeHint' not in original, 'B must contain no hint setter')
    later = git('show', PINS['v1.5.7'] + ':' + upstream + 'zstdseek_compress.c', repo=CORES / 'v1.5.7')
    check(later.count(HINT_LINES) == 1 and later.replace(HINT_LINES, b'') == original,
          'tagged writer difference is not exactly the PR assert/setter')
    original_with_hint = (FROZEN / 'A-compress.c').read_bytes()
    check(original_with_hint == later, 'frozen A is not exactly the tagged two-line writer')
    check(original_with_hint.count(b'ZSTD_c_srcSizeHint') == 1, 'A must contain one hint setter')
    bridge = (FROZEN / 'bridge.c').read_bytes()
    check(bridge == bridge_source(), 'frozen resident bridge is not the literal 1c bridge')
    return {'bridge.c': bridge, 'zstd_seekable.h': header, 'decompress.c': decoder,
            'A-compress.c': original_with_hint, 'B-compress.c': original}


def build(core, allow_create=True):
    check(core in PINS, 'unsupported core; a bisect core requires its separate protocol')
    protocol = admission()
    checkout = CORES / core
    check(git('rev-parse', 'HEAD', repo=checkout).decode().strip() == PINS[core]
          and not git('status', '--porcelain', '--untracked-files=no', repo=checkout).strip(), 'core checkout changed')
    setup_path = STATE / 'setup.json'
    setup = json.loads(setup_path.read_bytes())
    check(setup['schema'] == 'hw-gift-1e-setup-v1' and setup['no_clocks'] is True
          and setup['measurements_of_time'] is False and setup['cflags'] == '-O3 -fPIC -fno-lto',
          'separately recorded core setup with common no-LTO flags is required')
    check(setup['protocol']['commit'] == CALIBRATION_COMMIT
          and setup['protocol']['sha256'] == protocol['calibration']['sha256']
          and setup['protocol']['setup_sha256'] == file_sha(HERE / 'setup.py'), 'setup protocol/source changed')
    compiler = Path(shutil.which('cc') or '').resolve()
    check(compiler.is_file() and file_sha(compiler) == setup['compiler']['sha256']
          and subprocess.check_output(['cc', '--version']).decode() == setup['compiler']['version'], 'setup compiler changed')
    prepared = setup['cores'][core]
    check(prepared['commit'] == PINS[core] and prepared['source_clean'] is True,
          'setup core source pin changed')
    check(prepared['version'] == prepared['expected_version_number'] == VERSIONS[core], 'setup core version changed')
    for name, digest in prepared['headers_sha256'].items():
        source_header = (checkout / name).resolve()
        check(source_header.is_relative_to((checkout / 'lib').resolve()) and file_sha(source_header) == digest,
              'prepared core header changed: ' + name)
    for record in prepared['build_commands']:
        check(file_sha(record['stdout_path']) == record['stdout_sha256']
              and file_sha(record['stderr_path']) == record['stderr_sha256'], 'prepared build logs changed')
    payload = writer_payloads()
    check(setup['frozen']['source_sha256'] == {name: sha(data) for name, data in payload.items()},
          'setup frozen payload bindings differ')
    folder = STATE / 'native' / core
    library = checkout / 'lib/libzstd.a'
    cli = checkout / 'programs/zstd'
    check(library.is_file() and cli.is_file(), 'core static library and CLI must be built outside the instrument first')
    check(Path(prepared['library_path']).resolve() == library.resolve()
          and prepared['library_sha256'] == file_sha(library)
          and Path(prepared['cli_path']).resolve() == cli.resolve()
          and prepared['cli_sha256'] == file_sha(cli), 'prepared core binary identity changed')
    cli_version = subprocess.check_output([str(cli), '-V'], stderr=subprocess.STDOUT).decode().strip()
    check(core.removeprefix('v') in cli_version and prepared['cli_version'] == cli_version, 'core CLI reports wrong version')
    headers = {name: file_sha(checkout / 'lib' / name) for name in ('zstd.h', 'zstd_errors.h')}
    headers.update({'common/' + p.name: file_sha(p) for p in sorted((checkout / 'lib/common').glob('*.h'))})
    identity = dict(core=core, core_commit=PINS[core], protocol=protocol, instrument_sha256=file_sha(__file__),
                    setup_sha256=file_sha(setup_path), core_setup=prepared,
                    frozen_from_commit=PINS['v1.5.4'], source_sha256={name: sha(data) for name, data in payload.items()},
                    core_headers_sha256=headers, static_library_sha256=file_sha(library),
                    cli_sha256=file_sha(cli), cli_version=cli_version,
                    bridge_source_sha256=file_sha(ROOT / 'evidence/hw-gift-1c/timing.py'),
                    hint_patch_sha256=sha(HINT_LINES), hint_A='setter present', hint_B='setter absent',
                    flags=['-O3', '-fPIC', '-fno-lto', '-shared', '-Wl,-Bsymbolic'], loader='RTLD_LOCAL')
    receipt = folder / 'build.json'
    if receipt.exists():
        saved = json.loads(receipt.read_bytes())
        check(saved['identity'] == identity, 'native build identity changed')
        check(set(saved['libraries']) == set(VARIANTS), 'saved native receipt is missing a writer')
        for name, digest in identity['source_sha256'].items():
            check(file_sha(folder / name) == digest, 'native frozen source copy changed')
        for variant, record in saved['libraries'].items():
            check(file_sha(folder / f'{variant}.so') == record['sha256'], 'native shared library changed')
        return saved
    check(allow_create and not os.environ.get('OVH_BENCH_LOCK_HELD'), 'build shared libraries outside the OVH benchmark lock first')
    folder.mkdir(parents=True, exist_ok=True)
    check(not any(folder.glob('*.so')), 'unrecorded shared library: inspect instead of rebuilding')
    for name, data in payload.items():
        immutable(folder / name, data)
    libraries = {}
    for variant in VARIANTS:
        output = folder / f'{variant}.so'
        command = ['cc', '-O3', '-fPIC', '-fno-lto', '-shared', '-Wall', '-Wextra', '-Werror', '-Wl,-Bsymbolic',
                   '-DXXH_NAMESPACE=ZSTD_', '-I' + str(folder), '-I' + str(checkout / 'lib'),
                   '-I' + str(checkout / 'lib/common'), str(folder / 'bridge.c'), str(folder / f'{variant}-compress.c'),
                   str(folder / 'decompress.c'), str(library), '-pthread', '-o', str(output)]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        immutable(folder / f'{variant}-build.stdout', result.stdout)
        immutable(folder / f'{variant}-build.stderr', result.stderr)
        result.check_returncode()
        lib = load(core, variant)
        libraries[variant] = dict(path=str(output), sha256=file_sha(output), command=command,
                                  zstd_version_number=lib.ZSTD_versionNumber(),
                                  zstd_version_string=lib.ZSTD_versionString().decode())
    value = dict(schema='hw-gift-1e-native-v1', identity=identity, libraries=libraries,
                 compiler=subprocess.check_output(['cc', '--version']).decode().splitlines()[0])
    save(receipt, value)
    return value


def request(core, scope, L, G):
    check(core in PINS and scope in ('full', 'prefix') and (L, G) in CASES,
          'cell outside the fixed core/scope/level/frame grid')
    native = build(core, allow_create=False)
    source = INPUTS / 'enwik8'
    raw = source.read_bytes()
    check(len(raw) == FULL_BYTES and sha(raw) == FULL_SHA256, 'full enwik8 identity changed')
    if scope == 'prefix':
        raw = raw[:PREFIX_BYTES]
    digest = sha(raw)
    frozen = STATE / 'inputs' / f'{digest}.bin'
    immutable(frozen, raw)
    value = dict(schema='hw-gift-1e-cell-v1', core=core, core_commit=PINS[core], scope=scope,
                 corpus='enwik8', level=L, g=G, variants=list(VARIANTS),
                 input_path=str(frozen), input_bytes=len(raw), input_sha256=digest,
                 full_corpus_bytes=FULL_BYTES, full_corpus_sha256=FULL_SHA256,
                 prefix_bytes=PREFIX_BYTES if scope == 'prefix' else None,
                 calibration_commit=CALIBRATION_COMMIT,
                 calibration_sha256=native['identity']['protocol']['calibration']['sha256'],
                 protocol_commit=native['identity']['protocol']['execution_protocol']['commit'],
                 protocol_sha256=native['identity']['protocol']['execution_protocol']['sha256'],
                 instrument_sha256=file_sha(__file__), setup_sha256=file_sha(STATE / 'setup.json'),
                 native_build_sha256=file_sha(STATE / 'native' / core / 'build.json'),
                 frozen_source_sha256=native['identity']['source_sha256'])
    value['cell_id'] = f'{core}-{scope}-L{L}-G{G}-' + sha(packed(value))[:16]
    return value


def validate_cell(cell):
    check(cell['schema'] == 'hw-gift-1e-cell-v1' and cell['core'] in PINS
          and cell['scope'] in ('full', 'prefix') and (cell['level'], cell['g']) in CASES,
          'invalid core grid cell')
    check(cell['variants'] == list(VARIANTS) and cell['core_commit'] == PINS[cell['core']], 'cell variants/core changed')
    check(cell['instrument_sha256'] == file_sha(__file__), 'cell instrument changed')
    native = build(cell['core'], allow_create=False)
    check(file_sha(STATE / 'native' / cell['core'] / 'build.json') == cell['native_build_sha256'], 'cell native build changed')
    check(cell['setup_sha256'] == file_sha(STATE / 'setup.json')
          and cell['frozen_source_sha256'] == native['identity']['source_sha256'], 'cell setup/frozen writer changed')
    protocols = native['identity']['protocol']
    check(cell['calibration_commit'] == CALIBRATION_COMMIT
          and cell['calibration_sha256'] == protocols['calibration']['sha256']
          and (cell['protocol_commit'], cell['protocol_sha256']) ==
          (protocols['execution_protocol']['commit'], protocols['execution_protocol']['sha256']), 'cell protocol changed')
    prefix = PREFIX_BYTES if cell['scope'] == 'prefix' else None
    check((cell['corpus'], cell['full_corpus_bytes'], cell['full_corpus_sha256'], cell['prefix_bytes'], cell['input_bytes'])
          == ('enwik8', FULL_BYTES, FULL_SHA256, prefix, prefix or FULL_BYTES), 'cell input scope changed')
    check(prefix is not None or cell['input_sha256'] == FULL_SHA256, 'full corpus digest differs')
    frozen = Path(cell['input_path']).resolve()
    check(frozen.is_relative_to((STATE / 'inputs').resolve()), 'frozen input escaped experiment state')
    original = dict(cell)
    supplied = original.pop('cell_id')
    label = f"{cell['core']}-{cell['scope']}-L{cell['level']}-G{cell['g']}-"
    check(supplied == label + sha(packed(original))[:16], 'cell identity changed')
    return cell


def load(core, variant):
    check(core in PINS and variant in VARIANTS, 'invalid native core/variant')
    lib = ct.CDLL(str(STATE / 'native' / core / f'{variant}.so'), mode=ct.RTLD_LOCAL)
    ptr, size = ct.c_void_p, ct.c_size_t
    methods = {'ZSTD_versionNumber': ([], ct.c_uint), 'ZSTD_versionString': ([], ct.c_char_p),
               'ZSTD_isError': ([size], ct.c_uint), 'ZSTD_getErrorName': ([size], ct.c_char_p),
               'ZSTD_decompress': ([ptr, size, ptr, size], size),
               'ZSTD_seekable_createCStream': ([], ptr),
               'ZSTD_seekable_initCStream': ([ptr, ct.c_int, ct.c_int, ct.c_uint], size),
               'ZSTD_seekable_freeCStream': ([ptr], size), 'probe_encode': ([ptr, ptr, size, ptr, size], size),
               'ZSTD_seekable_create': ([], ptr), 'ZSTD_seekable_free': ([ptr], size),
               'ZSTD_seekable_initBuff': ([ptr, ptr, size], size),
               'ZSTD_seekable_decompress': ([ptr, ptr, size, ct.c_ulonglong], size)}
    for name, (arguments, returns) in methods.items():
        fn = getattr(lib, name)
        fn.argtypes, fn.restype = arguments, returns
    check(lib.ZSTD_versionNumber() == VERSIONS[core]
          and lib.ZSTD_versionString().decode() == core.removeprefix('v'), 'wrong native core library version')
    return lib


def native_check(lib, code):
    check(not lib.ZSTD_isError(code), lib.ZSTD_getErrorName(code).decode())


def header(data, source_bytes, frame_bytes):
    """Summarize table geometry without serializing hundreds of thousands of rows."""
    check(len(data) >= 17, 'truncated seekable archive')
    count, descriptor, magic = struct.unpack_from('<IBI', data, len(data)-9)
    check(magic == 0x8F92EAB1 and descriptor == 128 and count > 0, 'invalid seek footer/checksum flag')
    table_bytes = 17 + count*12
    table_start = len(data)-table_bytes
    check(table_start >= 0, 'truncated seek table')
    marker, payload_bytes = struct.unpack_from('<II', data, table_start)
    check(marker == 0x184D2A5E and payload_bytes == table_bytes-8, 'invalid seek table header')
    compressed, decompressed, empty = 0, 0, 0
    for index in range(count):
        c, d, _ = struct.unpack_from('<III', data, table_start+8+index*12)
        check(c > 0 and d <= frame_bytes, 'invalid frame sizes in seek table')
        if d == 0:
            check(index == count-1 and source_bytes % frame_bytes == 0, 'only a terminal empty frame is permitted')
            empty += 1
        elif index < count-1:
            check(d == frame_bytes, 'nonterminal frame source size changed')
        compressed += c
        decompressed += d
    check(compressed == table_start and decompressed == source_bytes, 'complete seek table does not account for archive/source')
    spec = importlib.util.spec_from_file_location('_gift1e_header', ROOT / 'evidence/hw-gift-1c/seekable.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict(header=module.parse_header(data), frame_count=count, seek_table_bytes=table_bytes,
                seek_checksum_flag=True, empty_terminal_frames=empty)


def evaluate(cell, order, clock=None, input_override=None):
    """Fresh/prepared native contexts; all slots encoded before untimed restore."""
    validate_cell(cell)
    order = list(order)
    check(order and all(v in VARIANTS for v in order), 'order contains an unknown writer')
    if clock is not None:
        check(os.environ.get('OVH_BENCH_LOCK_HELD') == LOCK and os.sched_getaffinity(0) == {0},
              'timing requires the shared lock and pinned CPU 0')
    check(input_override is None or clock is None, 'changed-input controls are untimed only')
    raw = Path(cell['input_path']).read_bytes() if input_override is None else bytes(input_override)
    if input_override is None:
        check(len(raw) == cell['input_bytes'] and sha(raw) == cell['input_sha256'], 'frozen input changed')
    check(raw, 'empty probe input')
    input_sha = sha(raw)
    source = ct.create_string_buffer(raw, len(raw))
    capacity = 2*len(raw)+17+12*((len(raw)+cell['g']-1)//cell['g']+1)+(1 << 20)
    slots, results, calls = [], [], 0
    try:
        for index, variant in enumerate(order):
            lib = load(cell['core'], variant)
            encoded, restored = ct.create_string_buffer(capacity), ct.create_string_buffer(len(raw))
            ct.memset(encoded, 0xA5, capacity)
            ct.memset(restored, 0xA5, len(raw))
            encoder = lib.ZSTD_seekable_createCStream()
            check(bool(encoder), 'fresh encoder creation failed')
            slot = dict(slot=index, variant=variant, lib=lib, encoder=encoder, decoder=None,
                        encoded=encoded, restored=restored, compression_ns=None)
            slots.append(slot)
            native_check(lib, lib.ZSTD_seekable_initCStream(encoder, cell['level'], 1, cell['g']))
        for slot in slots:
            if clock is not None:
                start = clock(); calls += 1
            length = slot['lib'].probe_encode(slot['encoder'], source, len(raw), slot['encoded'], capacity)
            if clock is not None:
                slot['compression_ns'] = clock()-start; calls += 1
            native_check(slot['lib'], length)
            check(length <= capacity, 'native encoder exceeded capacity')
            slot['length'] = length
        # Decoder creation, restoration, hashing and disk publication are untimed.
        for slot in slots:
            slot['decoder'] = slot['lib'].ZSTD_seekable_create()
            check(bool(slot['decoder']), 'fresh decoder creation failed')
            native_check(slot['lib'], slot['lib'].ZSTD_seekable_initBuff(slot['decoder'], slot['encoded'], slot['length']))
            length = slot['lib'].ZSTD_seekable_decompress(slot['decoder'], slot['restored'], len(raw), 0)
            native_check(slot['lib'], length)
            check(length == len(raw), 'archive restored an unexpected byte count')
            restored = ct.string_at(slot['restored'], length)
            check(restored == raw, 'archive does not restore bit for bit')
            data = ct.string_at(slot['encoded'], slot['length'])
            wire = header(data, len(raw), cell['g'])
            library = STATE / 'native' / cell['core'] / f"{slot['variant']}.so"
            key = sha(packed(dict(input_sha256=input_sha, level=cell['level'], g=cell['g'],
                                 core=cell['core'], variant=slot['variant'], library_sha256=file_sha(library))))
            cache = STATE / ('controls' if input_override is not None else 'archives') / f'{key}.zst'
            immutable(cache, data)
            result = dict(slot=slot['slot'], variant=slot['variant'], compression_ns=slot['compression_ns'],
                          archive_bytes=len(data), archive_sha256=sha(data), archive_path=str(cache),
                          decoded_bytes=length, decoded_sha256=sha(restored), bit_perfect=True, **wire)
            if clock is not None:
                check(type(result['compression_ns']) is int and result['compression_ns'] > 0, 'invalid compression interval')
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


def known_1d(cell, results):
    known = cell['core'] == 'v1.5.7' and cell['scope'] == 'prefix'
    if not known:
        return None
    path = ROOT / f"evidence/hw-gift-1d/cells/train/L{cell['level']}-G{cell['g']}.json"
    previous = json.loads(path.read_bytes())
    check(previous['status'] == 'COMPLETE' and previous['input_bytes'] == cell['input_bytes']
          and previous['input_sha256'] == cell['input_sha256'], 'known 1d input/scope changed')
    for result in results:
        expected = previous['variants']['original' if result['variant'] == 'A' else 'nohint']
        check((result['archive_bytes'], result['archive_sha256']) == (expected['archive_bytes'], expected['archive_sha256']),
              'v1.5.7 prefix does not reproduce the complete 1d archive')
    return dict(path='../' + path.relative_to(HERE.parent).as_posix(), sha256=file_sha(path))


def untimed_selfcheck(cell):
    validate_cell(cell)
    path = selfcheck_path(cell)
    if path.exists():
        old = json.loads(path.read_bytes())
        check(old['schema'] == 'hw-gift-1e-selfcheck-v1' and old['status'] == 'PASS'
              and old['cell_sha256'] == cell_sha(cell) and old['clock_calls'] == 0
              and old['measurements_of_time'] is False, 'saved untimed selfcheck changed')
        for result in old['results']:
            check(file_sha(result['archive_path']) == result['archive_sha256'], 'saved selfcheck archive changed')
        check(old['known_1d_source'] == known_1d(cell, old['results']), 'known-answer source binding changed')
        return old
    value = evaluate(cell, VARIANTS, clock=None)
    known = known_1d(cell, value['results'])
    result = dict(schema='hw-gift-1e-selfcheck-v1', status='PASS', measurements_of_time=False,
                  cell_id=cell['cell_id'], cell_sha256=cell_sha(cell), clock_calls=0,
                  core=cell['core'], scope=cell['scope'], known_1d_checked=known is not None,
                  known_1d_source=known, results=value['results'])
    save(path, result)
    return result


def timed_worker(cell, pair_index, order=('A', 'B'), method=False, method_check=None, output=None):
    validate_cell(cell)
    check(type(pair_index) is int and 0 <= pair_index < 5, 'pair index must be 0..4')
    check(os.environ.get('OVH_BENCH_LOCK_HELD') == LOCK and os.sched_getaffinity(0) == {0},
          'worker requires shared external OVH lock and pinned CPU 0')
    control_path = selfcheck_path(cell)
    check(control_path.exists(), 'untimed cell selfcheck must pass before timing')
    control = untimed_selfcheck(cell)
    order = list(order)
    if method:
        check((cell['scope'], cell['level'], cell['g']) == ('full', 10, 256)
              and order == ['A', 'A'], 'only the preregistered full/L10/G256 A/A control bypasses the main gate')
    else:
        check(sorted(order) == list(VARIANTS), 'main order must contain A and B once each')
        path = Path(method_check) if method_check is not None else HERE / f"method-{cell['core']}.json"
        gate = json.loads(path.read_bytes())
        check(gate['status'] == 'PASS' and gate['core'] == cell['core']
              and gate['protocol_sha256'] == cell['protocol_sha256']
              and gate['calibration_sha256'] == cell['calibration_sha256']
              and gate['instrument_sha256'] == cell['instrument_sha256']
              and gate['native_build_sha256'] == cell['native_build_sha256'], 'per-core method gate must pass before main timing')
    if output is not None:
        output = Path(output).resolve()
        check(output.is_relative_to(ROOT.resolve()) and not output.exists(), 'worker output must be new and inside this checkout')
    import time
    result = evaluate(cell, order, clock=time.perf_counter_ns)
    expected = {r['variant']: (r['archive_bytes'], r['archive_sha256']) for r in control['results']}
    for row in result['results']:
        check((row['archive_bytes'], row['archive_sha256']) == expected[row['variant']],
              'timed archive differs from the first untimed manifest')
    result.update(schema='hw-gift-1e-worker-v1', core=cell['core'], core_commit=cell['core_commit'],
                  scope=cell['scope'], cell_id=cell['cell_id'], cell_sha256=cell_sha(cell), pair_index=pair_index,
                  order=order, method_control=bool(method), measurements_of_time=True,
                  calibration_sha256=cell['calibration_sha256'], protocol_sha256=cell['protocol_sha256'],
                  instrument_sha256=cell['instrument_sha256'], native_build_sha256=cell['native_build_sha256'],
                  selfcheck_sha256=file_sha(control_path), cpu_affinity=[0], lock_path=LOCK,
                  timer_scope='native encode API loop only; fresh init/prefault/hash/full restore/disk outside; first-use codec allocation inside')
    if output is not None:
        save(output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'request', 'selfcheck', 'worker'))
    parser.add_argument('--core', choices=PINS)
    parser.add_argument('--scope', choices=('full', 'prefix'))
    parser.add_argument('--level', type=int)
    parser.add_argument('--frame', type=int)
    parser.add_argument('--cell', type=Path)
    parser.add_argument('--pair', type=int)
    parser.add_argument('--order', default='A,B')
    parser.add_argument('--method', action='store_true')
    parser.add_argument('--method-check', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.action == 'build':
        value = build(args.core)
    elif args.action == 'request':
        value = request(args.core, args.scope, args.level, args.frame)
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
            value = timed_worker(cell, args.pair, args.order.split(','), args.method, args.method_check, args.output)
    print(json.dumps(value, sort_keys=True, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    main()
