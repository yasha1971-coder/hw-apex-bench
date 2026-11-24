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
CHUNKS = ('enwik8-L3', 'enwik8-L19', 'silesia-L3', 'silesia-L19')
GS = (65536, 262144, 1048576, 4194304, 16777216, 67108864)
FILES = [f'samples-{g}.jsonl.gz' for g in GS] + ['archives.json', 'controls.json', 'run.json', 'SHA256SUMS']
SOURCES = tuple('evidence/hw-gift-1/' + name for name in
                ('CALIBRATION.md', 'reproduce.sh', 'chunks.py', 'sweep.py', 'pair.c', 'report.py')) + (
    'codecs/native/zstd_seekable.c', 'harness/resident_context.h')
STOP_AFTER_TARGET = 75
REJECTED_LOAD = 76


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
    _gift_module.boundary(main, HERE, Path(os.environ['GIFT_STATE']), sys.argv[1:])
"""
    check(text.count(entry) == 1, 'original entry point changed')
    return text.replace(entry, replacement).encode()


def manifest():
    check(sys.platform == 'linux', 'Linux executor required')
    check(platform.node() == 'ace-core', 'ace-core executor required')
    check(git(ROOT, 'branch', '--show-current').decode().strip() == 'hw-gift-1b', 'wrong parent branch')
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', AMENDMENT, 'HEAD'], check=True)
    actual = (HERE / 'CALIBRATION.md').read_bytes()
    check(actual == git(ROOT, 'show', f'{AMENDMENT}:evidence/hw-gift-1b/CALIBRATION.md'), 'host amendment changed')
    tracked = ['evidence/hw-gift-1b/' + n for n in ('CALIBRATION.md', 'c_baseline.py', 'load_guard.py')]
    check(not git(ROOT, 'status', '--porcelain', '--', *tracked).strip(), 'uncommitted C orchestration')
    originals = {name: git(ROOT, 'show', f'{SOURCE}:{name}') for name in SOURCES}
    patched = patch_chunks(originals['evidence/hw-gift-1/chunks.py'])
    patch = ''.join(difflib.unified_diff(
        originals['evidence/hw-gift-1/chunks.py'].decode().splitlines(keepends=True),
        patched.decode().splitlines(keepends=True),
        fromfile='original/chunks.py', tofile='ace-core/chunks.py', n=0)).encode()
    record = dict(runner_source_commit=SOURCE, amendment_commit=AMENDMENT,
                  protocol_sha256=digest(actual), source_sha256={k: digest(v) for k, v in originals.items()},
                  original_chunks_sha256=digest(originals['evidence/hw-gift-1/chunks.py']),
                  patched_chunks_sha256=digest(patched), host_gate_patch_sha256=digest(patch),
                  orchestration_sha256=sha(__file__), load_guard_sha256=sha(HERE / 'load_guard.py'))
    return record, originals, patched, patch


def prepare():
    record, originals, patched, patch = manifest()
    saved = STATE / 'c-runner-manifest.json'
    if RUNNER.exists() or ORIGIN.exists() or saved.exists():
        check(RUNNER.is_dir() and ORIGIN.is_dir() and saved.exists(), 'partial C runner initialization; inspect it')
        check(saved.read_bytes() == packed(record), 'C runner provenance changed')
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
    try:
        module.require_idle(start)
    except module.BusyHost:
        receipt['rejection_reason'] = 'foreign load at start'
        write(STATE / 'c-boundaries' / f'{chunk}-rejected-start-{uuid.uuid4().hex}.json', packed(receipt))
        pending = STATE / 'c-pending' / f'{chunk}.json'
        if pending.exists() or (here / chunk).exists() or (cstate / chunk).exists():
            if pending.exists():
                previous = json.loads(pending.read_bytes())
                previous.update(load_end=start, load_accepted=False, rejection_reason='foreign load at resume')
                receipt = previous
            quarantine(chunk, here / chunk, cstate / chunk, receipt)
        raise SystemExit(REJECTED_LOAD)
    pending = STATE / 'c-pending' / f'{chunk}.json'
    if pending.exists():
        receipt = json.loads(pending.read_bytes())
        check(all(receipt.get(k) == v for k, v in manifest_record.items()), 'resumed C provenance changed')
        module.require_idle(receipt['load_start'])
        if not snapshots_match(receipt['load_start'], start):
            receipt.update(load_end=start, rejection_reason='host/core/governor changed across resume')
            quarantine(chunk, here / chunk, cstate / chunk, receipt)
            raise SystemExit(REJECTED_LOAD)
        receipt.setdefault('load_resume_starts', []).append(start)
    write(pending, packed(receipt))
    original_main()
    end = module.snapshot(cpu=0, interval=2.0)
    receipt['load_end'] = end
    try:
        module.require_idle(end)
        check(snapshots_match(receipt['load_start'], end), 'CPU/kernel/governor changed during C checkpoint')
    except (module.BusyHost, ValueError) as error:
        receipt['rejection_reason'] = str(error)
        quarantine(chunk, here / chunk, cstate / chunk, receipt)
        raise SystemExit(REJECTED_LOAD)
    run = json.loads((here / chunk / 'run.json').read_bytes())
    original_host = run['host']
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
        check({p.name for p in target.iterdir()} == set(FILES + ['acecore.json']), 'unexpected exported C files')
        check(all((target / f).read_bytes() == (folder / f).read_bytes() for f in FILES)
              and (target / 'acecore.json').read_bytes() == packed(receipt), 'exported C checkpoint changed')
        return
    temporary = STATE / f'c-export-{chunk}'
    check(not temporary.exists(), 'partial C export exists; inspect it')
    temporary.mkdir()
    for name in FILES:
        shutil.copyfile(folder / name, temporary / name)
    write(temporary / 'acecore.json', packed(receipt))
    temporary.replace(target)


def _run(chunk, inputs, zstd, python):
    check(sys.platform == 'linux' and platform.node() == 'ace-core', 'ace-core Linux required')
    check(0 in os.sched_getaffinity(0), 'original C worker requires CPU 0')
    module = guard()
    module.require_idle(module.snapshot(cpu=0, interval=2.0))  # Also before the shell's build.
    record = prepare()
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
    if interpreter.exists():
        check(interpreter.resolve() == python.resolve(), 'C interpreter shim changed')
    else:
        interpreter.symlink_to(python.resolve())
    environment = os.environ.copy()
    environment.update(GIFT_INPUTS=str(inputs.resolve()), GIFT_ZSTD=str(zstd.resolve()),
                       GIFT_STATE=str(CSTATE), GIFT1B_TARGET=chunk, GIFT1B_BOUNDARY_MODULE=str(Path(__file__).resolve()))
    environment['PATH'] = os.pathsep.join((str(bin_dir), str(zstd / 'programs'), str(zstd), environment['PATH']))
    result = subprocess.run(['bash', str(RUNNER / 'evidence/hw-gift-1/reproduce.sh')], cwd=RUNNER, env=environment)
    check(result.returncode in (0, STOP_AFTER_TARGET), f'C shell stopped with exit {result.returncode}; inspect logs/attempts')
    check((STATE / 'c-runner-manifest.json').read_bytes() == packed(record), 'C runner manifest changed')
    export(chunk)
    print('C_CHECKPOINT_READY_TO_PUBLISH', chunk, flush=True)


def run(chunk, inputs, zstd, python):
    check(sys.platform == 'linux', 'Linux executor required')
    import fcntl
    STATE.mkdir(parents=True, exist_ok=True)
    # Shared with measure.py: builds and C/Python readers never overlap.
    with (STATE / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _run(chunk, inputs, zstd, python)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'files'))
    parser.add_argument('chunk', choices=CHUNKS)
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--zstd', type=Path)
    parser.add_argument('--python', type=Path, default=Path(sys.executable))
    args = parser.parse_args()
    if args.action == 'files':
        print('\n'.join(f'evidence/hw-gift-1b/c-baseline/{args.chunk}/{f}' for f in [*FILES, 'acecore.json']))
        print('evidence/hw-gift-1b/c-baseline/host-gate.patch')
        return
    check(args.inputs is not None and args.zstd is not None, '--inputs and --zstd required')
    run(args.chunk, args.inputs, args.zstd, args.python)


if __name__ == '__main__':
    main()
