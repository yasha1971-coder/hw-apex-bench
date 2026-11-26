# SPDX-License-Identifier: Apache-2.0
"""Independent public saved-data audit of the chr1 reader extension.

This parser calls no controller, library, native executable, network or clock.
The earlier pure auditor supplies byte-capture and raw /proc validators only.
"""
import argparse
from datetime import datetime, timedelta
from decimal import Decimal
from fractions import Fraction
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = HERE.parent / 'casefix'
LABEL = 'twobit_casefix_binary_mask1'
DISPLAY = 'lib2bit-casefix + binary search (reader change, not upstream)'
ORDER = ('aa-first', 'aa-second', 'boundary', 'main')
LOCK = '/run/lock/ovh-bench.lock'
BINDS, COHORT, BUILD, HOST = {}, None, None, None
A = None


class Incomplete(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def digest(value):
    return hashlib.sha256(packed(value)).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def read(path):
    path = Path(path).resolve()
    require(path.is_relative_to(ROOT) and not path.is_relative_to(ROOT / '.work'), 'public repository inputs only')
    if not path.is_file():
        raise Incomplete('missing public proof: ' + path.relative_to(ROOT).as_posix())
    raw = path.read_bytes(); value = hashlib.sha256(raw).hexdigest(); name = path.relative_to(ROOT).as_posix()
    require(BINDS.setdefault(name, value) == value, 'evidence changed during audit: ' + name)
    return raw


def sha(path):
    return hashlib.sha256(read(path)).hexdigest()


def load(path):
    return json.loads(read(path), object_pairs_hook=unique)


def file_ref(value):
    require(isinstance(value, dict) and isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str), 'missing public reference')
    name = value['path'].replace('\\', '/')
    if '/evidence/' in name:
        path = ROOT / ('evidence/' + name.split('/evidence/', 1)[1])
    else:
        require(not name.startswith('/') and ':' not in name, 'private artifact is an identity, not a public proof')
        path = (ROOT if value.get('base') == 'repository' else HERE) / name
    path = path.resolve()
    require(sha(path) == value['sha256'], 'public reference SHA differs: ' + str(path))
    if 'bytes' in value:
        require(type(value['bytes']) is int and len(read(path)) == value['bytes'], 'artifact bytes differ')
    return path


def jref(value):
    return load(file_ref(value))


def ref(path):
    return dict(base='repository', path=path.relative_to(ROOT).as_posix(), sha256=sha(path))


def stamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None and result.utcoffset() == timedelta(0), 'UTC timestamp required')
    return result


def sources():
    names = [HERE / n for n in ('CALIBRATION.md', 'PROTOCOL.md', 'stage.py', 'lib2bit-binary-search.patch', 'test_binary_search.py', 'mask_counts.py')]
    names += [BASE / n for n in ('drive.py', 'setup.py', 'native.c', 'worker.c', 'coordinate.h', 'ovh_bench.py', 'CALIBRATION.md', 'PROTOCOL.md')]
    names += [HERE.parent / 'writer.py', HERE.parent / 'lib2bit-casefix.patch']
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in names}


def support():
    global A
    path = BASE / 'audit.py'; sha(path)
    spec = importlib.util.spec_from_file_location('_saved_casefix_support', path)
    A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
    A.HERE = HERE; A.sha = sha; A.load = load; A.file_ref = file_ref; A.json_ref = jref
    A.SEMANTICS = {LABEL: 0}; A.SOURCE_MAP = sources(); A.NATIVE = BUILD
    return A


def unchanged_parent():
    global HOST
    path = BASE / 'audit/resumed-all.json'; value = load(path)
    require(value['status'] == 'PASS' and value['stage'] == 'resumed-all' and value['completion'] == 'COMPLETE'
            and value['full_comparison_complete'] is True and value['counts']['cases'] == 31 and value['counts']['rows'] == 186,
            'completed original casefix proof required')
    anchors = {r['path']: r['sha256'] for r in value['source_bindings']}
    require(len(anchors) == len(value['source_bindings']), 'duplicate parent binding')
    rows = {(r['corpus'], r['profile']): r for r in value['rows']}
    ace, fixed = rows['chr1', 'aceapex'], rows['chr1', 'twobit_casefix_mask1']
    wins = sum(rows[f't2t-{i:02d}', 'twobit_casefix_mask1']['p50_ns'] < rows[f't2t-{i:02d}', 'aceapex']['p50_ns'] for i in range(30))
    require(100 * ace['stored_bytes'] <= 95 * fixed['stored_bytes'] and 4 * fixed['p50_ns'] > ace['p50_ns']
            and wins == 30 and fixed['p50_ns'] == 88965, 'original P1/P2/P3 or fixed baseline changed')
    require([value['forecasts'][p]['verdict'] for p in ('P1', 'P2', 'P3')] == ['HIT', 'MISS', 'HIT'], 'parent forecast labels changed')
    HOST = tuple(value['host'])
    return value, anchors, fixed


