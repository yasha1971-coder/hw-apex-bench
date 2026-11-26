# SPDX-License-Identifier: Apache-2.0
"""Isolated chr1 binary-search extension; no work occurs on import.

prepare/check are untimed. poll observes once when due. Each method-aa,
boundary or main invocation starts at most one load-admitted worker attempt.
Original casefix source, binaries, evidence and P1-P3 are never rewritten.
"""
import argparse
from datetime import datetime, timedelta, timezone
import fcntl
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = HERE.parent / 'casefix'
STATE = ROOT / '.work/hw-region-2/binary-search'
LABEL = 'twobit_casefix_binary_mask1'
CALIBRATION_COMMIT = '633badf83a934cbbfe063a8455ffe348114e2f36'
PIN = '58e20daa898a6fc338eae82e5d2ef7108d4fc07f'
UNITS = ('aa-first', 'aa-second', 'boundary', 'main')


def require(ok, why):
    if not ok:
        raise ValueError(why)


def load(path):
    return json.loads(Path(path).read_bytes())


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def artifact(path):
    path = Path(path).resolve()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def verify(record):
    p = Path(record['path'])
    require(p.is_file() and p.stat().st_size == record['bytes'] and sha(p) == record['sha256'], 'artifact changed: ' + str(p))


def ref(path):
    path = Path(path).resolve()
    require(path.is_relative_to(HERE), 'extension reference escaped its stage')
    return dict(path=path.relative_to(HERE).as_posix(), sha256=sha(path))


def external(path):
    path = Path(path).resolve()
    require(path.is_relative_to(ROOT), 'public input reference escaped repository')
    return dict(base='repository', path=path.relative_to(ROOT).as_posix(), sha256=sha(path))


def deref(record):
    base = ROOT if record.get('base') == 'repository' else HERE
    p = (base / record['path']).resolve()
    require(p.is_relative_to(base) and p.is_file() and sha(p) == record['sha256'], 'retained reference changed')
    return p


def immutable(path, value):
    path = Path(path); raw = value if isinstance(value, bytes) else packed(value)
    require(path.resolve().is_relative_to(HERE) or path.resolve().is_relative_to(STATE), 'extension output escaped owned scope')
    if path.exists():
        require(path.read_bytes() == raw, 'changed/partial extension output: ' + str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)


def module(path, name):
    spec = importlib.util.spec_from_file_location('_binary_' + name, path)
    value = importlib.util.module_from_spec(spec); sys.modules[spec.name] = value; spec.loader.exec_module(value)
    return value


def original(name):
    return module(BASE / (name + '.py'), 'base_' + name)


def guard():
    require(not (HERE / 'KILL.json').exists(), 'retained extension Kill stops all later native work')
    require(not (HERE / 'ERROR.json').exists(), 'retained fatal admission error stops polling and timing')


