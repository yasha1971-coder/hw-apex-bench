# SPDX-License-Identifier: Apache-2.0
"""Casefix build, whole-grid correctness admission and first-CLEAN controller.

No work occurs on import. CLI: build; check; method-aa; main --corpus CORPUS.
Controls reuse checked_unit() and timed_unit(); neither changes its input trace.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STATE = ROOT / '.work/hw-region-2/casefix'
PROFILES = ('aceapex', 'zstd_seekable', 'bgzip', 'twobit_casefix_mask1',
            'twobit_original_mask1', 'twobit_original_mask0')
EQUIVALENT = PROFILES[:4]
CORPORA = ('chr1',) + tuple(f't2t-{i:02d}' for i in range(30))
SEMANTICS = {p: (1 if p == 'twobit_original_mask1' else 2 if p == 'twobit_original_mask0' else 0) for p in PROFILES}


def require(ok, why):
    if not ok:
        raise ValueError(why)


def load(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def digest(value):
    return hashlib.sha256(packed(value)).hexdigest()


def immutable(path, value):
    path = Path(path)
    raw = value if isinstance(value, bytes) else packed(value)
    require(path.resolve().is_relative_to(HERE) or path.resolve().is_relative_to(STATE), 'output escaped casefix')
    if path.exists():
        require(path.read_bytes() == raw, 'retained output changed: ' + str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as out:
            out.write(raw)


def artifact(path):
    path = Path(path).resolve()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def ref(path):
    path = Path(path).resolve()
    require(path.is_relative_to(HERE), 'public reference escaped casefix')
    return dict(path=path.relative_to(HERE).as_posix(), sha256=sha(path))


def deref(record):
    path = (HERE / record['path']).resolve()
    require(path.is_relative_to(HERE) and path.is_file() and sha(path) == record['sha256'], 'public evidence changed')
    return path


def module(name):
    spec = importlib.util.spec_from_file_location('_casefix_' + name, HERE / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = value
    spec.loader.exec_module(value)
    return value


def source_map():
    files = [HERE / n for n in ('CALIBRATION.md', 'PROTOCOL.md', 'setup.py', 'drive.py', 'ovh_bench.py',
                                'native.c', 'worker.c', 'coordinate.h', 'controls.py')]
    files += [HERE.parent / n for n in ('CALIBRATION.md', 'writer.py', 'lib2bit-casefix.patch')]
    names = [p.relative_to(ROOT).as_posix() for p in files]
    subprocess.run(['git', '-C', str(ROOT), 'ls-files', '--error-unmatch', '--', *names], check=True, capture_output=True)
    require(not subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain', '--', *names]).strip(), 'all controller/native inputs must be committed')
    require(not {k for k in os.environ if k.startswith(('ACEAPEX_', 'AX_', 'LIT_', 'FSE_'))}, 'codec overrides must be absent')
    return {name: sha(ROOT / name) for name in names}


def guard():
    require(not (HERE / 'KILL.json').exists(), 'retained KILL stops every later native/timed operation')


def stop(reason, evidence):
    immutable(HERE / 'KILL.json', dict(schema='hw-region-2-casefix-kill-v1', status='KILL', reason=reason,
              source_sha256=source_map(), evidence=evidence))
    raise ValueError('KILL: ' + reason)


def native_build():
    value = load(HERE / 'native/build.json')
    require(value['identity']['source_sha256'] == source_map() and value['identity']['setup_sha256'] == sha(HERE / 'setup.json'), 'native/source cohort changed')
    require((STATE / 'native/build.json').read_bytes() == (HERE / 'native/build.json').read_bytes(), 'native public/private receipt differs')
    module('setup').check_tree(value['artifacts'])
    module('setup').check_tree(value['build_inputs'])
    return value


def build():
    guard()
    setup_module = module('setup')
    prepared = setup_module.prepare()
    sources = source_map()
    if (HERE / 'native/build.json').exists():
        return native_build()
    directory = STATE / 'native'
    directory.mkdir(parents=True, exist_ok=True)
    deps, libs = prepared['deps'], prepared['lib2bit']
    z = Path(deps['zstd']['path']); a = Path(deps['aceapex']['path']); h = Path(deps['htslib']['path'])
    common = ['gcc', '-O3', '-fPIC', '-fno-lto', '-shared', '-Wall', '-Wextra', '-Wl,-Bsymbolic', '-std=c11', '-I' + str(HERE)]
    dsos, inputs = {}, []
    for profile in PROFILES:
        output = directory / (profile + '.so')
        args = common + ['-DCOORD_LABEL="' + profile + '"']
        if profile == 'aceapex':
            args += ['-DCOORD_ACE', '-DXXH_NAMESPACE=ZSTD_', '-I' + str(a / 'c'), '-I' + str(z / 'lib'), '-I' + str(z / 'lib/common'),
                     HERE / 'native.c', a / 'c/aceapex_decode.c', deps['zstd']['library_path'], '-pthread']
            inputs += [a / 'c/aceapex_decode.c', a / 'c/aceapex_decode.h', Path(deps['zstd']['library_path'])]
        elif profile == 'zstd_seekable':
            seek = z / 'contrib/seekable_format'
            args += ['-DCOORD_ZSTD', '-DXXH_NAMESPACE=ZSTD_', '-I' + str(z / 'lib'), '-I' + str(z / 'lib/common'), '-I' + str(seek),
                     HERE / 'native.c', seek / 'zstdseek_decompress.c', deps['zstd']['library_path'], '-pthread']
            inputs += [seek / 'zstdseek_decompress.c', seek / 'zstd_seekable.h']
        elif profile == 'bgzip':
            args += ['-DCOORD_BGZF', '-I' + str(h), '-I' + deps['libdeflate']['path'], HERE / 'native.c',
                     deps['htslib']['library_path'], deps['libdeflate']['library_path'], '-lz', '-lm', '-pthread']
            inputs += [Path(deps['htslib']['library_path']), Path(deps['libdeflate']['library_path']), h / 'htslib/faidx.h']
        else:
            original = 'original' in profile
            variant = libs['variants']['original' if original else 'casefix']
            args += ['-DCOORD_TWOBIT', '-DCOORD_STORE_MASKED=' + ('0' if profile.endswith('mask0') else '1'),
                     '-DCOORD_ORIGINAL=' + ('1' if original else '0'), '-I' + libs['path'], HERE / 'native.c', variant['library_path']]
            inputs += [Path(libs['header_path']), Path(variant['source_path']), Path(variant['library_path'])]
        setup_module.run('native-' + profile, args + ['-o', output], outputs=(output,))
        dsos[profile] = artifact(output)
    worker = directory / 'worker'
    setup_module.run('native-worker', ['gcc', '-O3', '-fno-lto', '-std=c11', '-Wall', '-Wextra', '-I' + str(HERE),
                     HERE / 'worker.c', '-ldl', '-o', worker], outputs=(worker,))
    value = dict(schema='hw-region-2-casefix-native-v1', status='PASS',
                 identity=dict(source_sha256=sources, setup_sha256=sha(HERE / 'setup.json'),
                               source_commit=subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).decode().strip()),
                 artifacts=dict(worker=artifact(worker), dsos=dsos), build_inputs=[artifact(p) for p in sorted(set(inputs))])
    immutable(STATE / 'native/build.json', value); immutable(HERE / 'native/build.json', value)
    return value


def load_case(corpus):
    require(corpus in CORPORA, 'unknown corpus')
    path = HERE / 'archives' / (corpus + '.json')
    require(path.exists(), 'prepare case first: setup.py case --corpus ' + corpus)
    value = load(path)
    require(value['schema'] == 'hw-region-2-casefix-archives-v1' and value['setup_sha256'] == sha(HERE / 'setup.json'), 'archive case changed')
    module('setup').check_tree(value)
    return value


def load_trace(corpus):
    value = load(HERE / 'traces' / (corpus + '.json'))
    require(value['corpus'] == corpus and value['request_bases'] == 16384 and value['resampled'] is False, 'trace identity changed')
    for group in ('warmups', 'requests'):
        require(not value['statistics'][group]['terminal'] and not value['statistics'][group]['end_in_last_packed_byte'], 'unchanged lib2bit EOF boundary reached; stop, do not pad or remap')
    return value


def worker_command(mode, profile, case, trace, prefix, *, fresh=False, probe=False):
    native = native_build()
    require(profile in PROFILES, 'unknown profile')
    fmt = case['formats']['twobit' if profile.startswith('twobit_') else profile]
    indexes = fmt['indexes']
    fai = indexes[0]['path'] if indexes else '-'
    gzi = indexes[1]['path'] if profile == 'bgzip' else '-'
    command = ['taskset', '-c', '0' if mode == 'latency' else '15', native['artifacts']['worker']['path'], mode,
               native['artifacts']['dsos'][profile]['path'], fmt['path'], fai, gzi, case['fai']['geometry']['name'],
               case['input']['path'], case['fai']['path'], trace['warmups']['path'], trace['requests']['path'], str(prefix)]
    return command + (['--fresh'] if fresh else []) + (['--probe'] if probe else [])


def unit_identity(mode, profile, case, trace, fresh, probe):
    return dict(mode=mode, profile=profile, case_sha256=digest(case), trace_sha256=digest(trace), fresh=fresh, probe=probe,
                source_sha256=source_map(), native_build_sha256=sha(HERE / 'native/build.json'), setup_sha256=sha(HERE / 'setup.json'))


def published_capture(path, destination):
    """Keep raw private bytes and a public deterministic gzip with both hashes."""
    path, destination = Path(path), Path(destination)
    raw = artifact(path)
    if destination.exists():
        digestor = hashlib.sha256()
        count = 0
        with gzip.open(destination, 'rb') as source:
            for block in iter(lambda: source.read(1 << 20), b''):
                digestor.update(block); count += len(block)
        require(count == raw['bytes'] and digestor.hexdigest() == raw['sha256'], 'public capture gzip differs')
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        pending = destination.with_name(destination.name + '.writing')
        require(not pending.exists(), 'partial public capture retained; inspect before retry')
        with pending.open('xb') as out, path.open('rb') as source:
            with gzip.GzipFile(filename='', mode='wb', fileobj=out, mtime=0) as compressed:
                shutil.copyfileobj(source, compressed)
        pending.rename(destination)
    return dict(**raw, public_gzip=artifact(destination))


def parse_observation(folder, prefix, identity, case, trace):
    stdout, stderr = folder / 'worker.stdout', folder / 'worker.stderr'
    objects = [json.loads(line) for line in stdout.read_bytes().splitlines()]
    require(objects and objects[0]['schema'] == 'hw-region-2-coordinate-summary-v1', 'missing normal worker summary')
    summary, rows = objects[0], objects[1:]
    offsets = trace['requests']['offsets']; timed = identity['mode'] == 'latency'; semantics = SEMANTICS[identity['profile']]
    require(summary['status'] == 'PASS' and summary['label'] == identity['profile'] and summary['mode'] == identity['mode']
            and summary['semantics'] == semantics and summary['byte_equivalent'] is (semantics == 0)
            and summary['fresh_per_request'] is identity['fresh'] and summary['queries'] == summary['planned_queries'] == len(offsets)
            and summary['warmups'] == len(trace['warmups']['offsets']) and summary['request_bases'] == 16384
            and summary['measurements_of_time'] is timed and summary['no_clocks'] is (not timed)
            and summary['query_clock_calls'] == (2 * len(offsets) if timed else 0), 'worker summary workload/semantics changed')
    require(len(rows) == len(offsets), 'worker row count differs')
    returned, expected = Path(str(prefix) + '.returned.bin'), Path(str(prefix) + '.expected.bin')
    require(returned.stat().st_size == expected.stat().st_size == 16384 * len(offsets), 'capture size differs')
    with returned.open('rb') as actual, expected.open('rb') as reference, Path(case['sequence']['path']).open('rb') as truth:
        for i, (row, start) in enumerate(zip(rows, offsets)):
            left, right = reference.read(16384), actual.read(16384)
            truth.seek(start)
            require(left == truth.read(16384), 'captured reference differs from structurally verified source sequence')
            wanted = left.upper() if semantics == 2 else left
            differences = [] if wanted == right else [(a, b) for a, b in zip(wanted, right) if a != b]
            permitted = sum(a == 110 and b == 78 for a, b in differences) if semantics == 1 else 0
            require(len(differences) == permitted and row['differences'] == permitted and row['permitted_n_to_N'] == permitted,
                    'captured sequence violates declared comparison semantics')
            require(row['schema'] == 'hw-region-2-coordinate-row-v1' and row['query'] == i and row['start0'] == start
                    and row['requested_bases'] == 16384 and row['verified'] is True and row['semantics'] == semantics,
                    'raw request/order or judgement changed')
            require(type(row['elapsed_ns']) is int and row['elapsed_ns'] > 0 if timed else row['elapsed_ns'] is None, 'query interval invalid')
    if timed:
        require(summary['open_clock_calls'] == 2 * summary['opens'] and summary['open_ns'] > 0
                and summary['peak_process_rss_kib'] > 0, 'open/RSS observation missing')
    else:
        require(summary['open_clock_calls'] == 0 and summary['open_ns'] is None and summary['peak_process_rss_kib'] is None, 'untimed check clock/RSS scope changed')
    ns = sorted(row['elapsed_ns'] for row in rows) if timed else []
    quantiles = dict(p50_ns=ns[(len(ns) + 1) // 2 - 1], p99_ns=ns[(99 * len(ns) + 99) // 100 - 1]) if timed else None
    expected_destination = HERE / 'captures/expected' / (sha(expected) + '.bin.gz')
    value = dict(schema='hw-region-2-casefix-observation-v1', status='PASS', identity=identity, profile=identity['profile'],
                 summary=summary, rows=rows, quantiles=quantiles,
                 returned=published_capture(returned, folder / 'returned.bin.gz'),
                 expected=published_capture(expected, expected_destination),
                 native_stdout=artifact(stdout), native_stderr=artifact(stderr))
    immutable(folder / 'observation.json', value)
    return value


def failure(folder, code, prefix=None):
    files = [artifact(p) for p in folder.rglob('*') if p.is_file()]
    captures = []
    if prefix is not None:
        for p in Path(prefix).parent.glob('*.bin'):
            captures.append(published_capture(p, folder / (p.name + '.gz')))
    stop('worker mismatch' if code == 2 else 'worker method/error (not a measured case-mismatch claim)', dict(returncode=code, artifacts=files, captures=captures))


def checked_unit(unit_id, profile, case, trace, fresh=False, probe=False):
    guard()
    require('/' not in unit_id and '..' not in unit_id, 'invalid unit id')
    identity = unit_identity('check', profile, case, trace, fresh, probe)
    folder = HERE / 'checks' / unit_id / profile
    path = folder / 'observation.json'
    prefix = STATE / 'captures/checks' / unit_id / profile / 'out'
    if path.exists():
        value = load(path); require(value['identity'] == identity, 'cached check identity changed')
        module('setup').check_tree([value[k] for k in ('returned', 'expected', 'native_stdout', 'native_stderr')])
        return value, path
    require(not folder.exists() and not prefix.parent.exists(), 'orphan check cannot be silently rerun')
    folder.mkdir(parents=True); prefix.parent.mkdir(parents=True)
    argv = worker_command('check', profile, case, trace, prefix, fresh=fresh, probe=probe)
    immutable(folder / 'started.json', dict(identity=identity, command=argv, status='STARTED'))
    proc = subprocess.run(argv, cwd=ROOT, env=module('setup').environment(), capture_output=True)
    immutable(folder / 'worker.stdout', proc.stdout); immutable(folder / 'worker.stderr', proc.stderr)
    immutable(folder / 'command.json', dict(identity=identity, command=argv, status='COMPLETE' if proc.returncode == 0 else 'ERROR', returncode=proc.returncode))
    if proc.returncode:
        failure(folder, proc.returncode, prefix)
    try:
        return parse_observation(folder, prefix, identity, case, trace), path
    except Exception as exc:
        stop('correctness parser/capture validation failed: ' + str(exc), dict(command=argv, raw=artifact(folder / 'worker.stdout')))


def admitted():
    guard()
    value = load(HERE / 'admission.json')
    require(value['status'] == 'PASS' and value['source_sha256'] == source_map()
            and value['native_build_sha256'] == sha(HERE / 'native/build.json') and value['setup_sha256'] == sha(HERE / 'setup.json'), 'whole-grid admission missing/changed')
    require(len(value['grid']) == 31 * 6, 'whole-grid correctness gate incomplete')
    for record in value['grid'] + [value['lowercase_n_witness'], value['controls_plan']]:
        deref(record)
    return value


def check():
    guard(); build()
    if (HERE / 'admission.json').exists():
        return admitted()
    setup_module = module('setup')
    for corpus in CORPORA:
        setup_module.case(corpus)
    grid = []
    for corpus in CORPORA:
        case, trace = load_case(corpus), load_trace(corpus)
        for profile in PROFILES:
            value, path = checked_unit(corpus, profile, case, trace)
            grid.append(ref(path))
    case = load_case('chr1')
    trace = dict(warmups=dict(path=str(STATE / 'traces/witness/warmups.bin'), offsets=[]),
                 requests=dict(path=str(STATE / 'traces/witness/requests.bin'), offsets=[121757468 - 8192]))
    for key in ('warmups', 'requests'):
        immutable(Path(trace[key]['path']), b''.join(struct.pack('<Q', p) for p in trace[key]['offsets']))
        trace[key].update(artifact(trace[key]['path']))
    witness, witness_path = checked_unit('lowercase-n-witness', 'twobit_casefix_mask1', case, trace, probe=True)
    require(witness['rows'][0]['differences'] == 0, 'casefix did not restore original lowercase n')
    module('controls').prepare(sys.modules[__name__])
    plan = HERE / 'controls-plan.json'
    require(plan.exists() and load(plan)['status'] in ('PASS', 'PREPARED'), 'synthetic correctness/control plan required before timing')
    value = dict(schema='hw-region-2-casefix-admission-v1', status='PASS', source_sha256=source_map(),
                 native_build_sha256=sha(HERE / 'native/build.json'), setup_sha256=sha(HERE / 'setup.json'),
                 grid=grid, lowercase_n_witness=ref(witness_path), controls_plan=ref(plan), no_clocks=True, measurements_of_time=False)
    immutable(HERE / 'admission.json', value)
    return value


def timed_unit(kind, unit_id, profile, case, trace, fresh=False, probe=False):
    admitted()
    require(kind in ('aa-first', 'aa-second', 'boundary', 'main') and '/' not in unit_id and '..' not in unit_id, 'invalid timed unit')
    if kind == 'main':
        verify_aa(); verify_controls()
    identity = unit_identity('latency', profile, case, trace, fresh, probe)
    path = HERE / 'units' / kind / unit_id / (profile + '.json')
    if path.exists():
        unit = load(path); require(unit['identity'] == identity and unit['status'] == 'CLEAN', 'blocked/changed unit cannot be retimed')
        selected = load(deref(unit['selected']))
        module('setup').check_tree([selected[k] for k in ('returned', 'expected', 'native_stdout', 'native_stderr')])
        return selected, path
    helper = module('ovh_bench'); attempts = []
    for number in range(1, 4):
        folder = HERE / 'raw' / kind / unit_id / profile / ('attempt-' + str(number))
        private = STATE / 'captures' / kind / unit_id / profile / ('attempt-' + str(number))
        prefix = private / 'out'; receipt = folder / 'ovh-bench.json'
        argv = worker_command('latency', profile, case, trace, prefix, fresh=fresh, probe=probe)
        if not receipt.exists():
            require(not folder.exists() and not private.exists(), 'orphan attempt cannot be silently retimed')
            folder.mkdir(parents=True); private.mkdir(parents=True)
        code = helper.run_locked(argv, receipt, stdout_path=folder / 'worker.stdout')
        record = load(receipt)
        immutable(folder / 'worker.stderr', Path(str(receipt) + '.stderr').read_bytes())
        require(record['schema'] == 'hw-region-2-casefix-ovh-v1' and record['command'] == argv
                and record['protocol_sha256'] == sha(HERE / 'PROTOCOL.md')
                and record['calibration_sha256'] == sha(HERE / 'CALIBRATION.md'), 'shared-lock receipt identity differs')
        if code not in (0, 77) or record['status'] == 'ERROR':
            failure(folder, record.get('returncode') or code, prefix)
        observation = None
        if record['command_started']:
            try:
                observation = parse_observation(folder, prefix, identity, case, trace)
            except Exception as exc:
                stop('timed capture validation failed: ' + str(exc), dict(receipt=ref(receipt)))
        attempts.append(dict(number=number, status=record['status'], receipt=ref(receipt),
                             observation=ref(folder / 'observation.json') if observation else None))
        if code == 0:
            require(record['status'] == 'CLEAN' and observation is not None, 'CLEAN observation missing')
            unit = dict(schema='hw-region-2-casefix-unit-v1', status='CLEAN', identity=identity,
                        selected=ref(folder / 'observation.json'), attempts=attempts)
            immutable(path, unit)
            return observation, path
    immutable(path, dict(schema='hw-region-2-casefix-unit-v1', status='BLOCKED: load', identity=identity, selected=None, attempts=attempts))
    raise ValueError('BLOCKED: load; three retained attempts, no fourth attempt admitted')


def verify_aa():
    value = load(HERE / 'method-aa.json')
    require(value['status'] == 'PASS' and value['source_sha256'] == source_map() and value['admission'] == ref(HERE / 'admission.json'), 'AA gate missing/changed')
    require(set(value['profiles']) == set(PROFILES), 'AA six-profile gate incomplete')
    for row in value['profiles'].values():
        deref(row['first']); deref(row['second'])
        require(20 * abs(row['second_p50_ns'] - row['first_p50_ns']) < row['first_p50_ns'], 'strict AA <5% failed')
    return value


def verify_controls():
    value = load(HERE / 'controls.json')
    require(value['status'] == 'PASS' and value['source_sha256'] == source_map()
            and value['native_build_sha256'] == sha(HERE / 'native/build.json') and value['setup_sha256'] == sha(HERE / 'setup.json'), 'boundary gate missing/changed')
    require(set(value['controls']) == set(EQUIVALENT), 'four equivalent boundary controls required')
    for row in value['controls'].values():
        require(row['strictly_more_cost'] is True and row['crossing_p50_ns'] > row['aligned_p50_ns'], 'strict boundary cost gate failed')
    for record in value['evidence_refs']:
        deref(record)
    require((HERE / 'controls-summary.json').read_bytes() == (HERE / 'controls.json').read_bytes(), 'control gate mirrors differ')
    return value


def method_aa():
    admitted()
    if (HERE / 'method-aa.json').exists():
        return verify_aa()
    case, trace, rows = load_case('chr1'), load_trace('chr1'), {}
    for profile in PROFILES:
        first, p1 = timed_unit('aa-first', 'chr1', profile, case, trace)
        second, p2 = timed_unit('aa-second', 'chr1', profile, case, trace)
        a, b = first['quantiles']['p50_ns'], second['quantiles']['p50_ns']
        rows[profile] = dict(first=ref(p1), second=ref(p2), first_p50_ns=a, second_p50_ns=b, strict_under_five_percent=20 * abs(b - a) < a)
        if not rows[profile]['strict_under_five_percent']:
            immutable(HERE / 'method-aa.json', dict(status='FAIL', source_sha256=source_map(), admission=ref(HERE / 'admission.json'), profiles=rows))
            raise ValueError('AA failed; no elapsed-time retry admitted')
    value = dict(schema='hw-region-2-casefix-aa-v1', status='PASS', source_sha256=source_map(), admission=ref(HERE / 'admission.json'), profiles=rows)
    immutable(HERE / 'method-aa.json', value)
    return value


def main_grid(corpus):
    admitted(); verify_aa(); verify_controls()
    require(corpus in CORPORA, 'unknown corpus')
    path = HERE / 'cases' / (corpus + '.json')
    if path.exists():
        value = load(path); require(value['source_sha256'] == source_map(), 'main source changed')
        for record in value['units'].values():
            deref(record)
        return value
    case, trace = load_case(corpus), load_trace(corpus)
    k = CORPORA.index(corpus) % len(PROFILES)
    order = PROFILES[k:] + PROFILES[:k]
    units = {}
    for profile in order:
        observation, unit = timed_unit('main', corpus, profile, case, trace)
        units[profile] = ref(unit)
    value = dict(schema='hw-region-2-casefix-case-v1', status='COMPLETE', corpus=corpus, order=list(order),
                 source_sha256=source_map(), admission=ref(HERE / 'admission.json'), aa=ref(HERE / 'method-aa.json'),
                 controls=ref(HERE / 'controls.json'), archive_case=ref(HERE / 'archives' / (corpus + '.json')), units=units)
    immutable(path, value)
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('build', 'check', 'method-aa', 'main'))
    p.add_argument('--corpus', choices=CORPORA)
    args = p.parse_args()
    require(sys.platform == 'linux', 'Linux executor required')
    require(not os.environ.get('OVH_BENCH_LOCK_HELD'), 'controller must not already hold the benchmark lock')
    os.sched_setaffinity(0, {15})
    result = {'build': build, 'check': check, 'method-aa': method_aa, 'main': lambda: main_grid(args.corpus)}[args.action]()
    print(args.action.upper(), result.get('status', 'PASS'))


if __name__ == '__main__':
    main()
