"""HW-GIFT-1d stage controller. Importing this module performs no experiment."""
import argparse
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = ROOT / '.work/hw-gift-1d'
CODEC = HERE / 'instrument.py'
HELPER = HERE.parent / 'hw-gift-1b/ovh_bench.py'
LEVELS = (3, 10, 19)
FRAMES = (256, 1024, 4096, 16384, 65536, 262144, 524288)
THRESHOLDS = (1024, 4096, 16384, 65536)
CALIBRATION_COMMIT = '2d02a8b466ab1d1a07a4c604e17775bb60d7162d'
ORDER_COMMIT = '695457a'


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
    temporary = path.with_name(path.name + '.writing')
    with temporary.open('wb') as stream:
        stream.write(packed(value))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def relative(path):
    path = Path(path).resolve()
    require(path.is_relative_to(HERE), 'public evidence path escaped HW-GIFT-1d')
    return path.relative_to(HERE).as_posix()


def ref(path):
    return dict(path=relative(path), sha256=sha(path))


def deref(value):
    require(isinstance(value, dict) and set(value) == {'path', 'sha256'}, 'invalid file reference')
    path = (HERE / value['path']).resolve()
    relative(path)
    require(path.is_file() and not path.is_symlink() and sha(path) == value['sha256'],
            'retained evidence changed: ' + value['path'])
    return path


def command(*args):
    return [sys.executable, '-B', str(CODEC), *map(str, args)]


def invoke(args):
    # Builds, deterministic controls and requests deliberately run outside the
    # shared benchmark lock. Only worker commands go through locked_pair().
    result = subprocess.run([str(item) for item in args], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        sys.stderr.buffer.write(result.stderr)
        sys.stderr.buffer.flush()
    result.check_returncode()


def copy_bytes(source, target):
    data = Path(source).read_bytes()
    if target.exists():
        require(target.read_bytes() == data, 'public build evidence changed: ' + str(target))
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.writing')
    with temporary.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(target)


def expose_build(threshold=None):
    name = 'base' if threshold is None else 'conditional-%d' % threshold
    source, target = STATE / 'native' / name, HERE / 'native' / name
    require((source / 'build.json').is_file(), 'native build receipt missing')
    for path in source.iterdir():
        if path.suffix in ('.json', '.stdout', '.stderr', '.patch'):
            copy_bytes(path, target / path.name)
    original = (STATE / 'native/base/original-compress.c').read_text()
    variants = ['nohint'] if threshold is None else ['conditional']
    for variant in variants:
        changed = (source / (variant + '-compress.c')).read_text()
        patch = ''.join(difflib.unified_diff(original.splitlines(keepends=True),
            changed.splitlines(keepends=True), fromfile='original/zstdseek_compress.c',
            tofile=variant + '/zstdseek_compress.c', n=0)).encode()
        path = target / (variant + '.patch')
        if path.exists():
            require(path.read_bytes() == patch, 'public writer patch changed')
        else:
            path.write_bytes(patch)
    return ref(target / 'build.json')


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def committed(paths):
    for path in paths:
        name = str(Path(path).resolve().relative_to(ROOT))
        git('ls-files', '--error-unmatch', '--', name)
    names = [str(Path(path).resolve().relative_to(ROOT)) for path in paths]
    require(not git('status', '--porcelain', '--', *names).strip(), 'source/freeze files must be committed and clean')


def provenance():
    paths = [HERE / name for name in ('CALIBRATION.md', 'PROTOCOL.md', 'run.py',
                                      'instrument.py', 'controls.py')] + [HELPER]
    committed(paths)
    require(git('branch', '--show-current').decode().strip() == 'hw-gift-1d', 'wrong experiment branch')
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor',
                    CALIBRATION_COMMIT, 'HEAD'], check=True)
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor',
                    ORDER_COMMIT, 'HEAD'], check=True)
    return dict(source_commit=git('rev-parse', 'HEAD').decode().strip(),
                calibration_commit=CALIBRATION_COMMIT,
                order_commit=git('rev-parse', ORDER_COMMIT).decode().strip(),
                calibration_sha256=sha(HERE / 'CALIBRATION.md'),
                protocol_sha256=sha(HERE / 'PROTOCOL.md'),
                source_hashes={os.path.relpath(path, HERE).replace('\\', '/'): sha(path) for path in paths})


