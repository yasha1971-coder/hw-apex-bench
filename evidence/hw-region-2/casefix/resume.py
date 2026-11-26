# SPDX-License-Identifier: Apache-2.0
"""Owner-authorized, polling-admitted continuation without changing the cohort.

CLI poll performs one observational admission poll; step performs at most one
new locked attempt; status only materializes/verifies the current ledger.
After an inadmissible poll or LOADED attempt, poll waits at least 300 seconds.
After CLEAN, the next target may be polled immediately. No internal long sleep.
"""
import argparse
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STATE = ROOT / '.work/hw-region-2/casefix'
AREA = HERE / 'resume'
QUOTE = 'T2T-15: 3 попытки LOADED из-за постороннего cc1plus ~99 % CPU; выдан новый бюджет 3 попытки для того же прохода'
ALIAS = dict(corpus='t2t-15', profile='twobit_original_mask1', unit_id='t2t-15-resume-1')
INTERVAL = 300
PROTOCOL_COMMIT = 'ae84313194d36a4e5fd61e98383088408f43fe09'


def require(ok, why):
    if not ok:
        raise ValueError(why)


def utc():
    return datetime.now(timezone.utc)


def stamp(value):
    return datetime.fromisoformat(value)


def load(path):
    return json.loads(Path(path).read_bytes())


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    path = Path(path).resolve()
    require(path.is_relative_to(HERE), 'resume reference escaped casefix')
    return dict(path=path.relative_to(HERE).as_posix(), sha256=sha(path))


def deref(record):
    path = (HERE / record['path']).resolve()
    require(path.is_relative_to(HERE) and path.is_file() and sha(path) == record['sha256'], 'retained resume evidence changed')
    return path


def immutable(path, value):
    path = Path(path); raw = value if isinstance(value, bytes) else packed(value)
    require(path.resolve().is_relative_to(HERE) or path.resolve().is_relative_to(STATE), 'resume output escaped owned scope')
    if path.exists():
        require(path.read_bytes() == raw, 'resume output changed: ' + str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as out:
            out.write(raw)


def module(name):
    spec = importlib.util.spec_from_file_location('_resume_' + name, HERE / (name + '.py'))
    value = importlib.util.module_from_spec(spec); sys.modules[spec.name] = value; spec.loader.exec_module(value)
    return value


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args]).decode().strip()


def authorization():
    drive = module('drive'); drive.admitted(); drive.verify_aa(); drive.verify_controls(); drive.native_build()
    protocol, controller = HERE / 'RESUME_PROTOCOL.md', Path(__file__).resolve()
    require(QUOTE in protocol.read_text(encoding='utf-8'), 'owner-authorized exact resume quote missing')
    names = [p.relative_to(ROOT).as_posix() for p in (protocol, controller)]
    require(subprocess.check_output(['git', '-C', str(ROOT), 'show', PROTOCOL_COMMIT + ':' + names[0]]) == protocol.read_bytes(),
            'first committed resume protocol changed')
    git('ls-files', '--error-unmatch', '--', *names)
    require(not git('status', '--porcelain', '--', *names), 'resume protocol/controller must be committed first')
    current = dict(controller_sha256=sha(controller), protocol_sha256=sha(protocol), core_source_sha256=drive.source_map(),
                   native_build_sha256=sha(HERE / 'native/build.json'), setup_sha256=sha(HERE / 'setup.json'))
    path = AREA / 'authorization.json'
    if path.exists():
        value = load(path)
        require(all(value[k] == v for k, v in current.items()), 'resume source/authorization changed')
        for r in value['retained_case_refs'] + value['retained_clean_units'] + [value['original_blocked_unit'], value['original_checkpoint']]:
            deref(r)
        return value
    old_path = HERE / 'units/main/t2t-15/twobit_original_mask1.json'; old = load(old_path)
    require(old['status'] == 'BLOCKED: load' and old['selected'] is None and len(old['attempts']) == 3
            and all(a['status'] == 'LOADED' and a['observation'] is None for a in old['attempts']), 'original three-LOADED unit differs')
    for a in old['attempts']:
        r = load(deref(a['receipt']))
        require(r['command_started'] is False and r['status'] == 'LOADED', 'original admissions must remain never-started')
    checkpoint = HERE / 'audit/checkpoint.json'; verified = load(checkpoint)
    require(verified['status'] == 'PASS' and verified['completion'] == 'BLOCKED: load'
            and verified['counts']['cases'] == 16 and verified['counts']['rows'] == 96, 'retained prefix integrity checkpoint required')
    retained = [ref(p) for p in sorted((HERE / 'units').rglob('*.json')) if load(p).get('status') == 'CLEAN']
    require(len(retained) == 112, 'exactly 96 old main and 16 old method CLEAN units must be anchored')
    cases = [ref(HERE / 'cases' / (c + '.json')) for c in drive.CORPORA[:16]]
    require(cases == verified['case_refs'], 'original sixteen case references differ')
    value = dict(schema='hw-region-2-casefix-resume-authorization-v1', status='AUTHORIZED', **current,
                 controller=ref(controller), protocol=ref(protocol), original_checkpoint=ref(checkpoint), original_blocked_unit=ref(old_path),
                 retained_case_refs=cases, retained_clean_units=retained, alias=ALIAS, max_attempts=3, poll_interval_seconds=INTERVAL,
                 protocol_commit=PROTOCOL_COMMIT,
                 controller_commit=git('log', '-1', '--format=%H', '--', names[1]), initial_head=git('rev-parse', 'HEAD'))
    immutable(path, value)
    return value