def checked_parent(path, anchors):
    require(sha(path) == anchors[path.relative_to(ROOT).as_posix()], 'frozen parent evidence/source changed: ' + str(path))
    return load(path)


def expected_identity(mode, case, trace, fresh, probe):
    return dict(mode=mode, profile=LABEL, case_sha256=digest(case), trace_sha256=digest(trace), fresh=fresh, probe=probe,
                source_sha256=COHORT['source_sha256'], native_build_sha256=COHORT['native_build_sha256'], setup_sha256=COHORT['setup_sha256'])


def observation(reference, mode, case, trace, fresh=False, probe=False):
    value = A.observation(reference, mode, LABEL, case, trace, fresh, probe)
    require(value['identity'] == expected_identity(mode, case, trace, fresh, probe), 'new reader observation identity differs')
    return value


def worker_command(mode, case, trace, prefix, fresh, probe):
    fmt = case['formats']['twobit']
    argv = ['taskset', '-c', '0' if mode == 'latency' else '15', BUILD['artifacts']['worker']['path'], mode,
        BUILD['artifacts']['dsos'][LABEL]['path'], fmt['path'], '-', '-', case['fai']['geometry']['name'],
        case['input']['path'], case['fai']['path'], trace['warmups']['path'], trace['requests']['path'], prefix]
    return argv + (['--fresh'] if fresh else []) + (['--probe'] if probe else [])


def boundary(value):
    require(tuple(value[k] for k in ('hostname', 'cpu', 'kernel', 'governor', 'pinned_core', 'host_logical_cpus')) == HOST
            and value['pinned_core'] == 0 and value['timed_threads'] == 1 and type(value['nproc']) is int and value['nproc'] > 0
            and value['date_u'], 'host/core/T/governor changed')
    stamp(value['timestamp_utc']); cells = value['loadavg_raw'].split(); require(len(cells) == 5, 'literal loadavg missing')
    number = Decimal(cells[0])
    require(number.is_finite() and number >= 0 and Decimal(value['load1_minus_T']) == number - 1, 'load1 minus T differs')
    return number


def receipt(path, status):
    value = load(path); argv, command = value['flock_command'], value['command']
    require(value['schema'] == 'hw-region-2-casefix-ovh-v1' and value['status'] == status and status in ('CLEAN', 'LOADED')
            and value['helper_sha256'] == sha(BASE / 'ovh_bench.py') and value['protocol_sha256'] == sha(BASE / 'PROTOCOL.md')
            and value['calibration_sha256'] == sha(BASE / 'CALIBRATION.md') and value['lock_path'] == LOCK
            and value['timed_threads'] == 1 and value['foreign_cpu_percent_threshold'] == '10.0', 'unchanged helper policy/source binding differs')
    require(argv[:2] == ['flock', LOCK] and argv[3] == '-B' and argv[4].endswith('/evidence/hw-region-2/casefix/ovh_bench.py')
            and argv[5:7] == ['_inside', '--receipt'] and argv[7].endswith('/evidence/hw-region-2/binary-search/' + path.relative_to(HERE).as_posix())
            and argv[8] == '--' and argv[9:] == command, 'blocking shared-flock command differs')
    foreign = A.foreign_cpu(value['foreign_cpu_start']); loads = [boundary(value[k]) for k in ('start', 'end')]
    loaded = foreign or any(v > Decimal('2.0') for v in loads)
    require(loaded is (status == 'LOADED') and value['command_started'] is (not foreign and loads[0] <= Decimal('2.0')), 'load admission/start decision differs')
    require(value['returncode'] == 0 and type(value['returncode']) is int if value['command_started'] else value['returncode'] is None,
            'ERROR is not a retriable LOADED attempt')
    require(stamp(value['waiting_since_utc']) <= stamp(value['start']['timestamp_utc']) <= stamp(value['end']['timestamp_utc']), 'attempt timestamps regressed')
    A.other_cores(value['start'], value['end'])
    for suffix, field in (('stdout', 'stdout_sha256'), ('stderr', 'stderr_sha256')):
        require(sha(Path(str(path) + '.' + suffix)) == value[field] == sha(path.parent / ('worker.' + suffix)), 'helper/worker raw output differs')
    if loaded:
        require(value['ps_command'] == 'ps -eo pid,user,pcpu,comm --sort=-pcpu | head -8' and value['ps_top8'], 'LOADED process names not retained')
    return value


