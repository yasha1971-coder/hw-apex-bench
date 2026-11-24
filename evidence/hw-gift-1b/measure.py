"""Preregistered HW-GIFT-1b worker; no timing occurs on import or in files mode.

Usage: python -B measure.py run enwik8-L3 --inputs .work/inputs \
    --receipt .work/hw-gift-1b/install.json --cpu 0

Only complete corpus/level checkpoints enter evidence/. Archives and every
completed request pair survive in .work/hw-gift-1b/. Interrupted archive writes
and failed checks stop, rather than silently encoding or measuring again.
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
AMENDMENT_TEXT = (
    'Pre-measurement host amendment: the HW-GIFT-1 host is not available. '
    'HW-GIFT-1b runs on ace-core (AMD EPYC 4344P); record CPU, kernel, governor, '
    'pinned core and other load at start and end. On the same host and pinned '
    'core, also rerun the HW-GIFT-1 C reader (evidence/hw-gift-1/reproduce.sh, '
    'unchanged) on the same grid, so both readers share one host. HW-GIFT-1 data '
    'on main stay unchanged. Predictions (a) and (b) unchanged.'
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
    'archives.json', 'controls.json', 'run.json']


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


def verify_protocol_bytes(original, amended, current):
    check(amended == original + b'\n' + AMENDMENT_TEXT.encode() + b'\n',
          'host amendment must preserve the exact original protocol prefix')
    check(current == amended, 'amended preregistered protocol changed')
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
    relative = 'evidence/hw-gift-1b/CALIBRATION.md'
    verify_protocol_bytes(git('show', f'{PROTOCOL}:{relative}'),
                          git('show', f'{AMENDMENT}:{relative}'),
                          (HERE / 'CALIBRATION.md').read_bytes())
    sources = [str((HERE / name).relative_to(ROOT)) for name in
               ('CALIBRATION.md', 'measure.py', 'report.py', 'load_guard.py')]
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
    import resource
    folder = part / f'pairs-{info["frame"]}-{n}-{rep}'
    folder.mkdir(exist_ok=True)
    samples = []
    for index, off in enumerate(offsets):
        path = folder / f'{index:04}.json'
        if path.exists():
            sample = json.loads(path.read_bytes())
            check(isinstance(sample, list) and len(sample) == 4 and sample[0] == off and
                  all(type(value) is int and value >= 0 for value in sample),
                  'invalid durable sample')
        else:
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
            sample = [off, open_ns, first_ns, repeat_ns]
            write(path, packed(sample))
        samples.append(sample)
    return dict(src=src, level=level, g=info['g'], frame=info['frame'], n=n, rep=rep,
                archive_sha256=info['sha256'], archive_bytes=info['bytes'], samples=samples,
                peak_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def check_load_snapshot(value, host):
    from load_guard import BusyHost
    for key in ('hostname', 'cpu', 'kernel', 'pinned_core'):
        check(value.get(key) == host[key], f'load receipt {key} differs from pinned host')
    if value.get('governor') != host['governor']:
        raise BusyHost('CPU governor changed within checkpoint')


def _run(chunk, inputs, receipt_path, cpu, attempt):
    from report import verify_chunk
    from load_guard import snapshot, require_idle, BusyHost
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
            raise BusyHost('attempt was rejected; retain it and select a new --attempt')
        check(not (part / 'FAILED').exists(), 'prior failed check; inspect FAILED and stop')
        run_record = dict(corpus=src, level=level, input_bytes=INPUT[src][0], input_sha256=INPUT[src][1],
                          protocol_commit=PROTOCOL, protocol_sha256=sha(HERE / 'CALIBRATION.md'),
                          amendment_commit=AMENDMENT,
                          original_protocol_sha256=hashlib.sha256(git('show',
                              f'{PROTOCOL}:evidence/hw-gift-1b/CALIBRATION.md')).hexdigest(),
                          runner_commit=git('log', '-1', '--format=%H', '--',
                              'evidence/hw-gift-1b/measure.py', 'evidence/hw-gift-1b/report.py',
                              'evidence/hw-gift-1b/load_guard.py').decode().strip(),
                          runner_sha256=sha(HERE / 'measure.py'), verifier_sha256=sha(HERE / 'report.py'),
                          guard_sha256=sha(HERE / 'load_guard.py'), attempt=attempt,
                          host=host, offset_source_sha256=offset_hashes,
                          sample_columns=['offset', 'open_ns', 'first_ns', 'repeat_ns'],
                          timer='time.perf_counter_ns; open separate; seek+read first and repeat',
                          peak_rss_scope='chunk process, including archives, source buffers and prior repeats')
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
            require_idle(current_load)
            check_load_snapshot(current_load, host)
            start_path, resumes_path = part / 'load-start.json', part / 'load-resume-starts.json'
            resumes = json.loads(resumes_path.read_bytes()) if resumes_path.exists() else []
            if start_path.exists():
                start_load = json.loads(start_path.read_bytes())
                require_idle(start_load)
                check_load_snapshot(start_load, host)
                resumes.append(current_load)
            else:
                start_load = current_load
                write(start_path, packed(start_load))
            write(resumes_path, packed(resumes))
            phase = 'measurement'
            publish = part / 'publish'
            publish.mkdir(exist_ok=True)
            archives, controls = [], []
            for g in GS:
                data, info = archive_once(pyzstd, archive_state, inputs / src, level, g)
                archives.append(info)
                records = []
                with (inputs / src).open('rb', buffering=0) as source:
                    for n in NS:
                        controls.append(control(pyzstd, part, data, info, n))
                        for rep in range(5):
                            records.append(repeat(pyzstd, part, data, info, source, src, level,
                                                  n, rep, offsets[g][n, rep]))
                            print('REPEAT_SAVED', chunk, label(g), n, rep, flush=True)
                check(hashlib.sha256(data).hexdigest() == info['sha256'], 'resident archive changed')
                write(publish / f'samples-{label(g)}.jsonl.gz',
                      gzip.compress(b''.join(map(packed, records)), compresslevel=6, mtime=0))
            check(sha(inputs / src) == INPUT[src][1], 'source changed during measurement')
            phase = 'end'
            current_load = snapshot(cpu)
            require_idle(current_load)
            check_load_snapshot(current_load, host)
            write(part / 'load-end.json', packed(current_load))
            run_record.update(load_start=start_load, load_end=current_load,
                              load_resume_starts=resumes, load_accepted=True)
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
        except BusyHost as error:
            write(part / 'REJECTED', packed(dict(phase=phase, load=current_load, reason=str(error))))
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
    # Share this lock with the matched C reader; only one measured chunk at once.
    with (STATE / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _run(chunk, inputs, receipt_path, cpu, attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'files'))
    parser.add_argument('chunk', choices=CHUNKS)
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--cpu', type=int, default=0)
    parser.add_argument('--attempt', type=int, default=1)
    args = parser.parse_args()
    if args.action == 'files':
        print('\n'.join(f'evidence/hw-gift-1b/{args.chunk}/{name}' for name in [*FILES, 'SHA256SUMS']))
        return
    check(args.inputs is not None and args.receipt is not None, '--inputs and --receipt required')
    try:
        run(args.chunk, args.inputs, args.receipt, args.cpu, args.attempt)
    except RuntimeError as error:
        from load_guard import BusyHost
        if isinstance(error, BusyHost):
            print(f'REJECTED_BUSY_HOST: {error}', file=sys.stderr)
            raise SystemExit(2)
        raise


if __name__ == '__main__':
    main()
