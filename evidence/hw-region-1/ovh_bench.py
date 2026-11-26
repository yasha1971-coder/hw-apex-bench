"""HW-REGION-1 OVH admission: shared flock, T=1 and foreign CPU at start.

No build or codec is imported. Only the explicit command can perform timing.
Observation sleeps/clock reads occur after flock and before decoder warmups.
"""
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
import time

HERE = Path(__file__).resolve().parent
LOCK_PATH = '/run/lock/ovh-bench.lock'
THREADS = 1
LOADED_EXIT = 77
OBSERVE_SECONDS = 1


def require(ok, message):
    if not ok:
        raise ValueError(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode()


def write(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name+'.writing')
    pending.write_bytes(raw)
    pending.replace(path)


def process_table():
    table, errors = {}, []
    for folder in Path('/proc').iterdir():
        if not folder.name.isdigit():
            continue
        try:
            raw = (folder/'stat').read_text()
            left, right = raw.index('('), raw.rindex(')')
            fields = raw[right+2:].split()
            table[int(folder.name)] = dict(pid=int(folder.name), comm=raw[left+1:right],
                state=fields[0], ppid=int(fields[1]), ticks=int(fields[11])+int(fields[12]),
                start_ticks=int(fields[19]), uid=folder.stat().st_uid, raw_stat=raw)
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (OSError, ValueError, IndexError) as error:
            if folder.exists():
                errors.append(dict(pid=int(folder.name), error=type(error).__name__))
    return table, errors


def own_ancestry(table):
    result, pid = set(), os.getpid()
    while pid in table and pid not in result:
        result.add(pid)
        pid = table[pid]['ppid']
    result.add(pid)
    return result


def foreign_exceeds(delta, hz, interval_ns):
    require(type(delta) is int and delta >= 0 and hz > 0 and interval_ns >= 1000000000,
            'invalid process CPU observation')
    return 10*delta*1000000000 > hz*interval_ns


def cpu_observation():
    started = utc()
    first_ns = time.monotonic_ns()
    before, errors_before = process_table()
    excluded = own_ancestry(before)
    time.sleep(OBSERVE_SECONDS)
    after, errors_after = process_table()
    last_ns = time.monotonic_ns()
    excluded |= own_ancestry(after)
    hz = os.sysconf('SC_CLK_TCK')
    elapsed = last_ns-first_ns
    require(elapsed >= 1000000000 and hz > 0, 'short CPU observation')
    live, exceeded = [], []
    for pid, row in sorted(after.items()):
        if pid in excluded:
            continue
        previous = before.get(pid)
        same = previous is not None and previous['start_ticks'] == row['start_ticks']
        delta = row['ticks']-(previous['ticks'] if same else 0)
        require(delta >= 0, 'process CPU counter regressed')
        # 100*delta/HZ/(ns/1e9)>10, with no display rounding.
        high = foreign_exceeds(delta,hz,elapsed)
        record = dict(pid=pid, start_ticks=row['start_ticks'], uid=row['uid'], comm=row['comm'],
            ticks_delta=delta, observed_since_birth=not same,
            percent_one_cpu=str(Decimal(100)*delta*1000000000/(hz*elapsed)), exceeds_ten_percent=high)
        live.append(record)
        if high:
            exceeded.append(record)
    return dict(start_utc=started, end_utc=utc(), interval_ns=elapsed, hz=hz,
        before=list(before.values()), after=list(after.values()), excluded_ancestry=sorted(excluded),
        exited_pids=sorted(set(before)-set(after)), live_processes=live, exceeded=exceeded,
        inspection_errors=errors_before+errors_after,
        method='one-second ticks delta; surviving processes at admission; new PID uses ticks since birth')


def boundary():
    cpu = next(line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
               if line.startswith('model name'))
    load = subprocess.check_output(['cat','/proc/loadavg'], text=True).strip()
    value = Decimal(load.split()[0])
    require(value.is_finite() and value >= 0, 'invalid load1')
    return dict(timestamp_utc=utc(), date_u=subprocess.check_output(['date','-u'],text=True).strip(),
        loadavg_raw=load, nproc=int(subprocess.check_output(['nproc'],text=True).strip()),
        host_logical_cpus=os.cpu_count(), cpu=cpu, hostname=platform.node(), kernel=platform.release(),
        governor=Path('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor').read_text().strip(),
        pinned_core=0, timed_threads=THREADS, load1_minus_T=str(value-THREADS),
        proc_stat_raw=Path('/proc/stat').read_text())


def other_cpu_delta(start, end):
    def parse(raw):
        result = {}
        for line in raw.splitlines():
            cells = line.split()
            if cells and cells[0].startswith('cpu') and cells[0][3:].isdigit():
                result[cells[0]] = list(map(int,cells[1:9]))
        return result
    first, last = parse(start['proc_stat_raw']), parse(end['proc_stat_raw'])
    require(first.keys() == last.keys() and 'cpu0' in first, 'CPU accounting set changed')
    result = {}
    for name in first:
        if name == 'cpu0':
            continue
        delta = [b-a for a,b in zip(first[name],last[name])]
        require(len(delta)==8 and min(delta)>=0, 'CPU accounting regressed')
        total, busy = sum(delta), sum(delta)-delta[3]-delta[4]
        result[name] = dict(total_jiffies=total,busy_jiffies=busy,
            idle_jiffies=delta[3],iowait_jiffies=delta[4],
            busy_percent=str(Decimal(100)*busy/total) if total else None)
    return dict(pinned_core=0, observational_only=True, cpus=result)


def loaded(start, end, foreign):
    return (any(Decimal(item['loadavg_raw'].split()[0])-THREADS > Decimal('1.0')
                for item in (start,end)) or bool(foreign['exceeded']))


def _inside(receipt_path, command):
    require(sys.platform=='linux' and Path('/proc',str(os.getppid()),'comm').read_text().strip()=='flock',
            'timing entry must be the external flock child')
    record = json.loads(receipt_path.read_bytes())
    require(record['status']=='WAITING' and record['command']==command and record['lock_path']==LOCK_PATH,
            'unexpected waiting command')
    output, errors, code = b'', b'', 1
    record.update(command_started=False, returncode=None)
    try:
        record['foreign_cpu_start'] = cpu_observation()
        record['start'] = boundary()
        require(not record['foreign_cpu_start']['inspection_errors'], 'uninspectable process telemetry')
        if not loaded(record['start'],record['start'],record['foreign_cpu_start']):
            environment = os.environ.copy()
            environment['OVH_BENCH_LOCK_HELD'] = LOCK_PATH
            record['command_started'] = True
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, env=environment)
            output, errors, record['returncode'] = result.stdout, result.stderr, result.returncode
        record['end'] = boundary()
        delta = other_cpu_delta(record['start'],record['end'])
        record['start']['other_cpu_delta'] = delta
        record['end']['other_cpu_delta'] = delta
        if record['command_started'] and record['returncode'] != 0:
            record['status'],code = 'ERROR',record['returncode'] or 1
        elif loaded(record['start'],record['end'],record['foreign_cpu_start']):
            record['status'],code = 'LOADED',LOADED_EXIT
        else:
            require(record['returncode']==0, 'command did not execute')
            record['status'],code = 'CLEAN',0
        if record['status']=='LOADED':
            record['ps_command'] = 'ps -eo pid,user,pcpu,comm --sort=-pcpu | head -8'
            record['ps_top8'] = subprocess.check_output(['bash','-c',record['ps_command']],text=True)
    except BaseException as error:
        record.update(status='ERROR',error=f'{type(error).__name__}: {error}')
        code = 1
    record.update(stdout_sha256=sha(output),stderr_sha256=sha(errors))
    write(str(receipt_path)+'.stdout',output)
    write(str(receipt_path)+'.stderr',errors)
    write(receipt_path,packed(record))
    return code


