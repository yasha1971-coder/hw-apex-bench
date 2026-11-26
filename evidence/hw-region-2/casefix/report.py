# SPDX-License-Identifier: Apache-2.0
"""Render saved casefix evidence only; no experiment imports or native calls."""
import argparse
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import posixpath
import re

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
SIGNATURE = "[written by ChatGPT (AI) at the author's request; checked by the author]"
PROFILES = ('aceapex', 'zstd_seekable', 'bgzip', 'twobit_casefix_mask1', 'twobit_original_mask1', 'twobit_original_mask0')
EQUIVALENT = PROFILES[:4]
CORPORA = ('chr1',) + tuple(f't2t-{i:02d}' for i in range(30))
LABELS = dict(aceapex='ACEAPEX 2.6.5 interactive L2', zstd_seekable='zstd-seekable 1.5.7 L3',
              bgzip='BGZF / HTSlib 1.24 L6', twobit_casefix_mask1='lib2bit-casefix (storeMasked=1)',
              twobit_original_mask1='lib2bit (storeMasked=1): not byte-equal: N in soft-masked runs',
              twobit_original_mask0='lib2bit (storeMasked=0): case-folded, not equivalent')


def require(ok, why):
    if not ok:
        raise ValueError(why)


def unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'duplicate JSON key')
        value[key] = item
    return value


def load(path):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def public_path(name):
    name = str(name).replace('\\', '/')
    marker = '/evidence/hw-region-2/casefix/'
    if marker in name:
        name = name.split(marker, 1)[1]
    require(not name.startswith('/') and ':' not in name, 'not a public casefix artifact')
    path = (HERE / name).resolve()
    require(path.is_relative_to(HERE), 'public reference escaped casefix')
    return path


def deref(record):
    path = public_path(record['path'])
    require(path.is_file() and sha(path) == record['sha256'], 'public evidence changed: ' + str(path))
    return path


def reference(path):
    return dict(path=path.relative_to(HERE).as_posix(), sha256=sha(path))


def bound_sources(value):
    for name, expected in value.items():
        path = (ROOT / name).resolve()
        require(path.is_relative_to(ROOT) and path.is_file() and sha(path) == expected, 'execution source changed: ' + name)


def observation(unit_ref, corpus, profile, case, trace, sources):
    unit = load(deref(unit_ref))
    require(unit['schema'] == 'hw-region-2-casefix-unit-v1' and unit['status'] == 'CLEAN', 'main logical unit incomplete')
    attempts = unit['attempts']
    require(1 <= len(attempts) <= 3 and attempts[-1]['status'] == 'CLEAN'
            and all(a['status'] == 'LOADED' for a in attempts[:-1])
            and unit['selected'] == attempts[-1]['observation'], 'first-CLEAN selection differs')
    identity = unit['identity']
    require(identity['profile'] == profile and identity['mode'] == 'latency' and identity['fresh'] is False
            and identity['probe'] is False and identity['source_sha256'] == sources
            and identity['case_sha256'] == hashlib.sha256(packed(case)).hexdigest()
            and identity['trace_sha256'] == hashlib.sha256(packed(trace)).hexdigest(), 'main observation scope changed')
    value = load(deref(unit['selected']))
    require(value['identity'] == identity and value['status'] == 'PASS', 'selected observation binding differs')
    summary, rows = value['summary'], value['rows']
    semantics = 1 if profile == 'twobit_original_mask1' else 2 if profile == 'twobit_original_mask0' else 0
    require(summary['label'] == profile and summary['semantics'] == semantics and summary['byte_equivalent'] is (semantics == 0)
            and summary['queries'] == summary['planned_queries'] == 1000 and summary['warmups'] == 12
            and summary['measurements_of_time'] is True and summary['query_clock_calls'] == 2000
            and summary['opens'] == 1 and summary['open_clock_calls'] == 2 and len(rows) == 1000, 'main workload differs')
    for i, row in enumerate(rows):
        require(row['query'] == i and row['start0'] == trace['requests']['offsets'][i]
                and row['verified'] is True and row['requested_bases'] == 16384
                and type(row['elapsed_ns']) is int and row['elapsed_ns'] > 0, 'main raw query differs')
        require(row['differences'] == row['permitted_n_to_N'] if semantics == 1 else row['differences'] == 0,
                'unexpected query difference')
    ns = sorted(row['elapsed_ns'] for row in rows)
    require(value['quantiles'] == dict(p50_ns=ns[499], p99_ns=ns[989]), 'quantiles differ from raw nanoseconds')
    for key in ('native_stdout', 'native_stderr'):
        path = deref(value[key]); require(path.stat().st_size == value[key]['bytes'], 'native stream size differs')
    for key in ('returned', 'expected'):
        capture = value[key]
        require(capture['bytes'] == 1000 * 16384 and 'public_gzip' in capture, 'full public capture proof missing')
        deref(capture['public_gzip'])
    fmt = case['formats']['twobit' if profile.startswith('twobit_') else profile]
    require(fmt['stored_bytes'] == fmt['bytes'] + sum(i['bytes'] for i in fmt['indexes']), 'stored-byte accounting differs')
    return dict(corpus=corpus, profile=profile, label=LABELS[profile], equivalent=profile in EQUIVALENT,
                stored_bytes=fmt['stored_bytes'], p50_ns=ns[499], p99_ns=ns[989], open_ns=summary['open_ns'],
                open_rss_delta_kib=summary['rss_after_open_kib'] - summary['rss_before_open_kib'],
                peak_process_rss_kib=summary['peak_process_rss_kib'], unit=unit_ref, selected=unit['selected'])


