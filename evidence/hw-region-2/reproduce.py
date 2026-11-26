# SPDX-License-Identifier: Apache-2.0
"""Untimed lib2bit equivalence admission; a mismatch ends all native work.

Run on the owned executor: taskset -c 15 python3 evidence/hw-region-2/reproduce.py
Completed admission replay verifies retained bytes and never invokes lib2bit.
"""
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = ROOT / '.work/hw-region-2'
PUBLIC = HERE / 'admission.json'
PIN = '58e20daa898a6fc338eae82e5d2ef7108d4fc07f'
URL = 'https://github.com/dpryan79/lib2bit.git'
CALIBRATION = '7fdcbd78b27739cbe1739bf0a8650f395c2afbde'
FROZEN_SOURCES = '327090a0'
COMMANDS = STATE / 'commands'
BUILD = STATE / 'build'


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path, algorithm='sha256'):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def load(path):
    return json.loads(Path(path).read_bytes())


def immutable(path, data):
    path = Path(path)
    require(path.resolve().is_relative_to(ROOT), 'output escaped owned repository')
    if path.exists():
        require(path.read_bytes() == data, 'retained artifact changed: ' + str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)


def artifact(path):
    path = Path(path).resolve()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def verify(record):
    path = Path(record['path'])
    require(path.is_file() and path.stat().st_size == record['bytes'] and sha(path) == record['sha256'],
            'saved artifact identity differs: ' + str(path))


def clean_environment():
    blocked = {'LD_PRELOAD', 'LD_LIBRARY_PATH', 'LIBRARY_PATH', 'CPATH', 'C_INCLUDE_PATH',
               'CPLUS_INCLUDE_PATH', 'CC', 'CXX', 'CFLAGS', 'CPPFLAGS', 'LDFLAGS', 'MAKEFLAGS'}
    return {key: value for key, value in os.environ.items() if key not in blocked}


