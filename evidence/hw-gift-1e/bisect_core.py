"""Bounded core-search native backend, gated by SEARCH_PROTOCOL.md.

Both primary predictions must HIT and the full tag grid must pass its audit.
The controller owns candidate selection, five-round summaries and published
checkpoints. No import-time commands, native calls, builds or clocks.
"""
import argparse
import ctypes as C
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'evidence/hw-gift-1e'
STATE = ROOT / '.work/hw-gift-1e'
SEARCH = STATE / 'search'
UPSTREAM = STATE / 'upstream'
OLD = '945f27758c0fd67b636103a38dbf050266c6b90a'
NEW = 'f8745da6ff1ad1e7bab384bd1f9d742439278e99'
LOCK = '/run/lock/ovh-bench.lock'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def load(path):
    return json.loads(Path(path).read_bytes())


def save(path, value):
    path, data = Path(path), packed(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == data, 'immutable receipt changed: ' + str(path))
    else:
        with path.open('xb') as stream:
            stream.write(data)


def deref(value):
    path = (HERE / value['path']).resolve()
    require(path.is_relative_to(HERE) and path.is_file() and sha(path) == value['sha256'], 'public gate reference changed')
    return path


def git(*args, repo=UPSTREAM):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def committed(path):
    relative = Path(path).relative_to(ROOT).as_posix()
    require(not git('status', '--porcelain', '--', relative, repo=ROOT).strip(), 'uncommitted search source/data')
    commit = git('log', '-1', '--format=%H', '--', relative, repo=ROOT).decode().strip()
    require(len(commit) == 40 and git('show', commit + ':' + relative, repo=ROOT) == Path(path).read_bytes(), 'search bytes not committed')
    return dict(commit=commit, sha256=sha(path))


def med(values):
    require(len(values) == 5 and all(type(n) is int and n > 0 for n in values), 'five positive integer observations required')
    return sorted(values)[2]