def overlap_info():
    path = HERE / 'writer-metadata/chr1.json.gz'
    meta = json.loads(gzip.decompress(path.read_bytes()), object_pairs_hook=unique)
    n, masks = meta['archive']['n_blocks'], meta['archive']['mask_blocks']
    i = j = total = 0
    first = None
    while i < len(n) and j < len(masks):
        a, an = n[i]; b, bn = masks[j]
        low, high = max(a, b), min(a + an, b + bn)
        if low < high:
            total += high - low
            first = low if first is None else min(first, low)
        if a + an <= b + bn:
            i += 1
        else:
            j += 1
    preflight = load(PARENT / 'input-preflight.json')
    chr1 = next(r for r in preflight['records'] if r['corpus'] == 'chr1')
    require(total == chr1['alphabet']['n'] == 181 and first == chr1['first_lowercase_n'] == 121757468, 'N/soft-mask overlap identity changed')
    return dict(overlap_bases=total, first_coordinate0=first, first_coordinate1=first + 1,
                sequence_sha256=chr1['sequence_sha256'], metadata=reference(path))


def timing_context():
    records = [load(p) for p in (HERE / 'raw').rglob('ovh-bench.json')] if (HERE / 'raw').exists() else []
    boundaries = [r[k] for r in records for k in ('start', 'end') if k in r]
    if not boundaries:
        return None
    keys = ('hostname', 'cpu', 'kernel', 'governor', 'pinned_core', 'host_logical_cpus')
    signature = {k: boundaries[0][k] for k in keys}
    require(all({k: b[k] for k in keys} == signature for b in boundaries), 'recorded timing host/governor changed')
    first = min(b['timestamp_utc'] for b in boundaries); last = max(b['timestamp_utc'] for b in boundaries)
    start_date, end_date = first[:10], last[:10]
    return dict(start_utc=first, end_utc=last, date_label=start_date if start_date == end_date else start_date + '–' + end_date,
                boundary_count=len(boundaries), **signature)


def state():
    if (HERE / 'KILL.json').exists():
        return 'KILL', 'Unexpected required call or string failure; no timing table is admitted.'
    for name in ('method-aa.json', 'controls.json'):
        path = HERE / name
        if path.exists() and load(path)['status'] != 'PASS':
            return 'METHODFAIL', name + ': ' + load(path)['status']
    for path in (HERE / 'units').rglob('*.json') if (HERE / 'units').exists() else []:
        if load(path).get('status') == 'BLOCKED: load':
            return 'BLOCKED: load', 'Three retained LOADED attempts; no fourth attempt or elapsed-based retry.'
    cases = [HERE / 'cases' / (c + '.json') for c in CORPORA]
    if not all(p.exists() and load(p).get('status') == 'COMPLETE' for p in cases):
        return 'INCOMPLETE', 'The 31-corpus / six-profile main grid has not completed.'
    audit = HERE / 'audit/all.json'
    if not audit.exists():
        return 'AWAITING AUDIT', 'Main records exist; the independent complete-grid audit has not passed.'
    if load(audit)['status'] != 'PASS':
        return 'AUDIT FAILED', 'The independent complete-grid audit has not passed; no main table is admitted.'
    return 'COMPLETE', 'All 31 corpora / 186 main rows passed the saved-data audit.'