def patched(source, patch):
    lines, changes = source.splitlines(keepends=True), patch.splitlines(keepends=True)
    require(changes[:2] == [b'--- a/2bit.c\n', b'+++ b/2bit.c\n'], 'unexpected patch target')
    match = re.fullmatch(rb'@@ -(\d+),(\d+) \+(\d+),(\d+) @@\n', changes[2]); require(match is not None, 'invalid sole patch hunk')
    pos = int(match[1]) - 1; output = lines[:pos]; before = after = 0
    require(len(output) == int(match[3]) - 1, 'new patch offset differs')
    for row in changes[3:]:
        require(row[:1] in (b' ', b'+', b'-'), 'extra patch hunk/metadata')
        if row[:1] in (b' ', b'-'):
            require(pos < len(lines) and lines[pos] == row[1:], 'patch context differs')
            pos += 1; before += 1
        if row[:1] in (b' ', b'+'):
            output.append(row[1:]); after += 1
    require((before, after) == (int(match[2]), int(match[4])), 'patch extent differs')
    return b''.join(output + lines[pos:])


def function(source):
    return source[source.index(b'void softMask('):source.index(b'char *constructSequence(')]


def prepare_stage():
    global BUILD, COHORT
    parent, anchors, fixed = unchanged_parent()
    setup = load(HERE / 'setup.json'); BUILD = load(HERE / 'native/build.json')
    source_map = sources()
    require(setup['schema'] == 'hw-region-2-binary-setup-v1' and setup['label'] == LABEL and setup['no_new_archives'] is True
            and setup['no_clocks'] is True and setup['lib2bit_commit'] == '58e20daa898a6fc338eae82e5d2ef7108d4fc07f'
            and setup['identity']['source_sha256'] == source_map, 'new setup/cohort differs')
    old_setup = checked_parent(BASE / 'setup.json', anchors); old_native = checked_parent(BASE / 'native/build.json', anchors)
    for name, value in source_map.items():
        if name.startswith('evidence/hw-region-2/casefix/') or name in ('evidence/hw-region-2/writer.py', 'evidence/hw-region-2/lib2bit-casefix.patch'):
            require(anchors[name] == value, 'original execution source changed')
    parents = setup['identity']['parents']
    expected_paths = dict(admission=BASE / 'admission.json', resumed_all=BASE / 'audit/resumed-all.json',
        baseline_unit=BASE / fixed['unit']['path'], baseline_observation=BASE / load(BASE / fixed['unit']['path'])['selected']['path'],
        parent_native=BASE / 'native/build.json', parent_setup=BASE / 'setup.json', archive_case=BASE / 'archives/chr1.json',
        trace=BASE / 'traces/chr1.json', controls_plan=BASE / 'controls-plan.json')
    require(parents['baseline_p50_ns'] == 88965 and set(parents) == set(expected_paths) | {'baseline_p50_ns'}, 'parent identity fields differ')
    for key, path in expected_paths.items():
        require(file_ref(parents[key]) == path, 'frozen parent reference swapped: ' + key)
        if key != 'resumed_all':
            require(sha(path) == anchors[path.relative_to(ROOT).as_posix()], 'parent input changed')
    require(BUILD['schema'] == 'hw-region-2-binary-native-v1' and BUILD['status'] == 'PASS'
            and BUILD['identity']['source_sha256'] == source_map and BUILD['identity']['setup_sha256'] == sha(HERE / 'setup.json')
            and BUILD['identity']['parents'] == parents and set(BUILD['artifacts']['dsos']) == {LABEL}
            and BUILD['artifacts']['worker'] == old_native['artifacts']['worker'], 'new build/unchanged worker differs')
    COHORT = dict(source_sha256=source_map, native_build_sha256=sha(HERE / 'native/build.json'), setup_sha256=sha(HERE / 'setup.json'),
                  calibration_sha256=sha(HERE / 'CALIBRATION.md'), protocol_sha256=sha(HERE / 'PROTOCOL.md'))
    require(sha(BASE / 'audit.py') == anchors[(BASE / 'audit.py').relative_to(ROOT).as_posix()], 'frozen pure validator changed')
    support()
    public = setup['public_sources']; require(set(public) == {'upstream-2bit.c', 'casefix-2bit.c', 'binary-2bit.c', '2bit.h', 'LICENSE'}, 'public source proof incomplete')
    raw = {k: read(file_ref(r)) for k, r in public.items()}
    lib = old_setup['lib2bit']; upstream, casefix, binary = (raw[n] for n in ('upstream-2bit.c', 'casefix-2bit.c', 'binary-2bit.c'))
    require(hashlib.sha256(upstream).hexdigest() == lib['original_source']['sha256']
            and hashlib.sha1(b'blob ' + str(len(upstream)).encode() + b'\0' + upstream).hexdigest() == '30631d05d305be8720ef3cc10a71a0d646163cfd', 'pinned upstream bytes differ')
    before, after = b"if(seq[pos] != 'N') seq[pos] = tolower(seq[pos]);", b'seq[pos] = tolower(seq[pos]);'
    require(upstream.count(before) == 1 and upstream.replace(before, after, 1) == casefix
            and hashlib.sha256(casefix).hexdigest() == lib['variants']['casefix']['source_sha256'], 'original one-line casefix changed')
    require(patched(casefix, read(HERE / 'lib2bit-binary-search.patch')) == binary
            and binary.replace(function(binary), function(casefix), 1) == casefix, 'new patch changes bytes outside softMask')
    old_loop, new_loop = b'for(i=0; i<tb->idx->maskBlockCount[tid]; i++) {', b'for(i=lo; i<tb->idx->maskBlockCount[tid]; i++) {'
    require(function(casefix).split(old_loop)[1] == function(binary).split(new_loop)[1]
            and b'uint64_t limit' in function(binary) and b'lo + (hi - lo) / 2' in function(binary)
            and b'if(limit <= start) lo = mid + 1;' in function(binary), 'search/unchanged clipping body differs')
    require(hashlib.sha256(binary).hexdigest() == setup['source']['sha256']
            and hashlib.sha256(raw['2bit.h']).hexdigest() == setup['header']['sha256'] == lib['header_sha256']
            and hashlib.sha256(raw['LICENSE']).hexdigest() == lib['license']['sha256']
            and setup['compiler']['sha256'] == lib['compiler']['gcc']['sha256'], 'compiled source/header/license/compiler identity differs')
    inputs = BUILD['build_inputs']; require(len(inputs) == 7 and inputs[0] == setup['source'] and inputs[3] == setup['header'], 'native build inputs differ')
    for item, path in zip(inputs[4:], (BASE / 'native.c', BASE / 'coordinate.h', BASE / 'worker.c')):
        require(item['sha256'] == sha(path) and item['bytes'] == len(read(path)), 'native wrapper/header/worker source changed')
    commands = {
        'binary-compile': ['taskset', '-c', '15', setup['compiler']['path'], '-O3', '-fPIC', '-I' + lib['path'], '-c', inputs[0]['path'], '-o', inputs[1]['path']],
        'binary-static': ['taskset', '-c', '15', 'ar', 'rcs', inputs[2]['path'], inputs[1]['path']],
        'coordinate-dso': ['taskset', '-c', '15', setup['compiler']['path'], '-O3', '-fPIC', '-fno-lto', '-shared', '-Wall', '-Wextra', '-Wl,-Bsymbolic', '-std=c11',
            '-I' + inputs[4]['path'].rsplit('/', 1)[0], '-DCOORD_LABEL="' + LABEL + '"', '-DCOORD_TWOBIT', '-DCOORD_STORE_MASKED=1', '-DCOORD_ORIGINAL=0',
            '-I' + lib['path'], inputs[4]['path'], inputs[2]['path'], '-o', BUILD['artifacts']['dsos'][LABEL]['path']]}
    for name, argv in commands.items():
        cmd = load(HERE / 'commands' / name / 'command.json')
        require(cmd['status'] == 'PASS' and cmd['returncode'] == 0 and cmd['identity']['argv'] == argv, 'compile/archive/link command differs: ' + name)
        for stream in ('stdout', 'stderr'):
            artifact = next(r for r in cmd['artifacts'] if r['path'].endswith('/' + stream))
            require(sha(HERE / 'commands' / name / stream) == artifact['sha256'], 'retained compiler output changed')
    counts = jref(setup['mask_counts']); require(counts['status'] == 'PASS' and counts['no_clocks'] is True and counts['native_calls'] == counts['query_calls'] == 0, 'saved mask geometry proof missing')
    for r in counts['source_bindings']:
        require(sha(ROOT / r['path']) == r['sha256'], 'mask-count numerical/source closure changed')
    case = jref(parents['archive_case']); trace = jref(parents['trace']); plan = jref(parents['controls_plan'])['controls']['twobit_casefix_mask1']
    for name, selected_case in (('chr1', case), ('synthetic', plan['case'])):
        meta = json.loads(gzip.decompress(read(file_ref(selected_case['writer_metadata']))), object_pairs_hook=unique)
        previous = 0
        for s, n in meta['archive']['mask_blocks']:
            require(type(s) is int and type(n) is int and n > 0 and previous <= s and s + n <= meta['sequence']['bytes'] < 2**32, 'invalid lower_bound interval invariant')
            previous = s + n
        expected = dict(blocks=len(meta['archive']['mask_blocks']), masked_bases=sum(n for s, n in meta['archive']['mask_blocks']), sequence_bases=meta['sequence']['bytes'],
                        sorted_disjoint=True, endpoint_arithmetic='uint64_t during binary search; existing loop unchanged')
        require(setup['mask_invariants'][name] == expected, 'claimed interval invariant count differs')
    return dict(parent=parent, anchors=anchors, setup=setup, case=case, trace=trace, plan=plan, baseline=jref(parents['baseline_observation']), binary=binary, fixed_source=casefix)


