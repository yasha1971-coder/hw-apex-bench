"""Run the unchanged HW-GIFT-1 shell/C worker in an isolated local Git origin.

Each invocation accepts at most one C checkpoint. No GitHub remote is configured
in the scratch runner; the parent HW-GIFT-1b checkout owns external delivery.
"""
import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = ROOT / '.work/hw-gift-1b'
RUNNER = STATE / 'c-runner'
ORIGIN = STATE / 'c-origin.git'
CSTATE = STATE / 'c-state'
OUTPUT = HERE / 'c-baseline'
SOURCE = '85603dc8f52f20ae5fa09c50820bc30000be726f'
AMENDMENT = '0bd4ab29794f610884e66fdb3ca6c6c93495a4e4'
OVH_POLICY = '3e7201a0933030de8d3011eb658270e577e6eced'
LOAD_AMENDMENT = 'f8a2fb2c82bce9eacd841eafcf584a4c81ffc37c'
THRESHOLD_AMENDMENT = 'c8de6772e001fd52aebd73731cdd564c5f9db332'
RETENTION_SNAPSHOT = '8022d9626b2b63b00b8891ccdc69996d071bb8bd'
RETENTION_SNAPSHOT_PATH = 'evidence/hw-gift-1b/blocked/c-enwik8-L3/BLOCKED.json'
RETENTION_SNAPSHOT_SHA256 = 'cadde5c9986064bca65f248cabeec62c7aacccd904c22b25afdafe68b43f91d0'
OLD_HELPER = 'df561159c762fad79d4ecc6cdf4f94934e7197b8de098c865acaa48010efd711'
HISTORY_PREFIX = 'pre-threshold/c8de6772'
RESET_KEY = dict(g=16777216, n=65536, rep=0)
LEGACY_MANIFEST_KEYS = ('runner_source_commit', 'amendment_commit', 'ovh_policy_commit',
    'load_amendment_commit', 'protocol_sha256', 'source_sha256', 'original_chunks_sha256',
    'patched_chunks_sha256', 'host_gate_patch_sha256', 'orchestration_sha256',
    'load_guard_sha256', 'ovh_bench_sha256', 'attempt_artifact_sha256')
CHUNKS = ('enwik8-L3', 'enwik8-L19', 'silesia-L3', 'silesia-L19')
GS = (65536, 262144, 1048576, 4194304, 16777216, 67108864)
FILES = [f'samples-{g}.jsonl.gz' for g in GS] + ['archives.json', 'controls.json', 'run.json', 'SHA256SUMS']
SOURCES = tuple('evidence/hw-gift-1/' + name for name in
                ('CALIBRATION.md', 'reproduce.sh', 'chunks.py', 'sweep.py', 'pair.c', 'report.py')) + (
    'codecs/native/zstd_seekable.c', 'harness/resident_context.h')
STOP_AFTER_TARGET = 75
REJECTED_LOAD = 76
BLOCKED_REPEAT = 78
PUBLIC_FILES = FILES + ['acecore.json', 'attempts.tar.gz', 'attempts.json']


