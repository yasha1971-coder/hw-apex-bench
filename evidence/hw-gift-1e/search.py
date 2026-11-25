"""Replayable, source-informed core search after both primary gates HIT.

The full tag grid must also pass its independent audit. Stages are
endpoints -> root reviews/commits classifier+new admission -> candidates.
Root owns Git checkpoints/publication. This script never commits or pushes.
"""
import argparse
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path

import bisect_core as backend

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'evidence/hw-gift-1e'
PUBLIC = HERE / 'search'
STATE = ROOT / '.work/hw-gift-1e/search'
SUSPECTS = ('e2965edd107acd0123294e23848cdc00af906468',
            '9420bce8a491e21821c4b372f837bf4bd47e5870',
            '91f4c23e634a1d260f290f00b6d870a56cd59ab6')
require, load, sha, save = backend.require, backend.load, backend.sha, backend.save


@contextmanager
def cpu(index):
    before = os.sched_getaffinity(0)
    os.sched_setaffinity(0, {index})
    try:
        require(os.sched_getaffinity(0) == {index}, 'CPU pin did not apply')
        yield
    finally:
        os.sched_setaffinity(0, before)


def ref(path):
    path = Path(path).resolve()
    require(path.is_relative_to(HERE), 'search reference escaped public evidence')
    return dict(path=path.relative_to(HERE).as_posix(), sha256=sha(path))


def copy(source, target):
    data = Path(source).read_bytes()
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        require(target.read_bytes() == data, 'published search bytes changed')
    else:
        with target.open('xb') as stream:
            stream.write(data)
    return ref(target)


def identity(admission_path, candidate=False):
    value = backend.gate(admission_path, candidate=candidate)
    backend.committed(Path(__file__))
    require(value['frontend_sha256'] == sha(__file__), 'search frontend changed')
    return dict(admission_sha256=sha(admission_path), frontend_sha256=sha(__file__),
                backend_sha256=sha(backend.__file__), search_protocol=value['search_protocol'])


def expose_round(record):
    """Copy all raw attempts, including excluded outputs, before a checkpoint."""
    attempts = []
    for attempt in record['attempts']:
        private = Path(attempt['receipt_path'])
        require(sha(private) == attempt['receipt_sha256'], 'private OVH receipt changed')
        folder = PUBLIC / 'raw' / private.parent.relative_to(STATE / 'raw')
        files = {}
        for path in sorted(private.parent.iterdir()):
            require(path.is_file() and path.suffix in ('.json', '.stdout', '.stderr'), 'unexpected raw search artifact')
            files[path.name] = copy(path, folder / path.name)
        receipt = load(private)
        attempts.append(dict(attempt=attempt['attempt'], status=attempt['status'],
                             receipt=files[private.name], files=files))
        require(receipt['status'] == attempt['status'], 'attempt status differs')
    value = dict(status=record['status'], pair_index=record['pair_index'], order=record['order'], attempts=attempts)
    if record['status'] == 'CLEAN':
        result = Path(record['selected_result']['path'])
        require(sha(result) == record['selected_result']['sha256'], 'selected private result changed')
        value['selected_result'] = ref(PUBLIC / 'raw' / result.relative_to(STATE / 'raw'))
        value['selected_receipt'] = attempts[-1]['receipt']
    else:
        value['ps_top8'] = record['ps_top8']
    return value