def old_ref(record):
    return dict(base='repository', path=(BASE / record['path']).relative_to(ROOT).as_posix(), sha256=record['sha256'])


def truth_match(observed, original):
    # Re-read both public reference/returned captures from the frozen source
    # experiment. Equality to a newly generated, unanchored expected file alone
    # would not establish equality to the unchanged FASTA truth.
    A.capture_checks(original, 0, original['rows'], ('old-truth', digest(original['identity'])))
    require(observed['expected']['sha256'] == original['expected']['sha256']
            and observed['expected']['bytes'] == original['expected']['bytes'], 'new query truth differs from frozen FASTA captures')


def admission_stage(data):
    value = load(HERE / 'admission.json')
    require(value['schema'] == 'hw-region-2-binary-admission-v1' and value['status'] == 'PASS'
            and value['identity'] == COHORT and value['no_clocks'] is True, 'new untimed admission missing')
    checks = value['checks']; paths = [file_ref(r) for r in checks]
    expected_paths = [HERE / 'edge-tests.json', HERE / 'edge-public.json']
    expected_paths += [HERE / 'checks' / name / LABEL / 'observation.json' for name in ('chr1-grid', 'synthetic-mask', 'lowercase-n-witness')]
    require(paths == expected_paths, 'untimed check set/order differs')
    edge = load(paths[0]); public = load(paths[1])
    require(edge['schema'] == 'hw-region-2-binary-search-synthetic-v1' and edge['status'] == 'PASS'
            and edge['no_clocks'] is True and edge['measurements_of_time'] is False and edge['archive_decodes'] == edge['study_worker_calls'] == 0
            and edge['source_sha256'] == sha(HERE / 'test_binary_search.py') and edge['patch_sha256'] == sha(HERE / 'lib2bit-binary-search.patch'), 'actual-C edge test scope/source differs')
    require(public['schema'] == 'hw-region-2-binary-edge-public-v1' and public['status'] == 'PASS' and file_ref(public['report']) == paths[0], 'public edge captures missing')
    def edge_file(record):
        path = file_ref(public['public_files'][record['path']])
        require(sha(path) == record['sha256'] and len(read(path)) == record['bytes'], 'edge source/runtime copy differs')
        return path
    path = HERE / 'test_binary_search.py'; spec = importlib.util.spec_from_file_location('_edge_source_only', path)
    test = importlib.util.module_from_spec(spec); spec.loader.exec_module(test)
    generated, identity = test.make_harness(read(file_ref(data['setup']['public_sources']['upstream-2bit.c'])))
    require(edge['identity'] == identity and read(edge_file(edge['artifacts']['source'])) == generated, 'compiled C oracle differs from pinned function pair and frozen tests')
    raw_native = json.loads(read(edge_file(edge['native_stdout'])), object_pairs_hook=unique)
    require(raw_native == edge['native'] and raw_native['status'] == 'PASS'
            and raw_native['byte_equality_cases'] == raw_native['first_index_cases'] > 0 and raw_native['empty_ranges'] > 0
            and raw_native['null_table_cases'] == 2 and raw_native['masked_N_to_n_bytes'] > 0
            and raw_native['guard_bytes_each_side'] == 32 and raw_native['random_tables'] == 256
            and raw_native['seed'] == 0x5eed2765 and read(edge_file(edge['native_stderr'])) == b'', 'actual-C edge result/coverage differs')
    commands = edge['commands']; require(len(commands) == 3 and all(c['returncode'] == 0 for c in commands), 'edge compilation/run incomplete')
    require(commands[1]['argv'] == [edge['compiler']['executable']['path'], '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
            edge['artifacts']['source']['path'], '-o', edge['artifacts']['binary']['path']]
            and commands[2]['argv'] == [edge['artifacts']['binary']['path']], 'edge native compile/runtime command differs')
    for cmd in commands:
        edge_file(cmd['stdout']); edge_file(cmd['stderr'])
    original_admission = jref(data['setup']['identity']['parents']['admission'])
    old_truth = dict(chr1_grid=data['baseline'], synthetic_mask=jref(old_ref(data['plan']['equality_unit'])),
                     lowercase_n_witness=jref(old_ref(original_admission['lowercase_n_witness'])))
    observed = {}
    for name, reference in zip(('chr1-grid', 'synthetic-mask', 'lowercase-n-witness'), checks[2:]):
        case, trace, fresh, probe = inputs(data, 'boundary' if name == 'synthetic-mask' else 'main')
        command = load(file_ref(reference).parent / 'command.json'); argv = command['command']
        if name == 'lowercase-n-witness':
            require(argv[12].endswith('/.work/hw-region-2/binary-search/traces/witness/warmups.bin')
                    and argv[13].endswith('/.work/hw-region-2/binary-search/traces/witness/requests.bin'), 'witness trace path differs')
            trace = dict(warmups=dict(path=argv[12], offsets=[], bytes=0, sha256=hashlib.sha256(b'').hexdigest()),
                         requests=dict(path=argv[13], offsets=[121749276], bytes=8, sha256=hashlib.sha256(struct.pack('<Q', 121749276)).hexdigest()))
            probe = True
        observed[name] = observation(reference, 'check', case, trace, fresh, probe)
        require(command['status'] == 'COMPLETE' and command['returncode'] == 0 and command['identity'] == observed[name]['identity']
                and argv[14].endswith('/.work/hw-region-2/binary-search/captures/checks/' + name + '/' + LABEL + '/out')
                and argv == worker_command('check', case, trace, argv[14], fresh, probe), 'untimed worker command differs')
        truth_match(observed[name], old_truth[name.replace('-', '_')])
    return dict(status='PASS', edge_byte_equality_cases=raw_native['byte_equality_cases'], frozen_chr1_requests=1000,
                frozen_warmups=12, boundary_requests=2000, lowercase_n_witness='PASS', no_clocks=True)


