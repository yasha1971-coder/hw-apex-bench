"""Shared OVH-BENCH command lock; no builds are performed by this module."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

POLICY_COMMIT = '3e7201a0933030de8d3011eb658270e577e6eced'
LOCK_PATH = '/run/lock/ovh-bench.lock'
LOADED_EXIT = 77


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.writing')
    with pending.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    pending.replace(path)


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def load_one(raw):
    value = Decimal(raw.split()[0])
    if not value.is_finite() or value < 0:
        raise ValueError('invalid /proc/loadavg one-minute value')
    return value


def is_loaded(start, end):
    return any(load_one(value['loadavg_raw']) > Decimal('1.0') for value in (start, end))


def boundary():
    from load_guard import process_table, own_tree
    table, errors = process_table()
    excluded = own_tree(table)
    processes = [{k: row[k] for k in ('pid', 'uid', 'comm', 'state', 'ticks')}
                 for pid, row in table.items() if pid not in excluded and row['uid'] >= 1000]
    cpu = next(line.split(':', 1)[1].strip() for line in
               Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name'))
    return dict(timestamp_utc=utc(),
                date_u=subprocess.check_output(['date', '-u'], text=True).strip(),
                loadavg_raw=subprocess.check_output(['cat', '/proc/loadavg'], text=True).strip(),
                nproc=int(subprocess.check_output(['nproc'], text=True).strip()),
                hostname=platform.node(), cpu=cpu, kernel=platform.release(),
                governor=Path('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor').read_text().strip(),
                pinned_core=0, other_processes=processes, process_inspection_errors=errors)


def _assert_flock_parent():
    if sys.platform != 'linux':
        raise ValueError('OVH timing requires Linux flock')
    # The only measured child entry is spawned by the external flock command.
    parent = Path('/proc') / str(os.getppid())
    if (parent / 'comm').read_text().strip() != 'flock':
        raise ValueError('measurement entry must be a child of the shared flock command')


def _inside(receipt_path, command):
    _assert_flock_parent()
    receipt_path = Path(receipt_path)
    record = json.loads(receipt_path.read_bytes())
    if record['status'] != 'WAITING' or record['command'] != command or record['lock_path'] != LOCK_PATH:
        raise ValueError('unexpected pending OVH measurement command')
    record.update(start=boundary(), command_started=False, returncode=None)
    output, errors = b'', b''
    try:
        if load_one(record['start']['loadavg_raw']) <= Decimal('1.0'):
            environment = os.environ.copy()
            environment['OVH_BENCH_LOCK_HELD'] = LOCK_PATH
            record['command_started'] = True
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, env=environment)
            output, errors = result.stdout, result.stderr
            record['returncode'] = result.returncode
        record['end'] = boundary()
        if record['command_started'] and record['returncode'] != 0:
            # A failed byte check or worker error is fatal, even on a loaded
            # host. Only successful timed commands may be retried for load.
            record['status'] = 'ERROR'
            code = record['returncode'] or 1
        elif is_loaded(record['start'], record['end']):
            record['status'] = 'LOADED'
            code = LOADED_EXIT
        elif record['returncode'] == 0:
            record['status'] = 'CLEAN'
            code = 0
        else:
            record['status'] = 'ERROR'
            code = record['returncode'] or 1
        if record['status'] == 'LOADED':
            record['ps_command'] = 'ps -eo pid,user,pcpu,comm --sort=-pcpu | head -8'
            listing = subprocess.check_output(['ps', '-eo', 'pid,user,pcpu,comm', '--sort=-pcpu'], text=True)
            record['ps_top8'] = '\n'.join(listing.splitlines()[:8]) + '\n'
            record['ps_captured_utc'] = utc()
    except BaseException as error:
        record.update(status='ERROR', error=f'{type(error).__name__}: {error}')
        code = 1
    record.update(stdout_sha256=sha(output), stderr_sha256=sha(errors))
    write(Path(str(receipt_path) + '.stdout'), output)
    write(Path(str(receipt_path) + '.stderr'), errors)
    write(receipt_path, packed(record))
    return code


def _deliver(receipt_path, stdout_path):
    receipt = json.loads(receipt_path.read_bytes())
    output = Path(str(receipt_path) + '.stdout').read_bytes()
    errors = Path(str(receipt_path) + '.stderr').read_bytes()
    if sha(output) != receipt['stdout_sha256'] or sha(errors) != receipt['stderr_sha256']:
        raise ValueError('retained measurement output changed')
    if stdout_path is not None:
        write(stdout_path, output)
    elif receipt['status'] == 'CLEAN':
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
    if errors:
        sys.stderr.buffer.write(errors)
        sys.stderr.buffer.flush()
    if receipt['status'] == 'CLEAN':
        return 0
    if receipt['status'] == 'LOADED':
        return LOADED_EXIT
    return receipt.get('returncode') or 1


def run_locked(command, receipt_path, stdout_path=None):
    """Block on the shared lock, retain output, and replay completed commands."""
    if sys.platform != 'linux':
        raise ValueError('OVH timing requires Linux flock')
    command = [str(arg) for arg in command]
    receipt_path = Path(receipt_path).resolve()
    helper_hash = sha(Path(__file__).read_bytes())
    if receipt_path.exists():
        old = json.loads(receipt_path.read_bytes())
        if old.get('command') != command or old.get('helper_sha256') != helper_hash:
            raise ValueError('retained OVH command/source changed')
        if old.get('status') not in ('CLEAN', 'LOADED'):
            raise ValueError('incomplete/error OVH measurement retained; inspect before retrying')
        return _deliver(receipt_path, stdout_path)
    invocation = ['flock', LOCK_PATH, sys.executable, '-B', str(Path(__file__).resolve()),
                  '_inside', '--receipt', str(receipt_path), '--', *command]
    record = dict(schema='ovh-bench-v1', policy_commit=POLICY_COMMIT, lock_path=LOCK_PATH,
                  flock_command=invocation, command=command, status='WAITING',
                  waiting_since_utc=utc(), helper_sha256=helper_hash)
    write(receipt_path, packed(record))
    completed = subprocess.run(invocation, stdin=subprocess.DEVNULL)
    final = json.loads(receipt_path.read_bytes())
    if final.get('status') not in ('CLEAN', 'LOADED', 'ERROR'):
        raise ValueError(f'flock command ended without a receipt ({completed.returncode})')
    return _deliver(receipt_path, stdout_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', '_inside'))
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--stdout', type=Path)
    arguments = sys.argv[1:]
    if arguments in (['-h'], ['--help']):
        parser.parse_args(arguments)
    if '--' not in arguments:
        parser.error('separate the measurement command with --')
    separator = arguments.index('--')
    args = parser.parse_args(arguments[:separator])
    command = arguments[separator + 1:]
    if not command:
        parser.error('measurement command required')
    return _inside(args.receipt, command) if args.action == '_inside' else run_locked(command, args.receipt, args.stdout)


if __name__ == '__main__':
    raise SystemExit(main())