def summary():
    status, reason = state()
    context = timing_context()
    value = dict(schema='hw-region-2-casefix-summary-v1', status=status, reason=reason, timing_context=context,
                 date_label=context['date_label'] if context else None,
                 saved_data_only=True, no_codecs=True, no_clocks=True, renderer_sha256=sha(__file__),
                 primary={}, forecasts={name: dict(verdict='NOT TESTED: ' + status) for name in ('P1', 'P2', 'P3')}, rows=[], corpus_decisions={})
    checkpoint = status == 'BLOCKED: load' and (HERE / 'audit/checkpoint.json').exists()
    if status != 'COMPLETE' and not checkpoint:
        return value
    audit_path = HERE / ('audit/checkpoint.json' if checkpoint else 'audit/all.json'); audit = load(audit_path)
    completed = tuple(c for c in CORPORA if (HERE / 'cases' / (c + '.json')).exists()
                      and load(HERE / 'cases' / (c + '.json')).get('status') == 'COMPLETE') if checkpoint else CORPORA
    require(completed and completed[0] == 'chr1' and completed == CORPORA[:len(completed)], 'only the verified sequential completed prefix may be published')
    require(audit['schema'] == 'hw-region-2-casefix-independent-audit-v1' and audit['status'] == 'PASS'
            and audit['stage'] == ('checkpoint' if checkpoint else 'all')
            and audit['saved_data_only'] is True and audit['no_codecs'] is True and audit['no_clocks'] is True
            and audit['counts']['cases'] == len(completed) and audit['counts']['rows'] == 6 * len(completed), 'independent audit scope differs')
    if checkpoint:
        require(audit['completion'] == 'BLOCKED: load', 'checkpoint integrity PASS is not experiment completion')
    require(audit['source_binding_base'] == 'repository', 'unknown audit source reference domain')
    for item in audit['source_bindings']:
        require(sha(ROOT / item['path']) == item['sha256'], 'audited source changed')
    require(any(r['path'] == 'evidence/hw-region-2/casefix/report.py' and r['sha256'] == sha(__file__) for r in audit['source_bindings']), 'report source not audited')
    build = load(HERE / 'native/build.json'); sources = build['identity']['source_sha256']; bound_sources(sources)
    references, all_rows = [], []
    for corpus in completed:
        path = HERE / 'cases' / (corpus + '.json'); current = load(path)
        require(current['source_sha256'] == sources and set(current['units']) == set(PROFILES), 'main case source/rows differ')
        k = CORPORA.index(corpus) % 6
        require(current['order'] == list(PROFILES[k:] + PROFILES[:k]), 'profile rotation differs')
        case = load(deref(current['archive_case'])); trace = load(HERE / 'traces' / (corpus + '.json'))
        require(case['corpus'] == corpus and case['g'] == case['request_bases'] == 16384, 'archive coordinate scope differs')
        rows = [observation(current['units'][p], corpus, p, case, trace, sources) for p in PROFILES]
        all_rows.extend(rows); references.append(reference(path))
        eq = [r for r in rows if r['equivalent']]
        low_time, low_size = min(r['p50_ns'] for r in eq), min(r['stored_bytes'] for r in eq)
        value['corpus_decisions'][corpus] = dict(fastest_p50_ns=low_time, smallest_stored_bytes=low_size,
            fastest=[r['profile'] for r in eq if r['p50_ns'] == low_time], smallest=[r['profile'] for r in eq if r['stored_bytes'] == low_size])
    require(audit['case_refs'] == references, 'audited case references differ')
    require(context is not None and context['pinned_core'] == 0 and 'AMD EPYC 4344P' in context['cpu'], 'actual timing host boundaries required')
    primary = {r['profile']: r for r in all_rows if r['corpus'] == 'chr1' and r['equivalent']}
    ace, two = primary['aceapex'], primary['twobit_casefix_mask1']
    wins = [c for c in completed[1:] if next(r['p50_ns'] for r in all_rows if r['corpus'] == c and r['profile'] == 'twobit_casefix_mask1')
            < next(r['p50_ns'] for r in all_rows if r['corpus'] == c and r['profile'] == 'aceapex')]
    tests = dict(P1=20 * ace['stored_bytes'] <= 19 * two['stored_bytes'], P2=4 * two['p50_ns'] <= ace['p50_ns'], P3=len(wins) >= 28)
    forecasts = {name: dict(passed=passed, verdict='HIT' if passed else 'MISS') for name, passed in tests.items()}
    forecasts['P1'].update(ACE_stored_bytes=ace['stored_bytes'], twobit_stored_bytes=two['stored_bytes'], exact_ratio=str(Fraction(ace['stored_bytes'], two['stored_bytes'])))
    forecasts['P2'].update(ACE_p50_ns=ace['p50_ns'], casefix_p50_ns=two['p50_ns'], exact_ratio=str(Fraction(two['p50_ns'], ace['p50_ns'])))
    forecasts['P3'].update(wins=len(wins), total=30, required=28, winning_corpora=wins)
    audited_forecasts = audit['prefix_forecasts'] if checkpoint else audit['forecasts']
    if checkpoint:
        forecasts['P3'].update(passed=None, verdict='PENDING', observed=len(completed) - 1, pending=31 - len(completed))
    for name in forecasts:
        for field in ('passed', 'verdict', *({'P1': ('ACE_stored_bytes', 'twobit_stored_bytes'),
                                           'P2': ('ACE_p50_ns', 'casefix_p50_ns'), 'P3': ('wins', 'required', 'total')}[name])):
            require(audited_forecasts[name][field] == forecasts[name][field], 'renderer/auditor forecast differs')
    missing = [c for c in CORPORA if c not in completed]
    if checkpoint:
        require(audit['missing_corpora'] == missing and audited_forecasts['P3']['observed'] == len(completed) - 1
                and audited_forecasts['P3']['pending'] == len(missing), 'checkpoint missing-corpus accounting differs')
    value.update(primary=primary, forecasts=forecasts, rows=all_rows, audit=reference(audit_path),
                 counts=audit['counts'], overlap=overlap_info(), native_build_sha256=sha(HERE / 'native/build.json'),
                 setup_sha256=sha(HERE / 'setup.json'), case_refs=references, completed_corpora=list(completed),
                 missing_corpora=missing, partial=checkpoint)
    if checkpoint:
        value['blocked_units'] = blocked_units(audit['blocked_units'], sources)
    return value