def unit_paths(target):
    profile, name = target['profile'], target['unit_id']
    return HERE / 'units/main' / name / (profile + '.json'), HERE / 'raw/main' / name / profile, STATE / 'captures/main' / name / profile


def budget_status(statuses):
    require(len(statuses) <= 3 and all(s in ('CLEAN', 'LOADED') for s in statuses), 'invalid/fourth actual attempt')
    require('CLEAN' not in statuses[:-1], 'attempt exists after first CLEAN')
    if statuses and statuses[-1] == 'CLEAN':
        return 'CLEAN'
    return 'BLOCKED: load' if len(statuses) == 3 else 'WAITING'


def target_order(corpus, corpora, profiles):
    offset = corpora.index(corpus) % len(profiles)
    return profiles[offset:] + profiles[:offset]


def cooldown_deadline(waiting_poll_ends, loaded_attempt_ends):
    dates = [stamp(t) + timedelta(seconds=INTERVAL) for t in [*waiting_poll_ends, *loaded_attempt_ends]]
    return max(dates) if dates else None


def passed_poll(record, target, consumed):
    return record['status'] == 'PASS' and record['target'] == target and not consumed


def consumption_for(receipt):
    matches = [p for p in (AREA / 'consumptions').glob('poll-*.json') if load(p)['receipt_path'] == receipt.relative_to(HERE).as_posix()]
    require(len(matches) == 1, 'attempt needs exactly one previously committed poll consumption')
    return matches[0], load(matches[0])


def attempts(target, case, trace, recover=False):
    drive = module('drive'); _, raw, private = unit_paths(target)
    result = []
    folders = sorted(raw.glob('attempt-*')) if raw.exists() else []
    require([p.name for p in folders] == ['attempt-' + str(i) for i in range(1, len(folders) + 1)] and len(folders) <= 3,
            'nonsequential or fourth resumed attempt')
    identity = drive.unit_identity('latency', target['profile'], case, trace, False, False)
    for number, folder in enumerate(folders, 1):
        receipt = folder / 'ovh-bench.json'
        require(receipt.exists(), 'reserved attempt has no receipt; inspect without retiming')
        record = load(receipt); token_path, token = consumption_for(receipt)
        prefix = private / folder.name / 'out'
        command = drive.worker_command('latency', target['profile'], case, trace, prefix)
        require(record['status'] in ('CLEAN', 'LOADED') and record['command'] == command
                and record['helper_sha256'] == sha(HERE / 'ovh_bench.py')
                and token['attempt_number'] == number and token['target'] == target
                and token['authorization'] == ref(AREA / 'authorization.json'), 'error/incomplete/changed resumed attempt')
        observation = folder / 'observation.json'
        if record['command_started'] and recover:
            for stream in ('stdout', 'stderr'):
                raw_stream = Path(str(receipt) + '.' + stream)
                require(sha(raw_stream) == record[stream + '_sha256'], 'retained helper stream changed')
                immutable(folder / ('worker.' + stream), raw_stream.read_bytes())
            try:
                drive.parse_observation(folder, prefix, identity, case, trace)
            except Exception as error:
                drive.stop('resumed capture validation failed: ' + str(error), dict(receipt=ref(receipt)))
        require(record['status'] != 'CLEAN' or observation.exists(), 'CLEAN attempt requires retained observation; run step to finalize')
        result.append(dict(number=number, status=record['status'], receipt=ref(receipt),
                           observation=ref(observation) if observation.exists() else None,
                           admission_poll=token['poll'], poll_consumption=ref(token_path)))
        if record['status'] == 'CLEAN':
            require(number == len(folders), 'later attempt exists after first CLEAN')
    return identity, result