def gate(admission_path, candidate=False):
    admission = load(admission_path)
    committed(Path(admission_path))
    require(admission['backend_sha256'] == sha(__file__), 'search backend changed')
    require(admission['search_protocol'] == committed(HERE / 'SEARCH_PROTOCOL.md'), 'search protocol changed')
    committed(Path(__file__))
    decision = load(deref(admission['decision']))
    require(decision['search_admitted'] is True and decision['Kill']['triggered'] is False, 'primary gates do not admit search')
    observed = {}
    for core, reference in decision['primary_cells'].items():
        cell = load(deref(reference))
        require(cell['status'] == 'COMPLETE' and (cell['scope'], cell['level'], cell['g']) == ('full', 10, 256), 'wrong primary cell')
        timings = {'A': [], 'B': []}
        for repeat in cell['repeats']:
            raw = load(deref(repeat['selected_result']))
            receipt = load(deref(repeat['selected_receipt']))
            require(receipt['status'] == 'CLEAN', 'primary includes excluded timing')
            for row in raw['results']:
                timings[row['variant']].append(row['compression_ns'])
        observed[core] = {v: med(ns) for v, ns in timings.items()}
    a, b = observed['v1.5.4']['A'], observed['v1.5.4']['B']
    require(b >= 5*a, 'recomputed P1 is not HIT')
    a, b = observed['v1.5.7']['A'], observed['v1.5.7']['B']
    require(5*max(a, b) < 6*min(a, b), 'recomputed P2 is not HIT')
    require(admission['setup_sha256'] == sha(STATE / 'setup.json'), 'baseline setup changed')
    audit = load(deref(admission['grid_audit']))
    require(audit['status'] == 'PASS' and audit['stage'] == 'all' and audit['verified_cells'] == 12
            and audit['grid_status'] == 'COMPLETE' and audit['literal_verdicts']['search_admitted'] is True,
            'completed baseline grid audit required')
    bound = {}
    for item in audit['source_bindings']:
        path = (HERE/item['path']).resolve()
        require(path.is_relative_to(ROOT/'evidence') and sha(path) == item['sha256'], 'grid audit source closure changed')
        bound[item['path']] = item['sha256']
    require(bound.get(admission['decision']['path']) == admission['decision']['sha256'], 'grid audit does not bind this decision')
    coordinates = set()
    require(len(admission['completed_grid']) == 12, 'all twelve baseline cells required before endpoint timing')
    for reference in admission['completed_grid']:
        cell = load(deref(reference))
        require(bound.get(reference['path']) == reference['sha256'], 'grid audit does not bind this cell')
        require(cell['status'] == 'COMPLETE', 'baseline grid is incomplete')
        coordinates.add((cell['core'], cell['scope'], cell['level'], cell['g']))
    require(coordinates == {(core, scope, level, frame) for core in ('v1.5.4', 'v1.5.7')
            for scope in ('full', 'prefix') for level, frame in ((10, 256), (10, 1024), (3, 256))}, 'baseline grid coordinates changed')
    public_build = deref(admission['baseline_build'])
    private_build = STATE / 'native/v1.5.7/build.json'
    require(public_build.read_bytes() == private_build.read_bytes(), 'public/private endpoint build differs')
    baseline = load(private_build)
    for name, digest in baseline['identity']['source_sha256'].items():
        require(sha(private_build.parent / name) == digest, 'frozen endpoint payload changed')
    for library in baseline['libraries'].values():
        require(sha(library['path']) == library['sha256'], 'endpoint library changed')
    if candidate:
        endpoint_path = deref(admission['endpoint_admission'])
        committed(endpoint_path)
        endpoint_admission = load(endpoint_path)
        amendment = None
        if 'source_branch_amendment' in admission:
            amendment_path = deref(admission['source_branch_amendment'])
            committed(amendment_path)
            amendment = load(amendment_path)
            require(amendment['status'] == 'PRE-BUILD SOURCE-ANCESTRY AMENDMENT'
                    and amendment['new_backend_sha256'] == sha(__file__)
                    and amendment['new_frontend_sha256'] == admission['frontend_sha256'], 'invalid source-branch amendment')
            require(amendment['protocol'] == committed(HERE/'SEARCH_AMENDMENT.md'), 'source-branch amendment protocol changed')
            require(amendment['endpoint_admission'] == admission['endpoint_admission']
                    and amendment['supersedes'] == admission['supersedes'], 'amendment changed historical admission')
            original = load(deref(admission['supersedes']))
            for key, filename in (('backend_sha256','bisect_core.txt'), ('frontend_sha256','search.txt')):
                require(original[key] == endpoint_admission[key] == sha(deref(amendment['original_sources'][filename])),
                        'historical endpoint source snapshot changed')
        for key in ('decision', 'setup_sha256', 'completed_grid', 'grid_audit', 'baseline_build',
                    'backend_sha256', 'frontend_sha256', 'search_protocol'):
            if amendment and key in ('backend_sha256','frontend_sha256'):
                continue
            require(endpoint_admission[key] == admission[key], 'candidate admission changed endpoint root: '+key)
        classifier_path = deref(admission['classifier'])
        require(admission['classifier_commit'] == committed(classifier_path), 'classifier was not frozen before candidates')
        classifier = load(classifier_path)
        require(classifier['status'] == 'BRACKET' and classifier['endpoint_slow_ns'] >= 2*classifier['endpoint_reference_ns'], 'no prefix endpoint bracket')
        require(classifier['identity']['admission_sha256'] == sha(endpoint_path), 'classifier does not bind immutable endpoint admission')
    return admission


def captured(command, prefix):
    require(not Path(str(prefix) + '.stdout').exists(), 'prior build attempt needs inspection')
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    Path(str(prefix) + '.stdout').write_bytes(result.stdout)
    Path(str(prefix) + '.stderr').write_bytes(result.stderr)
    result.check_returncode()
    return dict(command=command, stdout_sha256=sha(str(prefix) + '.stdout'), stderr_sha256=sha(str(prefix) + '.stderr'))


def native(path):
    lib = C.CDLL(str(path), mode=C.RTLD_LOCAL)
    pointer, size = C.c_void_p, C.c_size_t
    methods = {'ZSTD_versionNumber': ([], C.c_uint), 'ZSTD_versionString': ([], C.c_char_p),
               'ZSTD_isError': ([size], C.c_uint), 'ZSTD_seekable_createCStream': ([], pointer),
               'ZSTD_seekable_initCStream': ([pointer, C.c_int, C.c_int, C.c_uint], size),
               'ZSTD_seekable_freeCStream': ([pointer], size), 'probe_encode': ([pointer, pointer, size, pointer, size], size),
               'ZSTD_seekable_create': ([], pointer), 'ZSTD_seekable_initBuff': ([pointer, pointer, size], size),
               'ZSTD_seekable_decompress': ([pointer, pointer, size, C.c_ulonglong], size), 'ZSTD_seekable_free': ([pointer], size),
               'probe_seek_checksums': ([pointer, size, pointer, size], size), 'probe_empty_frame': ([pointer, size], C.c_uint)}
    for name, (arguments, returns) in methods.items():
        function = getattr(lib, name)
        function.argtypes, function.restype = arguments, returns
    return lib