def deliver(path, stdout_path):
    record = json.loads(path.read_bytes())
    output, errors = Path(str(path)+'.stdout').read_bytes(),Path(str(path)+'.stderr').read_bytes()
    require(sha(output)==record['stdout_sha256'] and sha(errors)==record['stderr_sha256'], 'retained output changed')
    if stdout_path:
        write(stdout_path,output)
    if errors:
        sys.stderr.buffer.write(errors)
    return 0 if record['status']=='CLEAN' else LOADED_EXIT if record['status']=='LOADED' else record.get('returncode') or 1


def run_locked(command, receipt_path, stdout_path=None):
    require(sys.platform=='linux', 'OVH timing requires Linux')
    command = list(map(str,command))
    path = Path(receipt_path).resolve()
    helper_sha = sha(Path(__file__).read_bytes())
    if path.exists():
        record = json.loads(path.read_bytes())
        require(record['command']==command and record['helper_sha256']==helper_sha
                and record['protocol_sha256']==sha((HERE/'PROTOCOL.md').read_bytes())
                and record['calibration_sha256']==sha((HERE/'CALIBRATION.md').read_bytes())
                and record['status'] in ('CLEAN','LOADED'), 'incomplete/error or changed retained attempt')
        return deliver(path,stdout_path)
    invocation = ['flock',LOCK_PATH,sys.executable,'-B',str(Path(__file__).resolve()),
                  '_inside','--receipt',str(path),'--',*command]
    record = dict(schema='hw-region-1-ovh-v1',command=command,flock_command=invocation,lock_path=LOCK_PATH,
        helper_sha256=helper_sha,protocol_sha256=sha((HERE/'PROTOCOL.md').read_bytes()),
        calibration_sha256=sha((HERE/'CALIBRATION.md').read_bytes()),status='WAITING',
        waiting_since_utc=utc(),timed_threads=THREADS,foreign_cpu_percent_threshold='10.0')
    write(path,packed(record))
    completed = subprocess.run(invocation,stdin=subprocess.DEVNULL)
    record = json.loads(path.read_bytes())
    require(record['status'] in ('CLEAN','LOADED','ERROR'), f'flock returned without complete receipt: {completed.returncode}')
    return deliver(path,stdout_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('run','_inside'))
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--stdout',type=Path)
    arguments = sys.argv[1:]
    require('--' in arguments, 'separate explicit command with --')
    split = arguments.index('--')
    args,command = parser.parse_args(arguments[:split]),arguments[split+1:]
    require(command,'missing command')
    return _inside(args.receipt.resolve(),command) if args.action=='_inside' else run_locked(command,args.receipt,args.stdout)


if __name__=='__main__':
    raise SystemExit(main())