def finish_unit(target, case, trace):
    path, _, _ = unit_paths(target)
    if path.exists():
        value = load(path)
        require(value['resume_authorization'] == ref(AREA / 'authorization.json'), 'resumed unit authorization differs')
        return value
    identity, history = attempts(target, case, trace, recover=True)
    status = budget_status([a['status'] for a in history])
    if status == 'CLEAN':
        value = dict(schema='hw-region-2-casefix-unit-v1', status='CLEAN', identity=identity, attempts=history,
                     selected=history[-1]['observation'], resume_authorization=ref(AREA / 'authorization.json'))
    elif status == 'BLOCKED: load':
        value = dict(schema='hw-region-2-casefix-unit-v1', status='BLOCKED: load', identity=identity, attempts=history,
                     selected=None, resume_authorization=ref(AREA / 'authorization.json'))
    else:
        return None
    immutable(path, value)
    return value


def next_target():
    drive = module('drive')
    for corpus in drive.CORPORA:
        current_case = HERE / 'cases' / (corpus + '.json')
        if current_case.exists():
            value = load(current_case)
            require(value['status'] == 'COMPLETE' and value['source_sha256'] == drive.source_map(), 'completed case changed')
            for r in value['units'].values():
                deref(r)
            continue
        order = target_order(corpus, drive.CORPORA, drive.PROFILES)
        units = {}
        for profile in order:
            target = dict(corpus=corpus, profile=profile, unit_id=ALIAS['unit_id'] if (corpus, profile) == (ALIAS['corpus'], ALIAS['profile']) else corpus)
            path, raw, _ = unit_paths(target)
            if not path.exists():
                return target
            value = load(path)
            require(value['identity']['source_sha256'] == drive.source_map(), 'unit source changed')
            if value['status'] != 'CLEAN':
                return target
            units[profile] = ref(path)
        value = dict(schema='hw-region-2-casefix-case-v1', status='COMPLETE', corpus=corpus, order=list(order),
                     source_sha256=drive.source_map(), admission=drive.ref(HERE / 'admission.json'), aa=drive.ref(HERE / 'method-aa.json'),
                     controls=drive.ref(HERE / 'controls.json'), archive_case=drive.ref(HERE / 'archives' / (corpus + '.json')),
                     units=units, resume_authorization=ref(AREA / 'authorization.json'))
        immutable(current_case, value)
    return None


def polls():
    result = sorted((AREA / 'polls').glob('poll-*.json')) if (AREA / 'polls').exists() else []
    require([p.name for p in result] == [f'poll-{n:06d}.json' for n in range(1, len(result) + 1)], 'poll history gap')
    return result


def next_due():
    failed = [load(p)['observed_end_utc'] for p in polls() if load(p)['status'] == 'WAITING']
    loaded = []
    for p in (HERE / 'raw/main').rglob('ovh-bench.json'):
        if any(c['receipt_path'] == p.relative_to(HERE).as_posix() for c in
               [load(t) for t in (AREA / 'consumptions').glob('poll-*.json')]):
            record = load(p)
            if record['status'] == 'LOADED':
                loaded.append(record['end']['timestamp_utc'])
    return cooldown_deadline(failed, loaded)


def ready_poll(target):
    history = polls()
    if not history:
        return None
    path = history[-1]; record = load(path)
    consumed = AREA / 'consumptions' / path.name
    return path if passed_poll(record, target, consumed.exists()) else None


def ledger(last_action=None):
    auth = authorization(); target = next_target(); deadline = next_due()
    alias_path, _, _ = unit_paths(ALIAS)
    status = 'COMPLETE' if target is None else 'READY' if ready_poll(target) else 'WAITING'
    if target is not None:
        path, raw, _ = unit_paths(target)
        used = len(list(raw.glob('attempt-*'))) if raw.exists() else 0
        if path.exists() and load(path)['status'] == 'BLOCKED: load':
            status = 'BLOCKED: load'
        target = dict(**target, attempts_used=used, max_attempts=3)
    error = AREA / 'ERROR.json'
    if error.exists():
        status = 'ERROR'
    value = dict(schema='hw-region-2-casefix-resume-ledger-v1', authorization=ref(AREA / 'authorization.json'),
                 original_blocked_unit=auth['original_blocked_unit'], resumed_unit=ref(alias_path) if alias_path.exists() else None,
                 status=status, next_target=target, next_due_utc=deadline.isoformat() if deadline and utc() < deadline else None,
                 polls=[ref(p) for p in polls()], consumptions=[ref(p) for p in sorted((AREA / 'consumptions').glob('poll-*.json'))],
                 completed_case_refs=[ref(HERE / 'cases' / (c + '.json')) for c in module('drive').CORPORA if (HERE / 'cases' / (c + '.json')).exists()])
    if error.exists():
        value['error'] = ref(error)
    if last_action is not None:
        value['last_action'] = last_action
    path = AREA / 'ledger.json'; path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix('.writing'); pending.write_bytes(packed(value)); pending.replace(path)
    return value


