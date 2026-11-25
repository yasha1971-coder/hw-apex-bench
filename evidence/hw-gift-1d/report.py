"""Render the final HW-GIFT-1d artifacts from complete, audited saved data.

No worker, codec, clock, build, Git command or network operation is called here.
The complete independent --stage all audit must exist before grid files are read.
"""
import argparse
import csv
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEVELS = (3, 10, 19)
GRIDS = (256, 1024, 4096, 16384, 65536, 262144, 524288)
CANDIDATES = (1024, 4096, 16384, 65536)
KEYS = {(l, g) for l in LEVELS for g in GRIDS}
PREFIX = 16777216


def check(ok, reason):
    if not ok:
        raise ValueError(reason)


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            check(key not in value, 'duplicate JSON key: ' + key)
            value[key] = item
        return value
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


def positive(value):
    return type(value) is int and value > 0


def median5(values):
    check(isinstance(values, list) and len(values) == 5 and all(positive(n) for n in values),
          'five positive integer observations required')
    return sorted(values)[2]


def public(root, name):
    check(isinstance(name, str) and name, 'missing public evidence path')
    path = (root / name).resolve()
    check(path.is_relative_to(root.resolve()), 'evidence path escapes experiment')
    return path


def reference(root, item):
    check(isinstance(item, dict), 'missing evidence reference')
    path = public(root, item['path'])
    check(sha(path) == item['sha256'], 'evidence hash changed: ' + item['path'])
    return load(path), path


def bound(root, summary, prefix):
    return reference(root, dict(path=summary[prefix + '_path'], sha256=summary[prefix + '_sha256']))[0]


def fraction_text(numerator, denominator, places=6):
    with localcontext() as context:
        context.prec = 50
        return f'{Decimal(numerator) / Decimal(denominator):.{places}f}'


def ms(value):
    return fraction_text(value, 1000000)


def ratio(numerator, denominator):
    return fraction_text(numerator, denominator)


def delta_percent(value, baseline):
    return fraction_text(100 * (value - baseline), baseline, 4)


def table(headers, rows):
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(map(cell, headers)) + ' |',
                      '| ' + ' | '.join('---' for _ in headers) + ' |'] +
                     ['| ' + ' | '.join(map(cell, row)) + ' |' for row in rows])


def link(path, label=None):
    return f'[{label or path}]({path})'


def audit_gate(root, path):
    """Deliberately called before opening any grid or selection result."""
    value = load(path)
    check(value.get('status') == 'PASS' and value.get('stage') == 'all',
          'complete independent audit --stage all PASS required; partial data are not rendered')
    check(value.get('saved_data_only') is True and value.get('no_codecs_or_clocks_executed') is True,
          'audit must declare saved-data-only verification')
    check(value.get('training_cells') == 21 and value.get('holdout_cells') == 21,
          'audit does not cover the complete baseline grid')
    check(isinstance(value.get('literal_verdicts'), dict) and isinstance(value.get('phase_counters'), dict),
          'final audit is missing verdicts/counters')
    bindings = value.get('source_bindings')
    check(isinstance(bindings, list) and bindings, 'final audit requires retained source bindings')
    seen = set()
    # The independent auditor also reads a few pinned 1b/1c anchors. Every
    # binding remains within repo/evidence; no private work file is opened here.
    for item in bindings:
        name = item['path']
        check(isinstance(name, str) and name and name not in seen, 'duplicate/invalid audit source binding')
        seen.add(name)
        bound_path = (root / name).resolve()
        check(bound_path.is_relative_to(root.parent.resolve()), 'audit binding escapes repo/evidence')
        check(sha(bound_path) == item['sha256'], 'final audit is stale: ' + name)
    return value


def native_proof(root, audit):
    """Validate the post-grid independent proof, without loading native code."""
    path = root / 'audit/native.json'
    proof = load(path)
    check(any(item['path'] == 'audit/native.json' and item['sha256'] == sha(path)
              for item in audit['source_bindings']), 'native proof is not bound by the complete final audit')
    check(proof.get('schema') == 'hw-gift-1d-independent-native-v1' and proof.get('status') == 'PASS',
          'independent native proof missing or failed')
    check(proof.get('no_clocks') is True and proof.get('measurements_of_time') is False
          and proof.get('all_attempts') is True and proof.get('minimal_encodings_authorized') == 2,
          'native proof must cover all attempts, with only two untimed known-answer encodings')
    check(proof.get('source_sha256') == sha(root / 'verify_native.py'), 'independent native verifier source changed')
    documents = proof.get('documents_sha256')
    check(isinstance(documents, dict) and documents, 'independent proof document bindings missing')
    for name, digest in documents.items():
        check(sha(public(root, name)) == digest, 'native proof document changed: ' + name)
    fields = ('archive_references', 'archive_paths_verified', 'unique_archives_verified',
              'frame_decodes_verified', 'restored_bytes_verified')
    check(all(positive(proof.get(key)) for key in fields), 'native proof counters missing')
    check(proof['unique_archives_verified'] <= proof['archive_paths_verified'] <= proof['archive_references'],
          'inconsistent native proof archive counts')
    archives, paths = proof.get('archives'), proof.get('archive_paths')
    check(isinstance(archives, list) and len(archives) == proof['unique_archives_verified']
          and isinstance(paths, dict) and len(paths) == proof['archive_paths_verified'],
          'native proof archive inventory/count mismatch')
    check(sum(item['frame_count'] for item in archives) == proof['frame_decodes_verified']
          and sum(item['restored_bytes'] for item in archives) == proof['restored_bytes_verified'],
          'native proof frame/restore totals do not match inventory')
    tiny = proof.get('tiny_probe')
    check(isinstance(tiny, dict) and set(tiny) == {'original', 'nohint'}
          and all(item['result']['roundtrip'] is True and item['result']['corrupted_magic_error'] is True
                  for item in tiny.values()), 'independent tiny known-answer controls did not pass')
    check(isinstance(proof.get('conditional_policy_byte_checks'), list), 'native policy byte checks missing')
    audited = audit.get('native_proof')
    check(isinstance(audited, dict), 'final audit is missing its independent native proof verdict')
    expected = dict(path='audit/native.json', sha256=sha(path), source_sha256=proof['source_sha256'],
                    minimal_encodings_authorized=2, conditional_policy_cells=len(proof['conditional_policy_byte_checks']))
    expected.update({key: proof[key] for key in fields})
    check(all(audited.get(key) == value for key, value in expected.items()), 'final audit/native proof summary mismatch')
    return proof