def verify_pairs(path):
    summary = load(path)
    require(summary['status'] in ('RUNNING', 'COMPLETE', 'BLOCKED: load'), 'invalid paired stage status')
    values = {'C': [], 'R': []}
    for pair, item in enumerate(summary['repeats']):
        require(item['pair_index'] == pair and 1 <= len(item['attempts']) <= 3, 'invalid logical-round accounting')
        for index, attempt in enumerate(item['attempts']):
            require(attempt['attempt'] == index+1, 'attempt sequence changed')
            for reference in attempt['files'].values():
                backend.deref(reference)
            receipt = load(backend.deref(attempt['receipt']))
            require(receipt['status'] == attempt['status'], 'raw attempt status changed')
            require(attempt['status'] == 'LOADED' or (attempt['status'] == 'CLEAN' and index == len(item['attempts'])-1),
                    'round contains a failed/retimed successful attempt')
        if item['status'] == 'BLOCKED: load':
            require(pair == len(summary['repeats'])-1 and len(item['attempts']) == 3
                    and all(a['status'] == 'LOADED' for a in item['attempts']), 'invalid blocked round')
            continue
        require(item['status'] == 'CLEAN' and item['attempts'][-1]['status'] == 'CLEAN', 'selected round is not CLEAN')
        raw = load(backend.deref(item['selected_result']))
        receipt = load(backend.deref(item['selected_receipt']))
        require(receipt['status'] == 'CLEAN' and receipt['returncode'] == 0 and raw['order'] == item['order'], 'selected raw round differs')
        require(receipt['stdout_sha256'] == item['selected_result']['sha256'], 'selected worker file differs from retained raw stdout')
        require(raw['pair_index'] == pair and raw['clock_calls'] == 4 and raw['cpu_affinity'] == [0]
                and raw['lock_path'] == backend.LOCK, 'worker scope/affinity proof differs')
        require(sorted(row['label'] for row in raw['results']) == ['C', 'R'], 'round lost one slot')
        for row in raw['results']:
            require(row['bit_perfect'] and row['seek_checksums_verified'], 'search archive restoration failed')
            values[row['label']].append(row['compression_ns'])
    if summary['status'] == 'COMPLETE':
        require(len(summary['repeats']) == 5, 'completed stage lacks five rounds')
        require(summary['median_C_ns'] == backend.med(values['C'])
                and summary['median_ref_ns'] == backend.med(values['R']), 'saved search medians differ from raw')
    return summary


def paired(request_path, path, frozen_identity):
    if path.exists():
        summary = verify_pairs(path)
        require(summary['identity'] == frozen_identity and summary['request_sha256'] == sha(request_path), 'saved stage identity changed')
        return summary
    with cpu(15):
        check_path = backend.selfcheck(request_path)
    # A private replay file is written after every completed logical round.
    progress = STATE / 'progress' / (load(request_path)['request_id']+'.json')
    records = []
    if progress.exists():
        old = verify_pairs(progress)
        require(old['identity'] == frozen_identity and old['request_sha256'] == sha(request_path), 'private stage progress changed')
        records = old['repeats']
        if records and records[-1]['status'] == 'BLOCKED: load':
            # Return to public finalization; no fourth attempt is admitted.
            pass
    for pair in range(len(records), 5):
        if records and records[-1]['status'] == 'BLOCKED: load':
            break
        with cpu(0):
            record = backend.locked_round(request_path, pair)
        records.append(expose_round(record))
        progress.parent.mkdir(parents=True, exist_ok=True)
        pending = progress.with_suffix('.writing')
        pending.write_bytes(backend.packed(dict(status='RUNNING', identity=frozen_identity, request_sha256=sha(request_path), repeats=records)))
        pending.replace(progress)
        if record['status'] == 'BLOCKED: load':
            break
    value = dict(schema='hw-gift-1e-search-pairs-v1', status='BLOCKED: load' if records[-1]['status'] == 'BLOCKED: load' else 'COMPLETE',
                 identity=frozen_identity, request_sha256=sha(request_path), request=copy(request_path, PUBLIC/'requests'/request_path.name),
                 selfcheck=copy(check_path, PUBLIC/'selfchecks'/check_path.name), repeats=records,
                 planned_repeats=5, started_repeats=len(records),
                 retaken_repeats=sum(len(r['attempts']) > 1 for r in records),
                 loaded_attempts=sum(a['status'] == 'LOADED' for r in records for a in r['attempts']))
    if value['status'] == 'COMPLETE':
        raw = [load(backend.deref(r['selected_result'])) for r in records]
        values = {label: [next(row['compression_ns'] for row in r['results'] if row['label'] == label) for r in raw] for label in ('C', 'R')}
        value.update(median_C_ns=backend.med(values['C']), median_ref_ns=backend.med(values['R']),
                     min_C_ns=min(values['C']), min_ref_ns=min(values['R']))
    else:
        value['ps_top8'] = records[-1]['ps_top8']
    save(path, value)
    return verify_pairs(path)