def build_candidate(commit, admission_path):
    admission = gate(admission_path, candidate=True)
    require(not os.environ.get('OVH_BENCH_LOCK_HELD') and re.fullmatch('[0-9a-f]{40}', commit), 'build outside timing lock using a full SHA')
    allowed = []
    if 'source_branch_amendment' in admission:
        allowed = load(deref(admission['source_branch_amendment']))['allowed_source_branch_commits']
        require(allowed == ['e2965edd107acd0123294e23848cdc00af906468',
                           '9420bce8a491e21821c4b372f837bf4bd47e5870',
                           '91f4c23e634a1d260f290f00b6d870a56cd59ab6'], 'side-branch allowance widened')
    ancestry = [(commit, NEW)] + ([] if commit in allowed else [(OLD, commit)])
    for left, right in ancestry:
        subprocess.run(['git', '-C', str(UPSTREAM), 'merge-base', '--is-ancestor', left, right], check=True)
    require(commit not in (OLD, NEW), 'endpoint libraries are already built')
    folder = SEARCH / 'builds' / commit
    receipt = folder / 'build.json'
    if receipt.exists():
        value = load(receipt)
        require(value['admission_sha256'] == sha(admission_path) and value['backend_sha256'] == sha(__file__)
                and sha(value['library_path']) == value['library_sha256'], 'cached candidate build changed')
        checkout = SEARCH / 'cores' / commit
        require(git('rev-parse', 'HEAD', repo=checkout).decode().strip() == commit
                and not git('status', '--porcelain', repo=checkout).strip(), 'cached candidate source tree changed')
        for name, digest in value['source_sha256'].items():
            require(sha(folder/name) == digest, 'cached frozen candidate payload changed')
        for name, digest in value['headers_sha256'].items():
            require(sha(checkout/name) == digest, 'cached candidate header changed')
        require(sha(checkout/'lib/libzstd.a') == value['static_library_sha256']
                and sha(checkout/'programs/zstd') == value['cli_sha256'], 'cached candidate core binary changed')
        return receipt
    reservation = SEARCH / 'reservations' / (commit + '.json')
    require(not reservation.exists(), 'candidate already attempted; failed builds consume budget and are not retried')
    count = 2 + len(list((SEARCH / 'reservations').glob('*.json')))
    require(count < 12, '12 total distinct core builds exhausted')
    save(reservation, dict(commit=commit, total_distinct_core_build_number=count+1, admission_sha256=sha(admission_path)))
    folder.mkdir(parents=True, exist_ok=False)
    checkout = SEARCH / 'cores' / commit
    checkout.parent.mkdir(parents=True, exist_ok=True)
    captured(['git', '-C', str(UPSTREAM), 'worktree', 'add', '--detach', str(checkout), commit], folder / 'checkout')
    setup = load(STATE / 'setup.json')
    template = setup['cores']['v1.5.7']
    compiler = Path(setup['compiler']['path'])
    require(sha(compiler) == setup['compiler']['sha256'], 'compiler changed')
    builds = []
    for i, record in enumerate(template['build_commands']):
        command = [arg.replace(template['path'], str(checkout)) for arg in record['command']]
        builds.append(captured(command, folder / ('core-build-' + str(i))))
    base = STATE / 'native/v1.5.7'
    base_receipt = load(base / 'build.json')
    source_hashes = {}
    for name in ('bridge.c', 'B-compress.c', 'decompress.c', 'zstd_seekable.h'):
        data = (base / name).read_bytes()
        require(sha(base / name) == base_receipt['identity']['source_sha256'][name], 'frozen non-core source changed')
        (folder / name).write_bytes(data)
        source_hashes[name] = sha(folder / name)
    library = folder / 'B.so'
    command = ['cc', '-O3', '-fPIC', '-fno-lto', '-shared', '-Wall', '-Wextra', '-Werror', '-Wl,-Bsymbolic',
               '-DXXH_NAMESPACE=ZSTD_', '-I'+str(folder), '-I'+str(checkout/'lib'), '-I'+str(checkout/'lib/common'),
               str(folder/'bridge.c'), str(folder/'B-compress.c'), str(folder/'decompress.c'),
               str(checkout/'lib/libzstd.a'), '-pthread', '-o', str(library)]
    builds.append(captured(command, folder / 'shared-build'))
    lib = native(library)
    header = (checkout / 'lib/zstd.h').read_text()
    version = [int(re.search(r'#define\s+ZSTD_VERSION_'+part+r'\s+(\d+)', header).group(1)) for part in ('MAJOR', 'MINOR', 'RELEASE')]
    require(lib.ZSTD_versionNumber() == version[0]*10000+version[1]*100+version[2], 'candidate runtime/header version differs')
    cli = checkout / 'programs/zstd'
    cli_version = subprocess.check_output([str(cli), '-V'], stderr=subprocess.STDOUT).decode().strip()
    require(lib.ZSTD_versionString().decode() in cli_version and not git('status', '--porcelain', repo=checkout).strip(), 'candidate CLI/source differs')
    value = dict(schema='hw-gift-1e-search-build-v1', commit=commit, title=git('show', '-s', '--format=%s', commit).decode().strip(),
                 admission_sha256=sha(admission_path), backend_sha256=sha(__file__), source_sha256=source_hashes,
                 library_path=str(library), library_sha256=sha(library), static_library_sha256=sha(checkout/'lib/libzstd.a'),
                 headers_sha256={p.relative_to(checkout).as_posix(): sha(p) for p in sorted((checkout/'lib').rglob('*.h'))},
                 cli_sha256=sha(cli), cli_version=cli_version, version_number=lib.ZSTD_versionNumber(),
                 version_string=lib.ZSTD_versionString().decode(), builds=builds)
    save(receipt, value)
    return receipt