def inputs(data, name):
    if name == 'boundary':
        return data['plan']['case'], data['plan']['trace'], True, True
    return data['case'], data['trace'], False, False


def unit(data, name):
    path = HERE / 'units' / (name + '.json'); value = load(path)
    case, trace, fresh, probe = inputs(data, name)
    require(value['schema'] == 'hw-region-2-binary-unit-v1' and value['stage_identity'] == COHORT
            and value['identity'] == expected_identity('latency', case, trace, fresh, probe)
            and value['status'] in ('CLEAN', 'BLOCKED: load'), 'timed unit identity differs')
    attempts = value['attempts']; require(1 <= len(attempts) <= 3, 'three-attempt budget exceeded')
    folder = HERE / 'raw' / name
    require({p.name for p in folder.iterdir()} == {'attempt-' + str(i) for i in range(1, len(attempts) + 1)}, 'fourth/unretained attempt directory')
    selected, records = None, []
    for i, item in enumerate(attempts, 1):
        require(item['number'] == i and item['status'] in ('CLEAN', 'LOADED')
                and (i == len(attempts) or item['status'] == 'LOADED'), 'CLEAN retaken or non-load error retried')
        rp = file_ref(item['receipt']); require(rp == folder / ('attempt-' + str(i)) / 'ovh-bench.json', 'attempt receipt swapped')
        record = receipt(rp, item['status']); argv = record['command']
        require(argv[14].endswith('/.work/hw-region-2/binary-search/captures/' + name + '/attempt-' + str(i) + '/out')
                and argv == worker_command('latency', case, trace, argv[14], fresh, probe), 'timed worker/DSO/archive/trace/CPU differs')
        op = rp.parent / 'observation.json'
        require(bool(item['observation']) is record['command_started'] and op.exists() is record['command_started'], 'worker start and raw observation presence differ')
        observed = None
        if item['observation']:
            require(file_ref(item['observation']) == op, 'attempt result swapped')
            observed = observation(item['observation'], 'latency', case, trace, fresh, probe)
            original = jref(old_ref(data['plan']['equality_unit'])) if name == 'boundary' else data['baseline']
            truth_match(observed, original)
            if item['status'] == 'CLEAN':
                selected = observed
        records.append(dict(item=item, receipt=record, observation=observed))
    if selected is None:
        require(value['status'] == 'BLOCKED: load' and len(attempts) == 3 and value['selected'] is None, 'invalid blocked budget')
        raise Incomplete('BLOCKED: load; retained three attempts for ' + name)
    require(value['status'] == 'CLEAN' and value['selected'] == attempts[-1]['observation'], 'winner differs from first CLEAN')
    return dict(value=value, reference=ref(path), selected=selected, records=records)