def proof_coverage(data):
    proof = data['native']
    required = {'method-controls.json', 'method-check.json', data['method']['selfcheck_path']}
    summaries = [data['method']]
    for phase in ('train', 'validate', 'holdout'):
        for cell in data[phase].values():
            required.add(cell['path'])
            required.add(cell['summary']['selfcheck_path'])
            summaries.append(cell['summary'])
    for summary in summaries:
        for repeat in summary['repeats']:
            for attempt in repeat['attempts']:
                if attempt.get('result') is not None:
                    required.add(attempt['result']['path'])
    check(required <= set(proof['documents_sha256']), 'native proof omitted inspected cells/controls/attempts')
    expected = []
    if data['threshold'] is not None:
        for corpus in ('enwik8', 'silesia.tar'):
            for level in LEVELS:
                for g in GRIDS:
                    expected.append(dict(corpus=corpus, level=level, g=g, threshold=data['threshold'],
                                         selected='original' if g < data['threshold'] else 'nohint', bytes_equal=True))
    actual = proof['conditional_policy_byte_checks']
    key = lambda item: (item['corpus'], item['level'], item['g'])
    check(sorted(actual, key=key) == expected, 'independent native conditional byte checks do not cover the frozen policy')


def repeated(root, summary, method=False):
    repeats = summary.get('repeats')
    check(isinstance(repeats, list) and len(repeats) == 5, 'five completed logical repeats required')
    rows, receipts, count, retaken, loaded = [], [], 0, 0, 0
    maximum = [Decimal(0), Decimal(0)]
    for number, repeat in enumerate(repeats):
        check(repeat['pair_index'] == number, 'logical repeat ordering changed')
        attempts = repeat['attempts']
        check(1 <= len(attempts) <= 3, 'load retry budget exceeded')
        retaken += len(attempts) > 1
        for index, attempt in enumerate(attempts, 1):
            status = 'CLEAN' if index == len(attempts) else 'LOADED'
            check(attempt['attempt'] == index and attempt['status'] == status,
                  'only LOADED can be retried and first CLEAN must win')
            receipt, path = reference(root, attempt['receipt'])
            check(receipt == attempt['receipt_data'] and receipt['status'] == status,
                  'receipt differs from retained attempt')
            for suffix, field in (('.stdout', 'stdout_sha256'), ('.stderr', 'stderr_sha256')):
                check(sha(Path(str(path) + suffix)) == receipt[field], 'raw helper output changed')
            for slot, boundary in enumerate(('start', 'end')):
                number_value = Decimal(receipt[boundary]['loadavg_raw'].split()[0])
                check(number_value.is_finite() and number_value >= 0, 'invalid boundary load')
                maximum[slot] = max(maximum[slot], number_value)
            if receipt['command_started']:
                result, _ = reference(root, attempt['result'])
                check(load(Path(str(path) + '.stdout')) == result, 'raw stdout/result mismatch')
            else:
                check(attempt.get('result') is None and status == 'LOADED', 'unstarted attempt has a result')
                result = None
            if status == 'CLEAN':
                check(result is not None, 'CLEAN result missing')
                check(repeat['selected_result'] == attempt['result'] and repeat['selected_receipt'] == attempt['receipt'],
                      'selected result is not first CLEAN')
                check(result['pair_index'] == repeat['pair_index'] and result['order'] == repeat['order'],
                      'selected worker order differs from summary')
                check([r['variant'] for r in result['results']] == repeat['order'], 'worker slot order changed')
                check(all(r['slot'] == i and r['bit_perfect'] is True and positive(r['compression_ns'])
                          for i, r in enumerate(result['results'])), 'invalid timed restoration/result')
                if method:
                    check(repeat['order'] == ['original', 'original'], 'AA duplicates were lost')
                rows.append(result)
            receipts.append(receipt)
            count += 1
            loaded += status == 'LOADED'
    counters = dict(logical_repeats=5, attempts=count, retaken=retaken, loaded_attempts=loaded)
    check(summary['planned_repeats'] == summary['started_repeats'] == 5
          and summary['retaken_repeats'] == retaken and summary['loaded_attempts'] == loaded,
          'saved repeat counters differ from attempts')
    return rows, receipts, counters, maximum


