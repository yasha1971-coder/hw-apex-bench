"""Independent saved-data controller for HW-GIFT-1d.

This module never imports the instrument/orchestrator and never encodes,
decodes, builds, invokes a worker, or reads a clock. Its default output is JSON
on stdout; --output is the only requested write operation.
"""
import argparse
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GRIDS = (256, 1024, 4096, 16384, 65536, 262144, 524288)
LEVELS = (3, 10, 19)
CANDIDATES = (1024, 4096, 16384, 65536)
PREFIX_BYTES = 16777216
INPUTS = {
    'enwik8': (100000000, '2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8'),
    'silesia.tar': (211947520, 'a667bac80089b3d04d5496772149e632f0758974b0579d743cd8d6e5e0d63eb2'),
}
LOCK = '/run/lock/ovh-bench.lock'
PRIVATE_CHECKED = set()
PRIVATE_UNAVAILABLE = set()
PREFIX_HASHES = {}
SOURCE_BINDINGS = {}


def bind_source(path, digest):
    """Bind every public input actually inspected; do not publish private paths."""
    path = Path(path).resolve()
    if path.is_relative_to((ROOT/'evidence').resolve()):
        import os
        name = os.path.relpath(path,HERE).replace('\\','/')
        old = SOURCE_BINDINGS.setdefault(name,digest)
        check(old == digest, 'evidence changed while being audited: '+name)


def private_file(name, digest, size=None, required=False):
    check(isinstance(name,str) and valid_sha(digest), 'invalid private artifact identity')
    path = Path(name)
    if path.is_file():
        identity = str(path), digest
        if size is not None:
            check(path.stat().st_size == size, 'private byte count mismatch: '+str(path))
        if identity not in PRIVATE_CHECKED:
            check(sha(path) == digest, 'private SHA-256 mismatch: '+str(path))
            PRIVATE_CHECKED.add(identity)
        return True
    PRIVATE_UNAVAILABLE.add(name)
    if required:
        raise Incomplete('private artifact unavailable: '+name)
    return False


class Incomplete(ValueError):
    pass


def check(ok, message):
    if not ok:
        raise ValueError(message)


def positive(value):
    return type(value) is int and value > 0


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def sha(path):
    with Path(path).open('rb') as stream:
        value = hashlib.file_digest(stream, 'sha256').hexdigest()
    bind_source(path,value)
    return value