def make_request(candidate_build, admission_path):
    gate(admission_path, candidate=candidate_build is not None)
    baseline = {}
    for tag, commit in (('v1.5.4', OLD), ('v1.5.7', NEW)):
        receipt = STATE / 'native' / tag / 'build.json'
        record = load(receipt)['libraries']['B']
        require(sha(record['path']) == record['sha256'], 'endpoint B binary changed')
        baseline[tag] = dict(path=record['path'], sha256=record['sha256'], commit=commit, build_sha256=sha(receipt))
    if candidate_build is not None:
        value = load(candidate_build)
        candidate = dict(path=value['library_path'], sha256=value['library_sha256'], commit=value['commit'], build_sha256=sha(candidate_build))
    else:
        candidate = baseline['v1.5.4']
    source = load(HERE / 'requests/v1.5.7/prefix-L10-G256.json')
    require(source['input_bytes'] == 16 << 20 and sha(source['input_path']) == source['input_sha256'], 'prefix input changed')
    value = dict(schema='hw-gift-1e-search-request-v1', admission_path=str(admission_path), admission_sha256=sha(admission_path),
                 backend_sha256=sha(__file__), endpoint=candidate_build is None, input_path=source['input_path'],
                 input_sha256=source['input_sha256'], input_bytes=source['input_bytes'], level=10, g=256,
                 libraries={'C': candidate, 'R': baseline['v1.5.7']})
    value['request_id'] = candidate['commit'] + '-' + hashlib.sha256(packed(value)).hexdigest()[:16]
    path = SEARCH / 'requests' / (value['request_id'] + '.json')
    save(path, value)
    return path