def metrics(rows, request):
    result = {}
    for worker in rows:
        check(worker['cell_sha256'] == hashlib.sha256(packed(request)).hexdigest(), 'raw worker request binding changed')
        check(worker['input_bytes'] == request['input_bytes'] and worker['input_sha256'] == request['input_sha256'],
              'raw worker source identity changed')
        for item in worker['results']:
            check(item['decoded_bytes'] == request['input_bytes'] and item['decoded_sha256'] == request['input_sha256'],
                  'restored bytes do not match source')
    for variant in request['variants']:
        values = [next(item for item in worker['results'] if item['variant'] == variant) for worker in rows]
        ids = {(v['archive_bytes'], v['archive_sha256']) for v in values}
        check(len(ids) == 1, 'archive bytes are not deterministic')
        size, digest = ids.pop()
        ns = [v['compression_ns'] for v in values]
        decoded = [v['decode_ns'] for v in values if v['decode_ns'] is not None]
        check(len(decoded) == 1 and positive(decoded[0]), 'exactly one full-decode observation required')
        result[variant] = dict(compression_ns=ns, median_ns=median5(ns), min_ns=min(ns),
                               archive_bytes=size, archive_sha256=digest, decode_ns=decoded[0])
    return result


def phase_data(root, name, threshold):
    cells = {}
    for level in LEVELS:
        for g in GRIDS:
            path = f'cells/{name}/L{level}-G{g}.json'
            summary = load(public(root, path))
            check(summary['status'] == 'COMPLETE' and summary['phase'] == name
                  and summary['level'] == level and summary['g'] == g, 'incomplete/wrong phase cell: ' + path)
            corpus = 'silesia.tar' if name == 'holdout' else 'enwik8'
            check(summary['corpus'] == corpus, 'phase corpus changed')
            request = bound(root, summary, 'request')
            bound(root, summary, 'selfcheck')
            check(bound(root, summary, 'method_check')['status'] == 'PASS', 'cell missing passing method gate')
            variants = ['original', 'conditional'] if name == 'validate' else ['original', 'nohint']
            if name == 'holdout' and threshold is not None:
                variants.append('conditional')
            check(request['variants'] == variants, 'phase variants differ from preregistered design')
            check((request['corpus'], request['level'], request['g']) == (corpus, level, g), 'request grid differs')
            check(request['prefix_bytes'] == (PREFIX if g in (256, 1024) else None), 'prefix scope changed')
            check(request['input_bytes'] == (PREFIX if g in (256, 1024) else request['full_corpus_bytes']), 'wrong source size')
            for key in ('input_bytes', 'input_sha256', 'prefix_bytes', 'full_corpus_bytes', 'full_corpus_sha256'):
                check(summary[key] == request[key], 'summary source scope changed')
            raw, receipts, counters, maximum = repeated(root, summary)
            values = metrics(raw, request)
            check(values == summary['variants'], 'summary differs from raw observations')
            cells[level, g] = dict(summary=summary, request=request, variants=values, raw=raw,
                                    receipts=receipts, counters=counters, maximum=maximum, path=path)
    return cells


def literal_verdicts(training, holdout, validation, threshold):
    """Literal preregistered predicates: integers first; formatting is separate."""
    first = training[10, 256]['variants']
    a, b = first['original']['median_ns'], first['nohint']['median_ns']
    p1 = dict(passed=b >= 3*a, original_ns=a, nohint_ns=b, ratio=str(Fraction(b, a)))
    p2, kill, p3 = [], [], []
    for corpus, cells in (('enwik8', training), ('silesia.tar', holdout)):
        for level in LEVELS:
            for g in GRIDS:
                if level not in (3, 10) or g < 65536:
                    continue
                v = cells[level, g]['variants']
                a, b = v['original']['median_ns'], v['nohint']['median_ns']
                p2.append(dict(corpus=corpus, level=level, g=g, ratio=str(Fraction(b, a)),
                               speed_pass=9*a <= 10*b <= 11*a,
                               size_pass=v['nohint']['archive_bytes'] <= v['original']['archive_bytes']))
                if level == 3 and g == 65536:
                    kill.append(dict(corpus=corpus, triggered=10*b >= 11*a, ratio=str(Fraction(b, a))))
    if threshold is not None:
        for corpus, cells, baseline in (('enwik8', validation, training), ('silesia.tar', holdout, holdout)):
            check(set(cells) == KEYS, 'all conditional cells required')
            for (level, g), cell in sorted(cells.items()):
                v, base = cell['variants'], baseline[level, g]['variants']
                a, c = v['original']['median_ns'], v['conditional']['median_ns']
                target = base['original' if g < threshold else 'nohint']
                identity = all(v['conditional'][k] == target[k] for k in ('archive_bytes', 'archive_sha256'))
                allowance = g < threshold or 2000*(v['conditional']['archive_bytes']-base['nohint']['archive_bytes']) <= base['nohint']['archive_bytes']
                p3.append(dict(corpus=corpus, level=level, g=g, ratio=str(Fraction(c, a)),
                               speed_pass=10*c <= 11*a, archive_identity_pass=identity, size_allowance_pass=allowance))
    return dict(P1=p1, P2=dict(passed=all(r['speed_pass'] and r['size_pass'] for r in p2), cells=p2),
                P3=dict(passed=threshold is not None and all(r['speed_pass'] and r['archive_identity_pass'] and r['size_allowance_pass'] for r in p3),
                        threshold_bytes=threshold, cells=p3), Kill=dict(triggered=any(r['triggered'] for r in kill), cells=kill))


