"""HW-GIFT-1e staged controller. Importing performs no experiment.

Only worker children run under OVH-BENCH. Preparation/correctness are untimed;
completed CLEAN rounds are rehashed and reused. Core search is a separate stage.
"""
import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = ROOT / '.work/hw-gift-1e'
CODEC = HERE / 'instrument.py'
HELPER = HERE.parent / 'hw-gift-1b/ovh_bench.py'
CORES = ('v1.5.4', 'v1.5.7')
SCOPES = ('full', 'prefix')
CASES = ((10, 256), (10, 1024), (3, 256))
CALIBRATION_COMMIT = '8b1fba61c325a4020dbad165a058d91848f9f914'
SOURCE_NAMES = {'CALIBRATION.md', 'PROTOCOL.md', 'instrument.py', 'run.py', 'controls.py',
                'setup.py', '../hw-gift-1b/ovh_bench.py'}


def require(ok, why):
    if not ok:
        raise ValueError(why)


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.writing')
    with pending.open('wb') as stream:
        stream.write(packed(value))
        stream.flush()
        os.fsync(stream.fileno())
    pending.replace(path)


def relative(path):
    path = Path(path).resolve()
    require(path.is_relative_to(HERE), 'public evidence path escaped HW-GIFT-1e')
    return path.relative_to(HERE).as_posix()


def ref(path):
    return dict(path=relative(path), sha256=sha(path))


def deref(value):
    require(isinstance(value, dict) and set(value) == {'path', 'sha256'}, 'invalid evidence reference')
    path = (HERE / value['path']).resolve()
    relative(path)
    require(path.is_file() and not path.is_symlink() and sha(path) == value['sha256'],
            'retained evidence changed: ' + value['path'])
    return path


def command(*args):
    return [sys.executable, '-B', str(CODEC), *map(str, args)]