def endpoints(admission_path):
    frozen = identity(admission_path)
    graph()  # Public ancestry inventory precedes candidate builds.
    request = backend.make_request(None, admission_path)
    path = PUBLIC / 'endpoints.json'
    result = paired(request, path, frozen)
    if result['status'] == 'BLOCKED: load':
        return 2
    slow, reference = result['median_C_ns'], result['median_ref_ns']
    classifier = dict(schema='hw-gift-1e-search-classifier-v1', status='BRACKET' if slow >= 2*reference else 'NO BRACKET',
                      endpoint_summary=ref(path), endpoint_slow_ns=slow, endpoint_reference_ns=reference,
                      guard_numerators=[81, 121], denominator=100,
                      formula='100*C^2*endpoint_ref compared with {81,121}*R^2*endpoint_slow',
                      boundary_equality='INDETERMINATE', identity=frozen, global_first_fast_claim=False)
    save(PUBLIC / 'classifier.json', classifier)
    if classifier['status'] == 'NO BRACKET':
        save(PUBLIC / 'result.json', dict(schema='hw-gift-1e-search-result-v1', status='NO BRACKET', build_count=2,
             tested=[], transition=None, remaining_range=None, endpoint_summary=ref(path),
             S1=dict(available=False, passed=None, verdict='NOT EVALUATED'), counters=totals([ref(path)]),
             global_first_fast_claim=False, reason='Fresh prefix endpoints are separated by less than 2x'))
    print('ENDPOINTS', classifier['status'], 'root must checkpoint/commit classifier before candidates', flush=True)
    return 0


def checked_classifier(admission_path):
    admission = backend.gate(admission_path, candidate=True)
    classifier = load(backend.deref(admission['classifier']))
    summary = verify_pairs(backend.deref(classifier['endpoint_summary']))
    require(summary['status'] == 'COMPLETE' and classifier['endpoint_slow_ns'] == summary['median_C_ns']
            and classifier['endpoint_reference_ns'] == summary['median_ref_ns']
            and classifier['guard_numerators'] == [81, 121] and classifier['denominator'] == 100,
            'classifier does not bind the fresh endpoint raw medians')
    return classifier


def title(commit):
    return backend.git('show', '-s', '--format=%s', commit).decode().strip()


def graph():
    text = backend.git('log', '--format=%H%x09%P%x09%s', backend.OLD+'..'+backend.NEW).decode()
    text += backend.git('show', '-s', '--format=%H%x09%P%x09%s', backend.OLD).decode()
    nodes = {}
    for line in text.splitlines():
        commit, parents, heading = line.split('\t', 2)
        nodes[commit] = dict(commit=commit, parents=parents.split(), title=heading)
    require(nodes[SUSPECTS[1]]['parents'][0] == SUSPECTS[0]
            and nodes[SUSPECTS[2]]['parents'][0] == SUSPECTS[1], 'source-informed parent sequence changed')
    save(PUBLIC/'history.json', dict(schema='hw-gift-1e-search-history-v1', slow=backend.OLD, fast=backend.NEW, nodes=nodes))
    return nodes


def is_ancestor(nodes, slow, fast):
    pending, visited = [fast], set()
    while pending:
        node = pending.pop()
        if node == slow:
            return True
        if node in visited or node not in nodes:
            continue
        visited.add(node)
        pending.extend(nodes[node]['parents'])
    return False


def ancestry_path(nodes, slow, fast):
    if not is_ancestor(nodes, slow, fast):
        return None
    path = [fast]
    while path[-1] != slow:
        parents = [parent for parent in nodes[path[-1]]['parents'] if is_ancestor(nodes, slow, parent)]
        require(parents, 'ancestry path cannot reach measured slow endpoint')
        path.append(parents[0])
    path.reverse()
    return dict(slow=slow, fast=fast, nodes=[nodes[commit] for commit in path],
                edges=[dict(slow=a, fast=b, first_parent=nodes[b]['parents'][0] == a) for a,b in zip(path, path[1:])])


def closest_bracket(tested, nodes):
    choices = []
    for slow in tested:
        for fast in tested:
            if slow['classifier'] != 'SLOW' or fast['classifier'] != 'FAST':
                continue
            path = ancestry_path(nodes, slow['commit'], fast['commit'])
            if path is not None:
                choices.append((len(path['nodes']), slow['commit'], fast['commit'], path))
    require(choices, 'measured endpoints lost their ancestry bracket')
    return min(choices, key=lambda item: item[:3])[3]


