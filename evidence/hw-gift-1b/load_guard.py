"""Record quiet-window receipts. No benchmark, governor change or process control."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import time


class BusyHost(RuntimeError):
    pass


# OS daemons are recorded separately from foreign user work. Interactive agents
# are deliberately absent: their observed CPU activity also makes a window busy.
SYSTEM = {
    'systemd', 'systemd-journal', 'systemd-udevd', 'systemd-resolve',
    'systemd-network', 'systemd-timesyn', 'dbus-daemon', 'sshd', 'cron',
    'rsyslogd', 'irqbalance', 'polkitd', 'networkd-dispat', 'unattended-upgr',
    'containerd', 'dockerd', 'containerd-shim', 'cloudflared', 'snapd',
    'accounts-daemon', 'multipathd', 'udisksd', 'upowerd', 'fwupd', 'ntpd',
    'chronyd', 'agetty', 'login', 'rpcbind', 'rpc.statd', 'nscd',
}
COMPUTE = re.compile(r'^(?:cc1(?:plus)?|gcc(?:-\d+)?|g\+\+(?:-\d+)?|clang.*|'
                     r'make|gmake|ninja|cmake|ctest|lzbench|fz_.*|aceapex.*|'
                     r'aeterna.*|zstd|seekable_compre|pytest|stress.*)$', re.I)


def utc():
    return datetime.now(timezone.utc).isoformat()


def process_table(proc=Path('/proc')):
    result, errors = {}, []
    for folder in proc.iterdir():
        if not folder.name.isdigit():
            continue
        try:
            raw = (folder / 'stat').read_text()
            left, right = raw.index('('), raw.rindex(')')
            fields = raw[right + 2:].split()
            cmdline = (folder / 'cmdline').read_bytes()
            # Empty cmdline denotes kernel threads or processes already exiting.
            if not cmdline:
                continue
            result[int(folder.name)] = dict(
                pid=int(folder.name), comm=raw[left + 1:right], state=fields[0],
                ppid=int(fields[1]), ticks=int(fields[11]) + int(fields[12]),
                start_ticks=int(fields[19]), uid=folder.stat().st_uid)
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (OSError, ValueError, IndexError) as error:
            errors.append(dict(pid=int(folder.name), error=type(error).__name__))
    return result, errors


def own_tree(table):
    """Exclude this observer and its controlling ancestry, never other sessions."""
    excluded, pid = {os.getpid()}, os.getpid()
    while pid in table and pid > 1:
        excluded.add(pid)
        pid = table[pid]['ppid']
    excluded.add(pid)
    return excluded


def classify(before, after, excluded):
    active, system = [], []
    for pid in sorted(set(before) | set(after)):
        if pid in excluded:
            continue
        current = after.get(pid, before.get(pid))
        previous = before.get(pid)
        same = previous is not None and previous['start_ticks'] == current['start_ticks']
        delta = max(0, current['ticks'] - (previous['ticks'] if same else 0))
        known_compute = COMPUTE.fullmatch(current['comm']) is not None
        is_system = current['uid'] < 1000 and current['comm'] in SYSTEM and not known_compute
        record = {key: current[key] for key in ('pid', 'start_ticks', 'uid', 'comm', 'state')}
        record['cpu_ticks_delta'] = delta
        if is_system:
            if delta:
                system.append(record)
        elif delta or known_compute or (pid not in after and current['state'] in ('R', 'D')):
            active.append(record)
    return active, system


def snapshot(cpu=0, interval=2.0):
    if platform.system() != 'Linux' or interval < 1:
        raise ValueError('Linux and at least one second of load observation required')
    started, start_ns = utc(), time.monotonic_ns()
    before, first_errors = process_table()
    excluded = own_tree(before)
    time.sleep(interval)
    after, last_errors = process_table()
    excluded |= own_tree(after)
    active, system = classify(before, after, excluded)
    errors = first_errors + last_errors
    model = next(line.split(':', 1)[1].strip() for line in
                 Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name'))
    governor = Path(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor').read_text().strip()
    return dict(sample_start_utc=started, sample_end_utc=utc(),
                interval_ns=time.monotonic_ns() - start_ns, hostname=platform.node(),
                cpu=model, kernel=platform.release(), governor=governor, pinned_core=cpu,
                loadavg=list(os.getloadavg()),
                other_load=dict(busy=bool(active or errors), active_processes=active,
                                inspection_errors=errors),
                os_daemon_activity=system, excluded_observer_ancestry=sorted(excluded),
                method='two /proc process snapshots; any foreign CPU tick or known compute process makes busy; OS daemon ticks recorded separately')


def require_idle(receipt):
    load = receipt.get('other_load', {})
    valid = (receipt.get('hostname') == 'ace-core'
             and 'AMD EPYC 4344P' in receipt.get('cpu', '')
             and receipt.get('pinned_core') == 0
             and isinstance(receipt.get('governor'), str) and bool(receipt['governor'])
             and type(receipt.get('interval_ns')) is int and receipt['interval_ns'] >= 1000000000
             and load.get('busy') is False and load.get('active_processes') == []
             and load.get('inspection_errors') == [])
    if not valid:
        raise BusyHost('host/load receipt is not an accepted idle ace-core CPU-0 window')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu', type=int, default=0)
    parser.add_argument('--interval', type=float, default=2.0)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    receipt = snapshot(args.cpu, args.interval)
    data = json.dumps(receipt, sort_keys=True, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding='utf-8')
    else:
        print(data, end='')
    try:
        require_idle(receipt)
    except BusyHost:
        raise SystemExit(2)