def same_sources(old, new):
    for name in ('calibration_sha256', 'protocol_sha256', 'source_hashes'):
        require(old[name] == new[name], 'experiment source/protocol changed: ' + name)


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def cell_index(level, frame):
    require(level in LEVELS and frame in FRAMES, 'cell outside preregistered grid')
    return LEVELS.index(level) * len(FRAMES) + FRAMES.index(frame)


def pair_order(phase, index, pair, variants):
    if phase == 'method':
        return ['original', 'original']
    order = list(variants)
    if phase == 'holdout':
        if index % 2:
            order.reverse()
        pivot = pair % len(order)
        return order[pivot:] + order[:pivot]
    if (index + pair) % 2:
        order.reverse()
    return order


def median(values):
    require(len(values) == 5 and all(type(x) is int and x > 0 for x in values),
            'five positive integer observations required')
    return sorted(values)[2]


def verify_controls(path, request):
    value = load(path)
    require(value.get('status') == 'PASS' and value.get('clock_calls') == 0,
            'untimed method controls did not pass')
    require(value.get('cell_sha256') == sha(request)
            and value.get('calibration_sha256') == sha(HERE / 'CALIBRATION.md')
            and value.get('instrument_sha256') == sha(CODEC)
            and value.get('controls_sha256') == sha(HERE / 'controls.py'),
            'method controls no longer bind these inputs/sources')
    return value


def selfcheck_request(request, output):
    if not output.exists():
        invoke(command('selfcheck', '--cell', request, '--output', output))
    value = load(output)
    require(value.get('status') == 'PASS' and value.get('clock_calls') == 0
            and value.get('cell_sha256') == sha(request), 'cell selfcheck failed or changed')
    require(all(result.get('bit_perfect') is True for result in value['results']),
            'untimed archive restoration failed')
    return value


def make_request(phase, corpus, level, frame, threshold=None, variants=None):
    name = 'L%d-G%d' % (level, frame)
    path = HERE / 'requests' / phase / (name + '.json')
    check_path = HERE / 'selfchecks' / phase / (name + '.json')
    if variants is None:
        variants = ['original', 'nohint']
        if threshold is not None:
            variants.append('conditional')
    variants = list(variants)
    if not path.exists():
        args = command('request', '--corpus', corpus, '--level', level, '--frame', frame,
                       '--variants', ','.join(variants), '--output', path)
        if threshold is not None:
            args += ['--threshold', str(threshold)]
        invoke(args)
    value = load(path)
    require((value['corpus'], value['level'], value['g']) == (corpus, level, frame)
            and value['variants'] == variants and value.get('threshold') == threshold,
            'saved cell request identity changed')
    expected_prefix = 16777216 if frame in (256, 1024) else None
    require(value.get('prefix_bytes') == expected_prefix, 'wrong full/prefix input scope')
    selfcheck = selfcheck_request(path, check_path)
    return path, check_path, value, selfcheck


def prepare():
    sources = provenance()
    path = HERE / 'preparation.json'
    if path.exists():
        value = load(path)
        same_sources(value['provenance'], sources)
        request = deref(value['request'])
        deref(value['selfcheck'])
        verify_controls(deref(value['controls']), request)
        require(value['status'] == 'PASS', 'preparation previously failed')
        print('PREPARATION_VERIFIED_SKIP', flush=True)
        return 0
    invoke(command('build'))
    base_build = expose_build()
    request, selfcheck, _, check_data = make_request('method', 'enwik8', 3, 262144)
    require(check_data.get('known_1c_checked') is True, 'known complete 1c archives were not reproduced')
    controls = HERE / 'method-controls.json'
    if not controls.exists():
        invoke([sys.executable, '-B', str(HERE / 'controls.py'), '--cell', str(request),
                '--output', str(controls)])
    verify_controls(controls, request)
    save(path, dict(schema='hw-gift-1d-preparation-v1', status='PASS', provenance=sources,
                    request=ref(request), selfcheck=ref(selfcheck), controls=ref(controls),
                    base_build=base_build))
    print('PREPARATION_PASS clock_calls=0', flush=True)
    return 0