def adjacent_transition(tested):
    slow = {row['commit'] for row in tested if row['classifier'] == 'SLOW'}
    for row in tested:
        if row['classifier'] == 'FAST':
            parent = backend.git('rev-parse', row['commit']+'^1').decode().strip()
            if parent in slow:
                return dict(slow_commit=parent, fast_commit=row['commit'], fast_title=row['title'], adjacent_first_parent=True)
    return None


def expose_build(path):
    folder = Path(path).parent
    for artifact in sorted(folder.iterdir()):
        if artifact.is_file() and artifact.suffix in ('.json', '.stdout', '.stderr'):
            copy(artifact, PUBLIC / 'builds' / folder.name / artifact.name)
    reservation = STATE/'reservations'/(folder.name+'.json')
    if reservation.exists():
        copy(reservation, PUBLIC/'reservations'/reservation.name)


def totals(references):
    summaries = {item['sha256']: verify_pairs(backend.deref(item)) for item in references}
    return dict(logical_repeats=sum(s['started_repeats'] for s in summaries.values()),
                attempts=sum(len(r['attempts']) for s in summaries.values() for r in s['repeats']),
                retaken=sum(s['retaken_repeats'] for s in summaries.values()),
                loaded_attempts=sum(s['loaded_attempts'] for s in summaries.values()))


def forecast(tested):
    by_commit = {item['commit']: item['classifier'] for item in tested}
    available = SUSPECTS[0] in by_commit and SUSPECTS[1] in by_commit
    passed = by_commit.get(SUSPECTS[0]) == 'SLOW' and by_commit.get(SUSPECTS[1]) == 'FAST' if available else None
    return dict(available=available, passed=passed, verdict=('HIT' if passed else 'MISS') if available else 'NOT EVALUATED',
                slow_parent=SUSPECTS[0], fast_child=SUSPECTS[1], observed_parent=by_commit.get(SUSPECTS[0]), observed_child=by_commit.get(SUSPECTS[1]))