def load_all(root, audit_path):
    audit = audit_gate(root, audit_path)
    native = native_proof(root, audit)
    selection = load(root / 'selection.json')
    threshold = selection['threshold_bytes']
    check(threshold is None or threshold in CANDIDATES, 'threshold outside preregistered candidates')
    check(threshold == audit['independent_threshold_bytes'] == audit['selection']['threshold_bytes'], 'audit/selection threshold mismatch')
    check(audit['validation_cells'] == (21 if threshold is not None else 0), 'conditional audit grid incomplete')
    method = load(root / 'method-check.json')
    check(method['status'] == 'PASS', 'AA gate must pass')
    bound(root, method, 'request')
    bound(root, method, 'selfcheck')
    check(reference(root, method['controls'])[0]['status'] == 'PASS', 'codec controls missing')
    raw, receipts, counters, maximum = repeated(root, method, True)
    first = [r['results'][0]['compression_ns'] for r in raw]
    second = [r['results'][1]['compression_ns'] for r in raw]
    a, b = median5(first), median5(second)
    check(abs(b-a)*20 < a, 'strict AA <5% gate failed')
    check(method['first_ns'] == audit['method']['first_ns'] == first and method['second_ns'] == audit['method']['second_ns'] == second,
          'AA observations differ from final audit')
    check((method['median_first_ns'], method['median_second_ns']) == (a, b), 'AA medians changed')
    check(counters == audit['method']['counters'], 'AA audit counters differ')
    training = phase_data(root, 'train', threshold)
    holdout = phase_data(root, 'holdout', threshold)
    validation = phase_data(root, 'validate', threshold) if threshold is not None else {}
    verdicts = literal_verdicts(training, holdout, validation, threshold)
    check(verdicts == audit['literal_verdicts'], 'integer verdicts differ from independent audit')
    phase_counters = {}
    for name, cells in (('train', training), ('validate', validation), ('holdout', holdout)):
        phase_counters[name] = {k: sum(c['counters'][k] for c in cells.values()) for k in counters}
    check(phase_counters == audit['phase_counters'], 'phase attempt counters differ from final audit')
    data = dict(root=root, audit=audit, audit_path=audit_path, native=native, selection=selection, threshold=threshold,
                method=method, method_raw=raw, method_counters=counters, method_maximum=maximum,
                train=training, holdout=holdout, validate=validation, verdicts=verdicts, counters=phase_counters)
    proof_coverage(data)
    return data


def baseline_rows(data, focused=False):
    rows = []
    for phase in ('train', 'holdout'):
        for (level, g), cell in sorted(data[phase].items()):
            if focused and g < 65536:
                continue
            v = cell['variants']
            a, b = v['original'], v['nohint']
            rows.append([cell['request']['corpus'], level, g,
                         f"16 MiB prefix ({PREFIX} B)" if g in (256, 1024) else f"full ({cell['request']['input_bytes']} B)",
                         a['archive_bytes'], b['archive_bytes'], delta_percent(b['archive_bytes'], a['archive_bytes']),
                         ms(a['median_ns']), ms(a['min_ns']), ms(b['median_ns']), ms(b['min_ns']),
                         ratio(b['median_ns'], a['median_ns']), ms(a['decode_ns']), ms(b['decode_ns']), link(cell['path'], 'raw refs')])
    return rows


def density_losses(data, conditional=False):
    losses = []
    for phase in (('validate', 'holdout') if conditional else ('train', 'holdout')):
        for (level, g), cell in sorted(data[phase].items()):
            v = cell['variants']
            chosen = 'conditional' if conditional else 'nohint'
            a, b = v['original'], v[chosen]
            if b['archive_bytes'] > a['archive_bytes']:
                losses.append([phase, cell['request']['corpus'], level, g, b['archive_bytes']-a['archive_bytes'],
                               delta_percent(b['archive_bytes'], a['archive_bytes']), ratio(b['median_ns'], a['median_ns'])])
    return losses


def conditional_rows(data):
    rows = []
    if data['threshold'] is None:
        return rows
    for phase in ('validate', 'holdout'):
        for (level, g), cell in sorted(data[phase].items()):
            v = cell['variants']
            baseline = data['train'][level, g]['variants'] if phase == 'validate' else v
            chosen = 'original' if g < data['threshold'] else 'nohint'
            target, c, a = baseline[chosen], v['conditional'], v['original']
            exact = (c['archive_bytes'], c['archive_sha256']) == (target['archive_bytes'], target['archive_sha256'])
            rows.append([phase, cell['request']['corpus'], level, g, cell['request']['input_bytes'],
                         ms(a['median_ns']), ms(a['min_ns']), ms(c['median_ns']), ms(c['min_ns']),
                         ratio(c['median_ns'], a['median_ns']), c['archive_bytes'], chosen,
                         c['archive_sha256'], 'YES' if exact else 'NO', link(cell['path'], 'raw refs')])
    return rows