def poll():
    authorization()
    if (AREA / 'ERROR.json').exists():
        return ledger(dict(status='ERROR', reason='retained fatal poll error; no further observations or attempts'))
    target = next_target()
    if target is None:
        return ledger()
    unit, _, _ = unit_paths(target)
    if unit.exists() and load(unit)['status'] == 'BLOCKED: load':
        return ledger()
    deadline = next_due()
    if deadline and utc() < deadline:
        return ledger(dict(status='WAITING', reason='300-second cooldown; no new observation', next_due_utc=deadline.isoformat()))
    if ready_poll(target):
        return ledger(dict(status='READY', reason='unused passed poll already available'))
    helper = module('ovh_bench')
    value = dict(schema='hw-region-2-casefix-resume-poll-v1', authorization=ref(AREA / 'authorization.json'), target=target,
                 observed_start_utc=utc().isoformat(), no_native_calls=True, status='ERROR')
    try:
        value['start'] = helper.boundary(); value['foreign_cpu_start'] = helper.cpu_observation(); value['end'] = helper.boundary()
        require(not value['foreign_cpu_start']['inspection_errors'], 'uninspectable process telemetry')
        value['status'] = 'WAITING' if helper.loaded(value['start'], value['end'], value['foreign_cpu_start']) else 'PASS'
    except Exception as error:
        value['error'] = str(error)
    value['observed_end_utc'] = utc().isoformat()
    path = AREA / 'polls' / f'poll-{len(polls())+1:06d}.json'; immutable(path, value)
    if value['status'] == 'ERROR':
        immutable(AREA / 'ERROR.json', dict(schema='hw-region-2-casefix-resume-error-v1', status='ERROR',
                  authorization=ref(AREA / 'authorization.json'), reason=value['error'], poll=ref(path)))
    return ledger(dict(status=value['status'], poll=ref(path)))


def step():
    authorization()
    if (AREA / 'ERROR.json').exists():
        return ledger(dict(status='ERROR', reason='retained fatal poll error; no further observations or attempts'))
    target = next_target()
    if target is None:
        return ledger()
    drive = module('drive'); case, trace = drive.load_case(target['corpus']), drive.load_trace(target['corpus'])
    finished = finish_unit(target, case, trace)
    if finished:
        return ledger(dict(status=finished['status'], finalized_without_worker=True, unit=ref(unit_paths(target)[0])))
    poll_path = ready_poll(target)
    if poll_path is None:
        return ledger(dict(status='WAITING', reason='a fresh, unused PASS poll is required; run poll when due'))
    deadline = next_due()
    require(deadline is None or utc() >= deadline, 'cooldown remains active')
    identity, history = attempts(target, case, trace)
    number = len(history) + 1; require(number <= 3, 'no fourth attempt is authorized')
    _, raw, private = unit_paths(target); folder = raw / ('attempt-' + str(number)); prefix = private / folder.name / 'out'
    require(not folder.exists() and not prefix.parent.exists(), 'orphan attempt cannot be retimed')
    receipt = folder / 'ovh-bench.json'
    token = dict(schema='hw-region-2-casefix-resume-consumption-v1', authorization=ref(AREA / 'authorization.json'),
                 poll=ref(poll_path), target=target, attempt_number=number, receipt_path=receipt.relative_to(HERE).as_posix(),
                 committed_before_attempt_utc=utc().isoformat())
    immutable(AREA / 'consumptions' / poll_path.name, token)
    folder.mkdir(parents=True); prefix.parent.mkdir(parents=True)
    argv = drive.worker_command('latency', target['profile'], case, trace, prefix)
    code = module('ovh_bench').run_locked(argv, receipt, stdout_path=folder / 'worker.stdout')
    record = load(receipt)
    immutable(folder / 'worker.stderr', Path(str(receipt) + '.stderr').read_bytes())
    if code not in (0, 77) or record['status'] == 'ERROR':
        drive.failure(folder, record.get('returncode') or code, prefix)
    finish_unit(target, case, trace)
    return ledger(dict(status=record['status'], attempt_number=number, receipt=ref(receipt), poll=ref(poll_path)))


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('action', choices=('poll', 'step', 'status')); args = p.parse_args()
    require(sys.platform == 'linux' and not os.environ.get('OVH_BENCH_LOCK_HELD'), 'Linux controller outside benchmark lock required')
    os.sched_setaffinity(0, {15})
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'resume-controller.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('another resume command is active; inspect the retained ledger without starting another command')
        value = {'poll': poll, 'step': step, 'status': ledger}[args.action]()
    print(packed(value).decode(), end='')
    return 1 if value['status'] in ('ERROR', 'BLOCKED: load') else 0


if __name__ == '__main__':
    sys.exit(main())
