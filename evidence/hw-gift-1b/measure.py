"""Preregistered HW-GIFT-1b worker; no timing occurs on import or in files mode.

Usage: python -B measure.py run enwik8-L3 --inputs .work/inputs \
    --receipt .work/hw-gift-1b/install.json --cpu 0

Only complete corpus/level checkpoints enter evidence/. Archives and completed
CLEAN repeats survive in .work/hw-gift-1b/. Samples stay in RAM during a repeat.
Interrupted archive writes and failed checks stop rather than silently retrying.
"""

import argparse
import gzip
import hashlib
import importlib.metadata
import inspect
import io
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASELINE = ROOT / 'evidence/hw-gift-1'
STATE = ROOT / '.work/hw-gift-1b'
PROTOCOL = 'c4809624beb0ad7a243163455d9c05545bc52d99'
AMENDMENT = '0bd4ab29794f610884e66fdb3ca6c6c93495a4e4'
POLICY = '3e7201a0933030de8d3011eb658270e577e6eced'
LOAD_AMENDMENT = 'f8a2fb2c82bce9eacd841eafcf584a4c81ffc37c'
THRESHOLD_AMENDMENT = 'c8de6772e001fd52aebd73731cdd564c5f9db332'
LOAD1_THRESHOLD = '2.0'
AMENDMENT_TEXT = (
    'Pre-measurement host amendment: the HW-GIFT-1 host is not available. '
    'HW-GIFT-1b runs on ace-core (AMD EPYC 4344P); record CPU, kernel, governor, '
    'pinned core and other load at start and end. On the same host and pinned '
    'core, also rerun the HW-GIFT-1 C reader (evidence/hw-gift-1/reproduce.sh, '
    'unchanged) on the same grid, so both readers share one host. HW-GIFT-1 data '
    'on main stay unchanged. Predictions (a) and (b) unchanged.'
)
POLICY_TEXT = (
    'Pre-measurement OVH-BENCH execution rule (2026-11-24): builds, tests and '
    'correctness checks may run in parallel without restriction. Every timed '
    'measurement must run through `flock /run/lock/ovh-bench.lock <measurement '
    'command>`; wait if the lock is occupied and never bypass it. Record `date '
    '-u`, `cat /proc/loadavg` and `nproc` at the beginning and end of each timed '
    'repeat. If the one-minute load average is above 1.0 at either boundary, '
    'retain the result as LOADED, exclude it from accepted evidence and repeat '
    'the measurement. Do not hold the shared benchmark lock during long builds. '
    'Existing OVH timing numbers from before this rule are not remeasured '
    'unless they will be published externally. This rule supersedes the earlier '
    'zero-foreign-activity admission policy; CPU, kernel, governor, pinned core '
    'and other-load receipts are still retained. Predictions (a) and (b) unchanged.'
)
LOAD_AMENDMENT_TEXT = (
    'Load amendment: a LOADED timed repeat is retaken alone with the same seed '
    'and offsets, up to 3 attempts, all attempts retained. This replaces the '
    'whole-checkpoint rerun from the next attempt on.'
)
THRESHOLD_AMENDMENT_TEXT = (
    'Load threshold amendment: the timed process itself contributes ≈1.0 to '
    'load1 (observed: LOADED at 1.08 with no other process above 1.5% CPU). '
    'LOADED now means load1 > 2.0 at either boundary. The 45 CLEAN repeats of '
    'the current enwik8-L3 trial were clean under the stricter rule and are '
    'retained. The blocked repeat (16 MiB / 64 KiB №0) restarts with a fresh '
    '3-attempt budget. Earlier excluded trials stay excluded. Predictions unchanged.'
)
MONITORING_TEXT = (
    'Additional observational monitoring: retain per-core /proc/stat counters '
    'at both boundaries and their deltas across each repeat, including '
    'busy/total jiffies and utilization for every logical CPU other than pinned '
    'CPU 0. These data never affect the load decision, which uses only exact '
    'load1 > 2.0 at either boundary. The already retained 45 CLEAN repeats '
    'predate this monitoring and are not remeasured or backfilled.'
)
GS = (65536, 262144, 1048576, 4194304, 16777216, 67108864, None)
NS = (4096, 65536)
CHUNKS = {f'{name}-L{level}': (src, level) for name, src in
          [('enwik8', 'enwik8'), ('silesia', 'silesia.tar')] for level in (3, 19)}
INPUT = {
    'enwik8': (100000000, '2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8'),
    'silesia.tar': (211947520, 'a667bac80089b3d04d5496772149e632f0758974b0579d743cd8d6e5e0d63eb2'),
}