def check(ok, why):
    if not ok:
        raise ValueError(why)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.writing')
    with temporary.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    if hasattr(os, 'O_DIRECTORY'):
        fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def guard():
    spec = importlib.util.spec_from_file_location('_gift1b_load_guard', HERE / 'load_guard.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def ovh():
    spec = importlib.util.spec_from_file_location('_gift1b_ovh_bench', HERE / 'ovh_bench.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def artifacts():
    spec = importlib.util.spec_from_file_location('_gift1b_attempt_artifact', HERE / 'attempt_artifact.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def trusted_retention_snapshot():
    """The exception is tied to one immutable published cohort, never a filename."""
    base = RETENTION_SNAPSHOT_PATH.rsplit('/', 1)[0]
    raw = {name: git(ROOT, 'show', f'{RETENTION_SNAPSHOT}:{base}/{name}')
           for name in ('BLOCKED.json', 'attempts.json', 'attempts.tar.gz')}
    check(digest(raw['BLOCKED.json']) == RETENTION_SNAPSHOT_SHA256, 'approved retention snapshot changed')
    blocked, files = json.loads(raw['BLOCKED.json']), json.loads(raw['attempts.json'])
    check(blocked['chunk'] == 'enwik8-L3' and blocked['reader'] == 'c'
          and blocked['status'] == 'BLOCKED: load', 'wrong approved retention cohort')
    check(len(blocked['benchmark_runs']) == 45 and blocked['ovh_bench_sha256'] == OLD_HELPER,
          'approved retention is not the specified 45 CLEAN repeats')
    check({k: blocked['blocked_repeat'][k] for k in RESET_KEY} == RESET_KEY
          and len(blocked['blocked_repeat']['attempts']) == 3
          and all(a['status'] == 'LOADED' for a in blocked['blocked_repeat']['attempts']),
          'approved reset is not the specified three LOADED attempts')
    check(digest(raw['attempts.json']) == blocked['attempts_manifest_sha256']
          and digest(raw['attempts.tar.gz']) == files['archive_sha256'], 'approved retention artifact changed')
    return blocked, files, raw


def retention(chunk):
    if chunk != 'enwik8-L3':
        return None
    path = STATE / 'c-approved-retention.json'
    if not path.exists():
        return None
    marker = json.loads(path.read_bytes())
    check(marker['status'] == 'COMPLETE', 'threshold migration is incomplete')
    record = marker['approved_retention']
    check(record['threshold_amendment_commit'] == THRESHOLD_AMENDMENT
          and record['snapshot_commit'] == RETENTION_SNAPSHOT
          and record['snapshot_sha256'] == RETENTION_SNAPSHOT_SHA256, 'unapproved C retention marker')
    return record


def preserve(path, backup, expected):
    if backup.exists():
        check(sha(backup) == expected, 'preserved pre-threshold bytes changed')
    else:
        check(path.exists() and sha(path) == expected, 'pre-threshold source changed before preservation')
        write(backup, path.read_bytes())


def verify_retained_files(directory, proof):
    history = directory / HISTORY_PREFIX
    for item in proof['files']:
        name = item['path']
        path = directory / name
        if name.startswith('ovh-repeats/16777216-65536-0/'):
            path = (history / name) if (history / 'ovh-repeats/16777216-65536-0').exists() else path
        elif name == 'FAILED' and (history / 'provenance/FAILED').exists():
            path = history / 'provenance/FAILED'
        check(path.exists() and not path.is_symlink() and path.stat().st_size == item['bytes']
              and sha(path) == item['sha256'], 'pre-threshold bytes changed during migration: ' + name)


def migrate_threshold(new_record):
    """Retain exactly the authorized 45 rows and reset exactly one budget once."""
    check(new_record.get('threshold_amendment_commit') == THRESHOLD_AMENDMENT
          and new_record.get('load1_threshold') == '2.0'
          and new_record.get('runner_source_commit') == SOURCE,
          'threshold migration target is not the authorized policy')
    chunk = 'enwik8-L3'
    source, proof, raw = trusted_retention_snapshot()
    directory = CSTATE / chunk
    history = directory / HISTORY_PREFIX
    marker_path = STATE / 'c-approved-retention.json'
    old_manifest = STATE / 'c-runner-manifest.json'
    pending_path = STATE / 'c-pending' / f'{chunk}.json'
    old_blocked_dir = directory / 'ovh-repeats/16777216-65536-0'
    historical_dir = history / 'ovh-repeats/16777216-65536-0'
    expected_old = {k: source[k] for k in LEGACY_MANIFEST_KEYS}
    public = HERE / 'blocked/c-enwik8-L3'
    check(all((public / name).read_bytes() == value for name, value in raw.items()), 'historical public blocked evidence changed')
    if marker_path.exists():
        marker = json.loads(marker_path.read_bytes())
        check(marker['new_manifest_sha256'] == digest(packed(new_record)), 'threshold migration target changed')
        if marker['status'] == 'COMPLETE':
            check(old_manifest.read_bytes() == packed(new_record), 'completed threshold manifest changed')
            verify_retained_files(directory, proof)
            return marker['approved_retention']
        check(marker['status'] == 'PREPARED', 'unknown threshold migration phase')
    else:
        check(json.loads(old_manifest.read_bytes()) == expected_old, 'only the known published C manifest may migrate')
        records = benchmark_runs(chunk, CSTATE)
        check(accepted_runs(records) == source['benchmark_runs'] and len(records) == 46,
              'C retention state is not exactly 45 approved CLEAN plus one blocked repeat')
        reset = [r for r in records if {k: r[k] for k in RESET_KEY} == RESET_KEY]
        check(len(reset) == 1 and reset[0] == source['blocked_repeat'], 'C reset state differs from immutable snapshot')
        check(pending_path.exists() and (directory / 'FAILED').exists(), 'published blocked C state is incomplete')
        pending = json.loads(pending_path.read_bytes())
        check(all(pending.get(k) == v for k, v in expected_old.items())
              and pending.get('load_start') == source['load_start']
              and pending.get('load_resume_starts') == source['load_resume_starts']
              and pending.get('started_at_utc') == source['started_at_utc'], 'retained C pending provenance changed')
        old_files = {f['path']: f for f in proof['files']}
        actual_files = {str(p.relative_to(directory)).replace('\\', '/') for p in directory.rglob('*') if p.is_file()}
        check(actual_files == set(old_files), 'unapproved files or missing files in retained C state')
        for name, item in old_files.items():
            path = directory / name
            check(not path.is_symlink() and path.stat().st_size == item['bytes'] and sha(path) == item['sha256'],
                  'retained C state bytes changed: ' + name)
        receipts = sorted(a['receipt_path'] for row in source['benchmark_runs'] for a in row['attempts'])
        approval = dict(schema='hw-gift-1b-approved-retention-v1', threshold_amendment_commit=THRESHOLD_AMENDMENT,
                        snapshot_commit=RETENTION_SNAPSHOT, snapshot_path=RETENTION_SNAPSHOT_PATH,
                        snapshot_sha256=digest(raw['BLOCKED.json']), snapshot_attempts_sha256=digest(raw['attempts.tar.gz']),
                        retained_count=45, retained_runs_sha256=digest(packed(source['benchmark_runs'])),
                        retained_receipt_paths=receipts, pre_threshold_blocked_repeat=source['blocked_repeat'],
                        old_helper_sha256=OLD_HELPER, new_helper_sha256=new_record['ovh_bench_sha256'],
                        reset_key=RESET_KEY, reset_once=True, history_prefix=HISTORY_PREFIX)
        marker = dict(status='PREPARED', approved_retention=approval, new_manifest_sha256=digest(packed(new_record)),
                      old_manifest_sha256=sha(old_manifest), old_pending_sha256=sha(pending_path),
                      old_failed_sha256=sha(directory / 'FAILED'))
        write(marker_path, packed(marker))
    # Every original file must still match the frozen archive, even when a
    # previous migration invocation was interrupted between atomic renames.
    verify_retained_files(directory, proof)
    provenance = history / 'provenance'
    preserve(old_manifest, provenance / 'c-runner-manifest.json', marker['old_manifest_sha256'])
    preserve(pending_path, provenance / 'pending.json', marker['old_pending_sha256'])
    preserve(directory / 'FAILED', provenance / 'FAILED', marker['old_failed_sha256'])
    for name, value in raw.items():
        path = provenance / name
        if path.exists():
            check(path.read_bytes() == value, 'retention proof copy changed')
        else:
            write(path, value)
    if not historical_dir.exists():
        check(old_blocked_dir.is_dir(), 'approved C reset directory is missing')
        historical_dir.parent.mkdir(parents=True, exist_ok=True)
        old_blocked_dir.replace(historical_dir)
    else:
        check(not old_blocked_dir.exists() or not any(old_blocked_dir.iterdir()), 'C budget reset already has new activity')
    old_blocked_dir.mkdir(exist_ok=True)
    if (directory / 'FAILED').exists():
        check(sha(directory / 'FAILED') == marker['old_failed_sha256'], 'FAILED marker changed during migration')
        # The immutable backup is already durable; retain another original-name
        # copy rather than unlinking any measurement data.
        (directory / 'FAILED').replace(provenance / 'FAILED.original')
    pending = json.loads((provenance / 'pending.json').read_bytes())
    pending.update(new_record, approved_retention=marker['approved_retention'])
    write(pending_path, packed(pending))
    write(old_manifest, packed(new_record))
    write(provenance / 'approved-retention.json', packed(marker['approved_retention']))
    marker['status'] = 'COMPLETE'
    write(marker_path, packed(marker))
    return marker['approved_retention']


def patch_chunks(original):
    """Only host admission and CLI boundary orchestration change; worker stays exact."""
    text = original.decode('utf-8')
    before = "'AMD EPYC 9V74' in model and 'Debian GNU/Linux 13' in result['os']"
    after = "'AMD EPYC 4344P' in model and 'Ubuntu' in result['os'] and platform.node() == 'ace-core'"
    check(text.count(before) == 1, 'original host gate changed')
    text = text.replace(before, after)
    entry = "if __name__=='__main__':\n    main()\n"
    replacement = """if __name__=='__main__':
    import importlib.util as _gift_import
    _gift_spec = _gift_import.spec_from_file_location('_gift1b_boundary', os.environ['GIFT1B_BOUNDARY_MODULE'])
    _gift_module = _gift_import.module_from_spec(_gift_spec)
    _gift_spec.loader.exec_module(_gift_module)
    sys.executable = os.environ['GIFT1B_PYTHON_SHIM']
    _gift_module.boundary(main, HERE, Path(os.environ['GIFT_STATE']), sys.argv[1:])
"""
    check(text.count(entry) == 1, 'original entry point changed')
    return text.replace(entry, replacement).encode()


def manifest():
    check(sys.platform == 'linux', 'Linux executor required')
    check(platform.node() == 'ace-core', 'ace-core executor required')
    check(git(ROOT, 'branch', '--show-current').decode().strip() == 'hw-gift-1b', 'wrong parent branch')
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', THRESHOLD_AMENDMENT, 'HEAD'], check=True)
    actual = (HERE / 'CALIBRATION.md').read_bytes()
    check(actual == git(ROOT, 'show', f'{THRESHOLD_AMENDMENT}:evidence/hw-gift-1b/CALIBRATION.md'), 'execution policy changed')
    tracked = ['evidence/hw-gift-1b/' + n for n in ('CALIBRATION.md', 'c_baseline.py', 'load_guard.py', 'ovh_bench.py', 'attempt_artifact.py')]
    check(not git(ROOT, 'status', '--porcelain', '--', *tracked).strip(), 'uncommitted C orchestration')
    originals = {name: git(ROOT, 'show', f'{SOURCE}:{name}') for name in SOURCES}
    patched = patch_chunks(originals['evidence/hw-gift-1/chunks.py'])
    patch = ''.join(difflib.unified_diff(
        originals['evidence/hw-gift-1/chunks.py'].decode().splitlines(keepends=True),
        patched.decode().splitlines(keepends=True),
        fromfile='original/chunks.py', tofile='ace-core/chunks.py', n=0)).encode()
    record = dict(runner_source_commit=SOURCE, amendment_commit=AMENDMENT, ovh_policy_commit=OVH_POLICY,
                  load_amendment_commit=LOAD_AMENDMENT,
                  threshold_amendment_commit=THRESHOLD_AMENDMENT, load1_threshold='2.0',
                  protocol_sha256=digest(actual), source_sha256={k: digest(v) for k, v in originals.items()},
                  original_chunks_sha256=digest(originals['evidence/hw-gift-1/chunks.py']),
                  patched_chunks_sha256=digest(patched), host_gate_patch_sha256=digest(patch),
                  orchestration_sha256=sha(__file__), load_guard_sha256=sha(HERE / 'load_guard.py'),
                  ovh_bench_sha256=sha(HERE / 'ovh_bench.py'),
                  attempt_artifact_sha256=sha(HERE / 'attempt_artifact.py'))
    return record, originals, patched, patch


def prepare():
    record, originals, patched, patch = manifest()
    saved = STATE / 'c-runner-manifest.json'
    if RUNNER.exists() or ORIGIN.exists() or saved.exists():
        check(RUNNER.is_dir() and ORIGIN.is_dir() and saved.exists(), 'partial C runner initialization; inspect it')
        marker = STATE / 'c-approved-retention.json'
        if saved.read_bytes() != packed(record) or (marker.exists() and json.loads(marker.read_bytes())['status'] != 'COMPLETE'):
            migrate_threshold(record)
        check(saved.read_bytes() == packed(record), 'C runner provenance changed')
        check(retention('enwik8-L3'), 'the approved 45 CLEAN repeats must be restored before production C execution')
        _, proof, raw = trusted_retention_snapshot()
        verify_retained_files(CSTATE / 'enwik8-L3', proof)
        public = HERE / 'blocked/c-enwik8-L3'
        check(all((public / name).read_bytes() == data for name, data in raw.items()), 'historical public blocked evidence changed')
        check(Path(git(RUNNER, 'remote', 'get-url', 'origin').decode().strip()).resolve() == ORIGIN.resolve(), 'C origin must remain local')
        check(Path(git(RUNNER, 'remote', 'get-url', '--push', 'origin').decode().strip()).resolve() == ORIGIN.resolve(), 'C push origin must remain local')
        for name, data in originals.items():
            expected = patched if name.endswith('/chunks.py') else data
            check((RUNNER / name).read_bytes() == expected, 'C source changed: ' + name)
        OUTPUT.mkdir(exist_ok=True)
        patch_path = OUTPUT / 'host-gate.patch'
        if patch_path.exists():
            check(patch_path.read_bytes() == patch, 'C host-gate patch changed')
        else:
            write(patch_path, patch)
        return record
    check(not (HERE / 'blocked/c-enwik8-L3/BLOCKED.json').exists(),
          'restore the approved 45-repeat C state before initializing a fresh runner')
    STATE.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'init', '--bare', str(ORIGIN)], check=True)
    subprocess.run(['git', 'init', '--initial-branch=hw-gift-1', str(RUNNER)], check=True)
    for name, data in originals.items():
        write(RUNNER / name, patched if name.endswith('/chunks.py') else data)
    for key, value in (('user.name', 'HW-GIFT-1b matched baseline'), ('user.email', 'benchmark@localhost'),
                       ('core.hooksPath', str(RUNNER / '.git/empty-hooks'))):
        git(RUNNER, 'config', key, value)
    git(RUNNER, 'add', '--', *SOURCES)
    git(RUNNER, 'commit', '-m', 'Seed isolated matched C baseline; original timing code unchanged')
    git(RUNNER, 'remote', 'add', 'origin', str(ORIGIN))
    git(RUNNER, 'push', '-u', 'origin', 'HEAD:refs/heads/hw-gift-1')
    write(saved, packed(record))
    OUTPUT.mkdir(exist_ok=True)
    write(OUTPUT / 'host-gate.patch', patch)
    return record


def snapshots_match(start, end):
    keys = ('hostname', 'cpu', 'kernel', 'governor', 'pinned_core')
    return all(start.get(k) == end.get(k) for k in keys)


def quarantine(chunk, folder, state, receipt):
    target = STATE / 'c-rejected' / chunk / uuid.uuid4().hex
    target.mkdir(parents=True)
    for name, path in (('checkpoint', folder), ('state', state)):
        if path.exists():
            check(path.resolve().is_relative_to(STATE.resolve()), 'quarantine target escaped task state')
            path.replace(target / name)
    pending = STATE / 'c-pending' / f'{chunk}.json'
    if pending.exists():
        pending.replace(target / 'pending.json')
    write(target / 'acecore.json', packed(receipt))
    return target


def measurement_args(args):
    """Only the original timed sweep worker gets the shared OVH lock."""
    for index, argument in enumerate(args):
        if argument.startswith('-'):
            continue
        path = Path(argument)
        if path.name != 'sweep.py':
            return None
        check(path.resolve() == (RUNNER / 'evidence/hw-gift-1/sweep.py').resolve(), 'unexpected C sweep path')
        tail = args[index + 1:]
        check(len(tail) == 4, 'unexpected C sweep arguments')
        src, g, n, rep = tail
        g, n, rep = int(g), int(n), int(rep)
        check(g in GS and n in (4096, 65536) and rep in range(-1, 5), 'C sweep outside preregistered grid')
        if rep == -1:
            return None
        return dict(src=src, g=g, n=n, rep=rep)
    return None


def python_shim(args, python):
    """Retake only a LOADED logical repeat, at most three locked attempts."""
    identity = measurement_args(args)
    if identity is None:
        return subprocess.run([str(python), *args]).returncode
    chunk = os.environ['GIFT1B_TARGET']
    check(chunk in CHUNKS, 'unknown C target chunk')
    expected_source = 'enwik8' if chunk.startswith('enwik8-') else 'silesia.tar'
    check(identity['src'] == expected_source, 'C repeat corpus differs from target')
    name = f"{identity['g']}-{identity['n']}-{identity['rep']}"
    directory = CSTATE / chunk / 'ovh-repeats' / name
    metadata_path = directory / 'metadata.json'
    base = {k: identity[k] for k in ('g', 'n', 'rep')}
    base.update(ovh_policy_commit=OVH_POLICY, load_amendment_commit=LOAD_AMENDMENT,
                threshold_amendment_commit=THRESHOLD_AMENDMENT, load1_threshold='2.0',
                ovh_bench_sha256=sha(HERE / 'ovh_bench.py'))
    attempts = []
    if metadata_path.exists():
        saved = json.loads(metadata_path.read_bytes())
        approval = retention(chunk)
        if approval and saved.get('status') == 'CLEAN':
            source, proof, _ = trusted_retention_snapshot()
            old = [r for r in source['benchmark_runs'] if all(r[k] == identity[k] for k in ('g', 'n', 'rep'))]
            if old:
                check(len(old) == 1 and accepted_runs([saved]) == old, 'retained CLEAN C summary changed')
                relative = str(metadata_path.relative_to(CSTATE / chunk)).replace('\\', '/')
                item = next(item for item in proof['files'] if item['path'] == relative)
                check(sha(metadata_path) == item['sha256'], 'retained CLEAN C metadata bytes changed')
                for attempt in saved['attempts']:
                    verify_attempt(attempt, CSTATE / chunk)
                replay_attempt(saved['attempts'][-1], CSTATE / chunk)
                return 0
        check(all(saved.get(k) == v for k, v in base.items()), 'saved C repeat identity or policy changed')
        attempts = saved['attempts']
        check(len(attempts) <= 3 and [a['attempt'] for a in attempts] == list(range(1, len(attempts) + 1)), 'invalid C attempt sequence')
        for attempt in attempts:
            verify_attempt(attempt, CSTATE / chunk)
        if saved['status'] == 'CLEAN':
            replay_attempt(attempts[-1], CSTATE / chunk)
            return 0
        if saved['status'] == 'BLOCKED':
            check(len(attempts) == 3 and all(a['status'] == 'LOADED' for a in attempts), 'invalid BLOCKED C repeat')
            return BLOCKED_REPEAT
        if saved['status'] == 'ERROR':
            return saved['returncode'] or 1
        check(saved['status'] in ('RUNNING', 'RETRYING'), 'unknown logical C repeat state')
        check(all(a['status'] == 'LOADED' for a in attempts), 'retry after a non-LOADED C attempt')
    directory.mkdir(parents=True, exist_ok=True)
    summary = dict(base, status='RUNNING', returncode=None, receipt=None, row_sha256=None, attempts=attempts)
    write(metadata_path, packed(summary))
    # There is no delay or active polling between attempts. run_locked blocks
    # in the shared flock command and never bypasses an occupied lock.
    for number in range(len(attempts) + 1, 4):
        attempt_path = directory / f'attempt-{number:03d}.metadata.json'
        receipt_path = directory / f'attempt-{number:03d}.receipt.json'
        stdout_path = directory / f'attempt-{number:03d}.stdout'
        if attempt_path.exists():
            attempt = json.loads(attempt_path.read_bytes())
            check(attempt['attempt'] == number, 'C attempt number changed')
            verify_attempt(attempt, CSTATE / chunk)
            code = 0 if attempt['status'] == 'CLEAN' else (77 if attempt['status'] == 'LOADED' else attempt.get('returncode') or 1)
        else:
            check(receipt_path.exists() or not stdout_path.exists(), 'C stdout exists without its lock receipt; inspect before retry')
            # An existing completed helper receipt is replayed safely. Its
            # WAITING/ERROR state stops for inspection, never remeasures.
            code = ovh().run_locked([str(python), *args], receipt_path, stdout_path=stdout_path)
            receipt = json.loads(receipt_path.read_bytes())
            raw = stdout_path.read_bytes()
            status = receipt.get('status')
            check(status in ('CLEAN', 'LOADED', 'ERROR'), 'unfinished C attempt lock receipt')
            row_sha256 = None
            if raw and status in ('CLEAN', 'LOADED'):
                try:
                    row = dict(src=expected_source, level=int(chunk.rsplit('L', 1)[1]),
                               g=identity['g'], n=identity['n'], rep=identity['rep'], **json.loads(raw))
                    row_sha256 = digest(packed(row))
                except (ValueError, TypeError):
                    if status == 'CLEAN':
                        raise
            check(status != 'CLEAN' or (code == 0 and row_sha256 is not None), 'CLEAN C attempt has no valid result')
            if status == 'ERROR':
                code = receipt.get('returncode') or code or 1
            elif status == 'LOADED':
                check(code == 77, 'LOADED C receipt has unexpected exit code')
            attempt = dict(attempt=number, status=status, receipt=receipt, row_sha256=row_sha256,
                           returncode=code, receipt_path=str(receipt_path.relative_to(CSTATE / chunk)).replace('\\', '/'),
                           raw_stdout_path=str(stdout_path.relative_to(CSTATE / chunk)).replace('\\', '/'),
                           raw_stdout_sha256=digest(raw))
            write(attempt_path, packed(attempt))
        attempts.append(attempt)
        summary.update(attempts=attempts, receipt=attempt['receipt'], row_sha256=attempt['row_sha256'])
        if attempt['status'] == 'CLEAN':
            summary.update(status='CLEAN', returncode=0)
            write(metadata_path, packed(summary))
            replay_attempt(attempt, CSTATE / chunk)
            return 0
        if attempt['status'] == 'ERROR':
            summary.update(status='ERROR', returncode=code or 1)
            write(metadata_path, packed(summary))
            return summary['returncode']
        summary.update(status='BLOCKED' if number == 3 else 'RETRYING',
                       returncode=BLOCKED_REPEAT if number == 3 else 77)
        write(metadata_path, packed(summary))
    return BLOCKED_REPEAT


def verify_attempt(attempt, source):
    receipt_path, stdout_path = (source / attempt[key] for key in ('receipt_path', 'raw_stdout_path'))
    check(receipt_path.resolve().is_relative_to(source.resolve()) and stdout_path.resolve().is_relative_to(source.resolve()), 'C attempt path escaped state')
    check(json.loads(receipt_path.read_bytes()) == attempt['receipt'], 'saved C lock receipt changed')
    check(sha(stdout_path) == attempt['raw_stdout_sha256'], 'saved C repeat stdout changed')


def replay_attempt(attempt, source):
    check(attempt['status'] == 'CLEAN', 'only CLEAN C output may enter original checkpoint')
    verify_attempt(attempt, source)
    sys.stdout.buffer.write((source / attempt['raw_stdout_path']).read_bytes())
    sys.stdout.buffer.flush()


def benchmark_runs(chunk, cstate=CSTATE):
    directory = cstate / chunk / 'ovh-repeats'
    records = [json.loads(path.read_bytes()) for path in sorted(directory.glob('*/metadata.json'))]
    return sorted(records, key=lambda r: (r['g'], r['n'], r['rep']))


def accepted_runs(records):
    return [{k: r[k] for k in ('g', 'n', 'rep', 'receipt', 'row_sha256', 'attempts')}
            for r in records if r['status'] == 'CLEAN']


def repeat_counts(records, approval=None):
    retaken = {(r['g'], r['n'], r['rep']) for r in records if len(r['attempts']) > 1}
    if approval:
        reset = tuple(approval['reset_key'][k] for k in ('g', 'n', 'rep'))
        if any(tuple(r[k] for k in ('g', 'n', 'rep')) == reset and r['attempts'] for r in records):
            retaken.add(reset)
    result = dict(planned_repeats=60, started_repeats=sum(bool(r['attempts']) for r in records),
                  retaken_repeats=len(retaken),
                  loaded_attempts=sum(a['status'] == 'LOADED' for r in records for a in r['attempts']))
    if approval:
        result['historical_loaded_attempts'] = len(approval['pre_threshold_blocked_repeat']['attempts'])
    return result


def stop_blocked(chunk, cstate, receipt):
    records = benchmark_runs(chunk, cstate)
    blocked = [record for record in records if record['status'] == 'BLOCKED']
    if not blocked:
        return
    check(len(blocked) == 1, 'multiple BLOCKED C logical repeats')
    record = blocked[0]
    check(len(record['attempts']) == 3 and all(a['status'] == 'LOADED' for a in record['attempts']), 'C repeat blocked before three LOADED attempts')
    last = record['attempts'][-1]['receipt']
    receipt.update(status='BLOCKED: load', reader='c', chunk=chunk, load_accepted=False, reason='three LOADED attempts for one logical C repeat',
                   benchmark_runs=accepted_runs(records), blocked_repeat=record,
                   **repeat_counts(records, receipt.get('approved_retention')),
                   ps_top8=last.get('ps_top8', ''))
    receipt.setdefault('load_end', receipt.get('load_resume_starts', [])[-1]
                       if receipt.get('load_resume_starts') else receipt['load_start'])
    source_run = cstate / chunk / 'run.json'
    check(source_run.exists(), 'BLOCKED C checkpoint lacks original host receipt')
    original_host = json.loads(source_run.read_bytes())['host']
    start = receipt['load_start']
    receipt['host'] = dict(hostname=start['hostname'], cpu=start['cpu'], cpu_affinity=[0], pinned_core=0,
                          governor=start['governor'], kernel=start['kernel'], os=original_host['os'],
                          host_boot_sha256=original_host['host_boot_sha256'])
    target = HERE / 'blocked' / f'c-{chunk}-threshold-2.0'
    target.mkdir(parents=True, exist_ok=True)
    artifacts().pack_attempts(cstate / chunk, target)
    receipt['attempts_manifest_sha256'] = sha(target / 'attempts.json')
    write(target / 'BLOCKED.json', packed(receipt))
    print(f"BLOCKED C {chunk}: {receipt['started_repeats']}/60 logical repeats started; "
          f"{receipt['retaken_repeats']} retaken; {receipt['loaded_attempts']} LOADED attempts. "
          'Successful CLEAN repeats are retained; a fourth attempt is prohibited.', file=sys.stderr, flush=True)
    raise SystemExit(BLOCKED_REPEAT)


def boundary(original_main, here, cstate, args):
    """Called only by the copied metadata dispatcher, never by the timed worker."""
    if not args or args[0] != 'run':
        original_main()
        return
    chunk = args[1]
    check(chunk in CHUNKS, 'unknown C chunk')
    if chunk != os.environ['GIFT1B_TARGET']:
        raise SystemExit(STOP_AFTER_TARGET)
    module = guard()
    start = module.snapshot(cpu=0, interval=2.0)
    manifest_record = json.loads((STATE / 'c-runner-manifest.json').read_bytes())
    receipt = dict(manifest_record, load_start=start, load_resume_starts=[], load_accepted=False,
                   started_at_utc=datetime.now(timezone.utc).isoformat())
    approval = retention(chunk)
    if approval:
        receipt['approved_retention'] = approval
    pending = STATE / 'c-pending' / f'{chunk}.json'
    if pending.exists():
        receipt = json.loads(pending.read_bytes())
        check(all(receipt.get(k) == v for k, v in manifest_record.items()), 'resumed C provenance changed')
        if not snapshots_match(receipt['load_start'], start):
            receipt.update(load_end=start, rejection_reason='host/core/governor changed across resume')
            quarantine(chunk, here / chunk, cstate / chunk, receipt)
            raise SystemExit(REJECTED_LOAD)
        receipt.setdefault('load_resume_starts', []).append(start)
    write(pending, packed(receipt))
    stop_blocked(chunk, cstate, receipt)
    try:
        original_main()
    except (Exception, SystemExit):
        receipt['load_end'] = module.snapshot(cpu=0, interval=2.0)
        stop_blocked(chunk, cstate, receipt)
        raise
    end = module.snapshot(cpu=0, interval=2.0)
    receipt['load_end'] = end
    try:
        check(snapshots_match(receipt['load_start'], end), 'CPU/kernel/governor changed during C checkpoint')
    except ValueError as error:
        receipt['rejection_reason'] = str(error)
        quarantine(chunk, here / chunk, cstate / chunk, receipt)
        raise SystemExit(REJECTED_LOAD)
    run = json.loads((here / chunk / 'run.json').read_bytes())
    original_host = run['host']
    records = benchmark_runs(chunk, cstate)
    expected = {(g, n, rep) for g in GS for n in (4096, 65536) for rep in range(5)}
    check(len(records) == 60 and {(r['g'], r['n'], r['rep']) for r in records} == expected,
          'missing or duplicate C OVH-BENCH repeat receipts')
    check(all(r['status'] == 'CLEAN' and r['returncode'] == 0 for r in records), 'C checkpoint includes failed timed repeats')
    receipt['benchmark_runs'] = accepted_runs(records)
    receipt.update(repeat_counts(records, receipt.get('approved_retention')))
    receipt.update(load_accepted=True, host=dict(
        hostname=start['hostname'], cpu=start['cpu'], cpu_affinity=[0], pinned_core=0,
        governor=start['governor'], kernel=start['kernel'], os=original_host['os'],
        host_boot_sha256=original_host['host_boot_sha256']),
        original_sha256sums_sha256=sha(here / chunk / 'SHA256SUMS'))
    write(STATE / 'c-boundaries' / f'{chunk}.json', packed(receipt))
    pending.replace(STATE / 'c-boundaries' / f'{chunk}-accepted-admissions.json')


def export(chunk):
    folder = RUNNER / 'evidence/hw-gift-1' / chunk
    receipt_path = STATE / 'c-boundaries' / f'{chunk}.json'
    check(receipt_path.exists(), 'no accepted C load receipt')
    receipt = json.loads(receipt_path.read_bytes())
    check(receipt.get('load_accepted') is True, 'C checkpoint load was rejected')
    check(sha(folder / 'SHA256SUMS') == receipt['original_sha256sums_sha256'], 'C checksum receipt changed')
    # The unchanged script must have actually committed and pushed this chunk.
    for name in FILES:
        path = f'evidence/hw-gift-1/{chunk}/{name}'
        check(git(RUNNER, 'show', f'refs/remotes/origin/hw-gift-1:{path}') == (folder / name).read_bytes(), 'C checkpoint is not pushed to its local durable origin')
    target = OUTPUT / chunk
    if target.exists():
        check({p.name for p in target.iterdir()} == set(PUBLIC_FILES), 'unexpected exported C files')
        receipt['attempts_manifest_sha256'] = sha(target / 'attempts.json')
        check(all((target / f).read_bytes() == (folder / f).read_bytes() for f in FILES)
              and (target / 'acecore.json').read_bytes() == packed(receipt), 'exported C checkpoint changed')
        retained = json.loads((target / 'attempts.json').read_bytes())
        check(sha(target / 'attempts.tar.gz') == retained['archive_sha256'], 'exported C attempt archive changed')
        return
    temporary = STATE / f'c-export-{chunk}'
    check(not temporary.exists(), 'partial C export exists; inspect it')
    temporary.mkdir()
    for name in FILES:
        shutil.copyfile(folder / name, temporary / name)
    artifacts().pack_attempts(CSTATE / chunk, temporary)
    receipt['attempts_manifest_sha256'] = sha(temporary / 'attempts.json')
    write(temporary / 'acecore.json', packed(receipt))
    temporary.replace(target)


def _run(chunk, inputs, zstd, python):
    check(sys.platform == 'linux' and platform.node() == 'ace-core', 'ace-core Linux required')
    # reproduce.sh runs in the isolated checkout, so its PATH cannot be relative
    # to the controller checkout where the CLI arguments were supplied.
    inputs, zstd, python = (Path(p).resolve() for p in (inputs, zstd, python))
    check(0 in os.sched_getaffinity(0), 'original C worker requires CPU 0')
    record = prepare()
    if chunk == 'enwik8-L3':
        check(retention(chunk), 'threshold-2.0 enwik8-L3 must retain the approved 45 CLEAN repeats')
    historical = HERE / 'blocked' / f'c-{chunk}'
    if historical.exists():
        check(chunk == 'enwik8-L3' and retention(chunk), 'unapproved historical C blocked checkpoint')
        _, _, raw = trusted_retention_snapshot()
        check(all((historical / name).read_bytes() == value for name, value in raw.items()),
              'historical C blocked checkpoint changed')
    blocked = HERE / 'blocked' / f'c-{chunk}-threshold-2.0' / 'BLOCKED.json'
    if blocked.exists():
        print('BLOCKED C', chunk, 'already reached the three-attempt limit; no fourth attempt.', flush=True)
        return 2
    if (OUTPUT / chunk).exists():
        export(chunk)
        print('C_CHECKPOINT_VERIFIED_SKIP', chunk, flush=True)
        return
    for previous in CHUNKS[:CHUNKS.index(chunk)]:
        check((OUTPUT / previous).is_dir(), 'C chunks must be exported and pushed in order')
    check(git(zstd, 'rev-parse', 'HEAD').decode().strip() == 'f8745da6ff1ad1e7bab384bd1f9d742439278e99', 'wrong zstd source pin')
    check(not git(zstd, 'status', '--porcelain').strip(), 'zstd source tree is dirty')
    binary = zstd / 'programs/zstd'
    check(binary.is_file(), 'build pinned zstd CLI before running the unchanged shell')
    bin_dir = STATE / 'c-bin'
    bin_dir.mkdir(exist_ok=True)
    interpreter = bin_dir / 'python3'
    shim = (f'#!{python.resolve()}\n'
            'import importlib.util,sys\n'
            f'spec=importlib.util.spec_from_file_location("_gift1b_c_shim",{str(Path(__file__).resolve())!r})\n'
            'module=importlib.util.module_from_spec(spec)\n'
            'spec.loader.exec_module(module)\n'
            f'raise SystemExit(module.python_shim(sys.argv[1:],{str(python.resolve())!r}))\n').encode()
    if interpreter.is_symlink():
        interpreter.unlink()  # Own prior preparation used a symlink; never follow it for writing.
    if interpreter.exists():
        check(interpreter.read_bytes() == shim, 'C interpreter shim changed')
    else:
        write(interpreter, shim)
        interpreter.chmod(0o755)
    environment = os.environ.copy()
    environment.update(GIFT_INPUTS=str(inputs.resolve()), GIFT_ZSTD=str(zstd.resolve()),
                       GIFT_STATE=str(CSTATE), GIFT1B_TARGET=chunk, GIFT1B_BOUNDARY_MODULE=str(Path(__file__).resolve()))
    environment['GIFT1B_PYTHON_SHIM'] = str(interpreter.resolve())
    environment['PATH'] = os.pathsep.join((str(bin_dir), str(zstd / 'programs'), str(zstd), environment['PATH']))
    result = subprocess.run(['bash', str(RUNNER / 'evidence/hw-gift-1/reproduce.sh')], cwd=RUNNER, env=environment)
    if result.returncode == BLOCKED_REPEAT and blocked.exists():
        print('BLOCKED C', chunk, 'retained at', blocked, flush=True)
        return 2
    check(result.returncode in (0, STOP_AFTER_TARGET), f'C shell stopped with exit {result.returncode}; inspect logs/attempts')
    check((STATE / 'c-runner-manifest.json').read_bytes() == packed(record), 'C runner manifest changed')
    export(chunk)
    print('C_CHECKPOINT_READY_TO_PUBLISH', chunk, flush=True)
    return 0


def run(chunk, inputs, zstd, python):
    check(sys.platform == 'linux', 'Linux executor required')
    import fcntl
    STATE.mkdir(parents=True, exist_ok=True)
    # Shared with measure.py: builds and C/Python readers never overlap.
    with (STATE / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _run(chunk, inputs, zstd, python)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'files'))
    parser.add_argument('chunk', choices=CHUNKS)
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--zstd', type=Path)
    parser.add_argument('--python', type=Path, default=Path(sys.executable))
    args = parser.parse_args()
    if args.action == 'files':
        print('\n'.join(f'evidence/hw-gift-1b/c-baseline/{args.chunk}/{f}' for f in PUBLIC_FILES))
        print('evidence/hw-gift-1b/c-baseline/host-gate.patch')
        return
    check(args.inputs is not None and args.zstd is not None, '--inputs and --zstd required')
    return run(args.chunk, args.inputs, args.zstd, args.python)


if __name__ == '__main__':
    raise SystemExit(main())