BASE_HEADERS = ['Corpus', 'L', 'G B', 'Input scope', 'A bytes', 'B bytes', 'B size ΔA %',
                'A median ms', 'A min ms', 'B median ms', 'B min ms', 'B/A median',
                'A decode once ms', 'B decode once ms', 'Saved source']
COND_HEADERS = ['Phase', 'Corpus', 'L', 'G B', 'Input B', 'A median ms', 'A min ms', 'C median ms', 'C min ms',
                'C/A median', 'C bytes', 'Policy target', 'C archive SHA-256', 'Exact target match', 'Saved source']


def verdict_table(data):
    v = data['verdicts']
    p2bad = sum(not(r['speed_pass'] and r['size_pass']) for r in v['P2']['cells'])
    p3bad = sum(not(r['speed_pass'] and r['archive_identity_pass'] and r['size_allowance_pass']) for r in v['P3']['cells'])
    rows = [
        ['P1', 'At enwik8 first 16 MiB, L10/G256 B compression ≥3× A',
         'HIT' if v['P1']['passed'] else 'MISS',
         f"A={v['P1']['original_ns']} ns; B={v['P1']['nohint_ns']} ns; B/A={ratio(v['P1']['nohint_ns'], v['P1']['original_ns'])}"],
        ['P2', 'Both corpora, L3/L10, G≥65536: 0.90≤B/A≤1.10 and B bytes≤A bytes',
         'HIT' if v['P2']['passed'] else 'MISS', f'{p2bad}/{len(v["P2"]["cells"])} violating cells'],
        ['P3', 'Some X in 1–64 KiB: C/A≤1.10 everywhere; at G≥X C bytes≤1.0005×B; actual policy byte identity',
         'HIT' if v['P3']['passed'] else 'MISS',
         'NO SUPPORTED X' if data['threshold'] is None else f'X={data["threshold"]} B; {p3bad}/42 violating cells'],
        ['Kill', 'L3/G65536 B/A≥1.10 on either corpus means size/speed trade-off',
         'TRIGGERED' if v['Kill']['triggered'] else 'NOT TRIGGERED',
         '; '.join(f"{r['corpus']}: B/A={fraction_text(Fraction(r['ratio']).numerator, Fraction(r['ratio']).denominator)}" for r in v['Kill']['cells'])],
    ]
    return table(['Forecast', 'Literal preregistered prediction', 'Verdict', 'Observed fact'], rows)


def violation_tables(data):
    v = data['verdicts']
    parts = []
    for name, fields in (('P2', ('speed_pass', 'size_pass')),
                         ('P3', ('speed_pass', 'archive_identity_pass', 'size_allowance_pass'))):
        rows = []
        for r in v[name]['cells']:
            failed = [field.removesuffix('_pass') for field in fields if not r[field]]
            if failed:
                value = Fraction(r['ratio'])
                rows.append([r['corpus'], r['level'], r['g'], fraction_text(value.numerator, value.denominator), ', '.join(failed)])
        parts.append(f'All {name} violations: ' + ('none.' if not rows else '\n\n' + table(['Corpus', 'L', 'G B', 'Median ratio', 'Failed conditions'], rows)))
    return '\n\n'.join(parts)


def attempt_table(data):
    rows = []
    for name in ('method', 'train', 'validate', 'holdout'):
        if name == 'method':
            counters, maximum = data['method_counters'], data['method_maximum']
        else:
            counters = data['counters'][name]
            maximum = [max((c['maximum'][i] for c in data[name].values()), default=Decimal(0)) for i in (0, 1)]
        rows.append([name, counters['logical_repeats'], counters['retaken'], counters['attempts'], counters['loaded_attempts'],
                     str(maximum[0]) if counters['attempts'] else 'n/a', str(maximum[1]) if counters['attempts'] else 'n/a'])
    return table(['Phase', 'M logical repeats', 'N retaken repeats', 'All attempts', 'LOADED attempts', 'Max start load1', 'Max end load1'], rows)


def native_paragraph(data):
    proof = data['native']
    return (f"The separate post-grid {link('verify_native.py', 'native verifier')} passed: "
            f"{proof['archive_paths_verified']} actual archive paths checked, "
            f"{proof['unique_archives_verified']} distinct archive/source/frame identities independently decoded, "
            f"{proof['frame_decodes_verified']} frame decodes and {proof['restored_bytes_verified']} restored bytes "
            f"across those distinct identities. It covers all retained attempts, verifies frame metadata and seek-table "
            f"checksums against actual bytes, and confirms {len(proof['conditional_policy_byte_checks'])} complete "
            f"conditional archives against the selected policy. The only permitted new encodings are two tiny "
            f"known-answer controls; no clocks are read and no performance ranking is derived. "
            f"{len(proof['documents_sha256'])} saved document hashes and the verifier source hash bind this proof "
            f"to the inspected evidence. {link('audit/native.json', 'Native proof')} is itself hash-bound by the "
            f"independent {link('audit/final.json', 'saved-data audit')}; that audit separately recalculates timing "
            f"medians, predicates, source bindings and load admission.")


