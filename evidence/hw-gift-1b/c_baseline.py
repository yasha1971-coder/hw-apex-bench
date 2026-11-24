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


def ovh():
    spec = importlib.util.spec_from_file_location('_gift1b_ovh_bench', HERE / 'ovh_bench.py')
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
    sys.executable = os.environ['GIFT1B_PYTHON_SHIM']
    _gift_module.boundary(main, HERE, Path(os.environ['GIFT_STATE']), sys.argv[1:])
"""
    check(text.count(entry) == 1, 'original entry point changed')
    return text.replace(entry, replacement).encode()


def manifest():
    check(sys.platform == 'linux', 'Linux executor required')
    check(platform.node() == 'ace-core', 'ace-core executor required')
    check(git(ROOT, 'branch', '--show-current').decode().strip() == 'hw-gift-1b', 'wrong parent branch')
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', OVH_POLICY, 'HEAD'], check=True)
    actual = (HERE / 'CALIBRATION.md').read_bytes()
    check(actual == git(ROOT, 'show', f'{OVH_POLICY}:evidence/hw-gift-1b/CALIBRATION.md'), 'execution policy changed')
    tracked = ['evidence/hw-gift-1b/' + n for n in ('CALIBRATION.md', 'c_baseline.py', 'load_guard.py', 'ovh_bench.py')]
    check(not git(ROOT, 'status', '--porcelain', '--', *tracked).strip(), 'uncommitted C orchestration')
    originals = {name: git(ROOT, 'show', f'{SOURCE}:{name}') for name in SOURCES}
    patched = patch_chunks(originals['evidence/hw-gift-1/chunks.py'])
    patch = ''.join(difflib.unified_diff(
        originals['evidence/hw-gift-1/chunks.py'].decode().splitlines(keepends=True),
        patched.decode().splitlines(keepends=True),
        fromfile='original/chunks.py', tofile='ace-core/chunks.py', n=0)).encode()
    record = dict(runner_source_commit=SOURCE, amendment_commit=AMENDMENT, ovh_policy_commit=OVH_POLICY,
                  protocol_sha256=digest(actual), source_sha256={k: digest(v) for k, v in originals.items()},
                  original_chunks_sha256=digest(originals['evidence/hw-gift-1/chunks.py']),
                  patched_chunks_sha256=digest(patched), host_gate_patch_sha256=digest(patch),
                  orchestration_sha256=sha(__file__), load_guard_sha256=sha(HERE / 'load_guard.py'),
                  ovh_bench_sha256=sha(HERE / 'ovh_bench.py'))
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
    """Forward Python calls, locking only one actual timed C repeat at a time."""
    identity = measurement_args(args)
    if identity is None:
        return subprocess.run([str(python), *args]).returncode
    chunk = os.environ['GIFT1B_TARGET']
    check(chunk in CHUNKS, 'unknown C target chunk')
    expected_source = 'enwik8' if chunk.startswith('enwik8-') else 'silesia.tar'
    check(identity['src'] == expected_source, 'C repeat corpus differs from target')
    directory = CSTATE / chunk / 'ovh-repeats'
    name = f"{identity['g']}-{identity['n']}-{identity['rep']}"
    metadata_path, receipt_path, stdout_path = (directory / f'{name}{suffix}' for suffix in
                                                ('.metadata.json', '.receipt.json', '.stdout'))
    if metadata_path.exists():
        saved = json.loads(metadata_path.read_bytes())
        check(all(saved[k] == identity[k] for k in ('g', 'n', 'rep')), 'saved C repeat identity changed')
        check(saved['returncode'] == 0, 'rejected C repeat must be quarantined before retry')
        check(json.loads(receipt_path.read_bytes()) == saved['receipt'], 'saved C lock receipt changed')
        check(sha(stdout_path) == saved['stdout_sha256'], 'saved C repeat stdout changed')
        sys.stdout.buffer.write(stdout_path.read_bytes())
        sys.stdout.buffer.flush()
        return 0
    check(receipt_path.exists() or not stdout_path.exists(), 'C stdout exists without its lock receipt; inspect before retry')
    directory.mkdir(parents=True, exist_ok=True)
    # The helper safely replays a completed CLEAN receipt after an interruption
    # between its durable write and this shim's metadata write. WAITING/ERROR
    # remains a manual stop; LOADED is returned as 77 for full-chunk quarantine.
    code = ovh().run_locked([str(python), *args], receipt_path, stdout_path=stdout_path)
    receipt = json.loads(receipt_path.read_bytes())
    metadata = {k: identity[k] for k in ('g', 'n', 'rep')}
    raw = stdout_path.read_bytes()
    row_sha256 = None
    if code == 0 or (code == 77 and raw):
        row = dict(src=expected_source, level=int(chunk.rsplit('L', 1)[1]),
                   g=identity['g'], n=identity['n'], rep=identity['rep'], **json.loads(raw))
        row_sha256 = digest(packed(row))
    metadata.update(returncode=code, receipt=receipt, stdout_sha256=digest(raw), row_sha256=row_sha256,
                    ovh_policy_commit=OVH_POLICY, ovh_bench_sha256=sha(HERE / 'ovh_bench.py'))
    write(metadata_path, packed(metadata))
    if code == 0:
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()
    return code


def benchmark_runs(chunk, cstate=CSTATE):
    directory = cstate / chunk / 'ovh-repeats'
    records = [json.loads(path.read_bytes()) for path in sorted(directory.glob('*.metadata.json'))]
    return sorted(records, key=lambda r: (r['g'], r['n'], r['rep']))


def reject_loaded(chunk, here, cstate, receipt):
    records = benchmark_runs(chunk, cstate)
    if any(record['returncode'] == 77 for record in records):
        receipt.update(load_accepted=False, rejection_reason='OVH-BENCH LOADED timed repeat', benchmark_runs=records)
        quarantine(chunk, here / chunk, cstate / chunk, receipt)
        raise SystemExit(REJECTED_LOAD)


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
    reject_loaded(chunk, here, cstate, receipt)
    try:
        original_main()
    except (Exception, SystemExit):
        reject_loaded(chunk, here, cstate, receipt)
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
    check(all(r['returncode'] == 0 for r in records), 'C checkpoint includes failed timed repeats')
    receipt['benchmark_runs'] = [{k: r[k] for k in ('g', 'n', 'rep', 'receipt', 'row_sha256')} for r in records]
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