def sample(request_path, order, clock=None):
    request = load(request_path)
    gate(request['admission_path'], candidate=not request['endpoint'])
    require(request['admission_sha256'] == sha(request['admission_path']) and request['backend_sha256'] == sha(__file__), 'search request changed')
    require(clock is None or (os.environ.get('OVH_BENCH_LOCK_HELD') == LOCK and os.sched_getaffinity(0) == {0}), 'worker requires OVH lock/CPU0')
    raw = Path(request['input_path']).read_bytes()
    require(len(raw) == 16 << 20 and hashlib.sha256(raw).hexdigest() == request['input_sha256'], 'source bytes changed')
    source = C.create_string_buffer(raw, len(raw))
    capacity = 2*len(raw)+17+12*(len(raw)//256+1)+(1 << 20)
    slots, results = [], []
    try:
        for slot, label in enumerate(order):
            record = request['libraries'][label]
            require(sha(record['path']) == record['sha256'], 'worker library changed')
            lib = native(record['path'])
            encoded, restored = C.create_string_buffer(capacity), C.create_string_buffer(len(raw))
            C.memset(encoded, 0xA5, capacity); C.memset(restored, 0xA5, len(raw))
            encoder = lib.ZSTD_seekable_createCStream()
            require(encoder, 'encoder creation failed')
            item = dict(label=label, lib=lib, encoder=encoder, decoder=None, encoded=encoded, restored=restored, ns=None, slot=slot)
            slots.append(item)
            require(not lib.ZSTD_isError(lib.ZSTD_seekable_initCStream(encoder, 10, 1, 256)), 'encoder initialization failed')
        for item in slots:
            if clock is not None:
                started = clock()
            size = item['lib'].probe_encode(item['encoder'], source, len(raw), item['encoded'], capacity)
            if clock is not None:
                item['ns'] = clock()-started
            require(not item['lib'].ZSTD_isError(size) and size <= capacity, 'candidate encoding failed')
            item['size'] = size
        for item in slots:
            lib = item['lib']
            item['decoder'] = lib.ZSTD_seekable_create()
            require(item['decoder'] and not lib.ZSTD_isError(lib.ZSTD_seekable_initBuff(item['decoder'], item['encoded'], item['size'])), 'decoder initialization failed')
            restored = lib.ZSTD_seekable_decompress(item['decoder'], item['restored'], len(raw), 0)
            require(not lib.ZSTD_isError(restored) and restored == len(raw) and item['restored'].raw == raw, 'candidate byte restoration failed')
            data = C.string_at(item['encoded'], item['size'])
            count, descriptor, magic = struct.unpack('<IBI', data[-9:])
            table = len(data)-17-12*count
            require(descriptor == 128 and magic == 0x8F92EAB1 and table >= 0
                    and struct.unpack_from('<II', data, table) == (0x184D2A5E, 12*count+9), 'invalid seek table')
            compressed = decompressed = empty = 0
            for index in range(count):
                cn, dn, _ = struct.unpack_from('<III', data, table+8+12*index)
                require(cn > 0 and compressed+cn <= table and (dn == 256 or dn == 0 and index == count-1), 'invalid frame extent')
                if dn == 0:
                    empty += 1
                    pointer = C.cast(C.byref(item['encoded'], compressed), C.c_void_p)
                    require(lib.probe_empty_frame(pointer, cn) == 0, 'invalid empty terminal frame')
                compressed += cn; decompressed += dn
            require(compressed == table and decompressed == len(raw) and empty <= 1, 'table accounting failed')
            require(lib.probe_seek_checksums(source, len(raw), C.cast(C.byref(item['encoded'], table+8), C.c_void_p), count) == 0, 'per-frame XXH64 failed')
            digest = hashlib.sha256(data).hexdigest()
            archive = SEARCH / 'archives' / (digest+'.zst')
            archive.parent.mkdir(parents=True, exist_ok=True)
            if archive.exists():
                require(archive.read_bytes() == data, 'candidate archive cache changed')
            else:
                archive.write_bytes(data)
            results.append(dict(slot=item['slot'], label=item['label'], commit=request['libraries'][item['label']]['commit'],
                                compression_ns=item['ns'], archive_bytes=len(data), archive_sha256=digest, archive_path=str(archive),
                                restored_bytes=restored, restored_sha256=request['input_sha256'], frame_count=count,
                                empty_terminal_frames=empty, empty_terminal_verified=True,
                                seek_table_bytes=17+12*count, seek_checksum_flag=True,
                                bit_perfect=True, seek_checksums_verified=True))
    finally:
        for item in slots:
            if item['decoder']:
                item['lib'].ZSTD_seekable_free(item['decoder'])
            item['lib'].ZSTD_seekable_freeCStream(item['encoder'])
    return dict(schema='hw-gift-1e-search-worker-v1', request_sha256=sha(request_path), results=results,
                clock_calls=2*len(order) if clock is not None else 0, measurements_of_time=clock is not None, order=list(order))


def selfcheck(request_path):
    path = SEARCH / 'checks' / (load(request_path)['request_id']+'.json')
    if not path.exists():
        value = sample(request_path, ['C', 'C', 'R'])
        require(value['results'][0]['archive_sha256'] == value['results'][1]['archive_sha256'], 'candidate determinism failed')
        save(path, value)
    value = load(path)
    require(value['request_sha256'] == sha(request_path) and value['clock_calls'] == 0, 'saved untimed check changed')
    for row in value['results']:
        require(sha(row['archive_path']) == row['archive_sha256'], 'untimed archive changed')
    return path


def worker(request_path, pair, order, output):
    require(type(pair) is int and 0 <= pair < 5, 'worker pair must be0..4')
    require(order == (['C', 'R'] if pair % 2 == 0 else ['R', 'C']), 'worker order must match frozen parity')
    check_path = SEARCH / 'checks' / (load(request_path)['request_id']+'.json')
    require(check_path.exists(), 'untimed selfcheck must finish outside OVH lock before worker')
    expected = load(selfcheck(request_path))
    import time
    value = sample(request_path, order, time.perf_counter_ns)
    hashes = {row['label']: row['archive_sha256'] for row in expected['results']}
    require(all(row['archive_sha256'] == hashes[row['label']] and row['compression_ns'] > 0 for row in value['results']), 'timed archive differs from selfcheck')
    value.update(pair_index=pair, backend_sha256=sha(__file__), cpu_affinity=[0], lock_path=LOCK)
    save(output, value)
    print(json.dumps(value, sort_keys=True, separators=(',', ':')), flush=True)


def locked_round(request_path, pair):
    require(type(pair) is int and 0 <= pair < 5, 'five rounds only')
    require(selfcheck(request_path).exists(), 'untimed check must precede locking')
    helper_path = ROOT / 'evidence/hw-gift-1b/ovh_bench.py'
    spec = importlib.util.spec_from_file_location('_gift1e_search_ovh', helper_path)
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    order = ['C', 'R'] if pair % 2 == 0 else ['R', 'C']
    attempts = []
    for attempt in range(1, 4):
        folder = SEARCH / 'raw' / load(request_path)['request_id'] / ('repeat-'+str(pair)) / ('attempt-'+str(attempt))
        output, receipt = folder / 'result.json', folder / 'ovh-bench.json'
        if folder.exists():
            require(receipt.exists() or not any(folder.iterdir()), 'orphan/interrupted attempt cannot be retimed')
            if receipt.exists():
                require(load(receipt)['status'] in ('CLEAN', 'LOADED'), 'interrupted/error attempt requires inspection')
        else:
            folder.mkdir(parents=True)
        command = [sys.executable, '-B', str(Path(__file__).resolve()), 'worker', '--request', str(request_path),
                   '--pair', str(pair), '--order', ','.join(order), '--output', str(output)]
        code = helper.run_locked(command, receipt, folder/'worker.stdout')
        record = load(receipt)
        attempts.append(dict(attempt=attempt, status=record['status'], receipt_path=str(receipt), receipt_sha256=sha(receipt)))
        if code == 0:
            return dict(status='CLEAN', pair_index=pair, order=order, attempts=attempts,
                        selected_result=dict(path=str(output), sha256=sha(output)))
        require(code == 77 and record['status'] == 'LOADED', 'worker/build/source error is fatal, never retaken')
    return dict(status='BLOCKED: load', pair_index=pair, order=order, attempts=attempts, ps_top8=record['ps_top8'])


def classify(candidate_ns, reference_ns, endpoint_slow_ns, endpoint_reference_ns):
    require(all(type(n) is int and n > 0 for n in (candidate_ns, reference_ns, endpoint_slow_ns, endpoint_reference_ns)), 'classifier requires integer medians')
    left = 100*candidate_ns*candidate_ns*endpoint_reference_ns
    right = reference_ns*reference_ns*endpoint_slow_ns
    return 'FAST' if left < 81*right else 'SLOW' if left > 121*right else 'INDETERMINATE'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('worker',))
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--pair', type=int, required=True)
    parser.add_argument('--order', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    worker(args.request, args.pair, args.order.split(','), args.output)