def polling(units):
    ledger = load(HERE / 'ledger.json')
    require(ledger['schema'] == 'hw-region-2-binary-ledger-v1' and ledger['identity'] == COHORT
            and ledger['status'] == 'COMPLETE' and ledger['next_target'] is None, 'complete polling ledger required')
    pp = sorted((HERE / 'polls').glob('*.json')); cp = sorted((HERE / 'consumptions').glob('*.json'))
    require([p.name for p in pp] == [f'poll-{i:06d}.json' for i in range(1, len(pp) + 1)]
            and [file_ref(r) for r in ledger['polls']] == pp and [file_ref(r) for r in ledger['consumptions']] == cp,
            'poll/consumption sequence or inventory differs')
    tokens = {p.name: (ref(p), load(p)) for p in cp}
    position, number, cooldown, previous_end = 0, 0, None, None
    consumed = set()
    for p, pr in zip(pp, ledger['polls']):
        poll = load(p)
        require(position < 4 and poll['schema'] == 'hw-region-2-binary-poll-v1' and poll['unit'] == ORDER[position]
                and poll['identity'] == COHORT and poll['no_native_calls'] is True and poll['status'] in ('PASS', 'WAITING'),
                'poll unit/order/source or fatal-error continuation differs')
        start, end = stamp(poll['observed_start_utc']), stamp(poll['observed_end_utc'])
        require(start <= end and (previous_end is None or start >= previous_end) and (cooldown is None or start >= cooldown), 'poll chronology/300-second cooldown differs')
        loads = [boundary(poll[k]) for k in ('start', 'end')]; foreign = A.foreign_cpu(poll['foreign_cpu_start'])
        require(start <= stamp(poll['start']['timestamp_utc']) <= stamp(poll['end']['timestamp_utc']) <= end
                and (foreign or any(v > Decimal('2.0') for v in loads)) is (poll['status'] == 'WAITING'), 'poll raw admission decision differs')
        previous_end = end
        token_pair = tokens.pop(p.name, None)
        if poll['status'] == 'WAITING':
            require(token_pair is None, 'waiting observation consumed an actual attempt')
            deadline = end + timedelta(seconds=300); cooldown = max(cooldown, deadline) if cooldown else deadline
            continue
        require(token_pair is not None, 'complete study has unused/bypassed PASS poll')
        token_ref, token = token_pair; name = ORDER[position]; number += 1
        history = units[name]['records']; require(number <= len(history) <= 3, 'poll started a fourth/nonretained attempt')
        item, record = history[number - 1]['item'], history[number - 1]['receipt']
        rp = HERE / 'raw' / name / ('attempt-' + str(number)) / 'ovh-bench.json'
        require(token['schema'] == 'hw-region-2-binary-consumption-v1' and token['identity'] == COHORT
                and token['unit'] == name and token['poll'] == pr and token['attempt_number'] == number
                and token['receipt_path'] == rp.relative_to(HERE).as_posix()
                and file_ref(item['poll_consumption']) == file_ref(token_ref) and item['admission_poll'] == pr,
                'poll token reused/swapped or stage identity differs')
        require(end <= stamp(token['committed_before_attempt_utc']) <= stamp(record['waiting_since_utc']) <= stamp(record['start']['timestamp_utc']), 'consumption was not retained before actual attempt')
        require(rp not in consumed, 'actual attempt consumed multiple polls'); consumed.add(rp)
        previous_end = stamp(record['end']['timestamp_utc'])
        if record['status'] == 'CLEAN':
            position += 1; number = 0
        else:
            deadline = previous_end + timedelta(seconds=300); cooldown = max(cooldown, deadline) if cooldown else deadline
    require(position == 4 and not tokens and set((HERE / 'raw').rglob('ovh-bench.json')) == consumed, 'unpolled/orphan/incomplete raw attempt closure')
    require({p.name for p in (HERE / 'raw').iterdir()} == set(ORDER)
            and {p.name for p in (HERE / 'units').glob('*.json')} == {n + '.json' for n in ORDER}, 'extra timing unit/archive corpus introduced')
    require(set(ledger['units']) == set(ORDER) and all(file_ref(ledger['units'][n]) == HERE / 'units' / (n + '.json') for n in ORDER), 'ledger unit references differ')
    for key, filename in (('admission', 'admission.json'), ('method_aa', 'method-aa.json'), ('boundary', 'boundary.json'), ('result', 'result.json')):
        require(file_ref(ledger[key]) == HERE / filename, 'ledger gate/result reference changed')
    if ledger['next_due_utc'] is not None:
        require(cooldown is not None and stamp(ledger['next_due_utc']) == cooldown, 'ledger deadline differs')
    return dict(polls=len(pp), consumed_polls=len(cp))