def blocked_units(records, sources):
    result = []
    for record in records:
        unit = load(deref(record['unit']))
        require(record['kind'] == 'main' and unit['status'] == 'BLOCKED: load' and unit['selected'] is None
                and record['selected'] is None and unit['identity']['profile'] == record['profile']
                and unit['identity']['source_sha256'] == sources and len(unit['attempts']) == 3,
                'blocked logical unit identity/budget differs')
        attempts = []
        require(len(record['attempts']) == 3 and record['worker_starts'] == record['query_clock_calls'] == record['open_clock_calls'] == 0,
                'blocked checkpoint must retain three never-started attempts')
        for number, (attempt, audited) in enumerate(zip(unit['attempts'], record['attempts']), 1):
            require(attempt['number'] == audited['number'] == number and attempt['status'] == audited['status'] == 'LOADED'
                    and attempt['observation'] is None and attempt['receipt'] == audited['receipt'], 'blocked attempt history differs')
            receipt = load(deref(attempt['receipt']))
            foreign = receipt['foreign_cpu_start']['exceeded']
            require(receipt['status'] == 'LOADED' and receipt['command_started'] is False and receipt['returncode'] is None
                    and audited['command_started'] is False and foreign == audited['foreign_exceeded'] and foreign
                    and all(Fraction(p['percent_one_cpu']) > 10 for p in foreign)
                    and receipt['ps_top8'] and receipt['ps_command'] == 'ps -eo pid,user,pcpu,comm --sort=-pcpu | head -8',
                    'blocked admission/foreign CPU evidence differs')
            start = receipt['start']['loadavg_raw'].split()[0]; end = receipt['end']['loadavg_raw'].split()[0]
            attempts.append(dict(number=number, receipt=attempt['receipt'], load1_start=start, load1_end=end,
                                 foreign=foreign, worker_started=False, ps_recorded=True, ps_top8=receipt['ps_top8']))
        result.append(dict(unit=record['unit'], unit_id=record['unit_id'], profile=record['profile'], attempts=attempts,
                           worker_starts=0, query_clock_calls=0, open_clock_calls=0))
    require(result, 'BLOCKED report needs its retained admission evidence')
    return result


def line_link(path, needle, label):
    full = ROOT / path
    lines = full.read_text(encoding='utf-8').splitlines()
    found = next(i for i, text in enumerate(lines, 1) if needle in text)
    target = posixpath.relpath(path, 'evidence/hw-region-2/casefix')
    return f'[{label}:{found}]({target}#L{found})'