def prepared():
    path = HERE / 'preparation.json'
    require(path.exists(), 'prepare must pass before timing')
    value = load(path)
    require(value.get('status') == 'PASS', 'preparation did not pass')
    same_sources(value['provenance'], provenance())
    request = deref(value['request'])
    deref(value['selfcheck'])
    verify_controls(deref(value['controls']), request)
    return value


def verify_receipt(path, expected_command=None):
    value = load(path)
    require(value.get('schema') == 'ovh-bench-v2' and value.get('load1_threshold') == '2.0'
            and value.get('lock_path') == '/run/lock/ovh-bench.lock'
            and value.get('helper_sha256') == sha(HELPER), 'wrong shared lock/load policy')
    if expected_command is not None:
        require(value['command'] == expected_command, 'saved worker command changed')
    for suffix, key in (('.stdout', 'stdout_sha256'), ('.stderr', 'stderr_sha256')):
        require(sha(Path(str(path) + suffix)) == value[key], 'retained worker output changed')
    return value


def verify_worker(path, request_path, pair, order, decode, expected):
    value, request = load(path), load(request_path)
    require(value.get('cell_id') == request['cell_id'] and value.get('cell_sha256') == sha(request_path)
            and value.get('pair_index') == pair and value.get('order') == order
            and value.get('decode_timed') is decode, 'worker identity/order changed')
    require(isinstance(value.get('results'), list) and len(value['results']) == len(order),
            'worker lost or duplicated a measurement slot')
    baseline = {item['variant']: item for item in expected['results']}
    for slot, (variant, result) in enumerate(zip(order, value['results'])):
        require(result.get('slot') == slot and result.get('variant') == variant
                and type(result.get('compression_ns')) is int and result['compression_ns'] > 0,
                'invalid native compression measurement')
        require(result.get('bit_perfect') is True and result.get('decoded_bytes') == request['input_bytes']
                and result.get('decoded_sha256') == request['input_sha256'], 'timed archive failed exact restore')
        require((result['archive_bytes'], result['archive_sha256'])
                == (baseline[variant]['archive_bytes'], baseline[variant]['archive_sha256']),
                'timed archive differs from untimed selfcheck')
        if decode:
            require(type(result.get('decode_ns')) is int and result['decode_ns'] > 0,
                    'requested decode observation missing')
        else:
            require(result.get('decode_ns') is None, 'unexpected timed decode observation')
    return value


class BlockedLoad(RuntimeError):
    def __init__(self, record):
        super().__init__('BLOCKED: load')
        self.record = record