def final_stage(data):
    units = {name: unit(data, name) for name in ORDER}
    aa = load(HERE / 'method-aa.json'); first, second = (units[n]['selected']['quantiles']['p50_ns'] for n in ORDER[:2])
    require(aa['schema'] == 'hw-region-2-binary-aa-v1' and aa['identity'] == COHORT and aa['status'] == 'PASS'
            and aa['first_p50_ns'] == first and aa['second_p50_ns'] == second and 20 * abs(second - first) < first
            and file_ref(aa['first']) == HERE / 'units/aa-first.json' and file_ref(aa['second']) == HERE / 'units/aa-second.json', 'strict integer A/A gate failed/differs')
    roles = data['plan']['trace']['roles']; values = units['boundary']['selected']['rows']
    require(len(roles) == len(values) == 2000 and roles == ['aligned', 'crossing', 'crossing', 'aligned'] * 500, 'unchanged AB/BA boundary roles differ')
    groups = {role: sorted(row['elapsed_ns'] for row, r in zip(values, roles) if r == role) for role in ('aligned', 'crossing')}
    aligned, crossing = groups['aligned'][499], groups['crossing'][499]
    control = load(HERE / 'boundary.json')
    require(control['schema'] == 'hw-region-2-binary-boundary-v1' and control['identity'] == COHORT and control['status'] == 'PASS'
            and control['aligned_p50_ns'] == aligned and control['crossing_p50_ns'] == crossing and crossing > aligned
            and file_ref(control['unit']) == HERE / 'units/boundary.json', 'strict boundary cost gate failed/differs')
    # Actual C chronological receipts prove main follows the clean method gates.
    times = [units[n]['records'] for n in ORDER]
    for earlier, later in zip(times, times[1:]):
        require(stamp(earlier[-1]['receipt']['end']['timestamp_utc']) <= stamp(later[0]['receipt']['waiting_since_utc']), 'timed pass executed before its method predecessor')
    polled = polling(units)
    observed = units['main']['selected']; q = observed['quantiles']; ns = q['p50_ns']; passed = 4 * ns <= 88965
    B1 = dict(passed=passed, verdict='HIT' if passed else 'MISS', lhs=4 * ns, rhs=88965)
    result = load(HERE / 'result.json')
    require(result['schema'] == 'hw-region-2-binary-result-v1' and result['status'] == 'COMPLETE' and result['identity'] == COHORT
            and result['p50_ns'] == ns and result['p99_ns'] == q['p99_ns'] and result['frozen_casefix_p50_ns'] == 88965
            and result['B1'] == B1 and result['unchanged_parent_forecasts'] is True
            and file_ref(result['main_unit']) == HERE / 'units/main.json'
            and result['baseline'] == data['setup']['identity']['parents']['baseline_observation'], 'B1 result differs from all raw integer samples')
    if (HERE / 'KILL.json').exists() or (HERE / 'ERROR.json').exists():
        raise Incomplete('retained KILL/ERROR prevents completed timing proof')
    summary = observed['summary']; fmt = data['case']['formats']['twobit']
    main = dict(label=DISPLAY, profile=LABEL, corpus='chr1', stored_bytes=fmt['stored_bytes'], p50_ns=ns, p99_ns=q['p99_ns'],
        open_ns=summary['open_ns'], open_rss_delta_kib=summary['rss_after_open_kib'] - summary['rss_before_open_kib'],
        peak_process_rss_kib=summary['peak_process_rss_kib'], selected=units['main']['value']['selected'], unit=units['main']['reference'])
    all_records = [r for value in units.values() for r in value['records']]
    accepted = [value['selected'] for value in units.values()]
    count = dict(units=4, accepted_timing_units=4, accepted_query_timing_observations=sum(len(o['rows']) for o in accepted),
        attempts=len(all_records), loaded_attempts=sum(r['item']['status'] == 'LOADED' for r in all_records),
        retaken=sum(len(v['records']) > 1 for v in units.values()), **polled)
    require(count['accepted_query_timing_observations'] == 5000, 'new accepted workload differs from exactly four passes/5000 queries')
    return dict(main=main, B1=dict(**B1, baseline_p50_ns=88965, new_p50_ns=ns, ratio=str(Fraction(ns, 88965))),
        AA=dict(status='PASS', first_p50_ns=first, second_p50_ns=second, relative_difference=str(Fraction(abs(second - first), first))),
        boundary=dict(status='PASS', aligned_p50_ns=aligned, crossing_p50_ns=crossing), counts=count)


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, default=HERE / 'audit.json'); args = parser.parse_args()
    result = dict(schema='hw-region-2-binary-independent-audit-v1', stage='all', saved_data_only=True, no_codecs=True, no_clocks=True,
                  private_paths_required=False, source_binding_base='repository')
    try:
        sha(Path(__file__).resolve())
        data = prepare_stage(); admitted = admission_stage(data); result.update(final_stage(data))
        require(sources() == COHORT['source_sha256'], 'source cohort changed during audit')
        result.update(status='PASS', completion='COMPLETE', admission=admitted, host=HOST,
            original_forecasts=dict(P1='HIT', P2='MISS', P3='HIT', P3_wins=30, P3_total=30), parent_audit=ref(BASE / 'audit/resumed-all.json'),
            reused_pure_validator=ref(BASE / 'audit.py'), independent_public_capture_pairs=len(A.CAPTURE_CACHE))
        # Bind the renderer if already present; no generated report text is an
        # input or prerequisite of this saved-data proof.
        for path in HERE.glob('*.py'):
            sha(path)
    except Incomplete as error:
        result.update(status='INCOMPLETE', reason=str(error))
    except (ValueError, KeyError, IndexError, TypeError, OSError, struct.error, StopIteration) as error:
        result.update(status='FAIL', reason=type(error).__name__ + ': ' + str(error))
    result['source_bindings'] = [dict(path=k, sha256=v) for k, v in sorted(BINDS.items())]
    output = args.output.resolve(); require(output.parent == HERE and output.suffix == '.json', 'audit output must stay in the new stage')
    output.write_bytes(packed(result))
    print(json.dumps({k: result[k] for k in ('status', 'reason', 'main', 'B1', 'counts') if k in result}, sort_keys=True))
    return 0 if result['status'] == 'PASS' else 2 if result['status'] == 'INCOMPLETE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