def method_data():
    aa_path, control_path = HERE / 'method-aa.json', HERE / 'controls.json'
    aa = load(aa_path) if aa_path.exists() else None
    controls = load(control_path) if control_path.exists() else None
    if not aa and not controls:
        return aa, controls
    sources = load(HERE / 'native/build.json')['identity']['source_sha256']; bound_sources(sources)
    case = load(HERE / 'archives/chr1.json'); trace = load(HERE / 'traces/chr1.json')
    if aa:
        require(aa['source_sha256'] == sources, 'AA source binding differs')
        for p, r in aa['profiles'].items():
            first = observation(r['first'], 'chr1', p, case, trace, sources)
            second = observation(r['second'], 'chr1', p, case, trace, sources)
            a, b = first['p50_ns'], second['p50_ns']
            require((a, b) == (r['first_p50_ns'], r['second_p50_ns'])
                    and r['strict_under_five_percent'] is (20 * abs(b - a) < a), 'AA result differs from selected raw passes')
    if controls:
        require(controls['source_sha256'] == sources, 'boundary source binding differs')
        plan = load(deref(controls['plan']))
        for p, r in controls['controls'].items():
            unit = load(deref(r['unit'])); observed = load(deref(unit['selected']))
            spec = plan['controls'][p]; asked = spec['trace']
            require(unit['status'] == 'CLEAN' and unit['attempts'][-1]['observation'] == unit['selected']
                    and all(a['status'] == 'LOADED' for a in unit['attempts'][:-1]), 'boundary first-CLEAN result differs')
            identity = observed['identity']; s = observed['summary']; rows = observed['rows']
            require(identity['profile'] == p and identity['mode'] == 'latency' and identity['fresh'] is True and identity['probe'] is True
                    and identity['source_sha256'] == sources and identity['case_sha256'] == hashlib.sha256(packed(spec['case'])).hexdigest()
                    and identity['trace_sha256'] == hashlib.sha256(packed(asked)).hexdigest()
                    and s['status'] == 'PASS' and s['semantics'] == 0 and s['queries'] == 2000 and s['warmups'] == 24 and len(rows) == 2000,
                    'boundary observation scope differs')
            groups = dict(aligned=[], crossing=[])
            for i, (row, role) in enumerate(zip(rows, asked['roles'])):
                require(row['query'] == i and row['start0'] == asked['requests']['offsets'][i] and row['verified'] is True
                        and row['differences'] == 0 and type(row['elapsed_ns']) is int and row['elapsed_ns'] > 0, 'boundary raw request differs')
                groups[role].append(row['elapsed_ns'])
            require(all(len(g) == 1000 for g in groups.values()), 'boundary pair balance differs')
            a, b = sorted(groups['aligned'])[499], sorted(groups['crossing'])[499]
            require((a, b) == (r['aligned_p50_ns'], r['crossing_p50_ns']) and r['strictly_more_cost'] is (b > a), 'boundary gate differs from raw values')
    return aa, controls