def candidates(admission_path):
    frozen = identity(admission_path, candidate=True)
    classifier = checked_classifier(admission_path)
    nodes = graph()
    backend.committed(PUBLIC/'history.json')
    endpoint_path = backend.deref(classifier['endpoint_summary'])
    endpoint = verify_pairs(endpoint_path)
    slow, reference = classifier['endpoint_slow_ns'], classifier['endpoint_reference_ns']
    tested = [dict(commit=backend.OLD, title=nodes[backend.OLD]['title'], classifier='SLOW', median_C_ns=slow,
                   median_ref_ns=reference, min_C_ns=endpoint['min_C_ns'], min_ref_ns=endpoint['min_ref_ns'], role='endpoint_candidate', pair_summary=ref(endpoint_path)),
              dict(commit=backend.NEW, title=nodes[backend.NEW]['title'], classifier='FAST', median_C_ns=reference,
                   median_ref_ns=reference, min_C_ns=endpoint['min_ref_ns'], min_ref_ns=endpoint['min_ref_ns'], role='endpoint_reference', pair_summary=ref(endpoint_path))]
    steps = sorted((PUBLIC/'steps').glob('step-*.json'))
    failed = []
    if steps:
        latest = load(steps[-1])
        require(latest['identity'] == frozen, 'candidate step source/admission changed')
        backend.committed(steps[-1])  # Root checkpoints before the next candidate.
        tested, failed = latest['tested'], latest['failed_builds']
        for row in tested:
            verify_pairs(backend.deref(row['pair_summary']))
    final = PUBLIC/'result.json'
    if final.exists():
        require(load(final)['identity'] == frozen, 'terminal search identity changed')
        print('SEARCH_REPLAY', load(final)['status'], flush=True)
        return 0

    def finish(reason, transition=None):
        bracket = closest_bracket(tested, nodes)
        if transition:
            transition.update(on_tag_ancestry_path=is_ancestor(nodes, backend.OLD, transition['slow_commit']),
                              fast_is_ancestor_of_v157=is_ancestor(nodes, transition['fast_commit'], backend.NEW),
                              qualification='measured first-parent source-branch edge; not a global first-fast claim')
        save(final, dict(schema='hw-gift-1e-search-result-v1', identity=frozen,
             status='ADJACENT TRANSITION' if transition else 'NARROWED RANGE', tested=tested, failed_builds=failed,
             build_count=2+len(list((STATE/'reservations').glob('*.json'))), transition=transition,
             remaining_range=dict(slow=bracket['slow'], fast=bracket['fast']),
             selected_path=bracket, history=ref(PUBLIC/'history.json'), S1=forecast(tested),
             counters=totals([row['pair_summary'] for row in tested]), global_first_fast_claim=False, reason=reason,
             source_branch_amendment=load(admission_path).get('source_branch_amendment')))
        print('SEARCH', load(final)['status'], flush=True)
        return 0

    transition = adjacent_transition(tested)
    if transition:
        return finish('Measured adjacent first-parent transition', transition)
    if failed or any(row['classifier'] == 'INDETERMINATE' for row in tested):
        return finish('Build failure or INDETERMINATE; no retakes')
    bracket = closest_bracket(tested, nodes)
    seen = {row['commit'] for row in tested}
    remaining = [commit for commit in SUSPECTS if commit not in seen]
    if remaining:
        commit, selection = remaining[0], 'source-informed'
    else:
        if len(bracket['nodes']) == 2:
            return finish('Adjacent ancestry edge uses a non-first parent; qualified range only')
        commit = bracket['nodes'][(len(bracket['nodes'])-1)//2]['commit']
        selection = 'deterministic ancestry midpoint'
        require(commit not in seen and commit not in (bracket['slow'], bracket['fast']), 'no usable untested interior midpoint')
    if 2+len(list((STATE/'reservations').glob('*.json'))) >= 12 and not (STATE/'builds'/commit/'build.json').exists():
        return finish('12 total distinct-core build budget exhausted')
    sequence = len(steps)+1
    plan = PUBLIC/'plans'/('plan-%03d.json' % sequence)
    save(plan, dict(sequence=sequence, identity=frozen, selection=selection, candidate=nodes[commit],
                    selected_path=bracket, history=ref(PUBLIC/'history.json')))
    try:
        with cpu(15):
            build = backend.build_candidate(commit, admission_path)
    except (backend.subprocess.CalledProcessError, AttributeError, ValueError) as error:
        # Source/admission failures before reservation remain fatal.
        require((STATE/'reservations'/(commit+'.json')).exists(), 'pre-build admission failed: '+str(error))
        failed.append(dict(commit=commit, title=nodes[commit]['title'], status='BUILD FAILED OR INCOMPATIBLE', error=str(error), plan=ref(plan)))
        expose_build(STATE/'builds'/commit/'build.json')
        save(PUBLIC/'steps'/('step-%03d.json' % sequence), dict(identity=frozen, tested=tested, failed_builds=failed, plan=ref(plan)))
        return finish('Failed/incompatible build consumes budget; stopped without retry')
    expose_build(build)
    request = backend.make_request(build, admission_path)
    pair_path = PUBLIC/'pairs'/(commit+'.json')
    summary = paired(request, pair_path, frozen)
    if summary['status'] == 'BLOCKED: load':
        print('SEARCH BLOCKED: load', commit, flush=True)
        return 2
    classification = backend.classify(summary['median_C_ns'], summary['median_ref_ns'], slow, reference)
    tested.append(dict(commit=commit, title=nodes[commit]['title'], classifier=classification,
                       median_C_ns=summary['median_C_ns'], median_ref_ns=summary['median_ref_ns'],
                       min_C_ns=summary['min_C_ns'], min_ref_ns=summary['min_ref_ns'], pair_summary=ref(pair_path),
                       build=ref(PUBLIC/'builds'/commit/'build.json')))
    save(PUBLIC/'steps'/('step-%03d.json' % sequence), dict(identity=frozen, tested=tested, failed_builds=failed, plan=ref(plan)))
    transition = adjacent_transition(tested)
    if transition or classification == 'INDETERMINATE':
        return finish('Measured adjacent transition' if transition else 'INDETERMINATE; stopped without retakes', transition)
    print('SEARCH CHECKPOINT', commit, classification, 'root must commit/push before next invocation', flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('endpoints', 'candidates'))
    parser.add_argument('--admission', required=True, type=Path)
    args = parser.parse_args()
    require(os.name == 'posix' and not os.environ.get('OVH_BENCH_LOCK_HELD'), 'frontend runs outside benchmark lock')
    STATE.mkdir(parents=True, exist_ok=True)
    import fcntl
    with (STATE/'controller.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return endpoints(args.admission.resolve()) if args.stage == 'endpoints' else candidates(args.admission.resolve())


if __name__ == '__main__':
    raise SystemExit(main())