def check(ok, why):
    if not ok:
        raise ValueError(why)


def label(g):
    return 'default' if g is None else str(g)


FILES = [f'samples-{label(g)}.jsonl.gz' for g in GS] + [
    'archives.json', 'controls.json', 'run.json', 'attempts.tar.gz', 'attempts.json']


def packed(value):
    return (json.dumps(value, separators=(',', ':'), sort_keys=True) + '\n').encode()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fsync_dir(path):
    fd = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.writing')
    with tmp.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)
    fsync_dir(path.parent)


def same_or_write(path, data):
    if path.exists():
        check(path.read_bytes() == data, f'changed durable state: {path}')
    else:
        write(path, data)


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def verify_protocol_bytes(original, amended, policy, load_amendment, threshold_amendment, current):
    check(amended == original + b'\n' + AMENDMENT_TEXT.encode() + b'\n',
          'host amendment must preserve the exact original protocol prefix')
    check(policy == amended + b'\n' + POLICY_TEXT.encode() + b'\n',
          'OVH-BENCH rule must preserve the exact amended protocol prefix')
    check(load_amendment == policy + b'\n' + LOAD_AMENDMENT_TEXT.encode() + b'\n',
          'load amendment must preserve the exact OVH-BENCH protocol prefix')
    check(threshold_amendment == load_amendment + b'\n' + THRESHOLD_AMENDMENT_TEXT.encode() +
          b'\n\n' + MONITORING_TEXT.encode() + b'\n',
          'threshold amendment must preserve the exact three-attempt protocol prefix')
    check(current == threshold_amendment, 'amended preregistered protocol changed')
    return hashlib.sha256(original).hexdigest()


def require_amended_host(cpu, model, hostname):
    check(cpu == 0, 'matched C reader comparison requires pinned CPU 0')
    check(hostname.split('.')[0] == 'ace-core' and 'AMD EPYC 4344P' in model,
          'amended protocol requires ace-core AMD EPYC 4344P')


def parse_archive(data, g, total):
    """Parse the seekable footer/table independently of pyzstd."""
    check(len(data) >= 17, 'short seekable archive')
    count, descriptor, magic = struct.unpack_from('<IBI', data, len(data) - 9)
    check(magic == 0x8F92EAB1 and descriptor in (0, 128) and count > 0,
          'invalid seek-table footer')
    checksum = descriptor == 128
    stride = 12 if checksum else 8
    table_bytes = 8 + count * stride + 9
    start = len(data) - table_bytes
    check(start >= 0, 'seek table exceeds archive')
    skip_magic, skip_size = struct.unpack_from('<II', data, start)
    check(skip_magic == 0x184D2A5E and skip_size == table_bytes - 8,
          'invalid seek-table skippable frame')
    frames = []
    pos = 0
    for index in range(count):
        compressed, decompressed = struct.unpack_from('<II', data, start + 8 + index * stride)
        check(compressed > 0 and decompressed > 0, 'empty data frame')
        check(data[pos:pos + 4] == b'\x28\xb5\x2f\xfd', 'invalid data frame magic')
        frames.append(dict(compressed_bytes=compressed, decompressed_bytes=decompressed))
        pos += compressed
    check(pos == start and sum(f['decompressed_bytes'] for f in frames) == total,
          'archive byte accounting failed')
    effective = (1 << 30) if g is None else g
    check(all(f['decompressed_bytes'] == effective for f in frames[:-1]) and
          0 < frames[-1]['decompressed_bytes'] <= effective, 'unexpected frame geometry')
    if g is None:
        check(count == 1, 'default must produce one frame for these corpora')
    return dict(frame_count=count, decompressed_bytes=total,
                seek_table_bytes=table_bytes, checksum_flag=checksum, frames=frames)


def offset_lists(chunk):
    """Reuse stored starts literally; never draw replacement random offsets."""
    src, level = CHUNKS[chunk]
    by_g, hashes = {}, {}
    for g in GS[:-1]:
        path = BASELINE / chunk / f'samples-{g}.jsonl.gz'
        hashes[path.name] = sha(path)
        rows = [json.loads(line) for line in gzip.decompress(path.read_bytes()).splitlines()]
        offsets = {}
        for row in rows:
            check((row['src'], row['level'], row['g']) == (src, level, g),
                  'baseline row identity mismatch')
            if row['rep'] == -1:
                continue
            key = (row['n'], row['rep'])
            check(key not in offsets, 'duplicate baseline repeat')
            starts = [sample[0] for sample in row['samples']]
            check(len(starts) == 1000 and all(type(off) is int and
                  0 <= off <= INPUT[src][0] - row['n'] for off in starts),
                  'invalid saved offset list')
            offsets[key] = starts
        check(set(offsets) == {(n, rep) for n in NS for rep in range(5)},
              'incomplete baseline offset lists')
        by_g[g] = offsets
    check(all(offsets == by_g[GS[0]] for offsets in by_g.values()),
          'original frame grids use different offsets')
    by_g[None] = by_g[GS[0]]
    return by_g, hashes