def render(value):
    text = [SIGNATURE, '', '# HW-REGION-2 — casefix continuation', '',
            '**' + value['status'] + '.** ' + value['reason'], '',
            'The retained [original Kill](../RESULTS-before-casefix.md) and its captures remain unchanged. The owner-authorized one-line [casefix](../lib2bit-casefix.patch) is the only lib2bit source change; no Kent/UCSC implementation or binary is used. [Full casefix stage report](RESULTS.md).', '',
            'The unchanged reader’s case discrepancy from FASTA is limited to N inside soft-mask runs: full-archive N/mask overlap analysis identifies 181 such positions on chr1, first chr1:121757469 (one-based); the retained original native witness confirms n→N.', '',
            'Scope: ace-core / AMD EPYC 4344P, one timed CPU0 and T=1, archive/index files warm in RAM/page cache; controller/build/correctness CPU15. These finite sampled coordinate results do not establish cross-host or exhaustive reader correctness. The terminal-packed-byte limitation remains unpatched; the frozen sampled grid has no terminal or last-packed-byte endpoint.', '',
            'Equivalent rows return the same 16,384 case-preserved bases. ACEAPEX 2.6.5 interactive L2 (LIT=65536/FSE=4096), zstd 1.5.7 L3 and BGZF/HTSlib 1.24 L6 use 16 KiB FASTA blocks/frames plus all required FAI/GZI bytes. The .2bit-casefix row uses storeMasked=1. Original masked and case-folded diagnostics are excluded from P1–P3 and fastest/smallest decisions.', '',
            'Main-cell protocol: a fresh process, one persistent handle, the same 12 warmups and 1000 saved starts mapped without resampling. Query timers include malloc-returning API work and ACE/zstd FAI span calculation, decode and newline removal. Validation, capture and free are outside. Open time is a separate single observation (n=1), excluding preload; RSS delta is after-open minus before-open, and peak RSS is the entire process including reference preparation, capture buffers, archive prefault and reader allocations. Neither is library-exclusive memory.', '']
    if value['timing_context']:
        t = value['timing_context']
        text += [f"Recorded timing boundaries: **{t['start_utc']} → {t['end_utc']} UTC**; {t['hostname']}, {t['cpu']}, kernel {t['kernel']}, governor {t['governor']}, pinned core {t['pinned_core']}. Dates come from retained start/end receipts.", '']
    aa, controls = method_data()
    if aa:
        text += ['## Method gates', '', 'A/A requires the strict integer comparison `20 × abs(B−A) < A`; clean slow results are never retried.', '',
                 '| Reader | A p50 ns | B p50 ns | abs(B−A)/A | Result |', '|---|---:|---:|---:|---|']
        for p, r in aa['profiles'].items():
            text.append(f"| {LABELS[p]} | {r['first_p50_ns']} | {r['second_p50_ns']} | {float(Fraction(abs(r['second_p50_ns']-r['first_p50_ns']),r['first_p50_ns'])):.6f} | {'PASS' if r['strict_under_five_percent'] else 'FAIL'} |")
        text += ['', '[A/A raw units](method-aa.json) · [Pre-timing execution clarification](EXECUTION_NOTE.md): each A/A pass is a separate load-admitted unit; the pair is judged once.', '']
    if controls:
        text += ['| Boundary control | Aligned p50 ns | Crossing p50 ns | Strict crossing > aligned |', '|---|---:|---:|---|']
        for p, r in controls['controls'].items():
            text.append(f"| {LABELS[p]} | {r['aligned_p50_ns']} | {r['crossing_p50_ns']} | {'PASS' if r['strictly_more_cost'] else 'FAIL'} |")
        text += ['', 'Real archive boundaries were selected by metadata alone; the .2bit control uses the preregistered uppercase/lowercase synthetic mask boundary. Fresh handles, 12 warmup pairs and 1000 AB/BA pairs separate aligned/crossing work. No timing-selected alternative or time-based retry is allowed. [Control plan](controls-plan.json) · [Control results](controls.json).', '']
    if not value['rows']:
        text += ['## Forecast status', '', *[f"- {p}: **{r['verdict']}**." for p, r in value['forecasts'].items()], '',
                 'No complete main timing table or new README performance row is published at this status. Existing retained method units are not a replacement main comparison.', '']
    else:
        text += ['## Unchanged forecasts', '', '| Forecast | Exact comparison | Verdict |', '|---|---|---|']
        p1, p2, p3 = (value['forecasts'][p] for p in ('P1', 'P2', 'P3'))
        p3_scope = (f"{p3['wins']} wins among {p3['observed']}/30 observed T2T windows; {p3['pending']} pending; required ≥28 of 30"
                    if value.get('partial') else f"{p3['wins']}/30 windows; required ≥28")
        text += [f"| P1 (65%) | 20 × {p1['ACE_stored_bytes']} ≤ 19 × {p1['twobit_stored_bytes']}; ACE/.2bit = {p1['exact_ratio']} | {p1['verdict']} |",
                 f"| P2 (75%) | 4 × {p2['casefix_p50_ns']} ≤ {p2['ACE_p50_ns']}; .2bit/ACE p50 = {p2['exact_ratio']} | {p2['verdict']} |",
                 f"| P3 (70%) | .2bit-casefix p50 < ACE p50 in {p3_scope} | {p3['verdict']} |", '',
                 'The fixed reader passed the mandatory repeated lowercase-n witness and whole sampled grid before any timer.', '',
                 '## Audited partial same-run table' if value.get('partial') else '## Complete same-run table', '']
        if value.get('partial'):
            text += [f"**Partial: {len(value['completed_corpora'])}/31 complete corpora, {len(value['rows'])}/186 main rows.** Checkpoint integrity is PASS; experiment completion is **BLOCKED: load**. The retained CLEAN rows remain valid. No final P3 verdict or README performance row is admitted.", '',
                     '**Not measured:** ' + ', '.join(value['missing_corpora']) + '. No zero-valued rows stand in for these missing measurements.', '']
        text += [
                 '| Corpus | Reader | Stored B | p50 µs | p99 µs | Open µs (n=1) | Open RSS delta KiB | Peak whole-process KiB |',
                 '|---|---|---:|---:|---:|---:|---:|---:|']
        for r in value['rows']:
            diagnostic = r['profile'] == 'twobit_original_mask1'
            stored, delta, peak = ('—', '—', '—') if diagnostic else (str(r['stored_bytes']), str(r['open_rss_delta_kib']), str(r['peak_process_rss_kib']))
            text.append(f"| {r['corpus']} | {r['label']} | {stored} | {r['p50_ns']/1000:.3f} | {r['p99_ns']/1000:.3f} | {r['open_ns']/1000:.3f} | {delta} | {peak} |")
        diagnostic_primary = {r['profile']: r for r in value['rows'] if r['corpus'] == 'chr1'}
        fixed = diagnostic_primary['twobit_casefix_mask1']['p50_ns']
        original = diagnostic_primary['twobit_original_mask1']['p50_ns']
        folded = diagnostic_primary['twobit_original_mask0']['p50_ns']
        diagnostic_ratio = Fraction(fixed, original)
        text += ['', 'Original storeMasked=1 is a time-only diagnostic: stored bytes and RSS are deliberately omitted. All thirty frozen T2T sequences contain no N/n; the diagnostic label identifies the unchanged reader’s failure to preserve chr1 case. The separate original storeMasked=0 row is case-folded and not equivalent.', '',
                 f"Primary chr1 p50, separate first-CLEAN passes: casefix/storeMasked=1 {fixed/1000:.3f} µs; original/storeMasked=1 {original/1000:.3f} µs; casefix/original {float(diagnostic_ratio):.6f} ({float(100*(diagnostic_ratio-1)):+.2f}%). Original/storeMasked=0 {folded/1000:.3f} µs is the separate case-folded diagnostic. These separate passes do not isolate a causal timing effect of the patch.", '',
                 '## Completed-corpus decisions — four equivalent rows only', '']
        for corpus, d in value['corpus_decisions'].items():
            fastest = ' / '.join(LABELS[p] for p in d['fastest']); smallest = ' / '.join(LABELS[p] for p in d['smallest'])
            text.append(f"- {corpus}: lowest p50 {fastest} ({d['fastest_p50_ns']/1000:.3f} µs); smallest {smallest} ({d['smallest_stored_bytes']} B).")
        if value.get('partial'):
            text += ['', '## Blocked logical unit', '',
                     'The three admissions below never started the timed worker: no warmups, query timers or open timers ran for this blocked unit. Foreign CPU strictly above 10% is an independent LOADED criterion, even when load1 is below 2.0. The linked raw receipts retain the one-second process observations and top-eight `ps` output.', '',
                     '| Unit / profile | Attempt | load1 start / end | Foreign process admission CPU | Worker started | Receipt + ps |',
                     '|---|---:|---:|---|---|---|']
            for blocked in value['blocked_units']:
                for attempt in blocked['attempts']:
                    processes = '; '.join(f"PID {p['pid']} {p['comm']} {float(Fraction(p['percent_one_cpu'])):.2f}%" for p in attempt['foreign'])
                    text.append(f"| {blocked['unit_id']} / {blocked['profile']} | {attempt['number']} | {attempt['load1_start']} / {attempt['load1_end']} | {processes} | no | [raw]({attempt['receipt']['path']}) |")
            for blocked in value['blocked_units']:
                text += ['', 'Recorded `ps -eo pid,user,pcpu,comm --sort=-pcpu | head -8`, third LOADED admission:', '',
                         '```text', blocked['attempts'][-1]['ps_top8'].rstrip(), '```', '']
            text += ['', '**One next step:** the owner provides a quiet window and explicitly authorizes a fresh three-attempt budget for this same blocked unit, with the same reader binaries, seed and offsets. Preserve its three old LOADED admissions and reuse every CLEAN unit; no CLEAN measurement needs to be rerun.', '']
        counts = value['counts']
        accounting = (f"Saved checkpoint: {counts['timed_logical_units']} CLEAN timing units ({len(value['rows'])} main + {counts['timed_logical_units']-len(value['rows'])} method), "
                      f"{counts['blocked_timed_logical_units']} blocked unit, {counts['attempts']} total attempts, {counts['loaded_attempts']} LOADED admissions, "
                      f"{counts['accepted_retaken']} accepted units retaken, and {counts['accepted_query_timing_observations']} accepted query timings."
                      if value.get('partial') else
                      f"Saved audit counts: {counts['timed_logical_units']} accepted timing units; {counts['attempts']} attempts; {counts['retaken']} retaken units; "
                      f"{counts['loaded_attempts']} LOADED attempts; {counts['accepted_query_timing_observations']} accepted query timings.")
        text += ['', '## Retention and audit', '',
                 'Every timing unit uses blocking `flock /run/lock/ovh-bench.lock`. LOADED means load1−T>1 at either boundary or a surviving foreign process strictly above 10% of one CPU at admission; equality at 2.0/10% passes. At most three identical attempts retain all LOADED data and accept the first CLEAN; worker errors stop even on loaded attempts. Other-core CPU accounting is observational.', '',
                 accounting + ' Full raw strings remain private and public deterministic gzip captures bind their raw/compressed hashes.', '',
                 '[Independent saved-data ' + ('checkpoint audit](audit/checkpoint.json)' if value.get('partial') else 'complete audit](audit/all.json)') +
                 ' · [Machine-readable summary and selected raw links](summary.json) · [Correctness admission](admission.json) · [Native source/build bindings](native/build.json) · [Pinned inputs, libraries and indexes](setup.json).', '']
    text += ['## Foundations and reproduction', '',
             '- ' + line_link('evidence/hw-region-1/RESULTS.md', '## Primary measured tradeoff', 'HW-REGION-1/RESULTS.md') + ' retains the separate FASTA-byte experiment; its timings are not reused as 16,384-base measurements.',
             '- ' + line_link('evidence/hw-region-2/PROTOCOL.md', '## Untimed admission procedure', 'Original PROTOCOL.md') + ' and [the retained Kill report](../RESULTS-before-casefix.md) define the original case mismatch; [this continuation protocol](PROTOCOL.md) preserves the forecasts and authorizes only the one-line patch.',
             '- The pinned [lib2bit API, 2bit.h:90](https://github.com/dpryan79/lib2bit/blob/58e20daa898a6fc338eae82e5d2ef7108d4fc07f/2bit.h#L90) opens masked tables; [2bit.h:116](https://github.com/dpryan79/lib2bit/blob/58e20daa898a6fc338eae82e5d2ef7108d4fc07f/2bit.h#L116) returns a malloc-owned sequence. The unchanged archive information and the one-line softMask reader patch remain separate identities.',
             '- ' + line_link('docs/METHOD_PROGNOZ_ZADANIE.md', 'Проверка метода', 'METHOD_PROGNOZ_ZADANIE.md') + ' requires method validation before the main grid; [CALIBRATION.md](CALIBRATION.md) retains the original four lines.', '',
             'The standalone [sequence adapter](../../../codecs/twobit.sh) builds the same pinned reader with the same one-line fix without requiring study corpora; [usage and domain exclusions](../../../docs/TWOBIT.md) describe seq-reader-build, seq-build and seq-fetch. Generic byte-axis qualification excludes this base-coordinate adapter before builds or fixtures.', '',
             'Render saved evidence only with `python3 -B evidence/hw-region-2/casefix/report.py`; the renderer imports no controller, library, clock or native code. The [original reader limitation](../PROTOCOL.md) is not broadened into an exhaustive correctness claim. No upstream post or merge is part of this experiment.', '']
    return '\n'.join(text)