def locked_pair(phase, name, pair, order, request, selfcheck, method_path=None):
    helper = module(HELPER, '_hwgift1d_ovh')
    root = HERE / 'raw' / phase / name / ('repeat-%d' % pair)
    root.mkdir(parents=True, exist_ok=True)
    require({p.name for p in root.iterdir()}.issubset({'attempt-1', 'attempt-2', 'attempt-3'}),
            'unexpected fourth attempt or unrelated raw data')
    attempts = []
    for number in range(1, 4):
        folder = root / ('attempt-%d' % number)
        folder.mkdir(exist_ok=True)
        result, receipt = folder / 'result.json', folder / 'ovh-bench.json'
        args = command('worker', '--cell', request, '--pair', pair, '--order', ','.join(order),
                       '--output', result)
        if pair == 0:
            args.append('--decode')
        if phase == 'method':
            args.append('--method')
        else:
            args += ['--method-check', str(method_path)]
        if receipt.exists():
            record = verify_receipt(receipt, args)
            require(record['status'] in ('CLEAN', 'LOADED'), 'retained ERROR/unfinished pair requires inspection')
            code = 0 if record['status'] == 'CLEAN' else 77
        else:
            require(not any(folder.iterdir()), 'interrupted pair without complete lock receipt; inspect it')
            code = helper.run_locked(args, receipt, stdout_path=folder / 'worker.stdout')
            require(receipt.exists(), 'shared helper produced no receipt')
            record = verify_receipt(receipt, args)
        result_ref = ref(result) if result.exists() else None
        attempt = dict(attempt=number, status=record['status'], result=result_ref,
                       receipt=ref(receipt), receipt_data=record)
        attempts.append(attempt)
        if record.get('status') == 'ERROR' or record.get('returncode') not in (None, 0) or code not in (0, 77):
            raise ValueError('native/byte failure is fatal and must not be retried')
        require((record['status'] == 'CLEAN' and code == 0) or (record['status'] == 'LOADED' and code == 77),
                'shared helper status/exit mismatch')
        if record.get('command_started'):
            require(result_ref is not None and record['returncode'] == 0, 'successful worker result is missing')
            verify_worker(result, request, pair, order, pair == 0, selfcheck)
        else:
            require(record['status'] == 'LOADED' and record.get('returncode') is None and result_ref is None,
                    'unstarted worker has unexpected result')
        if record['status'] == 'CLEAN':
            require(not any((root / ('attempt-%d' % later)).exists() for later in range(number + 1, 4)),
                    'a CLEAN pair must never be retimed')
            return dict(pair_index=pair, order=order, selected_result=result_ref,
                        selected_receipt=ref(receipt), attempts=attempts)
        # Retry only this pair, with the same request/order and without sleeping.
    raise BlockedLoad(dict(pair_index=pair, order=order, selected_result=None,
                           selected_receipt=None, attempts=attempts,
                           ps_top8=attempts[-1]['receipt_data'].get('ps_top8')))


def verify_repeats(records, request, expected):
    for item in records:
        for attempt in item['attempts']:
            receipt = verify_receipt(deref(attempt['receipt']))
            require(receipt == attempt['receipt_data'], 'embedded lock receipt changed')
            if attempt['result'] is not None:
                verify_worker(deref(attempt['result']), request, item['pair_index'], item['order'],
                              item['pair_index'] == 0, expected)
        if item['selected_result'] is not None:
            require(item['attempts'][-1]['status'] == 'CLEAN'
                    and item['selected_result'] == item['attempts'][-1]['result']
                    and item['selected_receipt'] == item['attempts'][-1]['receipt'],
                    'selected result is not the first CLEAN attempt')
            deref(item['selected_result'])
            deref(item['selected_receipt'])


def counts(records, planned=5):
    return dict(planned_repeats=planned, started_repeats=len(records),
                retaken_repeats=sum(len(item['attempts']) > 1 for item in records),
                loaded_attempts=sum(a['status'] == 'LOADED' for item in records for a in item['attempts']))