def installed_hashes():
    result = {}
    for name in ('pyzstd', 'backports.zstd', 'typing_extensions'):
        try:
            distribution = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        result[name] = {'version': distribution.version, 'files': {}}
        for item in distribution.files or ():
            if item.suffix in ('.py', '.so', '.pyd'):
                path = Path(distribution.locate_file(item)).resolve()
                result[name]['files'][str(item)] = sha(path)
    return result


def preflight(receipt_path, cpu):
    check(sys.platform == 'linux' and platform.python_implementation() == 'CPython',
          'Linux CPython executor required')
    check(git('branch', '--show-current').decode().strip() == 'hw-gift-1b', 'wrong branch')
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', PROTOCOL, 'HEAD'], check=True)
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', AMENDMENT, 'HEAD'], check=True)
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', POLICY, 'HEAD'], check=True)
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', LOAD_AMENDMENT, 'HEAD'], check=True)
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', THRESHOLD_AMENDMENT, 'HEAD'], check=True)
    relative = 'evidence/hw-gift-1b/CALIBRATION.md'
    verify_protocol_bytes(git('show', f'{PROTOCOL}:{relative}'),
                          git('show', f'{AMENDMENT}:{relative}'),
                          git('show', f'{POLICY}:{relative}'),
                          git('show', f'{LOAD_AMENDMENT}:{relative}'),
                          git('show', f'{THRESHOLD_AMENDMENT}:{relative}'),
                          (HERE / 'CALIBRATION.md').read_bytes())
    sources = [str((HERE / name).relative_to(ROOT)) for name in
               ('CALIBRATION.md', 'measure.py', 'report.py', 'load_guard.py', 'ovh_bench.py',
                'attempt_artifact.py')]
    check(not git('status', '--porcelain', '--', *sources).strip(), 'uncommitted runner/protocol/verifier')
    check(cpu == 0, 'matched C reader comparison requires pinned CPU 0')
    check(len(os.sched_getaffinity(0)) > 0 and cpu in os.sched_getaffinity(0), 'CPU unavailable')
    os.sched_setaffinity(0, {cpu})
    check(os.sched_getaffinity(0) == {cpu}, 'single CPU affinity failed')
    model = next(line.split(':', 1)[1].strip() for line in
                 Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name'))
    require_amended_host(cpu, model, platform.node())
    receipt = json.loads(receipt_path.read_bytes())
    for key in ('pyzstd_version', 'wheel_filename', 'wheel_sha256', 'wheel_path', 'pypi_version'):
        check(key in receipt, f'missing installation receipt {key}')
    wheel = Path(receipt['wheel_path']).resolve()
    check(wheel.name == receipt['wheel_filename'] and sha(wheel) == receipt['wheel_sha256'],
          'pinned wheel SHA256/filename mismatch')
    check(receipt['pypi_version'] == receipt['pyzstd_version'], 'receipt did not select latest PyPI release')
    check(receipt.get('wheels'), 'missing dependency wheel manifest')
    for dependency in receipt['wheels']:
        path = Path(dependency['wheel_path']).resolve()
        check(path.name == dependency['wheel_filename'] and sha(path) == dependency['wheel_sha256'],
              'dependency wheel hash mismatch')
    import pyzstd
    check(pyzstd.__version__ == receipt['pyzstd_version'] ==
          importlib.metadata.version('pyzstd'), 'installed pyzstd version mismatch')
    signature = inspect.signature(pyzstd.SeekableZstdFile)
    check(signature.parameters['max_frame_content_size'].default == 1 << 30,
          'pyzstd default no longer equals preregistered 1 GiB')
    installed_base = Path(receipt['installed_files_base']).resolve()
    check(Path(pyzstd.__file__).resolve().is_relative_to(installed_base),
          'pyzstd imported outside hash-verified site-packages')
    check(receipt.get('installed_files_sha256'), 'missing installed wheel-payload hashes')
    for relative, digest in receipt['installed_files_sha256'].items():
        path = (installed_base / relative).resolve()
        check(path.is_relative_to(installed_base) and sha(path) == digest,
              f'installed file hash mismatch: {relative}')
    check(Path(sys.executable).resolve() == Path(receipt['installed_python']).resolve(),
          'runner is not using the pinned virtual environment')
    runtime = receipt.get('runtime', {})
    check(runtime.get('python') == platform.python_version() and
          runtime.get('pyzstd_version') == pyzstd.__version__ and
          runtime.get('zstd_version') == pyzstd.zstd_version,
          'interpreter or linked zstd backend differs from installation receipt')
    distributions = installed_hashes()
    for dependency in receipt['wheels']:
        check(importlib.metadata.version(dependency['name']) == dependency['version'],
              'installed dependency version mismatch')
    check(len(list(Path('/proc/self/task').iterdir())) == 1, 'worker has unexpected threads')
    governor_path = Path(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor')
    governor = governor_path.read_text().strip() if governor_path.exists() else 'unavailable'
    host = dict(cpu=model, hostname=platform.node(), cpu_affinity=[cpu], pinned_core=cpu,
                governor=governor, kernel=platform.release(),
                os=platform.freedesktop_os_release()['PRETTY_NAME'],
                python=platform.python_version(), python_implementation=platform.python_implementation(),
                pyzstd_version=pyzstd.__version__, zstd_version=str(pyzstd.zstd_version),
                installation_receipt=receipt, installed_distributions=distributions,
                encoder_options='integer level; no multithread option; max_frame_content_size omitted for default',
                host_boot_sha256=hashlib.sha256((platform.node() + '\n' +
                    Path('/proc/sys/kernel/random/boot_id').read_text()).encode()).hexdigest())
    return pyzstd, host


def archive_once(pyzstd, part, source, level, g):
    stem = f'archive-{label(g)}'
    archive = part / f'{stem}.zst'
    record = part / f'{stem}.json'
    started = part / f'{stem}.started'
    if record.exists():
        info = json.loads(record.read_bytes())
        check(archive.exists() and archive.stat().st_size == info['bytes'] and
              sha(archive) == info['sha256'], 'saved archive changed or missing')
        data = archive.read_bytes()
        check(parse_archive(data, g, source.stat().st_size) ==
              {k: info[k] for k in ('frame_count', 'decompressed_bytes', 'seek_table_bytes',
                                   'checksum_flag', 'frames')}, 'saved seek table changed')
        return data, info
    if started.exists():
        check(archive.exists(), 'interrupted archive encoding; inspect before any restart')
    else:
        check(not archive.exists(), 'unregistered archive exists')
        write(started, packed(dict(g=g, level=level, source_sha256=sha(source))))
        temporary = archive.with_suffix('.zst.writing')
        check(not temporary.exists(), 'partial encoder output exists')
        kwargs = {'level_or_option': level}
        if g is not None:
            kwargs['max_frame_content_size'] = g
        with source.open('rb') as raw, pyzstd.SeekableZstdFile(temporary, 'wb', **kwargs) as writer:
            shutil.copyfileobj(raw, writer, length=1 << 20)
        with temporary.open('rb') as stream:
            os.fsync(stream.fileno())
        temporary.replace(archive)
        fsync_dir(part)
    data = archive.read_bytes()
    info = dict(g=g, frame=label(g), bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                **parse_archive(data, g, source.stat().st_size))
    write(record, packed(info))
    return data, info


def control(pyzstd, part, data, info, n):
    path = part / f'control-{info["frame"]}-{n}.json'
    if path.exists():
        result = json.loads(path.read_bytes())
        check(result['archive_sha256'] == info['sha256'] and result['negative'] == 'pyzstd exception',
              'saved negative control changed')
        return result
    damaged = b'BAD!' + data[4:]
    try:
        with pyzstd.SeekableZstdFile(io.BytesIO(damaged), 'rb') as reader:
            reader.seek(0)
            reader.read(n)
    except pyzstd.ZstdError as error:
        result = dict(g=info['g'], frame=info['frame'], n=n, offset=0,
                      exception=f'{type(error).__module__}.{type(error).__name__}',
                      negative='pyzstd exception', archive_sha256=info['sha256'])
    else:
        raise ValueError('damaged data frame did not raise pyzstd.ZstdError')
    write(path, packed(result))
    return result


def repeat(pyzstd, part, data, info, source, src, level, n, rep, offsets):
    """Keep samples in RAM; persist the complete repeat after its timed loop."""
    import resource
    samples = []
    for off in offsets:
        buffer = io.BytesIO(data)
        t0 = time.perf_counter_ns()
        reader = pyzstd.SeekableZstdFile(buffer, 'rb')
        open_ns = time.perf_counter_ns() - t0
        try:
            t0 = time.perf_counter_ns()
            reader.seek(off)
            first = reader.read(n)
            first_ns = time.perf_counter_ns() - t0
            t0 = time.perf_counter_ns()
            reader.seek(off)
            second = reader.read(n)
            repeat_ns = time.perf_counter_ns() - t0
            source.seek(off)
            expected = source.read(n)
            check(len(first) == len(second) == len(expected) == n and
                  first == expected and second == expected, 'restored byte/length mismatch')
        finally:
            reader.close()
            buffer.close()
        samples.append([off, open_ns, first_ns, repeat_ns])
    return dict(src=src, level=level, g=info['g'], frame=info['frame'], n=n, rep=rep,
                archive_sha256=info['sha256'], archive_bytes=info['bytes'], samples=samples,
                peak_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


class BlockedLoad(RuntimeError):
    """Three retained LOADED attempts exhaust one logical timed repeat."""
    def __init__(self, record):
        super().__init__('BLOCKED: load; three LOADED attempts exhausted')
        self.record = record


def check_load_snapshot(value, host):
    # Observational receipts may contain foreign activity under the OVH rule.
    for key in ('hostname', 'cpu', 'kernel', 'pinned_core', 'governor'):
        check(value.get(key) == host[key], f'load receipt {key} differs from pinned host')


def timed_worker(request_path):
    """One timed repeat; callable only as the child of the shared flock helper."""
    check(os.environ.get('OVH_BENCH_LOCK_HELD') == '/run/lock/ovh-bench.lock',
          'timed worker requires the OVH-BENCH flock wrapper')
    request_path = request_path.resolve()
    check(request_path.is_relative_to(STATE), 'worker request outside durable state')
    request = json.loads(request_path.read_bytes())
    chunk, g, n, rep = (request[k] for k in ('chunk', 'g', 'n', 'rep'))
    check(chunk in CHUNKS and g in GS and n in NS and rep in range(5), 'invalid worker grid')
    check(request.get('cpu') == 0, 'timed worker requires CPU 0')
    pyzstd, host = preflight(Path(request['install_receipt']), 0)
    check(host == request['host'], 'timed child host/build differs from parent')
    src, level = CHUNKS[chunk]
    source_path, archive_path = Path(request['source_path']).resolve(), Path(request['archive_path']).resolve()
    part, row_path = Path(request['part']).resolve(), Path(request['row_path']).resolve()
    check(source_path.is_relative_to(ROOT) and archive_path.is_relative_to(STATE) and
          part == request_path.parent and row_path.parent == part, 'worker path outside assigned state')
    check(not row_path.exists(), 'timed repeat row already exists')
    check(source_path.stat().st_size == INPUT[src][0] and sha(source_path) == INPUT[src][1],
          'timed child input changed')
    data = archive_path.read_bytes()
    info = request['archive']
    check(len(data) == info['bytes'] and hashlib.sha256(data).hexdigest() == info['sha256'],
          'timed child archive changed')
    check(parse_archive(data, g, INPUT[src][0]) == {k: info[k] for k in
          ('frame_count', 'decompressed_bytes', 'seek_table_bytes', 'checksum_flag', 'frames')},
          'timed child seek table changed')
    offsets, _ = offset_lists(chunk)
    check(request['offsets'] == offsets[g][n, rep], 'timed child offsets differ from original evidence')
    with source_path.open('rb', buffering=0) as source:
        row = repeat(pyzstd, part, data, info, source, src, level, n, rep, request['offsets'])
    write(row_path, packed(row))


def timed_repeat(part, chunk, g, n, rep, source_path, archive_path, info,
                 receipt_path, host, offsets):
    from ovh_bench import run_locked
    repeats_root = part / 'repeats'
    logical = repeats_root / f'{label(g)}-{n}-{rep}'
    logical.mkdir(parents=True, exist_ok=True)
    check({p.name for p in logical.iterdir()}.issubset({'attempt-1', 'attempt-2', 'attempt-3'}),
          'unexpected attempt beyond the three-attempt limit')
    attempts = []
    for index in range(1, 4):
        folder = logical / f'attempt-{index}'
        folder.mkdir(exist_ok=True)
        request_path = folder / 'request.json'
        row_path, bench_path = folder / 'row.json', folder / 'ovh-bench.json'
        request = dict(chunk=chunk, g=g, n=n, rep=rep, cpu=0, source_path=str(source_path),
                       archive_path=str(archive_path), archive=info, part=str(folder),
                       row_path=str(row_path), install_receipt=str(receipt_path.resolve()),
                       host=host, offsets=offsets)
        command = [sys.executable, '-B', str(HERE / 'measure.py'), 'worker', '--request', str(request_path)]
        if bench_path.exists():
            check(request_path.read_bytes() == packed(request), 'saved repeat request changed')
            benchmark = json.loads(bench_path.read_bytes())
            code = 0 if benchmark.get('status') == 'CLEAN' else 77
        else:
            check(not any(folder.iterdir()),
                  'interrupted repeat without complete boundary receipt; retain and inspect')
            write(request_path, packed(request))
            code = run_locked(command, bench_path)
            check(bench_path.exists(), 'OVH-BENCH helper did not retain boundary receipt')
            benchmark = json.loads(bench_path.read_bytes())
        check(code in (0, 77), f'timed child/helper failed: exit {code}')
        check(benchmark.get('schema') == 'ovh-bench-v2' and
              benchmark.get('threshold_amendment_commit') == THRESHOLD_AMENDMENT and
              benchmark.get('load1_threshold') == LOAD1_THRESHOLD,
              'new pyzstd cohort requires the amended OVH-BENCH v2 threshold receipt')
        for boundary_name in ('start', 'end'):
            boundary = benchmark.get(boundary_name, {})
            check(isinstance(boundary, dict) and
                  {'proc_stat_raw', 'proc_stat_error', 'other_cpu_delta'}.issubset(boundary),
                  'new pyzstd repeat is missing per-core observational monitoring')
            delta = boundary['other_cpu_delta']
            check(isinstance(delta, dict) and delta.get('status') in ('ok', 'unavailable'),
                  'invalid per-core observational monitoring receipt')
        status = benchmark.get('status')
        check(status in ('CLEAN', 'LOADED') and benchmark.get('returncode') in (None, 0),
              'timed child ERROR/nonzero returncode is fatal and must not be retried')
        check(benchmark.get('command') == command, 'OVH-BENCH receipt command changed')
        check((status == 'CLEAN' and code == 0) or (status == 'LOADED' and code == 77),
              'OVH-BENCH status/exit mismatch')
        row = None
        if row_path.exists():
            row = json.loads(row_path.read_bytes())
            check((row.get('src'), row.get('level'), row.get('g'), row.get('n'), row.get('rep')) ==
                  (*CHUNKS[chunk], g, n, rep), 'timed child row identity mismatch')
            check(row_path.read_bytes() == packed(row), 'timed row is not deterministic JSON')
            check([sample[0] for sample in row.get('samples', [])] == offsets,
                  'retained raw row offsets differ from this logical repeat')
        check(type(benchmark.get('command_started')) is bool, 'missing timed command-start receipt')
        if benchmark['command_started']:
            check(row is not None and benchmark.get('returncode') == 0,
                  'successful timed child has no complete raw row')
        else:
            check(row is None and benchmark.get('returncode') is None,
                  'unstarted timed command has unexpected output/returncode')
        if status == 'CLEAN':
            check(row is not None and benchmark.get('returncode') == 0 and benchmark['command_started'],
                  'CLEAN repeat has no complete raw row')
        attempt_record = dict(attempt=index, status=status, receipt=benchmark,
            row_sha256=sha(row_path) if row is not None else None,
            request_sha256=sha(request_path),
            receipt_path=bench_path.relative_to(repeats_root).as_posix(),
            raw_row_path=row_path.relative_to(repeats_root).as_posix() if row is not None else None)
        attempts.append(attempt_record)
        if status == 'CLEAN':
            check(not any((logical / f'attempt-{later}').exists() for later in range(index + 1, 4)),
                  'a CLEAN repeat must never have a later attempt')
            record = dict(g=g, n=n, rep=rep, receipt=benchmark,
                          row_sha256=attempt_record['row_sha256'],
                          request_sha256=attempt_record['request_sha256'], attempts=attempts)
            return row, record
        # Immediate retry of this logical repeat only; run_locked itself blocks
        # on the common flock. No polling interval or independent sleep here.
    raise BlockedLoad(dict(g=g, n=n, rep=rep, attempts=attempts,
                          ps_top8=attempts[-1]['receipt'].get('ps_top8')))


def progress_counts(benchmark_runs, blocked_repeat=None):
    logical = [*benchmark_runs, *([blocked_repeat] if blocked_repeat else [])]
    return dict(planned_repeats=len(GS) * len(NS) * 5, started_repeats=len(logical),
                retaken_repeats=sum(len(record['attempts']) > 1 for record in logical),
                loaded_attempts=sum(item['status'] == 'LOADED' for record in logical
                                    for item in record['attempts']))


def _run(chunk, inputs, receipt_path, cpu, attempt):
    from report import verify_chunk
    from load_guard import snapshot
    from attempt_artifact import pack_attempts
    blocked_folder = HERE / 'blocked' / f'pyzstd-{chunk}'
    if (blocked_folder / 'BLOCKED.json').exists():
        raise BlockedLoad(json.loads((blocked_folder / 'BLOCKED.json').read_bytes())['blocked_repeat'])
    if (HERE / chunk).exists():
        verify_chunk(HERE / chunk, chunk)
        print('COMPLETE_CHECKPOINT_VERIFIED_SKIP', chunk, flush=True)
        return
    pyzstd, host = preflight(receipt_path, cpu)
    for previous in CHUNKS:
        if (HERE / previous).exists():
            check(verify_chunk(HERE / previous, previous)['run']['host'] == host,
                  'run crossed host/build boundary')
    inputs = inputs.resolve()
    check(inputs.is_relative_to(ROOT), 'inputs must remain inside hw-apex-bench workspace')
    for src, (size, digest) in INPUT.items():
        check((inputs / src).stat().st_size == size and sha(inputs / src) == digest,
              f'input SHA256/size mismatch: {src}')
    offsets, offset_hashes = offset_lists(chunk)
    src, level = CHUNKS[chunk]
    part = STATE / 'attempts' / f'{attempt:03}' / chunk
    part.mkdir(parents=True, exist_ok=True)
    archive_state = STATE / 'archives' / chunk
    archive_state.mkdir(parents=True, exist_ok=True)
    import fcntl
    with (part / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (part / 'REJECTED').exists():
            raise ValueError('previous whole-checkpoint attempt is rejected and cannot be reused')
        check(not (part / 'FAILED').exists(), 'prior failed check; inspect FAILED and stop')
        run_record = dict(corpus=src, level=level, input_bytes=INPUT[src][0], input_sha256=INPUT[src][1],
                          protocol_commit=PROTOCOL, protocol_sha256=sha(HERE / 'CALIBRATION.md'),
                          amendment_commit=AMENDMENT, ovh_policy_commit=POLICY,
                          load_amendment_commit=LOAD_AMENDMENT,
                          threshold_amendment_commit=THRESHOLD_AMENDMENT,
                          load1_threshold=LOAD1_THRESHOLD,
                          original_protocol_sha256=hashlib.sha256(git('show',
                              f'{PROTOCOL}:evidence/hw-gift-1b/CALIBRATION.md')).hexdigest(),
                          runner_commit=git('log', '-1', '--format=%H', '--',
                              'evidence/hw-gift-1b/measure.py', 'evidence/hw-gift-1b/report.py',
                              'evidence/hw-gift-1b/load_guard.py',
                              'evidence/hw-gift-1b/ovh_bench.py',
                              'evidence/hw-gift-1b/attempt_artifact.py').decode().strip(),
                          runner_sha256=sha(HERE / 'measure.py'), verifier_sha256=sha(HERE / 'report.py'),
                          guard_sha256=sha(HERE / 'load_guard.py'),
                          ovh_bench_sha256=sha(HERE / 'ovh_bench.py'),
                          attempt_artifact_sha256=sha(HERE / 'attempt_artifact.py'), attempt=attempt,
                          host=host, offset_source_sha256=offset_hashes,
                          sample_columns=['offset', 'open_ns', 'first_ns', 'repeat_ns'],
                          timer='time.perf_counter_ns; open separate; seek+read first and repeat',
                          peak_rss_scope='timed-repeat child process, including resident archive and request buffers')
        # Source commits remain fixed when checkpoint commits advance HEAD.
        saved = part / 'run-base.json'
        if saved.exists():
            original = json.loads(saved.read_bytes())
            run_record['runner_commit'] = original['runner_commit']
        same_or_write(saved, packed(run_record))
        same_or_write(archive_state / 'encoder.json', packed(dict(
            corpus=src, level=level, host=host, protocol_sha256=run_record['protocol_sha256'],
            runner_sha256=run_record['runner_sha256'])))
        phase, current_load = 'start', None
        try:
            current_load = snapshot(cpu)
            check_load_snapshot(current_load, host)
            start_path, resumes_path = part / 'load-start.json', part / 'load-resume-starts.json'
            resumes = json.loads(resumes_path.read_bytes()) if resumes_path.exists() else []
            if start_path.exists():
                start_load = json.loads(start_path.read_bytes())
                check_load_snapshot(start_load, host)
                resumes.append(current_load)
            else:
                start_load = current_load
                write(start_path, packed(start_load))
            write(resumes_path, packed(resumes))
            phase = 'measurement'
            publish = part / 'publish'
            publish.mkdir(exist_ok=True)
            archives, controls, benchmark_runs = [], [], []
            for g in GS:
                data, info = archive_once(pyzstd, archive_state, inputs / src, level, g)
                archives.append(info)
                records = []
                for n in NS:
                    controls.append(control(pyzstd, part, data, info, n))
                    for rep in range(5):
                        row, benchmark = timed_repeat(part, chunk, g, n, rep, inputs / src,
                            archive_state / f'archive-{label(g)}.zst', info, receipt_path,
                            host, offsets[g][n, rep])
                        records.append(row)
                        benchmark_runs.append(benchmark)
                        print('REPEAT_SAVED_CLEAN', chunk, label(g), n, rep, flush=True)
                check(hashlib.sha256(data).hexdigest() == info['sha256'], 'resident archive changed')
                write(publish / f'samples-{label(g)}.jsonl.gz',
                      gzip.compress(b''.join(map(packed, records)), compresslevel=6, mtime=0))
            check(sha(inputs / src) == INPUT[src][1], 'source changed during measurement')
            phase = 'end'
            current_load = snapshot(cpu)
            check_load_snapshot(current_load, host)
            write(part / 'load-end.json', packed(current_load))
            run_record.update(load_start=start_load, load_end=current_load,
                              load_resume_starts=resumes, load_accepted=True,
                              benchmark_runs=benchmark_runs, **progress_counts(benchmark_runs))
            pack_attempts(part / 'repeats', publish)
            write(part / 'run.json', packed(run_record))
            write(publish / 'archives.json', packed(archives))
            write(publish / 'controls.json', packed(controls))
            write(publish / 'run.json', packed(run_record))
            write(publish / 'SHA256SUMS', ''.join(
                f'{sha(publish / name)}  {name}\n' for name in sorted(FILES)).encode())
            verify_chunk(publish, chunk, calibration_path=HERE / 'CALIBRATION.md')
            check(not (HERE / chunk).exists(), 'checkpoint appeared concurrently')
            publish.replace(HERE / chunk)
            fsync_dir(HERE)
            verify_chunk(HERE / chunk, chunk)
        except BlockedLoad as error:
            summary = dict(run_record, status='BLOCKED: load', reader='pyzstd', chunk=chunk,
                           benchmark_runs=benchmark_runs, blocked_repeat=error.record,
                           load_start=start_load, load_end=snapshot(cpu),
                           load_resume_starts=resumes, load_accepted=False,
                           ps_top8=error.record.get('ps_top8'),
                           **progress_counts(benchmark_runs, error.record))
            write(part / 'BLOCKED', packed(summary))
            stage = part / 'blocked-publish'
            stage.mkdir(exist_ok=True)
            pack_attempts(part / 'repeats', stage)
            write(stage / 'BLOCKED.json', packed(summary))
            blocked_folder.parent.mkdir(parents=True, exist_ok=True)
            check(not blocked_folder.exists(), 'blocked evidence already published')
            stage.replace(blocked_folder)
            fsync_dir(blocked_folder.parent)
            raise
        except Exception as error:
            write(part / 'FAILED', f'{type(error).__name__}: {error}\n'.encode())
            raise
    print('LOCAL_CHECKPOINT_READY_TO_PUBLISH', chunk, flush=True)


def run(chunk, inputs, receipt_path, cpu, attempt=1):
    check(sys.platform == 'linux', 'Linux CPython executor required')
    check(type(attempt) is int and attempt >= 1, '--attempt must be a positive integer')
    import fcntl
    STATE.mkdir(parents=True, exist_ok=True)
    # Workspace-state lock only. The shared OVH lock wraps each timed child,
    # and is never held while this parent encodes or verifies archives.
    with (STATE / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _run(chunk, inputs, receipt_path, cpu, attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'files', 'worker'))
    parser.add_argument('chunk', nargs='?', choices=CHUNKS)
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--cpu', type=int, default=0)
    parser.add_argument('--attempt', type=int, default=1)
    parser.add_argument('--request', type=Path)
    args = parser.parse_args()
    if args.action == 'worker':
        check(args.request is not None, '--request required')
        timed_worker(args.request)
        return
    check(args.chunk is not None, 'chunk required')
    if args.action == 'files':
        print('\n'.join(f'evidence/hw-gift-1b/{args.chunk}/{name}' for name in [*FILES, 'SHA256SUMS']))
        return
    check(args.inputs is not None and args.receipt is not None, '--inputs and --receipt required')
    try:
        run(args.chunk, args.inputs, args.receipt, args.cpu, args.attempt)
    except BlockedLoad as error:
        print(f'BLOCKED: load: {error}', file=sys.stderr)
        raise SystemExit(2)


if __name__ == '__main__':
    main()