def outputs():
    value = summary()
    document = render(value)
    def rebase(match):
        target = match.group(1)
        return match.group(0) if re.match(r'(?:[a-z]+:|#|/)', target) else '](' + posixpath.normpath(posixpath.join('casefix', target)) + ')'
    return value, document, re.sub(r'\]\(([^\s)]+)\)', rebase, document)


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--check', action='store_true'); args = p.parse_args()
    value, document, parent_document = outputs()
    expected = load(PARENT / 'verification.json')['report_sha256']
    backup = PARENT / 'RESULTS-before-casefix.md'
    if backup.exists():
        require(sha(backup) == expected, 'retained original Kill report changed')
    else:
        require(sha(PARENT / 'RESULTS.md') == expected, 'original Kill report must be preserved byte-for-byte')
        if not args.check:
            with backup.open('xb') as stream:
                stream.write((PARENT / 'RESULTS.md').read_bytes())
    generated = {HERE / 'summary.json': packed(value), HERE / 'RESULTS.md': document.encode(), PARENT / 'RESULTS.md': parent_document.encode()}
    for path, raw in generated.items():
        if args.check:
            require(path.exists() and path.read_bytes() == raw, 'generated report differs: ' + str(path))
        else:
            path.write_bytes(raw)
    print('REPORT', value['status'], 'rows', len(value['rows']))


if __name__ == '__main__':
    main()