def valid_sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def load(path):
    path = Path(path)
    if not path.is_file():
        raise Incomplete('missing evidence: ' + str(path))
    def unique(pairs):
        result = {}
        for key, value in pairs:
            check(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    raw = path.read_bytes()
    bind_source(path,hashlib.sha256(raw).hexdigest())
    return json.loads(raw, object_pairs_hook=unique)


def relative(name):
    check(isinstance(name, str) and name, 'missing evidence path')
    path = (HERE / name).resolve()
    check(path.is_relative_to(HERE.resolve()), 'evidence path escapes the experiment')
    return path


def ref(value):
    check(isinstance(value, dict) and valid_sha(value.get('sha256')), 'invalid evidence reference')
    path = relative(value.get('path'))
    if not path.is_file():
        raise Incomplete('missing referenced evidence: ' + str(path))
    check(sha(path) == value['sha256'], 'referenced bytes changed: ' + value['path'])
    return load(path), path


def median5(values):
    check(isinstance(values, list) and len(values) == 5 and all(positive(v) for v in values),
          'exactly five positive integer observations required')
    return sorted(values)[2]


def cell_index(level, g):
    check(level in LEVELS and g in GRIDS, 'cell outside preregistered grid')
    return LEVELS.index(level) * len(GRIDS) + GRIDS.index(g)


def expected_order(phase, index, repeat, conditional=True):
    if phase == 'method':
        return ['original', 'original']
    base = ['original', 'conditional'] if phase == 'validate' else ['original', 'nohint']
    if phase == 'holdout' and conditional:
        base = ['original', 'nohint', 'conditional']
        if index % 2:
            base.reverse()
        shift = repeat % 3
        return base[shift:] + base[:shift]
    return list(reversed(base)) if (index + repeat) % 2 else base


def choose_x(training):
    """Return the first qualifying measured threshold; no holdout is consulted."""
    check(set(training) == {(level, g) for level in LEVELS for g in GRIDS}, 'X selection needs all 21 training cells')
    eligibility = []
    for threshold in CANDIDATES:
        failures = []
        for (level, g), variants in sorted(training.items()):
            if g >= threshold:
                a = variants['original']['median_ns']
                b = variants['nohint']['median_ns']
                if 10*b > 11*a:
                    failures.append(dict(level=level, g=g, ratio=str(Fraction(b, a))))
        eligibility.append(dict(threshold_bytes=threshold, passed=not failures, failures=failures))
    selected = next((r['threshold_bytes'] for r in eligibility if r['passed']), None)
    return selected, eligibility


def literal_gates(training, holdout, validation, threshold):
    check(set(training) == {(l, g) for l in LEVELS for g in GRIDS}, 'P1/P2 need all training cells')
    p1cell = training[10, 256]
    a, b = p1cell['original']['median_ns'], p1cell['nohint']['median_ns']
    p1 = dict(passed=b >= 3*a, original_ns=a, nohint_ns=b, ratio=str(Fraction(b, a)))
    p2rows, killrows = [], []
    for corpus, cells in (('enwik8', training), ('silesia.tar', holdout)):
        for level in LEVELS:
            for g in GRIDS:
                if level not in (3, 10) or g < 65536:
                    continue
                if (level, g) not in cells:
                    raise Incomplete('P2 missing ' + corpus + '/' + str((level, g)))
                v = cells[level, g]
                a, b = v['original']['median_ns'], v['nohint']['median_ns']
                speed = 9*a <= 10*b <= 11*a
                size = v['nohint']['archive_bytes'] <= v['original']['archive_bytes']
                p2rows.append(dict(corpus=corpus, level=level, g=g, ratio=str(Fraction(b, a)), speed_pass=speed, size_pass=size))
                if level == 3 and g == 65536:
                    killrows.append(dict(corpus=corpus, triggered=10*b >= 11*a, ratio=str(Fraction(b, a))))
    p3rows = []
    if threshold is not None:
        for corpus, cells, baseline in (('enwik8', validation, training), ('silesia.tar', holdout, holdout)):
            if set(cells) != {(l, g) for l in LEVELS for g in GRIDS}:
                raise Incomplete('P3 needs all conditional cells on ' + corpus)
            for (level, g), v in sorted(cells.items()):
                a, c = v['original']['median_ns'], v['conditional']['median_ns']
                chosen = 'original' if g < threshold else 'nohint'
                identity = (v['conditional']['archive_bytes'], v['conditional']['archive_sha256']) == (
                    baseline[level, g][chosen]['archive_bytes'], baseline[level, g][chosen]['archive_sha256'])
                size_allowance = g < threshold or 2000*(v['conditional']['archive_bytes']-baseline[level,g]['nohint']['archive_bytes']) <= baseline[level,g]['nohint']['archive_bytes']
                p3rows.append(dict(corpus=corpus, level=level, g=g, ratio=str(Fraction(c, a)), speed_pass=10*c <= 11*a,
                                   archive_identity_pass=identity, size_allowance_pass=size_allowance))
    return dict(P1=p1, P2=dict(passed=all(r['speed_pass'] and r['size_pass'] for r in p2rows), cells=p2rows),
                P3=dict(passed=threshold is not None and all(r['speed_pass'] and r['archive_identity_pass'] and r['size_allowance_pass'] for r in p3rows),
                        threshold_bytes=threshold, cells=p3rows), Kill=dict(triggered=any(r['triggered'] for r in killrows), cells=killrows))


def cpu_delta(start, end):
    def parse(boundary):
        check('proc_stat_raw' in boundary and 'proc_stat_error' in boundary, 'missing per-core observation')
        if boundary['proc_stat_error'] or not isinstance(boundary['proc_stat_raw'], str):
            raise ValueError('capture unavailable')
        result = {}
        for line in boundary['proc_stat_raw'].splitlines():
            fields = line.split()
            if fields and fields[0].startswith('cpu') and fields[0][3:].isdigit():
                if len(fields) < 9 or not all(x.isdigit() for x in fields[1:9]) or fields[0] in result:
                    raise ValueError('invalid per-core counters')
                result[fields[0]] = list(map(int, fields[1:9]))
        if 'cpu0' not in result:
            raise ValueError('missing CPU0')
        return result
    unavailable = False
    try:
        a, b = parse(start), parse(end)
        if a.keys() != b.keys():
            raise ValueError('CPU set changed')
        cpus = {}
        for name in a:
            if name == 'cpu0':
                continue
            d = [last-first for first,last in zip(a[name],b[name])]
            if min(d) < 0:
                raise ValueError('counter regression')
            total, idle, wait = sum(d), d[3], d[4]
            busy = total-idle-wait
            cpus[name] = dict(total_jiffies=total,busy_jiffies=busy,idle_jiffies=idle,iowait_jiffies=wait,
                              busy_percent=100.0*busy/total if total else None)
    except ValueError:
        unavailable = True
    actual = start.get('other_cpu_delta')
    check(isinstance(actual,dict) and actual == end.get('other_cpu_delta') and actual.get('pinned_core') == 0,
          'per-core observations differ across boundaries')
    if unavailable:
        check(actual.get('status') == 'unavailable' and actual.get('cpus') == {} and isinstance(actual.get('error'),str),
              'unavailable per-core data not identified')
    else:
        check(actual == dict(status='ok',pinned_core=0,cpus=cpus), 'per-core busy/total deltas differ from raw counters')


def receipt(value, status):
    check(value.get('schema') == 'ovh-bench-v2' and value.get('load1_threshold') == '2.0', 'wrong load policy')
    check(value.get('status') == status and status in ('CLEAN','LOADED'), 'ERROR or unfinished attempt')
    check(value.get('lock_path') == LOCK, 'wrong benchmark lock')
    argv = value.get('flock_command')
    check(isinstance(argv,list) and len(argv) >= 6 and argv[:2] == ['flock',LOCK] and argv[3] == '-B' and argv[5] == '_inside',
          'timed work did not use the blocking external flock command')
    command = value.get('command')
    check(isinstance(command,list) and command and argv[-len(command):] == command, 'flock worker command mismatch')
    if value.get('command_started'):
        check(type(value.get('returncode')) is int and value['returncode'] == 0, 'nonzero worker error cannot be a load retry')
    else:
        check(value.get('command_started') is False and value.get('returncode') is None and status == 'LOADED', 'unstarted CLEAN command')
    one = []
    for boundary in (value.get('start'), value.get('end')):
        check(isinstance(boundary,dict) and boundary.get('hostname') == 'ace-core' and boundary.get('pinned_core') == 0,
              'wrong benchmark host/core')
        check(isinstance(boundary.get('date_u'),str) and boundary['date_u'] and positive(boundary.get('nproc')), 'missing literal boundary receipts')
        raw = boundary.get('loadavg_raw')
        check(isinstance(raw,str) and len(raw.split()) == 5, 'missing raw load average')
        number = Decimal(raw.split()[0])
        check(number.is_finite() and number >= 0, 'invalid raw load1')
        one.append(number)
    loaded = any(n > Decimal('2.0') for n in one)
    check(loaded == (status == 'LOADED'), 'load classification does not match exact threshold')
    check(bool(value['command_started']) == (one[0] <= Decimal('2.0')), 'worker-start marker contradicts load1')
    cpu_delta(value['start'],value['end'])
    if status == 'LOADED':
        check(value.get('ps_command') == 'ps -eo pid,user,pcpu,comm --sort=-pcpu | head -8'
              and isinstance(value.get('ps_top8'),str) and value['ps_top8'], 'missing literal ps top eight')


def verify_request(value):
    check(value.get('schema') == 'hw-gift-1d-cell-v1' and value.get('corpus') in INPUTS, 'invalid worker cell request')
    level, g, corpus = value.get('level'), value.get('g'), value['corpus']
    index = cell_index(level,g)
    full_size, full_sha = INPUTS[corpus]
    prefix = PREFIX_BYTES if g in (256,1024) else None
    check((value.get('full_corpus_bytes'),value.get('full_corpus_sha256'),value.get('prefix_bytes'),value.get('input_bytes'))
          == (full_size,full_sha,prefix,prefix or full_size), 'wrong input/prefix scope')
    check(valid_sha(value.get('input_sha256')), 'missing input SHA')
    if prefix is None:
        check(value['input_sha256'] == full_sha, 'full input SHA differs from retained corpus')
    else:
        prior = PREFIX_HASHES.setdefault(corpus,value['input_sha256'])
        check(prior == value['input_sha256'], 'prefix changes across cells/phases')
    private_file(value.get('input_path'),value['input_sha256'],value['input_bytes'])
    original = dict(value)
    supplied = original.pop('cell_id')
    corpus_label = 'enwik8' if corpus == 'enwik8' else 'silesia'
    expected = f'{corpus_label}-L{level}-G{g}-'+hashlib.sha256(packed(original)).hexdigest()[:16]
    check(supplied == expected, 'cell request identity changed')
    check(value.get('protocol_sha256') == sha(HERE/'CALIBRATION.md'), 'calibration changed')
    check(value.get('instrument_sha256') == sha(HERE/'instrument.py'), 'worker instrument changed')
    check(valid_sha(value.get('base_build_sha256')), 'missing native base identity')
    conditional = 'conditional' in value.get('variants',[])
    check((conditional and value.get('threshold') in CANDIDATES and valid_sha(value.get('conditional_build_sha256')))
          or (not conditional and value.get('threshold') is None and value.get('conditional_build_sha256') is None),
          'conditional build/threshold mismatch')
    return index


def verify_row(row, request, variant, slot, timed, decode):
    check(row.get('slot') == slot and row.get('variant') == variant, 'measurement slot/order mismatch')
    check(row.get('bit_perfect') is True and row.get('decoded_bytes') == request['input_bytes']
          and row.get('decoded_sha256') == request['input_sha256'], 'incomplete byte restoration')
    check(positive(row.get('archive_bytes')) and valid_sha(row.get('archive_sha256')), 'invalid archive identity')
    check(positive(row.get('frame_count')) and row.get('seek_checksum_flag') is True
          and row.get('seek_table_bytes') == 17+12*row['frame_count'], 'complete seek table/checksum format changed')
    check(row['archive_bytes'] > row['seek_table_bytes'] and positive(row.get('context_bytes')), 'invalid frame/context byte count')
    check(isinstance(row.get('header'),dict), 'missing frame header observation')
    if timed:
        check(positive(row.get('compression_ns')), 'invalid compression observation')
        check(positive(row.get('decode_ns')) if decode else row.get('decode_ns') is None, 'decode timing scope changed')
    else:
        check(row.get('compression_ns') is None and row.get('decode_ns') is None, 'untimed selfcheck includes clocks')
    private_file(row.get('archive_path'),row['archive_sha256'],row['archive_bytes'])


def verify_worker(value, request, order, pair_index, selfcheck, selfcheck_sha, method=False):
    check(value.get('schema') == 'hw-gift-1d-worker-v1' and value.get('measurements_of_time') is True, 'not a timed worker result')
    check(value.get('cell_id') == request['cell_id'] and value.get('cell_sha256') == hashlib.sha256(packed(request)).hexdigest(),
          'worker cell differs from its request')
    check(value.get('order') == order and value.get('pair_index') == pair_index and value.get('method_control') is method,
          'worker order/repeat/method identity changed')
    check(value.get('input_bytes') == request['input_bytes'] and value.get('input_sha256') == request['input_sha256']
          and value.get('control_override') is False, 'timed worker changed input')
    check(value.get('protocol_sha256') == request['protocol_sha256']
          and value.get('instrument_sha256') == request['instrument_sha256'] and value.get('selfcheck_sha256') == selfcheck_sha,
          'worker source/selfcheck identity changed')
    check(value.get('cpu_affinity') == [0] and value.get('lock_path') == LOCK, 'worker not pinned/locked')
    decode = value.get('decode_timed')
    check(type(decode) is bool and (method or decode == (pair_index == 0)), 'full-decode observation count changed')
    check(value.get('clock_calls') == len(order)*(4 if decode else 2), 'unexpected clock-read count')
    results = value.get('results')
    check(isinstance(results,list) and len(results) == len(order), 'missing measurement slots')
    reference = {r['variant']:(r['archive_bytes'],r['archive_sha256']) for r in selfcheck['results']}
    for slot, (variant,row) in enumerate(zip(order,results)):
        verify_row(row,request,variant,slot,True,decode)
        check((row['archive_bytes'],row['archive_sha256']) == reference[variant], 'timed bytes differ from untimed manifest')
    return results


def selfcheck_for(summary, request):
    value, path = ref(dict(path=summary['selfcheck_path'],sha256=summary['selfcheck_sha256']))
    check(value.get('schema') == 'hw-gift-1d-selfcheck-v1' and value.get('status') == 'PASS'
          and value.get('clock_calls') == 0 and value.get('measurements_of_time') is False, 'untimed selfcheck did not pass')
    check(value.get('cell_id') == request['cell_id'] and value.get('cell_sha256') == hashlib.sha256(packed(request)).hexdigest(),
          'selfcheck cell identity differs')
    check([r['variant'] for r in value.get('results',[])] == request['variants'], 'selfcheck variants changed')
    for slot,row in enumerate(value['results']):
        verify_row(row,request,row['variant'],slot,False,False)
    known = request['corpus'] == 'enwik8' and request['level'] == 3 and request['g'] == 262144
    check(value.get('known_1c_checked') is known, 'known-answer marker differs from cell scope')
    if known:
        case = load(HERE.parent/'hw-gift-1c/cases/enwik8-L3-262144.json')
        for row in value['results']:
            branch = 'original' if row['variant'] == 'original' or (row['variant'] == 'conditional' and request['g'] < request['threshold']) else 'patched'
            check((row['archive_bytes'],row['archive_sha256']) == (case['archives'][branch]['bytes'],case['archives'][branch]['sha256']),
                  'known HW-GIFT-1c full archive does not reproduce')
    return value, path


def verify_repeats(summary, request, method=False):
    phase = 'method' if method else summary['phase']
    index = verify_request(request)
    control, control_path = selfcheck_for(summary,request)
    repeats = summary.get('repeats')
    if not isinstance(repeats,list) or len(repeats) != 5:
        raise Incomplete('five complete paired/triple repetitions required')
    rows, attempts_count, loaded_count, retaken = [],0,0,0
    used_receipts = set()
    for number, logical in enumerate(repeats):
        order = expected_order(phase,index,number,'conditional' in request['variants'])
        check(logical.get('pair_index') == number and logical.get('order') == order, 'interleaved order differs from frozen schedule')
        attempts = logical.get('attempts')
        check(isinstance(attempts,list) and 1 <= len(attempts) <= 3, 'attempt budget exceeded')
        retaken += len(attempts)>1
        last = None
        for attempt_number, attempt in enumerate(attempts,1):
            status = 'CLEAN' if attempt_number == len(attempts) else 'LOADED'
            check(attempt.get('attempt') == attempt_number and attempt.get('status') == status, 'first CLEAN must win; only load retries allowed')
            record, record_path = ref(attempt['receipt'])
            check(record == attempt.get('receipt_data'), 'receipt metadata differs from retained bytes')
            check(str(record_path) not in used_receipts, 'one receipt reused by several logical attempts')
            used_receipts.add(str(record_path))
            receipt(record,status)
            check(record.get('helper_sha256') == sha(HERE.parent/'hw-gift-1b/ovh_bench.py'), 'shared lock helper changed')
            for suffix,field in (('.stdout','stdout_sha256'),('.stderr','stderr_sha256')):
                file = Path(str(record_path)+suffix)
                check(file.is_file() and sha(file) == record.get(field), 'helper stdout/stderr bytes changed')
            selected = attempt.get('result')
            if record['command_started']:
                value, result_path = ref(selected)
                actual_rows = verify_worker(value,request,order,number,control,sha(control_path),method)
                check(json.loads(Path(str(record_path)+'.stdout').read_bytes()) == value, 'raw stdout differs from retained result')
                if status == 'CLEAN':
                    rows.append(actual_rows)
            else:
                check(selected is None, 'unstarted attempt has a result')
            attempts_count += 1
            loaded_count += status == 'LOADED'
            last = attempt
        check(logical.get('selected_result') == last.get('result') and logical.get('selected_receipt') == last['receipt'],
              'selected result is not the first CLEAN')
    return rows, dict(logical_repeats=5,attempts=attempts_count,retaken=retaken,loaded_attempts=loaded_count)


def verify_cell(path):
    summary = load(path)
    if summary.get('status') != 'COMPLETE':
        raise Incomplete('cell has not completed: '+str(path))
    phase = summary.get('phase')
    check(phase in ('train','validate','holdout'), 'unknown experiment phase')
    request, _ = ref(dict(path=summary['request_path'],sha256=summary['request_sha256']))
    expected_corpus = 'silesia.tar' if phase == 'holdout' else 'enwik8'
    check(summary.get('corpus') == request['corpus'] == expected_corpus
          and summary.get('level') == request['level'] and summary.get('g') == request['g'], 'summary grid identity mismatch')
    check(summary.get('cell_index') == cell_index(request['level'],request['g']), 'summary cell index mismatch')
    if phase == 'train':
        check(request['variants'] == ['original','nohint'], 'training must remain A/B only')
    if phase == 'validate':
        check(request['variants'] == ['original','conditional'], 'conditional validation must be A/C')
    verify_provenance(summary['provenance'])
    method, _ = ref(dict(path=summary['method_check_path'],sha256=summary['method_check_sha256']))
    check(method.get('status') == 'PASS', 'main grid ran without passing the AA method gate')
    for key in ('input_bytes','input_sha256','full_corpus_bytes','full_corpus_sha256','prefix_bytes'):
        check(summary.get(key) == request[key], 'summary input scope differs from its request')
    verify_native_builds(request)
    rows, counters = verify_repeats(summary,request)
    derived = {}
    for variant in request['variants']:
        values = [next(row for row in group if row['variant'] == variant) for group in rows]
        ns = [row['compression_ns'] for row in values]
        ids = {(row['archive_bytes'],row['archive_sha256']) for row in values}
        check(len(ids) == 1, 'repeated encodings are not deterministic')
        size, digest = next(iter(ids))
        decoded = [row['decode_ns'] for row in values if row['decode_ns'] is not None]
        check(len(decoded) == 1, 'exactly one full-decode observation per cell/variant is required')
        derived[variant] = dict(compression_ns=ns,median_ns=median5(ns),min_ns=min(ns),archive_bytes=size,archive_sha256=digest,decode_ns=decoded[0])
        for key,value in derived[variant].items():
            check(summary['variants'][variant].get(key) == value, 'summary statistic differs from raw measurements: '+variant+'/'+key)
    verify_counters(summary,counters)
    return dict(variants=derived,request=request,counters=counters,source_path=str(path),summary=summary)


def verify_provenance(value):
    check(isinstance(value,dict) and value.get('calibration_commit') == '2d02a8b466ab1d1a07a4c604e17775bb60d7162d', 'wrong first preregistration commit')
    check(value.get('calibration_sha256') == sha(HERE/'CALIBRATION.md') and value.get('protocol_sha256') == sha(HERE/'PROTOCOL.md'),
          'experiment protocol bytes changed')
    check(isinstance(value.get('order_commit'),str) and value['order_commit'].startswith('695457a'), 'counterbalanced order amendment missing')
    required = {'CALIBRATION.md','PROTOCOL.md','run.py','instrument.py','controls.py','../hw-gift-1b/ovh_bench.py'}
    check(set(value.get('source_hashes',{})) == required, 'source fingerprint coverage changed')
    for name,digest in value['source_hashes'].items():
        path = (HERE/name).resolve()
        check(path.is_relative_to(ROOT.resolve()) and sha(path) == digest, 'source changed: '+name)


def verify_counters(summary, derived):
    for name, expected in (('planned_repeats',5),('started_repeats',derived['logical_repeats']),
                           ('retaken_repeats',derived['retaken']),('loaded_attempts',derived['loaded_attempts'])):
        check(type(summary.get(name)) is int and summary[name] == expected, 'attempt counter differs from raw receipts: '+name)


def verify_native_builds(request):
    paths = [(HERE/'native/base/build.json',request['base_build_sha256'],None)]
    if request.get('threshold') is not None:
        paths.append((HERE/f"native/conditional-{request['threshold']}/build.json",request['conditional_build_sha256'],request['threshold']))
    prior = load(HERE.parent/'hw-gift-1c/timing/native-build.json')['request']
    for path,digest,threshold in paths:
        value = load(path)
        check(sha(path) == digest and value.get('schema') == 'hw-gift-1d-native-v1', 'native build receipt changed')
        identity = value['identity']
        check(identity['protocol']['sha256'] == request['protocol_sha256']
              and identity['instrument_sha256'] == request['instrument_sha256'] and identity['threshold'] == threshold,
              'native build scope/source differs from request')
        check(identity['zstd_commit'] == 'f8745da6ff1ad1e7bab384bd1f9d742439278e99'
              and identity['static_library_sha256'] == prior['static_library_sha256'], 'zstd pin/static library changed')
        check(identity['upstream_compress_sha256'] == prior['source_sha256']['original-compress.c'], 'upstream writer source changed')
        check(identity['bridge_source_sha256'] == sha(HERE.parent/'hw-gift-1c/timing.py'), 'native API-loop bridge changed')
        if threshold is not None:
            check(identity['base_build_sha256'] == request['base_build_sha256'], 'conditional build changed the base cohort')
            check(identity['conditional_protocol']['sha256'] == sha(HERE/'CONDITIONAL_PROTOCOL.md'), 'conditional development protocol changed')
        for name,item in value['libraries'].items():
            check('-Wl,-Bsymbolic' in item['command'] and valid_sha(item['sha256']), 'library binding/build fingerprint missing')
            private_file(item['path'],item['sha256'])


def verify_codec_controls(preparation, request):
    controls, _ = ref(preparation['controls'])
    check(controls.get('status') == 'PASS' and controls.get('clock_calls') == 0 and controls.get('measurements_of_time') is False,
          'untimed codec controls did not pass')
    for field,name in (('calibration_sha256','CALIBRATION.md'),('instrument_sha256','instrument.py'),('controls_sha256','controls.py')):
        check(controls[field] == sha(HERE/name), 'codec-control source binding changed')
    check(controls['cell_sha256'] == hashlib.sha256(packed(request)).hexdigest(), 'codec-control input cell changed')
    known_file = HERE.parent/'hw-gift-1c/cases/enwik8-L3-262144.json'
    known = load(known_file)
    check(controls['known_answer_sha256'] == sha(known_file), 'known answer source changed')
    positive = controls['positive']
    check(positive['clock_calls'] == 0 and [r['variant'] for r in positive['results']] == ['original','original'], 'positive control lost duplicate slots')
    check((positive['results'][0]['archive_bytes'],positive['results'][0]['archive_sha256'])
          == (positive['results'][1]['archive_bytes'],positive['results'][1]['archive_sha256']), 'positive same-call byte equality failed')
    for group in (positive,controls['known_answer']):
        check(group['clock_calls'] == 0 and group['input_sha256'] == request['input_sha256'], 'untimed control input/clock scope changed')
        for slot,row in enumerate(group['results']):
            verify_row(row,request,row['variant'],slot,False,False)
            variant = 'original' if row['variant'] == 'original' else 'patched'
            check((row['archive_bytes'],row['archive_sha256']) == (known['archives'][variant]['bytes'],known['archives'][variant]['sha256']), 'known archive mismatch')
    negative = controls['negative_changed_input']
    check(negative['clock_calls'] == 0 and negative['control_override'] is True and negative['input_sha256'] != request['input_sha256'],
          'negative changed-input control failed')
    changed = dict(request,input_sha256=negative['input_sha256'])
    for slot,row in enumerate(negative['results']):
        verify_row(row,changed,row['variant'],slot,False,False)
        check(row['archive_sha256'] != positive['results'][0]['archive_sha256'], 'negative input invisible to instrument')
    check(controls.get('corrupt_magic_rejected') is True, 'corrupt-frame error control failed')
    expected = [('1.00','1.00',False),('2.00','2.00',False),('2.01','0.00',True),('0.00','2.01',True)]
    check(len(controls['load_gate_cases']) == 4, 'missing known load-gate cases')
    for value,(start,end,answer) in zip(controls['load_gate_cases'],expected):
        actual = any(Decimal(v)>Decimal('2.0') for v in (value['start'],value['end']))
        check((value['start'],value['end'],value['expected_loaded'],value['actual_loaded']) == (start,end,answer,actual), 'load gate failed known answer')
    check(controls['other_cpu_known_answer'] == dict(status='ok',pinned_core=0,cpus={'cpu1':dict(total_jiffies=10,busy_jiffies=3,idle_jiffies=7,iowait_jiffies=0,busy_percent=30.0)}),
          'CPU utilization known-answer check failed')
    return controls


def verify_method():
    prep = load(HERE/'preparation.json')
    check(prep.get('status') == 'PASS', 'preparation not passed')
    verify_provenance(prep['provenance'])
    request, _ = ref(prep['request'])
    verify_request(request)
    verify_native_builds(request)
    verify_codec_controls(prep,request)
    value = load(HERE/'method-check.json')
    check(value.get('schema') == 'hw-gift-1d-method-v1', 'unknown method-check schema')
    check(value.get('protocol_sha256') == request['protocol_sha256'] and value.get('instrument_sha256') == request['instrument_sha256'],
          'AA gate not bound to the current instrument/calibration')
    verify_provenance(value['provenance'])
    rows,counters = verify_repeats(value,request,True)
    first,second = [r[0]['compression_ns'] for r in rows],[r[1]['compression_ns'] for r in rows]
    a,b = median5(first),median5(second)
    passed = abs(b-a)*20<a
    check(value.get('first_ns') == first and value.get('second_ns') == second
          and value.get('median_first_ns') == a and value.get('median_second_ns') == b, 'AA medians differ from raw results')
    check(value.get('status') == ('PASS' if passed else 'FAIL'), 'AA method verdict differs from preregistered strict gate')
    verify_counters(value,counters)
    return dict(status=value['status'],first_ns=first,second_ns=second,median_first_ns=a,median_second_ns=b,
                relative_median_change=str(Fraction(b-a,a)),counters=counters)


def phase(name):
    result = {}
    for level in LEVELS:
        for g in GRIDS:
            result[level,g] = verify_cell(HERE/'cells'/name/f'L{level}-G{g}.json')
    return result


def variants(cells):
    return {key:value['variants'] for key,value in cells.items()}


def verify_selection(training):
    value = load(HERE/'selection.json')
    selected,candidates = choose_x(variants(training))
    check(value.get('threshold_bytes') == selected and value.get('status') == ('SELECTED' if selected is not None else 'NO SUPPORTED X'),
          'X differs from the smallest eligible preregistered training candidate')
    check(value.get('training_only') is True and value.get('holdout_inspected') is False, 'threshold not declared training-only')
    expected_paths = {f'cells/train/L{level}-G{g}.json' for level in LEVELS for g in GRIDS}
    check({v['path'] for v in value['training']} == expected_paths and len(value['training']) == 21, 'threshold selection omitted a training cell')
    for item in value['training']:
        ref(item)
    for field,name in (('calibration_sha256','CALIBRATION.md'),('protocol_sha256','PROTOCOL.md'),('selector_sha256','select_threshold.py')):
        check(value[field] == sha(HERE/name), 'threshold selector/source bytes changed')
    check([r['threshold_bytes'] for r in value['candidates']] == list(CANDIDATES), 'candidate list changed')
    for primary,independent in zip(value['candidates'],candidates):
        failures = [(f['level'],f['g']) for f in independent['failures']]
        check(primary['eligible'] == independent['passed'] and [(f['level'],f['g']) for f in primary['failures']] == failures,
              'candidate eligibility differs from raw-derived medians')
    return selected,dict(status=value['status'],threshold_bytes=selected,candidates=candidates)


def verify_freeze(cells, selected):
    selection_sha = sha(HERE/'selection.json')
    protocol_sha = sha(HERE/'CONDITIONAL_PROTOCOL.md')
    # Read-only Git inspection proves the actual selection/protocol versions
    # were committed before each validation/holdout cell was admitted.
    def git(*args):
        return subprocess.check_output(['git','-C',str(ROOT),*args],stderr=subprocess.PIPE)
    selection_commit = git('log','-1','--format=%H','--','evidence/hw-gift-1d/selection.json').decode().strip()
    check(selection_commit, 'selection is not committed')
    for item in cells.values():
        summary,request = item['summary'],item['request']
        freeze = summary.get('freeze')
        check(isinstance(freeze,dict) and freeze['selection']['sha256'] == selection_sha
              and freeze['conditional_protocol'] == dict(path='CONDITIONAL_PROTOCOL.md',sha256=protocol_sha),
              'cell does not bind the committed development freeze')
        ref(freeze['selection'])
        check(request['threshold'] == selected, 'X changed after development selection')
        source_commit = summary['provenance']['source_commit']
        completed = subprocess.run(['git','-C',str(ROOT),'merge-base','--is-ancestor',selection_commit,source_commit],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        check(completed.returncode == 0, 'holdout/validation predates the committed threshold selection')


def verify_native_proof(selected, *phases):
    """Bind the separate post-timing byte/decoder proof to these exact results."""
    path = HERE/'audit/native.json'
    proof = load(path)
    check(proof.get('schema') == 'hw-gift-1d-independent-native-v1' and proof.get('status') == 'PASS',
          'independent native correctness proof did not pass')
    check(proof.get('no_clocks') is True and proof.get('measurements_of_time') is False
          and proof.get('all_attempts') is True and type(proof.get('minimal_encodings_authorized')) is int
          and proof['minimal_encodings_authorized'] == 2,
          'native proof clock/attempt/minimal-encoding scope changed')
    check(proof.get('source_sha256') == sha(HERE/'verify_native.py'), 'native verifier source changed after its proof')
    count_names = ('archive_references','archive_paths_verified','unique_archives_verified',
                   'frame_decodes_verified','restored_bytes_verified')
    check(all(positive(proof.get(name)) for name in count_names), 'native proof lacks positive verification counts')
    archives,paths = proof['archives'],proof['archive_paths']
    check(isinstance(archives,list) and isinstance(paths,dict)
          and len(archives) == proof['unique_archives_verified'] and len(paths) == proof['archive_paths_verified']
          and proof['archive_references'] >= len(paths) >= len(archives), 'native archive/path counts disagree')
    for item in paths.values():
        check(positive(item.get('bytes')) and valid_sha(item.get('sha256')), 'invalid verified native path identity')
    for archive in archives:
        check(positive(archive.get('frame_count')) and positive(archive.get('nonempty_frame_count'))
              and type(archive.get('empty_terminal_frames')) is int and archive['empty_terminal_frames'] in (0,1)
              and archive['frame_count'] == archive['nonempty_frame_count'] + archive['empty_terminal_frames']
              and archive.get('seek_table_bytes') == 17+12*archive['frame_count']
              and archive.get('seek_checksums_verified') is True and positive(archive.get('restored_bytes'))
              and positive(archive.get('archive_bytes')) and valid_sha(archive.get('archive_sha256'))
              and valid_sha(archive.get('restored_sha256')), 'incomplete native frame/checksum/source proof')
    check(sum(a['frame_count'] for a in archives) == proof['frame_decodes_verified']
          and sum(a['restored_bytes'] for a in archives) == proof['restored_bytes_verified'],
          'native frame/source totals differ from individual archive proofs')
    prep = load(HERE/'preparation.json')
    check(proof['pins']['preparation_sha256'] == sha(HERE/'preparation.json'), 'native proof preparation changed')
    builds = proof['pins']['native_builds']
    required_builds = {'base'} | ({f'conditional-{selected}'} if selected is not None else set())
    check(set(builds) == required_builds, 'native proof uses a different build cohort')
    for name,item in builds.items():
        build_path = HERE/'native'/name/'build.json'
        build = load(build_path)
        check(item['sha256'] == sha(build_path) and item['identity'] == build['identity']
              and item['libraries'] == build['libraries'], 'native proof production build binding changed')
    oracle = proof['independent_build']['identity']
    check(oracle['zstd_commit'] == 'f8745da6ff1ad1e7bab384bd1f9d742439278e99'
          and oracle['static_library_sha256'] == builds['base']['identity']['static_library_sha256']
          and oracle['probe_source_sha256'] == sha(HERE.parent/'hw-gift-1c/frame_probe.c'),
          'independent decoder/probe build pins changed')
    known = {'original':'3cab61b1c4cec5296d5ff271d162bbbd3ef730604c00a8833a4dac211db461e6',
             'nohint':'bf72723ed208c90b32be0400bb1a611201f32555ca98d6f6261395614f2ec2c2'}
    check(set(proof['tiny_probe']) == set(known), 'native tiny proof variant set changed')
    for name,digest in known.items():
        tiny = proof['tiny_probe'][name]
        check(tiny['sha256'] == digest and tiny['result'].get('roundtrip') is True
              and tiny['result'].get('corrupted_magic_error') is True, 'native tiny known-answer proof failed')
    documents = proof['documents_sha256']
    check(isinstance(documents,dict), 'native document bindings missing')
    for name,digest in documents.items():
        document = relative(name)
        check(name == document.relative_to(HERE).as_posix() and valid_sha(digest)
              and sha(document) == digest, 'native proof document bytes changed: '+name)
    required_documents = {'method-controls.json','method-check.json',prep['selfcheck']['path']}
    summaries = [load(HERE/'method-check.json')]
    for cells in phases:
        for item in cells.values():
            required_documents.add(Path(item['source_path']).relative_to(HERE).as_posix())
            summaries.append(item['summary'])
    for summary in summaries:
        required_documents.add(summary['selfcheck_path'])
        for repeat in summary['repeats']:
            for attempt in repeat['attempts']:
                if attempt['result'] is not None:
                    required_documents.add(attempt['result']['path'])
    check(required_documents <= set(documents), 'native proof omits a summary, selfcheck, or retained attempt result')
    conditional = proof['conditional_policy_byte_checks']
    check(isinstance(conditional,list), 'conditional native byte checks missing')
    expected = {(corpus,level,g) for corpus in INPUTS for level in LEVELS for g in GRIDS} if selected is not None else set()
    actual = [(item['corpus'],item['level'],item['g']) for item in conditional]
    check(len(actual) == len(expected) and set(actual) == expected, 'native conditional byte-proof grid incomplete or duplicated')
    for item in conditional:
        check(item['threshold'] == selected and item['selected'] == ('original' if item['g'] < selected else 'nohint')
              and item['bytes_equal'] is True, 'actual conditional archive differs from its frozen branch')
    return dict(path='audit/native.json',sha256=sha(path),source_sha256=proof['source_sha256'],
                **{name:proof[name] for name in count_names},minimal_encodings_authorized=2,
                conditional_policy_cells=len(conditional))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('method','train','selection','all'),default='all')
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    try:
        method = verify_method()
        result = dict(status='PASS',stage=args.stage,method=method,saved_data_only=True,no_codecs_or_clocks_executed=True)
        if args.stage != 'method':
            check(method['status'] == 'PASS', 'method gate failed; main grid is inadmissible')
            training = phase('train')
            selected,candidates = choose_x(variants(training))
            result.update(training_cells=21,independent_threshold_bytes=selected,candidates=candidates)
            if args.stage in ('selection','all'):
                selected,selection = verify_selection(training)
                result['selection'] = selection
            if args.stage == 'all':
                validation = phase('validate') if selected is not None else {}
                holdout = phase('holdout')
                verify_freeze(validation,selected)
                verify_freeze(holdout,selected)
                result['literal_verdicts'] = literal_gates(variants(training),variants(holdout),variants(validation),selected)
                result.update(validation_cells=len(validation),holdout_cells=21,
                              phase_counters={name:{key:sum(v['counters'][key] for v in cells.values()) for key in ('logical_repeats','attempts','retaken','loaded_attempts')}
                                              for name,cells in (('train',training),('validate',validation),('holdout',holdout))})
                result['native_proof'] = verify_native_proof(selected,training,validation,holdout)
        result.update(private_artifacts_hash_verified=len(PRIVATE_CHECKED),private_paths_not_available=sorted(PRIVATE_UNAVAILABLE))
        if args.stage == 'all':
            for name in ('audit.py','report.py','verify_native.py','CALIBRATION.md','PROTOCOL.md','CONDITIONAL_PROTOCOL.md','select_threshold.py'):
                path = HERE/name
                if path.is_file():
                    sha(path)
            result['source_bindings'] = [dict(path=name,sha256=digest) for name,digest in sorted(SOURCE_BINDINGS.items())]
        code = 0
    except Incomplete as error:
        result,code = dict(status='INCOMPLETE',reason=str(error),saved_data_only=True),2
    except (ValueError,KeyError,TypeError) as error:
        result,code = dict(status='FAIL',reason=str(error),saved_data_only=True),1
    text = json.dumps(result,sort_keys=True,separators=(',',':'))+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text,encoding='utf-8',newline='\n')
    else:
        sys.stdout.write(text)
    return code


if __name__ == '__main__':
    raise SystemExit(main())