def decision_summary(data):
    x = data['threshold']
    if x is None:
        return 'No preregistered frame-size threshold met the training speed constraint. The complete original/nohint comparison is retained; no conditional default is established.'
    checks = data['verdicts']['P3']['cells']
    speed_passes = sum(row['speed_pass'] for row in checks)
    losses = len(density_losses(data, True))
    statement = (f'The experimental rule **hint only when maxFrameSize < {x} bytes** met the '
                 f'compression-time budget in {speed_passes}/{len(checks)} cells. Its actual archives '
                 f'were larger than the original in **{losses}/{len(checks)} cells**.')
    if losses:
        statement += ' The initial premise of a boundary below which the hint is needed for speed and above which it only costs bytes is not confirmed by this grid.'
    return statement


def results_markdown(data):
    x = data['threshold']
    v = data['verdicts']
    pieces = ['# HW-GIFT-1d results',
        decision_summary(data),
        'Complete saved-data report; the independent final audit passed. Predictions are evaluated before rounding, using integer nanoseconds and bytes. A PASS audit establishes completeness/integrity; each forecast has its own HIT/MISS below.',
        'Protocol: ' + ', '.join(link(p) for p in ('CALIBRATION.md', 'PROTOCOL.md', 'SOURCE_PATHS.md', 'audit/final.json', 'TABLE.csv')) + '.',
        'A = original `hint=maxFrameSize`; B = `hint=0`; C = the frozen conditional implementation. Archive bytes include the complete seek table with per-frame checksums in every variant. Compression figures are median/minimum of five CLEAN observations; decode is one full-decode observation per variant/cell/phase, with no decode ranking claim. Ratios are ratios of compression medians.',
        verdict_table(data),
        'P2 uses an inclusive ±10% band. Kill uses an inclusive 1.10 boundary, so both predicates can be true at exactly 1.10. P3 compares its size allowance with B, not with original A. A P3 HIT does not promise a universal free win or that hinting is necessary below X.',
        violation_tables(data),
        '## Complete baseline A/B grid',
        'The following 42 rows preserve the training enwik8 A/B phase and holdout silesia A/B phase. G=256 and 1024 B use only the first 16 MiB; all larger G use the full corpus. These different source scopes do not form a size-independent curve.',
        table(BASE_HEADERS, baseline_rows(data)),
        '## Archive losses against original',
        'Every baseline cell in which B is larger than A is retained below, including cells outside P2. Faster compression does not imply a smaller archive.',
        table(['Phase', 'Corpus', 'L', 'G B', 'Extra B bytes', 'B size ΔA %', 'B/A median'], density_losses(data)) if density_losses(data) else 'No measured baseline B archive is larger than A.',
        '## Frozen threshold and actual conditional check']
    if x is None:
        pieces.append('**NO SUPPORTED X.** None of the four preregistered candidates met the enwik8 speed constraint on all levels at G≥X. Conditional implementation/validation are inapplicable; the complete holdout A/B grid is reported. P3 is MISS, and no replacement threshold is invented.')
    else:
        pieces.extend([f'X = **{x} bytes**, selected only from enwik8 A/B by the frozen smallest-eligible-candidate rule. ' + link('selection.json') + ' and ' + link('CONDITIONAL_PROTOCOL.md') + ' were committed before conditional development and holdout. No threshold adjustment uses holdout outcomes.',
            'The actual native argument patch is:\n\n```c\nmaxFrameSize < ' + str(x) + ' ? (int)maxFrameSize : 0\n```',
            'The 42 checks below keep post-freeze enwik8 A/C separate from holdout silesia A/B/C. C/A compares contemporaneous observations; earlier training A observations are not pooled. At G<X C must equal the original archive; at G≥X C must equal nohint. The displayed complete-archive SHA and byte count belong to actual C outputs, not a simulated policy.',
            table(COND_HEADERS, conditional_rows(data)),
            'C size losses against contemporaneous original A are listed separately from the literal P3 allowance against B:',
            table(['Phase', 'Corpus', 'L', 'G B', 'Extra C bytes', 'C size ΔA %', 'C/A median'], density_losses(data, True)) if density_losses(data, True) else 'No actual C archive is larger than contemporaneous A.'])
    method = data['method']
    pieces.extend(['## Method and retained attempts',
        f"A/A medians: first={method['median_first_ns']} ns, second={method['median_second_ns']} ns; strict gate `20*abs(second-first)<first` passed. This is a method admission gate, with no time-based exclusion of grid observations. The untimed controls reproduce both complete HW-GIFT-1c enwik8 L3/256 KiB archive SHA values, distinguish changed input and reject corrupt magic; every produced archive restores bit for bit. See {link('method-controls.json')} and {link('method-check.json')}.",
        'The raw five A/A pairs: ' + ', '.join(link(r['selected_result']['path'], str(i)) for i, r in enumerate(method['repeats'])) + '.',
        attempt_table(data),
        'Counts include retained rejected attempts. Only successful pairs with load1>2.0 at a boundary are LOADED; each logical pair has at most three attempts, first CLEAN wins, and worker/byte errors are fatal. All request/result/receipt/stdout/stderr files remain linked from the cell summaries. Maximum loads above include CLEAN and LOADED attempts. Other-core /proc/stat deltas are observations, not admission criteria.',
        '## Independent post-grid native proof',
        native_paragraph(data),
        '## Scope and limits',
        'Measured host: ace-core, AMD EPYC 4344P, Linux, pinned CPU 0, schedutil governor; zstd 1.5.7 at `f8745da6ff1ad1e7bab384bd1f9d742439278e99`. Input/output are resident in RAM. Fresh contexts and prefaulted outer buffers precede each compression timer; codec internal lazy allocation is included. Hashing, restoration, disk I/O and context telemetry are outside compression timing. Native build/compiler/source digests are retained in the public native manifests and bound by each request.',
        'This is one machine, two corpora and the stated levels/frame grid. It establishes no universal threshold, process-RSS result, or performance claim for other APIs/versions/hosts. HW-GIFT-1c showed a window/header change at 512 KiB even where archive sizes match. Internal context size is not process RSS.',
        'The 2023 M1 numbers in PR #3544 are historical context. P1 tested the assumption that its speed factor persisted on this later library/host/API; the literal verdict above records whether that assumption survived. Later row-hash initialization/salt changes are present in pinned 1.5.7, but no version/feature ablation identifies the cause of this timing result. See ' + link('SOURCE_PATHS.md') + '.',
        ('Kill triggered: the issue must be framed as a size/speed trade-off.' if v['Kill']['triggered'] else 'Kill did not trigger; the complete speed and density losses above still qualify any proposal.'),
        f"Final audit SHA-256: `{sha(data['audit_path'])}`. Private artifact hashes verified by that audit: {data['audit']['private_artifacts_hash_verified']}; private paths unavailable on the audit host: {len(data['audit']['private_paths_not_available'])}. Archive files themselves remain in the experiment work area; public manifests bind their byte counts and SHA. This renderer uses only retained files and invokes no codecs, clocks, Git or remote commands. The issue draft is unsent."])
    return '\n\n'.join(pieces) + '\n'