def method():
    preparation = prepared()
    request = deref(preparation['request'])
    expected = load(deref(preparation['selfcheck']))
    path = HERE / 'method-check.json'
    if path.exists():
        value = load(path)
        verify_repeats(value['repeats'], request, expected)
        require(value['controls'] == preparation['controls'], 'method control reference changed')
        if value['status'] == 'BLOCKED: load':
            print('METHOD_BLOCKED load', flush=True)
            return 2
        require(value['status'] in ('PASS', 'FAIL'), 'unfinished method check')
        print('METHOD_VERIFIED_' + value['status'], flush=True)
        return 0 if value['status'] == 'PASS' else 1
    records = []
    summary = dict(schema='hw-gift-1d-method-v1', status='RUNNING', provenance=provenance(),
                   protocol_sha256=load(request)['protocol_sha256'],
                   execution_protocol_sha256=sha(HERE / 'PROTOCOL.md'),
                   instrument_sha256=sha(CODEC),
                   request_path=relative(request), request_sha256=sha(request),
                   selfcheck_path=preparation['selfcheck']['path'],
                   selfcheck_sha256=preparation['selfcheck']['sha256'], controls=preparation['controls'],
                   repeats=records)
    try:
        for pair in range(5):
            records.append(locked_pair('method', 'L3-G262144', pair, ['original', 'original'],
                                       request, expected))
        first, second = [], []
        for item in records:
            results = load(deref(item['selected_result']))['results']
            first.append(results[0]['compression_ns'])
            second.append(results[1]['compression_ns'])
        a, b = median(first), median(second)
        summary.update(first_ns=first, second_ns=second, median_first_ns=a, median_second_ns=b,
                       status='PASS' if abs(b - a) * 20 < a else 'FAIL', **counts(records))
    except BlockedLoad as error:
        records.append(error.record)
        summary.update(status='BLOCKED: load', ps_top8=error.record['ps_top8'], **counts(records))
        save(path, summary)
        print('METHOD_BLOCKED load', flush=True)
        return 2
    save(path, summary)
    print('METHOD_' + summary['status'], flush=True)
    return 0 if summary['status'] == 'PASS' else 1


def method_gate():
    preparation = prepared()
    path = HERE / 'method-check.json'
    require(path.exists(), 'timed AA method gate must precede the grid')
    value = load(path)
    require(value.get('status') == 'PASS' and len(value['repeats']) == 5, 'AA timing method gate failed/incomplete')
    verify_repeats(value['repeats'], deref(preparation['request']), load(deref(preparation['selfcheck'])))
    require(abs(value['median_second_ns'] - value['median_first_ns']) * 20 < value['median_first_ns'],
            'AA method gate does not satisfy the strict five-percent bound')
    return path


def phase_complete(phase):
    for level in LEVELS:
        for frame in FRAMES:
            path = HERE / 'cells' / phase / ('L%d-G%d.json' % (level, frame))
            require(path.exists() and load(path).get('status') == 'COMPLETE', 'prior phase is incomplete: ' + phase)


def freeze():
    phase_complete('train')
    selection, protocol = HERE / 'selection.json', HERE / 'CONDITIONAL_PROTOCOL.md'
    require(selection.is_file() and protocol.is_file(), 'selection and development protocol must be frozen first')
    committed([selection, protocol])
    value = load(selection)
    threshold = value.get('threshold_bytes')
    require(threshold is None or type(threshold) is int and threshold in THRESHOLDS,
            'threshold outside preregistered candidates')
    return threshold, dict(selection=ref(selection), conditional_protocol=ref(protocol))


def statistics(records, variants):
    observations = {name: [] for name in variants}
    archive = {}
    decode = {name: None for name in variants}
    for item in records:
        for result in load(deref(item['selected_result']))['results']:
            name = result['variant']
            observations[name].append(result['compression_ns'])
            identity = result['archive_bytes'], result['archive_sha256']
            require(name not in archive or archive[name] == identity, 'repetitions changed archive identity')
            archive[name] = identity
            if result['decode_ns'] is not None:
                require(decode[name] is None, 'more than one full-decode observation per cell')
                decode[name] = result['decode_ns']
    return {name: dict(compression_ns=values, median_ns=median(values), min_ns=min(values),
                       archive_bytes=archive[name][0], archive_sha256=archive[name][1],
                       decode_ns=decode[name]) for name, values in observations.items()}