def invoke(args):
    result = subprocess.run(list(map(str, args)), cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        sys.stderr.buffer.write(result.stderr)
        sys.stderr.buffer.flush()
    result.check_returncode()


def expose_build(core):
    source, target = STATE / 'native' / core, HERE / 'native' / core
    require((source / 'build.json').is_file(), 'native build receipt missing')
    target.mkdir(parents=True, exist_ok=True)
    for path in source.iterdir():
        if path.suffix not in ('.json', '.stdout', '.stderr', '.patch'):
            continue
        destination, data = target / path.name, path.read_bytes()
        if destination.exists():
            require(destination.read_bytes() == data, 'public native build evidence changed')
        else:
            destination.write_bytes(data)
    return ref(target / 'build.json')


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def provenance():
    paths = [HERE / name for name in ('CALIBRATION.md', 'PROTOCOL.md', 'instrument.py',
                                      'run.py', 'controls.py', 'setup.py')] + [HELPER]
    names = [p.relative_to(ROOT).as_posix() for p in paths]
    for name in names:
        git('ls-files', '--error-unmatch', '--', name)
    require(not git('status', '--porcelain', '--', *names).strip(), 'all experiment sources/protocol must be committed')
    require(git('branch', '--show-current').decode().strip() == 'hw-gift-1e', 'wrong branch')
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', CALIBRATION_COMMIT, 'HEAD'], check=True)
    return dict(source_commit=git('rev-parse', 'HEAD').decode().strip(), calibration_commit=CALIBRATION_COMMIT,
                calibration_sha256=sha(HERE / 'CALIBRATION.md'), protocol_sha256=sha(HERE / 'PROTOCOL.md'),
                source_hashes={os.path.relpath(p, HERE).replace('\\', '/'): sha(p) for p in paths})


def same_sources(old, new):
    require(all(old[k] == new[k] for k in ('calibration_commit', 'calibration_sha256', 'protocol_sha256', 'source_hashes')),
            'experiment source/protocol changed; do not silently resume another cohort')


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def cell_name(scope, level, frame):
    require(scope in SCOPES and (level, frame) in CASES, 'cell outside preregistered grid')
    return f'{scope}-L{level}-G{frame}'


def cell_index(core, scope, level, frame):
    require(core in CORES, 'invalid core')
    return CORES.index(core)*6 + SCOPES.index(scope)*3 + CASES.index((level, frame))


def median(values):
    require(len(values) == 5 and all(type(v) is int and v > 0 for v in values), 'five positive integer observations required')
    return sorted(values)[2]


def verify_selfcheck(path, request):
    value, cell = load(path), load(request)
    require(value['status'] == 'PASS' and value['clock_calls'] == 0 and value['measurements_of_time'] is False
            and value['cell_sha256'] == sha(request) and value['core'] == cell['core'], 'untimed selfcheck changed/failed')
    require([r['variant'] for r in value['results']] == ['A', 'B']
            and all(r['bit_perfect'] is True and r['decoded_bytes'] == cell['input_bytes']
                    and r['decoded_sha256'] == cell['input_sha256'] for r in value['results']), 'untimed restore failed')
    if cell['core'] == 'v1.5.7' and cell['scope'] == 'prefix':
        require(value['known_1d_checked'] is True, 'v1.5.7 prefix known 1d answer did not pass')
    return value


def make_request(core, scope, level, frame):
    name = cell_name(scope, level, frame)
    path, check_path = HERE / 'requests' / core / (name+'.json'), HERE / 'selfchecks' / core / (name+'.json')
    if not path.exists():
        invoke(command('request', '--core', core, '--scope', scope, '--level', level, '--frame', frame, '--output', path))
    value = load(path)
    require((value['core'], value['scope'], value['level'], value['g'], value['variants'])
            == (core, scope, level, frame, ['A', 'B']), 'saved request grid identity changed')
    require(value['protocol_sha256'] == sha(HERE / 'PROTOCOL.md')
            and value['calibration_sha256'] == sha(HERE / 'CALIBRATION.md')
            and value['instrument_sha256'] == sha(CODEC)
            and value['native_build_sha256'] == sha(HERE / 'native' / core / 'build.json'), 'saved request source/build changed')
    if not check_path.exists():
        invoke(command('selfcheck', '--cell', path, '--output', check_path))
    return path, check_path, value, verify_selfcheck(check_path, path)


def verify_controls(path):
    value = load(path)
    require(value['status'] == 'PASS' and value['clock_calls'] == 0 and value['measurements_of_time'] is False,
            'untimed controls did not pass')
    for key, source in (('calibration_sha256', HERE/'CALIBRATION.md'), ('protocol_sha256', HERE/'PROTOCOL.md'),
                        ('instrument_sha256', CODEC), ('controls_sha256', HERE/'controls.py'), ('setup_sha256', HERE/'setup.json')):
        require(value[key] == sha(source), 'controls source/setup binding changed: '+key)
    for core in CORES:
        item = value['cores'][core]
        request, check_path = deref(item['request']), deref(item['selfcheck'])
        cell = load(request)
        require((cell['core'], cell['scope'], cell['level'], cell['g']) == (core, 'full', 10, 256), 'method request differs')
        verify_selfcheck(check_path, request)
    return value


def prepared():
    path = HERE / 'preparation.json'
    require(path.exists(), 'prepare must pass before timing')
    value = load(path)
    require(value['status'] == 'PASS', 'preparation did not pass')
    same_sources(value['provenance'], provenance())
    deref(value['setup'])
    verify_controls(deref(value['controls']))
    for core in CORES:
        deref(value['native_builds'][core])
    return value


def prepare():
    sources = provenance()
    if (HERE / 'preparation.json').exists():
        prepared()
        print('PREPARATION_VERIFIED_SKIP', flush=True)
        return 0
    builds = {}
    for core in CORES:
        invoke(command('build', '--core', core))
        builds[core] = expose_build(core)
    controls = HERE / 'method-controls.json'
    if not controls.exists():
        invoke([sys.executable, '-B', str(HERE/'controls.py'), '--output', str(controls)])
    verify_controls(controls)
    save(HERE/'preparation.json', dict(schema='hw-gift-1e-preparation-v1', status='PASS', provenance=sources,
                                     setup=ref(HERE/'setup.json'), controls=ref(controls), native_builds=builds))
    print('PREPARATION_PASS clock_calls=0', flush=True)
    return 0


def verify_receipt(path, expected_command=None):
    value = load(path)
    require(value.get('schema') == 'ovh-bench-v2' and value.get('load1_threshold') == '2.0'
            and value.get('lock_path') == '/run/lock/ovh-bench.lock'
            and value.get('helper_sha256') == sha(HELPER), 'shared helper/load policy changed')
    if expected_command is not None:
        require(value['command'] == expected_command, 'worker command changed')
    require(value['flock_command'][:2] == ['flock', '/run/lock/ovh-bench.lock'], 'blocking external flock missing')
    for suffix, key in (('.stdout', 'stdout_sha256'), ('.stderr', 'stderr_sha256')):
        require(sha(Path(str(path)+suffix)) == value[key], 'helper stdout/stderr changed')
    require(value['status'] in ('CLEAN', 'LOADED'), 'ERROR/unfinished worker requires inspection')
    one = [Decimal(value[b]['loadavg_raw'].split()[0]) for b in ('start', 'end')]
    require(all(n.is_finite() and n >= 0 for n in one), 'invalid load average')
    require((any(n > Decimal('2.0') for n in one)) == (value['status'] == 'LOADED'), 'load classification changed')
    require(bool(value['command_started']) == (one[0] <= Decimal('2.0')), 'load-start/worker-start marker changed')
    require(all(value[b]['hostname'] == 'ace-core' and value[b]['pinned_core'] == 0 for b in ('start', 'end')),
            'receipt host/core changed')
    require(value['returncode'] == 0 if value['command_started'] else
            value['status'] == 'LOADED' and value['returncode'] is None, 'worker failure cannot be a load retry')
    return value


def verify_worker(path, request_path, pair, order, expected, is_method):
    value, request = load(path), load(request_path)
    require(value['schema'] == 'hw-gift-1e-worker-v1' and value['cell_id'] == request['cell_id']
            and value['cell_sha256'] == sha(request_path) and value['pair_index'] == pair
            and value['order'] == order and value['method_control'] is is_method,
            'worker identity/order/method changed')
    require(value['core'] == request['core'] and value['scope'] == request['scope']
            and value['clock_calls'] == 2*len(order) and value['measurements_of_time'] is True
            and value['control_override'] is False and value['cpu_affinity'] == [0], 'worker timing/source scope changed')
    require(value['selfcheck_sha256'] == hashlib.sha256(packed(expected)).hexdigest(), 'worker selfcheck binding changed')
    for key in ('input_bytes', 'input_sha256', 'protocol_sha256', 'calibration_sha256',
                'instrument_sha256', 'native_build_sha256'):
        require(value[key] == request[key], 'worker binding changed: '+key)
    require(isinstance(value['results'], list) and len(value['results']) == len(order), 'measurement slots missing')
    baseline = {item['variant']: item for item in expected['results']}
    for slot, (variant, item) in enumerate(zip(order, value['results'])):
        require(item['slot'] == slot and item['variant'] == variant and type(item['compression_ns']) is int
                and item['compression_ns'] > 0 and item.get('decode_ns') is None, 'invalid compression slot')
        require(item['bit_perfect'] is True and item['decoded_bytes'] == request['input_bytes']
                and item['decoded_sha256'] == request['input_sha256'], 'archive restore failed')
        require((item['archive_bytes'], item['archive_sha256']) ==
                (baseline[variant]['archive_bytes'], baseline[variant]['archive_sha256']), 'archive differs from untimed manifest')
    return value


def worker_command(request, pair, order, output, is_method, method_path=None):
    args = command('worker', '--cell', request, '--pair', pair, '--order', ','.join(order), '--output', output)
    return args+['--method'] if is_method else args+['--method-check', str(method_path)]


class BlockedLoad(RuntimeError):
    def __init__(self, record):
        super().__init__('BLOCKED: load')
        self.record = record


def locked_pair(core, name, pair, order, request, expected, is_method=False, method_path=None):
    require(os.sched_getaffinity(0) == {0}, 'controller must be pinned to CPU 0 before timing')
    helper = module(HELPER, '_hwgift1e_ovh')
    kind = 'method' if is_method else 'cells'
    folder = HERE/'raw'/kind/core
    if not is_method:
        folder = folder/name
    folder = folder/f'repeat-{pair}'
    folder.mkdir(parents=True, exist_ok=True)
    require({p.name for p in folder.iterdir()} <= {'attempt-1', 'attempt-2', 'attempt-3'}, 'unexpected fourth attempt/unrelated raw data')
    attempts = []
    for number in range(1, 4):
        attempt_dir = folder/f'attempt-{number}'
        attempt_dir.mkdir(exist_ok=True)
        result, receipt = attempt_dir/'result.json', attempt_dir/'ovh-bench.json'
        args = worker_command(request, pair, order, result, is_method, method_path)
        if receipt.exists():
            record = verify_receipt(receipt, args)
            code = 0 if record['status'] == 'CLEAN' else 77
        else:
            require(not any(attempt_dir.iterdir()), 'interrupted worker without completed receipt; inspect before retry')
            code = helper.run_locked(args, receipt, stdout_path=attempt_dir/'worker.stdout')
            require(receipt.exists(), 'shared helper did not save a receipt')
            record = verify_receipt(receipt, args)
        require(code in (0, 77) and (code == 77) == (record['status'] == 'LOADED'), 'fatal worker/status mismatch')
        result_ref = ref(result) if result.exists() else None
        if record['command_started']:
            require(result_ref is not None, 'started successful worker lacks result')
            verify_worker(result, request, pair, order, expected, is_method)
            require(load(Path(str(receipt)+'.stdout')) == load(result), 'raw helper stdout/result differ')
        else:
            require(result_ref is None, 'unstarted worker has an unexpected result')
        attempts.append(dict(attempt=number, status=record['status'], result=result_ref,
                             receipt=ref(receipt), receipt_data=record))
        if record['status'] == 'CLEAN':
            require(not any((folder/f'attempt-{n}').exists() for n in range(number+1, 4)), 'CLEAN round was retaken')
            return dict(pair_index=pair, order=order, selected_result=result_ref, selected_receipt=ref(receipt), attempts=attempts)
        # Only this LOADED pair is retried, immediately, with unchanged input/order.
    raise BlockedLoad(dict(pair_index=pair, order=order, selected_result=None, selected_receipt=None,
                           attempts=attempts, ps_top8=attempts[-1]['receipt_data'].get('ps_top8')))


def counts(records):
    return dict(planned_repeats=5, started_repeats=len(records), retaken_repeats=sum(len(r['attempts']) > 1 for r in records),
                loaded_attempts=sum(a['status'] == 'LOADED' for r in records for a in r['attempts']))


def verify_repeats(records, request, expected, is_method=False, method_path=None):
    cell = load(request)
    index = cell_index(cell['core'], cell['scope'], cell['level'], cell['g'])
    require(len(records) <= 5, 'too many logical rounds')
    for pair, item in enumerate(records):
        order = ['A', 'A'] if is_method else (['B', 'A'] if (index+pair)%2 else ['A', 'B'])
        require(item['pair_index'] == pair and item['order'] == order and 1 <= len(item['attempts']) <= 3,
                'saved repeat/order/retry budget changed')
        for number, attempt in enumerate(item['attempts'], 1):
            receipt_path = deref(attempt['receipt'])
            args = worker_command(request, pair, order, receipt_path.parent/'result.json', is_method, method_path)
            receipt = verify_receipt(receipt_path, args)
            require(attempt['attempt'] == number and receipt == attempt['receipt_data']
                    and receipt['status'] == attempt['status'], 'embedded receipt/attempt changed')
            if number < len(item['attempts']):
                require(attempt['status'] == 'LOADED', 'first CLEAN must win')
            if receipt['command_started']:
                path = deref(attempt['result'])
                verify_worker(path, request, pair, order, expected, is_method)
                require(load(Path(str(receipt_path)+'.stdout')) == load(path), 'raw stdout/result changed')
            else:
                require(attempt['result'] is None, 'unstarted worker has a result')
        last = item['attempts'][-1]
        if item['selected_result'] is None:
            require(pair == len(records)-1 and len(item['attempts']) == 3
                    and all(a['status'] == 'LOADED' for a in item['attempts']), 'unfinished round is not BLOCKED: load')
        else:
            require(last['status'] == 'CLEAN' and item['selected_result'] == last['result']
                    and item['selected_receipt'] == last['receipt'], 'selected result is not first CLEAN')
            deref(item['selected_result'])
            deref(item['selected_receipt'])


def statistics(records):
    values, identities = {'A': [], 'B': []}, {}
    for item in records:
        for row in load(deref(item['selected_result']))['results']:
            variant = row['variant']
            values[variant].append(row['compression_ns'])
            identity = row['archive_bytes'], row['archive_sha256']
            require(variant not in identities or identity == identities[variant], 'archive identity changed between repeats')
            identities[variant] = identity
    return {v: dict(compression_ns=ns, median_ns=median(ns), min_ns=min(ns),
                    archive_bytes=identities[v][0], archive_sha256=identities[v][1]) for v, ns in values.items()}


def summary_base(core, scope, level, frame, request, selfcheck, controls):
    cell = load(request)
    value = dict(core=core, core_commit=cell['core_commit'], scope=scope, corpus='enwik8', level=level, g=frame,
                 cell_index=cell_index(core, scope, level, frame), provenance=provenance(),
                 protocol_sha256=cell['protocol_sha256'], calibration_sha256=cell['calibration_sha256'],
                 instrument_sha256=cell['instrument_sha256'], native_build_sha256=cell['native_build_sha256'],
                 setup_sha256=cell['setup_sha256'], request_path=relative(request), request_sha256=sha(request),
                 selfcheck_path=relative(selfcheck), selfcheck_sha256=sha(selfcheck), controls=controls, repeats=[])
    for key in ('input_bytes', 'input_sha256', 'full_corpus_bytes', 'full_corpus_sha256', 'prefix_bytes'):
        value[key] = cell[key]
    return value


def verify_summary(path, is_method=False):
    """Saved files only: no subprocess, codec or clock, including on decision."""
    value = load(path)
    sources = value['provenance']
    require(sources['calibration_commit'] == CALIBRATION_COMMIT, 'summary calibration anchor changed')
    require(set(sources['source_hashes']) == SOURCE_NAMES, 'summary source fingerprint coverage changed')
    for name, digest in sources['source_hashes'].items():
        source = (HERE/name).resolve()
        require(source.is_relative_to(HERE.parent) and sha(source) == digest, 'summary source changed: '+name)
    request = deref(dict(path=value['request_path'], sha256=value['request_sha256']))
    check_path = deref(dict(path=value['selfcheck_path'], sha256=value['selfcheck_sha256']))
    expected = verify_selfcheck(check_path, request)
    verify_controls(deref(value['controls']))
    cell = load(request)
    require((value['core'], value['scope'], value['level'], value['g'])
            == (cell['core'], cell['scope'], cell['level'], cell['g']), 'summary request identity changed')
    for key in ('protocol_sha256', 'calibration_sha256', 'instrument_sha256', 'native_build_sha256', 'setup_sha256',
                'input_bytes', 'input_sha256', 'full_corpus_bytes', 'full_corpus_sha256', 'prefix_bytes'):
        require(value[key] == cell[key], 'summary/request binding changed: '+key)
    require(value['native_build_sha256'] == sha(HERE/'native'/cell['core']/'build.json'), 'native public manifest changed')
    method_path = None if is_method else deref(dict(path=value['method_check_path'], sha256=value['method_check_sha256']))
    verify_repeats(value['repeats'], request, expected, is_method, method_path)
    require(all(value[k] == v for k, v in counts(value['repeats']).items()), 'summary retry counters changed')
    if value['status'] == 'BLOCKED: load':
        require(value['repeats'] and value['repeats'][-1]['selected_result'] is None, 'BLOCKED summary lacks blocked round')
        return value
    require(len(value['repeats']) == 5 and all(r['selected_result'] is not None for r in value['repeats']), 'complete summary lacks five CLEAN rounds')
    if is_method:
        first, second = [], []
        for item in value['repeats']:
            rows = load(deref(item['selected_result']))['results']
            first.append(rows[0]['compression_ns'])
            second.append(rows[1]['compression_ns'])
        a, b = median(first), median(second)
        require(value['first_ns'] == first and value['second_ns'] == second
                and value['median_first_ns'] == a and value['median_second_ns'] == b
                and value['status'] == ('PASS' if 20*abs(b-a) < a else 'FAIL'), 'AA gate changed from raw observations')
    else:
        require(value['status'] == 'COMPLETE' and value['variants'] == statistics(value['repeats']), 'cell statistics changed')
    return value


def primary_path(core):
    return HERE/'cells'/core/'full-L10-G256.json'


def primary(core, required=True):
    path = primary_path(core)
    if not path.exists():
        require(not required, 'primary cell must precede this timing stage: '+core)
        return None
    value = verify_summary(path)
    require(value['status'] == 'COMPLETE', 'primary is blocked/incomplete: '+core)
    return value


def old_primary_gate():
    old = primary('v1.5.4')
    a, b = old['variants']['A']['median_ns'], old['variants']['B']['median_ns']
    return b >= 2*a


def decision():
    """Pure saved-data primary decisions. Missing auxiliary cells are not guessed."""
    old, new = primary('v1.5.4', False), primary('v1.5.7', False)
    p1, p2 = dict(available=False, passed=None), dict(available=False, passed=None)
    kill = dict(available=old is not None, triggered=False)
    if old is not None:
        a, b = old['variants']['A']['median_ns'], old['variants']['B']['median_ns']
        p1.update(available=True, passed=b >= 5*a, A_ns=a, B_ns=b)
        kill['triggered'] = b < 2*a
    if new is not None:
        a, b = new['variants']['A']['median_ns'], new['variants']['B']['median_ns']
        p2.update(available=True, passed=5*max(a,b) < 6*min(a,b), A_ns=a, B_ns=b)
    missing = []
    if kill['triggered']:
        for core in CORES:
            for scope in SCOPES:
                for level, frame in CASES:
                    if not (HERE/'cells'/core/(cell_name(scope, level, frame)+'.json')).exists():
                        missing.append(dict(core=core, scope=scope, level=level, g=frame, status='NOT RUN: Kill'))
    value = dict(schema='hw-gift-1e-decision-v1', status='STOP: Kill' if kill['triggered'] else
                 'PRIMARY COMPLETE' if old is not None and new is not None else 'PRIMARY INCOMPLETE',
                 P1=p1, P2=p2, Kill=kill, search_admitted=p1['passed'] is True and p2['passed'] is True,
                 primary_cells={core: ref(primary_path(core)) for core, cell in zip(CORES, (old,new)) if cell is not None},
                 not_run=missing, calibration_sha256=sha(HERE/'CALIBRATION.md'), protocol_sha256=sha(HERE/'PROTOCOL.md'))
    save(HERE/'decision.json', value)
    print('DECISION', value['status'], 'search_admitted='+str(value['search_admitted']), flush=True)
    return 3 if kill['triggered'] else 0


def method_gate(core):
    path = HERE/f'method-{core}.json'
    require(path.exists(), 'per-core AA method gate must precede its main cell')
    require(verify_summary(path, True)['status'] == 'PASS', 'per-core AA stability gate failed/incomplete')
    return path


def method(core):
    require(core in CORES, 'invalid method core')
    preparation = prepared()
    path = HERE/f'method-{core}.json'
    if path.exists():
        value = verify_summary(path, True)
        print('METHOD_VERIFIED_SKIP', core, value['status'], flush=True)
        return 0 if value['status'] == 'PASS' else 2 if value['status'] == 'BLOCKED: load' else 1
    require(not primary_path(core).exists(), 'method summary missing after primary; inspect instead of creating new method timing')
    if core == 'v1.5.7' and not old_primary_gate():
        return decision()
    controls = load(deref(preparation['controls']))['cores'][core]
    request, check_path = deref(controls['request']), deref(controls['selfcheck'])
    expected = verify_selfcheck(check_path, request)
    summary = summary_base(core, 'full', 10, 256, request, check_path, preparation['controls'])
    summary.update(schema='hw-gift-1e-method-v1', status='RUNNING')
    records = summary['repeats']
    try:
        for pair in range(5):
            records.append(locked_pair(core, 'full-L10-G256', pair, ['A','A'], request, expected, True))
        first, second = [], []
        for item in records:
            rows = load(deref(item['selected_result']))['results']
            first.append(rows[0]['compression_ns'])
            second.append(rows[1]['compression_ns'])
        a, b = median(first), median(second)
        summary.update(first_ns=first, second_ns=second, median_first_ns=a, median_second_ns=b,
                       status='PASS' if 20*abs(b-a) < a else 'FAIL', **counts(records))
    except BlockedLoad as error:
        records.append(error.record)
        summary.update(status='BLOCKED: load', ps_top8=error.record['ps_top8'], **counts(records))
        save(path, summary)
        print('METHOD_BLOCKED load', core, flush=True)
        return 2
    save(path, summary)
    print('METHOD_'+summary['status'], core, flush=True)
    return 0 if summary['status'] == 'PASS' else 1


def cell(core, scope, level, frame):
    require(core in CORES, 'invalid cell core')
    name, index = cell_name(scope, level, frame), cell_index(core, scope, level, frame)
    preparation = prepared()
    path = HERE/'cells'/core/(name+'.json')
    if path.exists():
        value = verify_summary(path)
        print('CELL_VERIFIED_SKIP', core, name, value['status'], flush=True)
        if value['status'] == 'BLOCKED: load':
            return 2
        return decision() if (scope,level,frame) == ('full',10,256) else 0
    is_primary = (scope,level,frame) == ('full',10,256)
    if not (core == 'v1.5.4' and is_primary):
        if not old_primary_gate():
            return decision()
        if not is_primary:
            primary('v1.5.7')
            # The two primary cells precede this fixed auxiliary sequence.
            auxiliary = [(c,s,l,g) for c in CORES for s in SCOPES for l,g in CASES if (s,l,g) != ('full',10,256)]
            for c,s,l,g in auxiliary[:auxiliary.index((core,scope,level,frame))]:
                prior = HERE/'cells'/c/(cell_name(s,l,g)+'.json')
                require(prior.exists() and verify_summary(prior)['status'] == 'COMPLETE',
                        'earlier auxiliary cell must be completed first: '+str(prior))
    method_path = method_gate(core)
    request, check_path, request_data, expected = make_request(core, scope, level, frame)
    summary = summary_base(core, scope, level, frame, request, check_path, preparation['controls'])
    summary.update(schema='hw-gift-1e-cell-v1', status='RUNNING', method_check_path=relative(method_path),
                   method_check_sha256=sha(method_path), variants={})
    records = summary['repeats']
    try:
        for pair in range(5):
            order = ['B','A'] if (index+pair)%2 else ['A','B']
            records.append(locked_pair(core, name, pair, order, request, expected, method_path=method_path))
        summary.update(status='COMPLETE', variants=statistics(records), **counts(records))
    except BlockedLoad as error:
        records.append(error.record)
        summary.update(status='BLOCKED: load', ps_top8=error.record['ps_top8'], **counts(records))
        save(path, summary)
        print('CELL_BLOCKED load', core, name, flush=True)
        return 2
    save(path, summary)
    print('CELL_COMPLETE', core, name, flush=True)
    return decision() if is_primary else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'method', 'cell', 'decision'))
    parser.add_argument('--core', choices=CORES)
    parser.add_argument('--scope', choices=SCOPES)
    parser.add_argument('--level', type=int)
    parser.add_argument('--frame', type=int)
    args = parser.parse_args()
    if args.action == 'decision':
        return decision()
    require(sys.platform == 'linux', 'native controller execution requires Linux')
    STATE.mkdir(parents=True, exist_ok=True)
    import fcntl
    with (STATE/'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'prepare':
            return prepare()
        require(args.core is not None, '--core required')
        if args.action == 'method':
            return method(args.core)
        require(args.scope is not None and args.level is not None and args.frame is not None,
                'cell requires --scope --level --frame')
        return cell(args.core, args.scope, args.level, args.frame)


if __name__ == '__main__':
    raise SystemExit(main())