def csv_text(data):
    fields = ['phase', 'corpus', 'level', 'frame_bytes', 'input_scope', 'input_bytes', 'input_sha256',
              'full_corpus_bytes', 'full_corpus_sha256', 'variant', 'archive_bytes', 'archive_sha256']
    fields += [f'compression_ns_{i}' for i in range(5)]
    fields += ['compression_median_ns', 'compression_min_ns', 'full_decode_once_ns', 'original_median_ns',
               'ratio_to_original_exact', 'archive_delta_original_bytes', 'conditional_target', 'conditional_target_sha256',
               'conditional_exact_match', 'cell_summary'] + [f'raw_repeat_{i}' for i in range(5)]
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for phase in ('train', 'validate', 'holdout'):
        for (level, g), cell in sorted(data[phase].items()):
            request, values = cell['request'], cell['variants']
            a = values['original']
            for variant, item in values.items():
                row = dict(phase=phase, corpus=request['corpus'], level=level, frame_bytes=g,
                           input_scope='first16MiB' if request['prefix_bytes'] is not None else 'full',
                           input_bytes=request['input_bytes'], input_sha256=request['input_sha256'],
                           full_corpus_bytes=request['full_corpus_bytes'], full_corpus_sha256=request['full_corpus_sha256'],
                           variant=variant, archive_bytes=item['archive_bytes'], archive_sha256=item['archive_sha256'],
                           compression_median_ns=item['median_ns'], compression_min_ns=item['min_ns'],
                           full_decode_once_ns=item['decode_ns'], original_median_ns=a['median_ns'],
                           ratio_to_original_exact=str(Fraction(item['median_ns'], a['median_ns'])),
                           archive_delta_original_bytes=item['archive_bytes']-a['archive_bytes'], cell_summary=cell['path'])
                row.update({f'compression_ns_{i}': n for i, n in enumerate(item['compression_ns'])})
                row.update({f'raw_repeat_{i}': r['selected_result']['path'] for i, r in enumerate(cell['summary']['repeats'])})
                if variant == 'conditional':
                    baseline = data['train'][level, g]['variants'] if phase == 'validate' else values
                    chosen = 'original' if g < data['threshold'] else 'nohint'
                    target = baseline[chosen]
                    row.update(conditional_target=chosen, conditional_target_sha256=target['archive_sha256'],
                               conditional_exact_match=(item['archive_bytes'], item['archive_sha256']) == (target['archive_bytes'], target['archive_sha256']))
                writer.writerow(row)
    return stream.getvalue()