def command(label, args, *, cwd=ROOT, allowed=(0,), outputs=()):
    """Completed commands replay; interrupted or failed commands require review."""
    folder = COMMANDS / label
    receipt = folder / 'command.json'
    argv = ['taskset', '-c', '15', *map(str, args)]
    identity = dict(argv=argv, cwd=str(cwd), allowed_returncodes=list(allowed), outputs=list(map(str, outputs)))
    if receipt.exists():
        value = load(receipt)
        require(value['identity'] == identity and value['status'] == 'COMPLETE',
                'unfinished/changed command requires review: ' + label)
        for record in value['artifacts']:
            verify(record)
        require(value['returncode'] in allowed, 'saved command failed: ' + label)
    else:
        require(not folder.exists(), 'orphan command requires review: ' + label)
        require(all(not Path(path).exists() for path in outputs), 'unrecorded command output: ' + label)
        folder.mkdir(parents=True)
        receipt.write_bytes(packed(dict(status='STARTED', identity=identity)))
        result = subprocess.run(argv, cwd=cwd, env=clean_environment(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        immutable(folder / 'stdout', result.stdout)
        immutable(folder / 'stderr', result.stderr)
        files = [folder / 'stdout', folder / 'stderr', *[Path(p) for p in outputs if Path(p).is_file()]]
        value = dict(status='COMPLETE' if result.returncode in allowed else 'ERROR', identity=identity,
                     returncode=result.returncode, artifacts=[artifact(path) for path in files])
        receipt.write_bytes(packed(value))
    for path in folder.iterdir():
        if path.is_file():
            immutable(HERE / 'commands' / label / path.name, path.read_bytes())
    require(value['status'] == 'COMPLETE' and value['returncode'] in allowed, 'command failed: ' + label)
    return value, (folder / 'stdout').read_bytes()


def git(*args, repo=ROOT):
    return subprocess.check_output(['git', '-C', str(repo), *args], env=clean_environment())


def identity():
    paths = [HERE / name for name in ('CALIBRATION.md', 'PROTOCOL.md', 'writer.py', 'equivalence.c',
                                      'input-preflight.json', 'reproduce.py')] + [ROOT / 'LICENSE']
    for path in paths:
        name = path.relative_to(ROOT).as_posix()
        git('ls-files', '--error-unmatch', '--', name)
        require(not git('status', '--porcelain', '--', name).strip(), 'source must be committed: ' + name)
    require(git('show', CALIBRATION + ':evidence/hw-region-2/CALIBRATION.md') == (HERE / 'CALIBRATION.md').read_bytes(),
            'first calibration changed')
    frozen = git('rev-parse', FROZEN_SOURCES + '^{commit}').decode().strip()
    for name in ('PROTOCOL.md', 'writer.py', 'equivalence.c', 'input-preflight.json'):
        require(git('show', frozen + ':evidence/hw-region-2/' + name) == (HERE / name).read_bytes(),
                'frozen admission source changed: ' + name)
    return dict(calibration_commit=CALIBRATION, frozen_sources_commit=frozen, lib2bit_commit=PIN,
                source_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in paths})


def source_record():
    preflight = load(HERE / 'input-preflight.json')
    require(preflight['schema'] == 'hw-region-2-input-preflight-v1' and preflight['no_clocks'] is True,
            'wrong saved input preflight')
    records = [r for r in preflight['records'] if r['corpus'] == 'chr1']
    require(len(records) == 1, 'exactly one chr1 preflight record required')
    source = records[0]
    require(source['source_bytes'] == 253935557 and source['source_sha256'] ==
            '04ee6db2e94ccc4daddc168453189d8c17a01454ba67ac0443a73a0401408ee0'
            and source['first_lowercase_n'] == 121757468 and source['alphabet']['n'] == 181,
            'chr1 source/preflight changed')
    verify(dict(path=source['source_path'], bytes=source['source_bytes'], sha256=source['source_sha256']))
    require(sha(source['source_path'], 'md5') == '9465e0f0df6e2c6eb39729c39cee5465', 'chr1 FASTA MD5 changed')
    return source


def build():
    repo = STATE / 'deps/lib2bit'
    if not repo.exists():
        command('lib2bit-clone', ['git', 'clone', '--no-checkout', URL, repo])
        command('lib2bit-checkout', ['git', '-C', repo, 'checkout', '--detach', PIN])
    require(not repo.is_symlink() and repo.resolve().is_relative_to(STATE.resolve()), 'dependency escaped owned state')
    require(git('rev-parse', 'HEAD', repo=repo).decode().strip() == PIN
            and git('remote', 'get-url', 'origin', repo=repo).decode().strip() == URL
            and not git('status', '--porcelain', '--untracked-files=no', repo=repo).strip(), 'dependency pin/source differs')
    files = [repo / name for name in git('ls-files', '-z', repo=repo).decode().split('\0') if name]
    license_path = repo / 'LICENSE'
    require('MIT License' in license_path.read_text(), 'expected MIT license missing')
    BUILD.mkdir(parents=True, exist_ok=True)
    command('compiler-version', ['gcc', '--version'])
    command('archiver-version', ['ar', '--version'])
    command('lib2bit-compile', ['gcc', '-O3', '-c', repo / '2bit.c', '-o', BUILD / '2bit.o'], outputs=(BUILD / '2bit.o',))
    command('lib2bit-static', ['ar', 'rcs', BUILD / 'lib2bit.a', BUILD / '2bit.o'], outputs=(BUILD / 'lib2bit.a',))
    command('equivalence-compile', ['gcc', '-O3', '-std=c11', '-Wall', '-Wextra', '-Werror', '-I' + str(repo),
            HERE / 'equivalence.c', BUILD / 'lib2bit.a', '-o', BUILD / 'equivalence'], outputs=(BUILD / 'equivalence',))
    require(not git('status', '--porcelain', '--untracked-files=no', repo=repo).strip(), 'build modified dependency source')
    return dict(url=URL, commit=PIN, source_clean=True, license=artifact(license_path), header=artifact(repo / '2bit.h'),
                source_files=[artifact(p) for p in files], object=artifact(BUILD / '2bit.o'),
                static_library=artifact(BUILD / 'lib2bit.a'), executable=artifact(BUILD / 'equivalence'))


def writer_module():
    spec = importlib.util.spec_from_file_location('hw_region_2_writer', HERE / 'writer.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def native(label, fasta, metadata, start, length, expected_literal=None):
    folder = STATE / 'returned' / label
    expected, actual = folder / 'expected.seq', folder / 'actual.seq'
    folder.mkdir(parents=True, exist_ok=True)
    record, stdout = command(label, [BUILD / 'equivalence', fasta, metadata['fai']['path'], metadata['archive']['path'],
                            metadata['fai']['geometry']['name'], start, length, expected, actual],
                            allowed=(0, 2), outputs=(expected, actual))
    value = json.loads(stdout)
    require(value['schema'] == 'hw-region-2-equivalence-v1' and value['no_clocks'] is True
            and value['storeMasked'] == 1 and value['start0'] == start and value['length'] == length,
            'native witness schema/workload differs')
    left, right = expected.read_bytes(), actual.read_bytes()
    require(len(left) == length and len(right) == length, 'native witness returned wrong lengths')
    differences = [i for i, pair in enumerate(zip(left, right)) if pair[0] != pair[1]]
    require(value['mismatches'] == len(differences)
            and value['status'] == ('KILL' if differences else 'PASS')
            and record['returncode'] == (2 if differences else 0), 'native witness and captured bytes disagree')
    if differences:
        first = differences[0]
        require((value['first_difference0'], value['first_difference1'], value['expected_byte'], value['actual_byte']) ==
                (start + first, start + first + 1, left[first], right[first]), 'first differing coordinate disagrees')
    outputs = {}
    for name, path in (('expected', expected), ('actual', actual)):
        public = HERE / 'returned' / (label + '-' + name + '.seq')
        immutable(public, path.read_bytes()); outputs[name] = artifact(public)
    if expected_literal is not None:
        require(left == expected_literal and right == expected_literal, 'positive native fixture failed')
    return dict(result=value, returncode=record['returncode'], outputs=outputs,
                command=dict(path='commands/' + label + '/command.json', sha256=sha(HERE / 'commands' / label / 'command.json')))


def inventory():
    paths = set()
    for folder in (COMMANDS, BUILD, STATE / 'fixture', STATE / 'chr1', STATE / 'returned',
                   HERE / 'commands', HERE / 'returned', HERE / 'writer-metadata'):
        if folder.exists():
            paths.update(p for p in folder.rglob('*') if p.is_file())
    return [artifact(path) for path in sorted(paths)]


def main():
    require(sys.platform == 'linux' and platform.node() == 'ace-core', 'owned ace-core Linux executor required')
    require(ROOT == Path('/home/ubuntu/hw-apex-bench-hw-region-2'), 'fresh owned HW-REGION-2 executor required')
    require(not os.environ.get('OVH_BENCH_LOCK_HELD'), 'untimed admission must run outside benchmark lock')
    os.sched_setaffinity(0, {15})
    require(os.sched_getaffinity(0) == {15}, 'correctness/build CPU15 required')
    state_identity, source = identity(), source_record()
    if PUBLIC.exists():
        saved = load(PUBLIC)
        require(saved['identity'] == state_identity and saved['source'] == source, 'completed admission identity changed')
        for record in saved['artifacts']:
            verify(record)
        for record in saved.get('dependency', {}).get('source_files', []):
            verify(record)
        print('ADMISSION_REPLAY', saved['status'], 'native calls: 0')
        return 1 if saved['status'] == 'ERROR' else 0
    require(not STATE.is_symlink(), 'owned admission state must not be a symlink')
    STATE.mkdir(parents=True, exist_ok=True)
    result = dict(schema='hw-region-2-admission-v1', status='ERROR', identity=state_identity, source=source,
                  no_clocks=True, measurements_of_time=False, performance_native_calls=0,
                  host=dict(hostname=platform.node(), kernel=platform.release(), cpu_affinity=[15]),
                  forecasts={name: 'NOT TESTED: untimed admission only' for name in ('P1', 'P2', 'P3')})
    try:
        result['dependency'] = build()
        writer = writer_module()
        fasta = STATE / 'fixture/source.fa'
        immutable(fasta, b'>fixture\nTCAGtcagNNnnACTG\n')
        fixture = writer.write_fasta(fasta, STATE / 'fixture')
        result['positive_controls'] = [native('fixture-acgt', fasta, fixture, 0, 8, b'TCAGtcag')]
        result['positive_controls'].append(native('fixture-N', fasta, fixture, 8, 2, b'NN'))
        command('writer-chr1', [sys.executable, HERE / 'writer.py', '--fasta', source['source_path'],
                '--outputdir', STATE / 'chr1', '--expected-source-sha', source['source_sha256'],
                '--expected-sequence-sha', source['sequence_sha256']],
                outputs=tuple(STATE / 'chr1' / name for name in ('seq.bin', 'source.fai', 'sequence.2bit', 'metadata.json')))
        metadata = load(STATE / 'chr1/metadata.json')
        require(metadata['sequence']['first_lowercase_n'] == source['first_lowercase_n']
                and metadata['sequence']['lowercase_n_count'] == 181, 'writer/preflight lowercase-n identity differs')
        for name, item in (('fixture', fixture), ('chr1', metadata)):
            target = HERE / 'writer-metadata' / (name + '.json.gz')
            immutable(target, gzip.compress(packed(item), mtime=0))
        start = source['first_lowercase_n'] - 8192
        require(0 <= start and start + 16384 < source['sequence_bytes'], 'nonterminal witness outside source')
        witness = native('chr1-first-lowercase-n', source['source_path'], metadata, start, 16384)
        # No native call exists after this point, for either result.
        with Path(metadata['sequence']['path']).open('rb') as stream:
            stream.seek(start)
            require(Path(witness['outputs']['expected']['path']).read_bytes() == stream.read(16384),
                    'independent FASTA witness differs from structurally checked sequence')
        result.update(status=witness['result']['status'], witness=witness, correctness_native_calls=3,
                      writer_metadata=artifact(HERE / 'writer-metadata/chr1.json.gz'))
        if result['status'] == 'KILL':
            result['forecasts'] = {name: 'NOT TESTED: Kill' for name in ('P1', 'P2', 'P3')}
            result['stop_reason'] = 'case-preserving sequence differs; no coordinate trace, other codecs, or timers admitted'
        else:
            result['stop_reason'] = 'this untimed witness passed; complete main protocol still required before any timer'
    except Exception as exc:
        result['error'] = str(exc)
    result['artifacts'] = inventory()
    immutable(PUBLIC, packed(result))
    print('ADMISSION', result['status'], sha(PUBLIC))
    return 1 if result['status'] == 'ERROR' else 0


if __name__ == '__main__':
    sys.exit(main())