def cell(phase, level, frame):
    index, method_path = cell_index(level, frame), method_gate()
    threshold, frozen = None, {}
    if phase in ('validate', 'holdout'):
        threshold, frozen = freeze()
        if phase == 'validate':
            require(threshold is not None, 'conditional validation is inapplicable: NO SUPPORTED X')
        if phase == 'holdout' and threshold is not None:
            phase_complete('validate')
        if threshold is not None:
            invoke(command('build', '--threshold', threshold))
            expose_build(threshold)
    corpus = 'silesia.tar' if phase == 'holdout' else 'enwik8'
    variants = (['original', 'conditional'] if phase == 'validate' else
                ['original', 'nohint', 'conditional'] if phase == 'holdout' and threshold is not None else
                ['original', 'nohint'])
    request, selfcheck, request_data, expected = make_request(phase, corpus, level, frame,
                                                            threshold, variants)
    if threshold is not None:
        policy = 'original' if frame < threshold else 'nohint'
        if phase == 'validate':
            training = load(HERE / 'cells/train' / ('L%d-G%d.json' % (level, frame)))
            selected = training['variants'][policy]
        else:
            selected = next(item for item in expected['results'] if item['variant'] == policy)
        conditional = next(item for item in expected['results'] if item['variant'] == 'conditional')
        require((conditional['archive_bytes'], conditional['archive_sha256'])
                == (selected['archive_bytes'], selected['archive_sha256']),
                'conditional writer does not reproduce the frozen selected policy')
    name = 'L%d-G%d' % (level, frame)
    path = HERE / 'cells' / phase / (name + '.json')
    sources = provenance()
    if path.exists():
        value = load(path)
        same_sources(value['provenance'], sources)
        require(value['request_sha256'] == sha(request) and value['selfcheck_sha256'] == sha(selfcheck)
                and value['method_check_sha256'] == sha(method_path)
                and value.get('freeze', {}) == frozen, 'retained cell source/freeze changed')
        verify_repeats(value['repeats'], request, expected)
        require(value['status'] in ('COMPLETE', 'BLOCKED: load'), 'unfinished/error cell requires inspection')
        if value['status'] == 'COMPLETE':
            require(value['variants'] == statistics(value['repeats'], variants), 'saved cell statistics changed')
        print('CELL_VERIFIED_SKIP', phase, name, value['status'], flush=True)
        return 0 if value['status'] == 'COMPLETE' else 2
    records = []
    summary = dict(schema='hw-gift-1d-cell-v1', status='RUNNING', phase=phase, corpus=corpus,
                   level=level, g=frame, cell_index=index, provenance=sources, freeze=frozen,
                   protocol_sha256=request_data['protocol_sha256'],
                   execution_protocol_sha256=sha(HERE / 'PROTOCOL.md'),
                   instrument_sha256=sha(CODEC),
                   request_path=relative(request), request_sha256=sha(request),
                   selfcheck_path=relative(selfcheck), selfcheck_sha256=sha(selfcheck),
                   method_check_path=relative(method_path), method_check_sha256=sha(method_path),
                   repeats=records, variants={})
    for key in ('input_bytes', 'input_sha256', 'prefix_bytes', 'full_corpus_bytes', 'full_corpus_sha256'):
        summary[key] = request_data[key]
    try:
        for pair in range(5):
            order = pair_order(phase, index, pair, variants)
            records.append(locked_pair(phase, name, pair, order, request, expected, method_path))
        summary.update(status='COMPLETE', variants=statistics(records, variants), **counts(records))
    except BlockedLoad as error:
        records.append(error.record)
        summary.update(status='BLOCKED: load', ps_top8=error.record['ps_top8'], **counts(records))
        save(path, summary)
        print('CELL_BLOCKED load', phase, name, flush=True)
        return 2
    save(path, summary)
    print('CELL_COMPLETE', phase, name, flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'method', 'cell'))
    parser.add_argument('--phase', choices=('train', 'validate', 'holdout'))
    parser.add_argument('--level', type=int)
    parser.add_argument('--frame', type=int)
    args = parser.parse_args()
    require(sys.platform == 'linux', 'native experiment execution requires Linux')
    STATE.mkdir(parents=True, exist_ok=True)
    import fcntl
    with (STATE / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'prepare':
            return prepare()
        if args.action == 'method':
            return method()
        require(args.phase is not None and args.level is not None and args.frame is not None,
                'cell requires --phase, --level and --frame')
        return cell(args.phase, args.level, args.frame)


if __name__ == '__main__':
    raise SystemExit(main())