def issue_markdown(data):
    x, v = data['threshold'], data['verdicts']
    parts = ['[PR #3544](https://github.com/meta/zstd/pull/3544) intentionally improved ingestion of tiny seekable frames by supplying an approximate source-size hint. Any proposed change should preserve that purpose.',
        '# Draft: empirical source-size hint policy for the seekable writer',
        '**UNSENT DRAFT.** No issue/comment has been posted. This document reports a pinned experiment and asks whether a conditional policy merits broader testing; it does not establish an upstream default.',
        decision_summary(data),
        'The original Pijul report described a regression, then supplied L10/256-byte settings. The PR author reported historical M1 enwik8 times of 35 s→2.5 s and 4 KiB-frame times of 3.6 s→1.8 s. Those are 2023 upstream observations, not the following measurements. Primary sources, attribution, exact commits and later row-hash changes are recorded in ' + link('SOURCE_PATHS.md') + '.',
        'We compared original A (`hint=maxFrameSize`) and B (`hint=0`) with identical seek-table checksums, resident input/output, five interleaved pairs, deterministic ordering and full restoration checks. G=256/1024 B uses a 16 MiB prefix; G≥4096 uses the full named corpus. Timing includes native compression only; decode was observed once per variant/cell/phase. Complete archives include their seek tables.',
        verdict_table(data),
        'The historical speed factor was a preregistered hypothesis, not a premise forced onto these results. Different CPU/API and later library behavior prevent direct transfer of the M1 ratio. The init-once/salt changes are source context; no old/new-version or feature ablation was run to attribute the measured timing outcome.',
        '## Measured costs at 64–512 KiB',
        table(BASE_HEADERS, baseline_rows(data, True)),
        'All 42 baseline cells, including tiny frames and every density loss, are in ' + link('RESULTS.md') + '; ' + link('TABLE.csv') + ' retains integer ns/bytes, full SHA values and all five raw references. B is not assumed smaller or slower monotonically. Violations of the literal forecasts are retained:',
        violation_tables(data)]
    if x is None:
        parts.append('**NO SUPPORTED X:** none of the declared training candidates meets the all-level enwik8 speed bound. Conditional validation is inapplicable. The full independent silesia A/B grid is retained; these data support a trade-off discussion rather than a proposed replacement default.')
    else:
        bad = sum(not(r['speed_pass'] and r['archive_identity_pass'] and r['size_allowance_pass']) for r in v['P3']['cells'])
        parts.extend([f'## Frozen experimental conditional rule: X={x} bytes',
            '```c\nmaxFrameSize < ' + str(x) + ' ? (int)maxFrameSize : 0\n```',
            f'The smallest qualifying measured X was selected from enwik8 alone and committed before development/holdout. Actual C was checked in 21 new enwik8 A/C cells and 21 silesia A/B/C cells; their repetitions are not pooled with training. P3 is {"HIT" if v["P3"]["passed"] else "MISS"}; {bad}/42 cells violate at least one declared C speed/byte predicate. The complete C byte counts, SHA values, contemporaneous A/C medians/minima and exact policy identities appear in ' + link('RESULTS.md') + '.',
            'P3 compares C size with B at G≥X; it does not promise C≤original A. C can inherit B density losses while satisfying that predicate. The observed threshold is not evidence that hinting is necessary below it or that every larger frame gains bytes. Holdout outcomes do not change X.',
            f'Actual C archives larger than original A: {len(density_losses(data, True))}/42. Baseline B archives larger than A: {len(density_losses(data))}/42. All such cells are listed in the report.'])
    parts.extend([('The preregistered Kill condition triggered: this proposal must be framed as a pure size/speed trade-off.' if v['Kill']['triggered'] else 'The preregistered Kill condition did not trigger. The other recorded forecast failures and density losses still limit the proposal.'),
        '## Reproduction scope and retained evidence',
        'ace-core AMD EPYC 4344P, Linux, CPU 0, schedutil; zstd 1.5.7 source `f8745da6ff1ad1e7bab384bd1f9d742439278e99`; levels 3/10/19, two corpora, RAM-resident operation. This is a single-machine observation, not a universal boundary. No process-RSS measurement is claimed. HW-GIFT-1c showed that an equal archive size at 512 KiB can coexist with changed header/window parameters.',
        'A/A passed the strict <5% median gate; known-answer complete 1c archive SHA values, positive/negative controls and every bit-perfect restore passed. All raw CLEAN/LOADED attempts and receipts are retained. Only load1>2.0 admits a mechanical retry, at most three attempts per pair, with no timing-based retakes.',
        native_paragraph(data),
        attempt_table(data),
        'Protocol, selection/freeze, native build manifests and independent audit: ' + ', '.join(link(p) for p in ('CALIBRATION.md', 'PROTOCOL.md', 'selection.json', 'audit/final.json')) + '. A failed holdout prediction is not repaired by choosing another X. Further machines/versions/workloads would be needed before recommending an upstream conditional default.'])
    return '\n\n'.join(parts) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, default=HERE / 'audit/final.json')
    parser.add_argument('--output-dir', type=Path, default=HERE)
    args = parser.parse_args()
    try:
        data = load_all(HERE, args.audit)
        # All admission, hash and exact-predicate checks precede any output write.
        artifacts = {'RESULTS.md': results_markdown(data), 'ZSTD_ISSUE_DRAFT.md': issue_markdown(data), 'TABLE.csv': csv_text(data)}
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for name, text in artifacts.items():
            if name.endswith('.md'):
                text = '\n'.join(line.rstrip() for line in text.splitlines()) + '\n'
            destination = args.output_dir / name
            pending = destination.with_name(destination.name + '.writing')
            pending.write_text(text, encoding='utf-8', newline='\n')
            pending.replace(destination)
        print(json.dumps(dict(status='PASS', baseline_cells=42, conditional_cells=42 if data['threshold'] is not None else 0,
                              output_files=list(artifacts)), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as error:
        print(json.dumps(dict(status='FAIL', reason=str(error)), sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