def source_map():
    files = [HERE / n for n in ('CALIBRATION.md', 'PROTOCOL.md', 'stage.py', 'lib2bit-binary-search.patch',
                                'test_binary_search.py', 'mask_counts.py')]
    files += [BASE / n for n in ('drive.py', 'setup.py', 'native.c', 'worker.c', 'coordinate.h', 'ovh_bench.py', 'CALIBRATION.md', 'PROTOCOL.md')]
    files += [HERE.parent / 'writer.py', HERE.parent / 'lib2bit-casefix.patch']
    names = [p.relative_to(ROOT).as_posix() for p in files]
    subprocess.run(['git', '-C', str(ROOT), 'ls-files', '--error-unmatch', '--', *names], check=True, capture_output=True)
    require(not subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain', '--', *names]).strip(), 'all extension execution inputs must be committed before native work')
    require(subprocess.check_output(['git', '-C', str(ROOT), 'show', CALIBRATION_COMMIT + ':evidence/hw-region-2/binary-search/CALIBRATION.md'])
            == (HERE / 'CALIBRATION.md').read_bytes(), 'first-only B1 calibration changed')
    require(not any(k.startswith(('ACEAPEX_', 'AX_', 'LIT_', 'FSE_')) for k in os.environ), 'reader overrides must be absent')
    return {name: sha(ROOT / name) for name in names}


def parent_inputs():
    admission = load(BASE / 'admission.json'); audit = load(BASE / 'audit/resumed-all.json')
    require(admission['status'] == 'PASS' and audit['status'] == 'PASS' and audit['stage'] == 'resumed-all'
            and audit['completion'] == 'COMPLETE' and audit['counts']['cases'] == 31 and audit['counts']['rows'] == 186,
            'complete verified parent casefix experiment required')
    drive = original('drive'); native = drive.native_build()
    case = drive.load_case('chr1'); trace = drive.load_trace('chr1')
    primary = load(BASE / 'cases/chr1.json'); unit_ref = primary['units']['twobit_casefix_mask1']
    unit = load(BASE / unit_ref['path']); require(sha(BASE / unit_ref['path']) == unit_ref['sha256'] and unit['status'] == 'CLEAN', 'frozen baseline unit changed')
    selected = unit['selected']; observed = load(BASE / selected['path'])
    require(sha(BASE / selected['path']) == selected['sha256'] and observed['quantiles']['p50_ns'] == 88965,
            'registered frozen baseline is not 88965 ns')
    plan = load(BASE / 'controls-plan.json')['controls']['twobit_casefix_mask1']
    return dict(admission=external(BASE / 'admission.json'), resumed_all=external(BASE / 'audit/resumed-all.json'),
                baseline_unit=external(BASE / unit_ref['path']), baseline_observation=external(BASE / selected['path']),
                baseline_p50_ns=88965, parent_native=external(BASE / 'native/build.json'), parent_setup=external(BASE / 'setup.json'),
                archive_case=external(BASE / 'archives/chr1.json'), trace=external(BASE / 'traces/chr1.json'),
                controls_plan=external(BASE / 'controls-plan.json')), case, trace, plan, native


def apply_patch(source, patch):
    """Strict unified-patch application to bytes in a new owned copy."""
    lines = source.splitlines(keepends=True); changes = patch.splitlines(keepends=True)
    output, position, hunk = [], 0, False
    i = 0
    while i < len(changes):
        line = changes[i]
        if not line.startswith(b'@@'):
            require(line.startswith((b'diff ', b'index ', b'--- ', b'+++ ')) or not line.strip(), 'unexpected patch metadata')
            i += 1; continue
        match = re.match(rb'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
        require(match is not None, 'invalid patch hunk')
        start = int(match[1]) - 1; require(start >= position, 'overlapping patch hunks')
        output.extend(lines[position:start]); position = start; i += 1; hunk = True
        before = after = 0
        while i < len(changes) and not changes[i].startswith(b'@@'):
            row = changes[i]
            require(row[:1] in (b' ', b'-', b'+'), 'unexpected patch body')
            if row[:1] in (b' ', b'-'):
                require(position < len(lines) and lines[position] == row[1:], 'patch context differs from exact casefix source')
                position += 1; before += 1
            if row[:1] in (b' ', b'+'):
                output.append(row[1:]); after += 1
            i += 1
        require(before == int(match[2] or 1) and after == int(match[4] or 1), 'patch hunk counts differ')
    require(hunk, 'binary-search patch has no hunk')
    output.extend(lines[position:]); result = b''.join(output)
    begin = source.index(b'void softMask('); tail = source.index(b'char *constructSequence(', begin)
    new_begin = result.index(b'void softMask('); new_tail = result.index(b'char *constructSequence(', new_begin)
    require(source[:begin] == result[:new_begin] and source[tail:] == result[new_tail:], 'patch changes code outside softMask')
    old_loop = b'for(i=0; i<tb->idx->maskBlockCount[tid]; i++) {'
    new_loop = b'for(i=lo; i<tb->idx->maskBlockCount[tid]; i++) {'
    old_body = source[begin:tail]; new_body = result[new_begin:new_tail]
    require(old_body.count(old_loop) == new_body.count(new_loop) == 1
            and old_body.split(old_loop, 1)[1] == new_body.split(new_loop, 1)[1], 'existing softMask loop body must remain byte-identical')
    require(b"if(seq[pos] != 'N')" not in new_body and b'seq[pos] = tolower(seq[pos]);' in new_body,
            'base casefix was removed or changed')
    return result


def mask_invariants(metadata):
    length = metadata['sequence']['bytes']; rows = metadata['archive']['mask_blocks']; previous = 0
    for start, size in rows:
        require(type(start) is int and type(size) is int and size > 0 and previous <= start and start + size <= length < 2**32,
                'binary search requires sorted disjoint in-range mask blocks')
        previous = start + size
    return dict(blocks=len(rows), masked_bases=sum(size for start, size in rows), sequence_bases=length,
                sorted_disjoint=True, endpoint_arithmetic='uint64_t during binary search; existing loop unchanged')


def publish_edge(value):
    """Expose existing synthetic source/stdout bytes, never compiled binaries."""
    copies = {}
    def visit(item):
        if isinstance(item, dict):
            if {'path', 'bytes', 'sha256'} <= item.keys():
                path = Path(item['path'])
                if path.suffix in ('.c', '.h', '.stdout', '.stderr') or path.name in ('stdout', 'stderr'):
                    verify(item)
                    target = HERE / 'edge-artifacts' / (item['sha256'] + '-' + path.name)
                    immutable(target, path.read_bytes()); copies[str(path)] = ref(target)
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
    visit(value)
    public = dict(schema='hw-region-2-binary-edge-public-v1', status='PASS', report=ref(HERE / 'edge-tests.json'), public_files=copies)
    immutable(HERE / 'edge-public.json', public)
    return public


def run(label, argv, outputs=()):
    folder = STATE / 'commands' / label; receipt = folder / 'command.json'
    identity = dict(argv=['taskset', '-c', '15', *map(str, argv)], outputs=list(map(str, outputs)))
    if receipt.exists():
        value = load(receipt); require(value['identity'] == identity and value['status'] == 'PASS', 'unfinished/changed untimed command')
        for record in value['artifacts']:
            verify(record)
    else:
        require(not folder.exists() and all(not Path(p).exists() for p in outputs), 'orphan build/check output; inspect without rerunning')
        folder.mkdir(parents=True); immutable(folder / 'started.json', identity)
        proc = subprocess.run(identity['argv'], cwd=ROOT, env=original('setup').environment(), capture_output=True)
        immutable(folder / 'stdout', proc.stdout); immutable(folder / 'stderr', proc.stderr)
        value = dict(identity=identity, status='PASS' if proc.returncode == 0 else 'ERROR', returncode=proc.returncode,
                     artifacts=[artifact(p) for p in [folder / 'stdout', folder / 'stderr', *[Path(o) for o in outputs if Path(o).is_file()]]])
        immutable(receipt, value)
    for p in folder.iterdir():
        immutable(HERE / 'commands' / label / p.name, p.read_bytes())
    require(value['status'] == 'PASS', 'untimed build/check failed')
    return value


def build_record():
    value = load(HERE / 'native/build.json')
    require(value['identity']['source_sha256'] == source_map() and value['identity']['setup_sha256'] == sha(HERE / 'setup.json'), 'extension build/source cohort changed')
    setup = load(HERE / 'setup.json')
    for record in [*setup['public_sources'].values(), setup['mask_counts']]:
        deref(record)
    for record in value['build_inputs'] + [value['artifacts']['worker'], value['artifacts']['dsos'][LABEL]]:
        verify(record)
    return value


def prepare():
    guard(); sources = source_map(); parents, case, trace, control, old_native = parent_inputs()
    counts = load(HERE / 'mask-counts.json')
    require(counts['schema'] == 'hw-region-2-mask-counts-v1' and counts['status'] == 'PASS' and counts['no_clocks'] is True
            and len(counts['corpora']) == 31 and counts['parent_audit']['sha256'] == parents['resumed_all']['sha256'], 'saved mask-count analysis is not bound to the completed parent')
    require(any(r['path'] == 'evidence/hw-region-2/binary-search/mask_counts.py' and r['sha256'] == sha(HERE / 'mask_counts.py')
                for r in counts['source_bindings']), 'mask-count helper source changed')
    identity = dict(source_sha256=sources, parents=parents)
    if (HERE / 'native/build.json').exists():
        require(load(HERE / 'setup.json')['identity'] == identity, 'frozen parent/input identity changed')
        return build_record()
    old_setup = load(BASE / 'setup.json'); lib = old_setup['lib2bit']; fixed = lib['variants']['casefix']
    require(lib['commit'] == PIN and sha(fixed['source_path']) == fixed['source_sha256']
            and sha(lib['header_path']) == lib['header_sha256'], 'pinned casefix source/header changed')
    source = Path(fixed['source_path']).read_bytes(); modified = apply_patch(source, (HERE / 'lib2bit-binary-search.patch').read_bytes())
    upstream = Path(lib['path']) / '2bit.c'
    before, after = b"if(seq[pos] != 'N') seq[pos] = tolower(seq[pos]);", b'seq[pos] = tolower(seq[pos]);'
    original_bytes = upstream.read_bytes()
    require(original_bytes.count(before) == 1 and source == original_bytes.replace(before, after, 1), 'base is not the exact one-line casefix of pinned upstream')
    public_sources = {}
    for name, raw in (('upstream-2bit.c', original_bytes), ('casefix-2bit.c', source), ('binary-2bit.c', modified),
                      ('2bit.h', Path(lib['header_path']).read_bytes()), ('LICENSE', (Path(lib['path']) / 'LICENSE').read_bytes())):
        target = HERE / 'sources' / name; immutable(target, raw); public_sources[name] = ref(target)
    folder = STATE / 'build'; new_source, obj, library = folder / '2bit.c', folder / '2bit.o', folder / 'lib2bit.a'
    immutable(new_source, modified)
    compiler = Path(shutil.which('gcc')).resolve(); require(sha(compiler) == lib['compiler']['gcc']['sha256'], 'compiler differs from original casefix')
    run('compiler-version', [compiler, '--version'])
    run('binary-compile', [compiler, '-O3', '-fPIC', '-I' + lib['path'], '-c', new_source, '-o', obj], (obj,))
    run('binary-static', ['ar', 'rcs', library, obj], (library,))
    dso = folder / (LABEL + '.so')
    run('coordinate-dso', [compiler, '-O3', '-fPIC', '-fno-lto', '-shared', '-Wall', '-Wextra', '-Wl,-Bsymbolic', '-std=c11',
        '-I' + str(BASE), '-DCOORD_LABEL="' + LABEL + '"', '-DCOORD_TWOBIT', '-DCOORD_STORE_MASKED=1', '-DCOORD_ORIGINAL=0',
        '-I' + lib['path'], BASE / 'native.c', library, '-o', dso], (dso,))
    metadata = json.loads(gzip.decompress((BASE / 'writer-metadata/chr1.json.gz').read_bytes()))
    control_metadata = load(BASE / 'controls-plan.json')['controls']['twobit_casefix_mask1']['case']['writer_metadata']
    verify(control_metadata); synthetic = json.loads(gzip.decompress(Path(control_metadata['path']).read_bytes()))
    setup = dict(schema='hw-region-2-binary-setup-v1', identity=identity, label=LABEL, lib2bit_commit=PIN,
                 source=artifact(new_source), original_casefix_source=artifact(fixed['source_path']), header=artifact(lib['header_path']),
                 compiler=artifact(compiler), mask_invariants=dict(chr1=mask_invariants(metadata), synthetic=mask_invariants(synthetic)),
                 chr1_case=parents['archive_case'], chr1_trace=parents['trace'], synthetic_plan=parents['controls_plan'],
                 public_sources=public_sources, mask_counts=ref(HERE / 'mask-counts.json'), no_new_archives=True, no_clocks=True)
    immutable(HERE / 'setup.json', setup); immutable(STATE / 'setup.json', setup)
    build = dict(schema='hw-region-2-binary-native-v1', status='PASS',
                 identity=dict(source_sha256=sources, setup_sha256=sha(HERE / 'setup.json'), parents=parents,
                               source_commit=subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).decode().strip()),
                 artifacts=dict(worker=old_native['artifacts']['worker'], dsos={LABEL: artifact(dso)}),
                 build_inputs=[artifact(p) for p in (new_source, obj, library, Path(lib['header_path']), BASE / 'native.c', BASE / 'coordinate.h', BASE / 'worker.c')])
    immutable(HERE / 'native/build.json', build); immutable(STATE / 'native/build.json', build)
    return build


def parser():
    """Compose unchanged parent parsing/correctness code in this namespace only."""
    d = original('drive'); d.HERE = HERE; d.STATE = STATE; d.PROFILES = (LABEL,); d.EQUIVALENT = (LABEL,); d.SEMANTICS = {LABEL: 0}
    d.source_map = source_map; d.native_build = build_record; d.module = original
    return d


def inputs(name):
    old = original('drive'); case = old.load_case('chr1'); trace = old.load_trace('chr1')
    if name == 'boundary':
        selected = load(BASE / 'controls-plan.json')['controls']['twobit_casefix_mask1']
        return selected['case'], selected['trace'], True, True
    return case, trace, False, False


def check():
    prepare(); d = parser()
    if (HERE / 'admission.json').exists():
        value = load(HERE / 'admission.json'); require(value['identity'] == cohort(), 'admission source changed')
        for r in value['checks']:
            deref(r)
        return value
    lib = load(BASE / 'setup.json')['lib2bit']
    edge = HERE / 'edge-tests.json'
    run('edge-tests', [sys.executable, '-B', HERE / 'test_binary_search.py', '--source', Path(lib['path']) / '2bit.c',
                      '--workdir', STATE / 'edge-tests', '--output', edge, '--cc', 'gcc'], (edge,))
    require(load(edge)['status'] == 'PASS' and load(edge)['no_clocks'] is True, 'actual-C synthetic edge checks must pass')
    publish_edge(load(edge))
    refs = [ref(edge), ref(HERE / 'edge-public.json')]
    case, trace, fresh, probe = inputs('main')
    for name, used_case, used_trace, fresh, probe in [('chr1-grid', case, trace, False, False),
            ('synthetic-mask', *inputs('boundary'))]:
        observed, path = d.checked_unit(name, LABEL, used_case, used_trace, fresh=fresh, probe=probe); refs.append(ref(path))
    witness = dict(warmups=dict(path=str(STATE / 'traces/witness/warmups.bin'), offsets=[]),
                   requests=dict(path=str(STATE / 'traces/witness/requests.bin'), offsets=[121749276]))
    for key in ('warmups', 'requests'):
        immutable(Path(witness[key]['path']), b''.join(struct.pack('<Q', p) for p in witness[key]['offsets']))
        witness[key].update(artifact(witness[key]['path']))
    observed, path = d.checked_unit('lowercase-n-witness', LABEL, case, witness, probe=True); refs.append(ref(path))
    value = dict(schema='hw-region-2-binary-admission-v1', status='PASS', identity=cohort(), checks=refs, no_clocks=True)
    immutable(HERE / 'admission.json', value)
    return value


def cohort():
    build_record()
    return dict(source_sha256=source_map(), native_build_sha256=sha(HERE / 'native/build.json'),
                setup_sha256=sha(HERE / 'setup.json'), calibration_sha256=sha(HERE / 'CALIBRATION.md'), protocol_sha256=sha(HERE / 'PROTOCOL.md'))


def admitted():
    guard(); value = load(HERE / 'admission.json')
    require(value['status'] == 'PASS' and value['identity'] == cohort(), 'new extension correctness admission required')
    for record in value['checks']:
        deref(record)


def history(name, recover=False):
    d = parser(); case, trace, fresh, probe = inputs(name)
    identity = d.unit_identity('latency', LABEL, case, trace, fresh, probe)
    folders = sorted((HERE / 'raw' / name).glob('attempt-*')) if (HERE / 'raw' / name).exists() else []
    require([p.name for p in folders] == ['attempt-' + str(i) for i in range(1, len(folders) + 1)] and len(folders) <= 3, 'invalid/fourth extension attempt')
    records = []
    for number, folder in enumerate(folders, 1):
        receipt = folder / 'ovh-bench.json'; require(receipt.exists(), 'orphan reserved attempt; inspect without retiming')
        r = load(receipt); prefix = STATE / 'captures' / name / folder.name / 'out'
        if r['status'] == 'ERROR':
            d.failure(folder, r.get('returncode') or 1, prefix)
        argv = d.worker_command('latency', LABEL, case, trace, prefix, fresh=fresh, probe=probe)
        tokens = [p for p in (HERE / 'consumptions').glob('poll-*.json') if load(p)['receipt_path'] == receipt.relative_to(HERE).as_posix()]
        require(len(tokens) == 1, 'actual attempt needs one prior passed-poll consumption')
        token = load(tokens[0]); require(token['identity'] == cohort() and token['unit'] == name and token['attempt_number'] == number, 'extension poll consumption changed')
        require(r['status'] in ('CLEAN', 'LOADED') and r['command'] == argv and r['helper_sha256'] == sha(BASE / 'ovh_bench.py')
                and r['protocol_sha256'] == sha(BASE / 'PROTOCOL.md') and r['calibration_sha256'] == sha(BASE / 'CALIBRATION.md'), 'original helper receipt/source differs')
        obs = folder / 'observation.json'
        if r['command_started'] and recover:
            for stream in ('stdout', 'stderr'):
                raw = Path(str(receipt) + '.' + stream); require(sha(raw) == r[stream + '_sha256'], 'helper stream differs')
                immutable(folder / ('worker.' + stream), raw.read_bytes())
            try:
                d.parse_observation(folder, prefix, identity, case, trace)
            except Exception as error:
                d.stop('binary-search capture validation failed: ' + str(error), dict(receipt=ref(receipt)))
        records.append(dict(number=number, status=r['status'], receipt=ref(receipt), observation=ref(obs) if obs.exists() else None,
                            admission_poll=token['poll'], poll_consumption=ref(tokens[0])))
        require(r['status'] != 'CLEAN' or number == len(folders), 'attempt exists after first CLEAN')
    return identity, records


def finish(name):
    path = HERE / 'units' / (name + '.json')
    if path.exists():
        unit = load(path); require(unit['stage_identity'] == cohort(), 'extension unit identity changed')
        return unit
    identity, records = history(name, recover=True)
    if not records or (records[-1]['status'] != 'CLEAN' and len(records) < 3):
        return None
    unit = dict(schema='hw-region-2-binary-unit-v1', status='CLEAN' if records[-1]['status'] == 'CLEAN' else 'BLOCKED: load',
                identity=identity, stage_identity=cohort(), attempts=records,
                selected=records[-1]['observation'] if records[-1]['status'] == 'CLEAN' else None)
    immutable(path, unit)
    return unit


def selected(name):
    unit = load(HERE / 'units' / (name + '.json'))
    require(unit['status'] == 'CLEAN' and unit['stage_identity'] == cohort(), 'selected extension unit unavailable')
    return load(deref(unit['selected']))


def gates():
    if all((HERE / 'units' / (n + '.json')).exists() and load(HERE / 'units' / (n + '.json'))['status'] == 'CLEAN' for n in UNITS[:2]):
        a, b = selected('aa-first')['quantiles']['p50_ns'], selected('aa-second')['quantiles']['p50_ns']
        aa = dict(schema='hw-region-2-binary-aa-v1', status='PASS' if 20 * abs(b - a) < a else 'METHODFAIL',
                  identity=cohort(), first=ref(HERE / 'units/aa-first.json'), second=ref(HERE / 'units/aa-second.json'), first_p50_ns=a, second_p50_ns=b)
        immutable(HERE / 'method-aa.json', aa)
        if aa['status'] != 'PASS':
            return 'METHODFAIL', None
    if (HERE / 'units/boundary.json').exists() and load(HERE / 'units/boundary.json')['status'] == 'CLEAN':
        obs = selected('boundary'); roles = inputs('boundary')[1]['roles']
        groups = {r: sorted(row['elapsed_ns'] for row, role in zip(obs['rows'], roles) if role == r) for r in ('aligned', 'crossing')}
        require(all(len(rows) == 1000 for rows in groups.values()), 'synthetic boundary pair count differs')
        a, b = groups['aligned'][499], groups['crossing'][499]
        control = dict(schema='hw-region-2-binary-boundary-v1', status='PASS' if b > a else 'METHODFAIL', identity=cohort(),
                       aligned_p50_ns=a, crossing_p50_ns=b, unit=ref(HERE / 'units/boundary.json'))
        immutable(HERE / 'boundary.json', control)
        if control['status'] != 'PASS':
            return 'METHODFAIL', None
    for name in UNITS:
        path = HERE / 'units' / (name + '.json')
        if not path.exists():
            return 'WAITING', name
        if load(path)['status'] != 'CLEAN':
            return load(path)['status'], name
    obs = selected('main'); n = obs['quantiles']['p50_ns']; baseline = 88965
    result = dict(schema='hw-region-2-binary-result-v1', status='COMPLETE', identity=cohort(), main_unit=ref(HERE / 'units/main.json'),
                  p50_ns=n, p99_ns=obs['quantiles']['p99_ns'], frozen_casefix_p50_ns=baseline,
                  B1=dict(passed=4 * n <= baseline, verdict='HIT' if 4 * n <= baseline else 'MISS', lhs=4 * n, rhs=baseline),
                  baseline=load(HERE / 'setup.json')['identity']['parents']['baseline_observation'], unchanged_parent_forecasts=True)
    immutable(HERE / 'result.json', result)
    return 'COMPLETE', None


def poll_paths():
    paths = sorted((HERE / 'polls').glob('poll-*.json')) if (HERE / 'polls').exists() else []
    require([p.name for p in paths] == [f'poll-{i:06d}.json' for i in range(1, len(paths) + 1)], 'poll history gap')
    return paths


def now():
    return datetime.now(timezone.utc)


def due():
    ends = [load(p)['observed_end_utc'] for p in poll_paths() if load(p)['status'] == 'WAITING']
    for p in (HERE / 'raw').rglob('ovh-bench.json') if (HERE / 'raw').exists() else []:
        r = load(p)
        if r['status'] == 'LOADED':
            ends.append(r['end']['timestamp_utc'])
    return max(datetime.fromisoformat(t) + timedelta(seconds=300) for t in ends) if ends else None


def ready(name):
    paths = poll_paths()
    if not paths:
        return None
    p = paths[-1]; r = load(p)
    return p if r['status'] == 'PASS' and r['unit'] == name and r['identity'] == cohort() and not (HERE / 'consumptions' / p.name).exists() else None


def status():
    if (HERE / 'KILL.json').exists():
        return dict(status='KILL', next_target=None, next_due_utc=None)
    if (HERE / 'ERROR.json').exists():
        return dict(status='ERROR', next_target=None, next_due_utc=None)
    if not (HERE / 'native/build.json').exists():
        return dict(status='NEEDS PREPARE', next_target=None, next_due_utc=None)
    if not (HERE / 'admission.json').exists():
        return dict(status='NEEDS CHECK', next_target=None, next_due_utc=None)
    admitted(); state, target = gates(); deadline = due()
    value = dict(status='READY' if target and ready(target) and state == 'WAITING' else state, next_target=target,
                 next_due_utc=deadline.isoformat() if deadline and now() < deadline else None)
    if state == 'COMPLETE':
        value.update({k: load(HERE / 'result.json')[k] for k in ('p50_ns', 'p99_ns', 'B1')})
    return value


def write_ledger(view):
    value = dict(schema='hw-region-2-binary-ledger-v1', **view,
                 polls=[ref(p) for p in poll_paths()],
                 consumptions=[ref(p) for p in sorted((HERE / 'consumptions').glob('poll-*.json'))],
                 units={name: ref(HERE / 'units' / (name + '.json')) for name in UNITS if (HERE / 'units' / (name + '.json')).exists()})
    if (HERE / 'native/build.json').exists():
        value['identity'] = cohort()
    for key, name in (('admission', 'admission.json'), ('method_aa', 'method-aa.json'), ('boundary', 'boundary.json'), ('result', 'result.json')):
        if (HERE / name).exists():
            value[key] = ref(HERE / name)
    path = HERE / 'ledger.json'; pending = path.with_suffix('.writing'); pending.write_bytes(packed(value)); pending.replace(path)


def poll():
    admitted(); view = status(); name = view['next_target']
    if name is None or view['status'] not in ('WAITING', 'READY') or view['next_due_utc'] or ready(name):
        return view
    helper = original('ovh_bench')
    value = dict(schema='hw-region-2-binary-poll-v1', status='ERROR', unit=name, identity=cohort(), no_native_calls=True,
                 observed_start_utc=now().isoformat())
    try:
        value['start'] = helper.boundary(); value['foreign_cpu_start'] = helper.cpu_observation(); value['end'] = helper.boundary()
        require(not value['foreign_cpu_start']['inspection_errors'], 'uninspectable process telemetry')
        value['status'] = 'WAITING' if helper.loaded(value['start'], value['end'], value['foreign_cpu_start']) else 'PASS'
    except Exception as error:
        value['error'] = str(error)
    value['observed_end_utc'] = now().isoformat()
    path = HERE / 'polls' / f'poll-{len(poll_paths())+1:06d}.json'; immutable(path, value)
    if value['status'] == 'ERROR':
        immutable(HERE / 'ERROR.json', dict(status='ERROR', identity=cohort(), poll=ref(path), error=value['error']))
    return status()


def timed(action):
    admitted(); view = status(); name = view['next_target']
    wanted = ('aa-first', 'aa-second') if action == 'method-aa' else (action,)
    if name not in wanted or view['status'] not in ('WAITING', 'READY'):
        return view
    case, trace, fresh, probe = inputs(name); unit = finish(name)
    if unit:
        return status()
    passed = ready(name)
    if passed is None or view['next_due_utc']:
        return view
    d = parser(); identity, records = history(name); number = len(records) + 1
    require(number <= 3, 'no fourth extension attempt')
    folder = HERE / 'raw' / name / ('attempt-' + str(number)); prefix = STATE / 'captures' / name / folder.name / 'out'
    require(not folder.exists() and not prefix.parent.exists(), 'orphan actual attempt cannot be retimed')
    receipt = folder / 'ovh-bench.json'
    immutable(HERE / 'consumptions' / passed.name, dict(schema='hw-region-2-binary-consumption-v1', identity=cohort(), unit=name,
              poll=ref(passed), attempt_number=number, receipt_path=receipt.relative_to(HERE).as_posix(), committed_before_attempt_utc=now().isoformat()))
    folder.mkdir(parents=True); prefix.parent.mkdir(parents=True)
    argv = d.worker_command('latency', LABEL, case, trace, prefix, fresh=fresh, probe=probe)
    code = original('ovh_bench').run_locked(argv, receipt, stdout_path=folder / 'worker.stdout'); r = load(receipt)
    immutable(folder / 'worker.stderr', Path(str(receipt) + '.stderr').read_bytes())
    if code not in (0, 77) or r['status'] == 'ERROR':
        d.failure(folder, r.get('returncode') or code, prefix)
    finish(name)
    return status()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('prepare', 'check', 'poll', 'method-aa', 'boundary', 'main', 'status')); args = p.parse_args()
    require(sys.platform == 'linux' and not os.environ.get('OVH_BENCH_LOCK_HELD'), 'Linux controller outside benchmark lock required')
    os.sched_setaffinity(0, {15}); STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'controller.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('another binary-search controller is active')
        if (HERE / 'KILL.json').exists() or (HERE / 'ERROR.json').exists():
            view = status()
        elif args.action == 'prepare':
            prepare(); view = status()
        elif args.action == 'check':
            check(); view = status()
        elif args.action == 'poll':
            view = poll()
        elif args.action == 'status':
            view = status()
        else:
            view = timed(args.action)
        write_ledger(view)
    print(packed(view).decode(), end='')
    return 1 if view['status'] in ('KILL', 'ERROR', 'BLOCKED: load', 'METHODFAIL') else 0


if __name__ == '__main__':
    sys.exit(main())
