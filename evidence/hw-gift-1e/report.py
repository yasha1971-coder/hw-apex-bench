"""Render HW-GIFT-1e from complete independently audited saved evidence only.

No clocks, codecs, builds, Git, SSH, workers or network operations are invoked.
Missing required cells/search proof means INCOMPLETE, never an inferred result.
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
EVIDENCE = HERE.parent
CORES = ('v1.5.4', 'v1.5.7')
SCOPES = ('full', 'prefix')
CASES = ((10, 256), (10, 1024), (3, 256))
OLD_GRIDS = (256, 1024, 4096, 16384, 65536, 262144, 524288)


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'duplicate JSON key: '+key)
            value[key] = item
        return value
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


def median5(values):
    require(isinstance(values, list) and len(values) == 5 and all(type(v) is int and v > 0 for v in values),
            'five positive integer observations required')
    return sorted(values)[2]


def number(numerator, denominator=1, places=6):
    with localcontext() as context:
        context.prec = 60
        return f'{Decimal(numerator)/Decimal(denominator):.{places}f}'


def ms(ns):
    return number(ns, 1000000)


def table(headers, rows):
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| '+' | '.join(map(cell, headers))+' |', '| '+' | '.join('---' for _ in headers)+' |']+
                     ['| '+' | '.join(map(cell, row))+' |' for row in rows])


def link(path, title=None):
    return f'[{title or path}]({path})'


def bindings(root, audit):
    rows = audit.get('source_bindings')
    require(isinstance(rows, list) and rows, 'audit source bindings required')
    result = {}
    for row in rows:
        path = (root/row['path']).resolve()
        require(path.is_relative_to(EVIDENCE.resolve()) and path not in result, 'invalid/duplicate audit binding')
        require(sha(path) == row['sha256'], 'stale audit source binding: '+str(path))
        result[path] = row['sha256']
    return result


def checked(path, bound):
    path = Path(path).resolve()
    require(path in bound and sha(path) == bound[path], 'file not bound by the final audit: '+str(path))
    return load(path)


def referenced(root, value, bound):
    path = (root/value['path']).resolve()
    require(path.is_relative_to(root.resolve()) and sha(path) == value['sha256'], 'referenced evidence changed')
    return checked(path, bound)


def audit_gate(path):
    """This admission runs before opening any result or decision grid file."""
    audit = load(path)
    require(audit.get('status') == 'PASS' and audit.get('stage') == 'all'
            and audit.get('saved_data_only') is True and audit.get('no_codecs_or_clocks_executed') is True,
            'INCOMPLETE: independent final --stage all PASS audit required')
    require(audit.get('final_verification') is True, 'INCOMPLETE: presearch grid audit cannot replace final native/search verification')
    bound = bindings(HERE, audit)
    require(Path(__file__).resolve() in bound, 'final audit must bind this renderer before generation')
    require(isinstance(audit.get('literal_verdicts'), dict) and isinstance(audit.get('methods'), dict),
            'final audit has no primary/method verdicts')
    proof = audit.get('native_proof')
    require(isinstance(proof,dict), 'INCOMPLETE: final independent native proof required')
    native = referenced(HERE,dict(path=proof['path'],sha256=proof['sha256']),bound)
    require(native.get('schema') == 'hw-gift-1e-independent-native-v1' and native.get('status') == 'PASS'
            and native.get('no_clocks') is True and native.get('measurements_of_time') is False
            and native.get('all_attempts') is True and native.get('encodings_performed') == 0
            and proof.get('encodings_performed') == 0
            and native['source_sha256'] == proof['source_sha256'] == sha(HERE/'verify_native.py'), 'final native proof/source scope differs')
    for key in ('archive_references','archive_paths_verified','unique_archives_verified','frame_decodes_verified','restored_bytes_verified'):
        require(type(proof.get(key)) is int and proof[key] > 0 and proof[key] == native[key], 'native proof count differs: '+key)
    return audit, bound


def raw_summary(root, path, bound, variants, method=False):
    summary = checked(path, bound)
    require(summary['status'] == ('PASS' if method else 'COMPLETE'), 'saved summary incomplete/failed')
    repeats = summary['repeats']
    require(len(repeats) == 5, 'five complete CLEAN logical repeats required')
    selected, all_receipts = [], []
    attempts, retaken, loaded = 0, 0, 0
    maximum = [Decimal(0), Decimal(0)]
    for pair, item in enumerate(repeats):
        require(item['pair_index'] == pair and 1 <= len(item['attempts']) <= 3, 'repeat/retry shape changed')
        retaken += len(item['attempts']) > 1
        for index, attempt in enumerate(item['attempts'], 1):
            status = 'CLEAN' if index == len(item['attempts']) else 'LOADED'
            require(attempt['attempt'] == index and attempt['status'] == status, 'first CLEAN must win')
            receipt = referenced(root, attempt['receipt'], bound)
            require(receipt == attempt['receipt_data'] and receipt['status'] == status, 'retained receipt changed')
            if attempt.get('result') is not None:
                referenced(root, attempt['result'], bound)
            for slot, name in enumerate(('start', 'end')):
                value = Decimal(receipt[name]['loadavg_raw'].split()[0])
                require(value.is_finite() and value >= 0, 'invalid boundary load')
                maximum[slot] = max(maximum[slot], value)
            all_receipts.append(receipt)
            attempts += 1
            loaded += status == 'LOADED'
        final = item['attempts'][-1]
        require(item['selected_result'] == final['result'] and item['selected_receipt'] == final['receipt'], 'selected attempt changed')
        worker = referenced(root, item['selected_result'], bound)
        require(worker['pair_index'] == pair and worker['order'] == item['order'], 'selected worker order changed')
        require([r['variant'] for r in worker['results']] == item['order'], 'measurement slots changed')
        require(all(r['bit_perfect'] is True and type(r['compression_ns']) is int and r['compression_ns'] > 0
                    for r in worker['results']), 'invalid compression/restore observation')
        selected.append(worker['results'])
    counters = dict(logical_repeats=5, attempts=attempts, retaken=retaken, loaded_attempts=loaded)
    require(summary['planned_repeats'] == summary['started_repeats'] == 5
            and summary['retaken_repeats'] == retaken and summary['loaded_attempts'] == loaded, 'summary counts differ from raw')
    result = dict(summary=summary, selected=selected, counters=counters, maximum=maximum,
                  path=path.relative_to(HERE).as_posix() if path.is_relative_to(HERE) else '../'+path.relative_to(EVIDENCE).as_posix())
    if method:
        require(all([r['variant'] for r in rows] == ['A','A'] for rows in selected), 'AA slots lost')
        first, second = [r[0]['compression_ns'] for r in selected], [r[1]['compression_ns'] for r in selected]
        a, b = median5(first), median5(second)
        require(20*abs(b-a) < a and summary['first_ns'] == first and summary['second_ns'] == second
                and (summary['median_first_ns'], summary['median_second_ns']) == (a,b), 'strict AA admission changed')
        result.update(first_ns=first, second_ns=second, median_first_ns=a, median_second_ns=b)
        return result
    metrics = {}
    for variant in variants:
        rows = [next(row for row in pair if row['variant'] == variant) for pair in selected]
        times = [row['compression_ns'] for row in rows]
        identities = {(r['archive_bytes'],r['archive_sha256']) for r in rows}
        require(len(identities) == 1, 'archive identity changed between repetitions')
        size, digest = identities.pop()
        metrics[variant] = dict(compression_ns=times, median_ns=median5(times), min_ns=min(times), archive_bytes=size, archive_sha256=digest)
        require(all(summary['variants'][variant][key] == value for key, value in metrics[variant].items()), 'summary differs from raw')
    result['variants'] = metrics
    return result


def predicates(old, new):
    a, b = old['variants']['A']['median_ns'], old['variants']['B']['median_ns']
    p1 = dict(available=True, passed=b >= 5*a, A_ns=a, B_ns=b, ratio=str(Fraction(b,a)))
    p2 = dict(available=False, passed=None)
    if new is not None:
        c, d = new['variants']['A']['median_ns'], new['variants']['B']['median_ns']
        p2 = dict(available=True, passed=5*max(c,d) < 6*min(c,d), A_ns=c, B_ns=d, ratio=str(Fraction(d,c)))
    kill = b < 2*a
    return dict(P1=p1, P2=p2, Kill=dict(available=True,triggered=kill),
                search_admitted=bool(p1['passed'] and p2['passed'] and not kill))


def old_tradeoffs(bound):
    root = EVIDENCE/'hw-gift-1d'
    audit_path = root/'audit/final.json'
    audit = checked(audit_path, bound)
    require(audit['status'] == 'PASS' and audit['stage'] == 'all', 'complete saved 1d audit required')
    prior_bound = bindings(root, audit)
    rows = []
    for phase, corpus in (('train','enwik8'), ('holdout','silesia.tar')):
        for level in (3,10,19):
            for g in OLD_GRIDS:
                path = root/'cells'/phase/f'L{level}-G{g}.json'
                require(path.resolve() in bound, '1d trade-off summary is not bound by the 1e final audit')
                cell = raw_summary(root, path, prior_bound, ('original','nohint'))
                require(cell['summary']['corpus'] == corpus and cell['summary']['level'] == level and cell['summary']['g'] == g,
                        '1d trade-off coordinate changed')
                a, b = cell['variants']['original'], cell['variants']['nohint']
                cell.update(corpus=corpus, level=level, g=g, A=a, B=b, summary_sha256=sha(path))
                rows.append(cell)
    return rows, dict(path='../hw-gift-1d/audit/final.json', sha256=sha(audit_path))


def search_data(required, bound):
    if not required:
        require(not (HERE/'search/result.json').exists(), 'search result exists although primary search gates did not admit it')
        return None
    path, audit_path = HERE/'search/result.json', HERE/'search/audit.json'
    require(path.is_file() and audit_path.is_file(), 'INCOMPLETE: admitted core search needs search/result.json and search/audit.json')
    result, audit = checked(path, bound), checked(audit_path, bound)
    require(audit.get('status') == 'PASS' and audit.get('saved_data_only') is True, 'independent search audit must pass')
    require(audit.get('result_sha256') == sha(path), 'search audit/result binding changed')
    require(result['status'] in ('ADJACENT TRANSITION', 'NARROWED RANGE', 'NO BRACKET')
            and type(result['build_count']) is int and 2 <= result['build_count'] <= 12
            and result['global_first_fast_claim'] is False, 'invalid bounded search result')
    require(isinstance(result['tested'], list), 'search tested list missing')
    summaries = {}
    for row in result['tested']:
        require(isinstance(row['commit'],str) and len(row['commit']) == 40 and isinstance(row['title'],str), 'search commit identity missing')
        require('classifier' in row and 'median_C_ns' in row and 'median_ref_ns' in row and 'pair_summary' in row,
                'search test lacks classifier/median/saved-pair source')
        summaries[row['pair_summary']['path']] = referenced(HERE, row['pair_summary'], bound)
    if 'endpoint_summary' in result:
        summaries[result['endpoint_summary']['path']] = referenced(HERE,result['endpoint_summary'],bound)
    pair_stats = {}
    for name, summary in summaries.items():
        require(summary['status'] == 'COMPLETE' and len(summary['repeats']) == 5,'search paired summary incomplete')
        samples = {'C':[],'R':[]}
        for repeat in summary['repeats']:
            raw = referenced(HERE,repeat['selected_result'],bound)
            for slot in raw['results']:
                samples[slot['label']].append(slot['compression_ns'])
        stats = dict(median_C_ns=median5(samples['C']),median_ref_ns=median5(samples['R']),
                     min_C_ns=min(samples['C']),min_ref_ns=min(samples['R']),logical_repeats=5,
                     attempts=sum(len(r['attempts']) for r in summary['repeats']),
                     retaken=sum(len(r['attempts']) > 1 for r in summary['repeats']),
                     loaded_attempts=sum(a['status']=='LOADED' for r in summary['repeats'] for a in r['attempts']))
        require(all(summary[key] == stats[key] for key in ('median_C_ns','median_ref_ns','min_C_ns','min_ref_ns')),
                'search medians/minima changed from saved raw')
        pair_stats[name] = stats
    if result['status'] == 'ADJACENT TRANSITION':
        require(result['transition']['adjacent_first_parent'] is True, 'transition must be qualified as first-parent adjacent')
    elif result['status'] == 'NARROWED RANGE':
        require(set(result['remaining_range']) >= {'slow','fast'}, 'narrowed range endpoints missing')
    s1 = audit.get('S1')
    require(isinstance(s1,dict) and s1.get('verdict') in ('HIT','MISS','NOT TESTED')
            and s1.get('slow_commit') == 'e2965edd107acd0123294e23848cdc00af906468'
            and s1.get('fast_commit') == '9420bce8a491e21821c4b372f837bf4bd47e5870', 'independent local forecast S1 verdict missing')
    result['_audit'],result['_pairs'] = audit,pair_stats
    return result


def load_all(audit_path):
    audit, bound = audit_gate(audit_path)
    old = raw_summary(HERE, HERE/'cells/v1.5.4/full-L10-G256.json', bound, ('A','B'))
    kill = old['variants']['B']['median_ns'] < 2*old['variants']['A']['median_ns']
    cells = {('v1.5.4','full',10,256):old}
    new = None
    if not kill:
        for core in CORES:
            for scope in SCOPES:
                for level,g in CASES:
                    key = core,scope,level,g
                    if key not in cells:
                        cells[key] = raw_summary(HERE, HERE/'cells'/core/f'{scope}-L{level}-G{g}.json', bound, ('A','B'))
        new = cells['v1.5.7','full',10,256]
    verdicts = predicates(old,new)
    require(verdicts == audit['literal_verdicts'] and audit['verified_cells'] == len(cells), 'primary integer verdict/count differs from audit')
    decision = checked(HERE/'decision.json', bound)
    missing = []
    for core in CORES:
        for scope in SCOPES:
            for level,g in CASES:
                if (core,scope,level,g) not in cells:
                    require(kill and not (HERE/'cells'/core/f'{scope}-L{level}-G{g}.json').exists(), 'unapproved missing/extra cell')
                    missing.append(dict(core=core,scope=scope,level=level,g=g,status='NOT RUN: Kill'))
    require(decision['not_run'] == missing and decision['search_admitted'] == verdicts['search_admitted'], 'decision missing-cell/search state changed')
    methods = {}
    for core in (CORES[:1] if kill else CORES):
        methods[core] = raw_summary(HERE, HERE/f'method-{core}.json', bound, (), True)
        method = methods[core]
        expected = {k:method[k] for k in ('first_ns','second_ns','median_first_ns','median_second_ns')}
        expected.update(passed=True, counters=method['counters'])
        require(expected == audit['methods'][core], 'method gate differs from independent audit')
    if kill:
        require(not (HERE/'method-v1.5.7.json').exists(), 'modern AA must remain NOT RUN after Kill')
    counters = {k:sum(c['counters'][k] for c in cells.values()) for k in old['counters']}
    require(counters == audit['cell_counters'], 'cell attempt counts differ from audit')
    tradeoffs, prior_audit = old_tradeoffs(bound)
    search = search_data(verdicts['search_admitted'], bound)
    return dict(audit=audit,audit_path=audit_path,verdicts=verdicts,cells=cells,methods=methods,
                missing=missing,tradeoffs=tradeoffs,prior_audit=prior_audit,search=search)


def cell_rows(data):
    rows = []
    for core in CORES:
        for scope in SCOPES:
            for level,g in CASES:
                cell = data['cells'].get((core,scope,level,g))
                prefix = [core, 'full 100000000 B' if scope == 'full' else 'first 16777216 B', level,g]
                if cell is None:
                    rows.append(prefix+['—']*8+['NOT RUN: Kill'])
                    continue
                a,b = cell['variants']['A'],cell['variants']['B']
                rows.append(prefix+[a['archive_bytes'],b['archive_bytes'],ms(a['median_ns']),ms(a['min_ns']),
                                    ms(b['median_ns']),ms(b['min_ns']),number(b['median_ns'],a['median_ns']),
                                    number(max(a['median_ns'],b['median_ns']),min(a['median_ns'],b['median_ns'])),link(cell['path'],'COMPLETE')])
    return rows


def forecast_rows(data):
    v = data['verdicts']
    rows = []
    for name, forecast in (('P1','v1.5.4 FULL/L10/G256: median(B) ≥5×median(A)'),
                           ('P2','v1.5.7 same FULL primary: max(medians)/min(medians) <1.2')):
        r = v[name]
        if not r['available']:
            rows.append([name,forecast,'NOT RUN: Kill','No substituted prefix/auxiliary result'])
        else:
            a,b = r['A_ns'],r['B_ns']
            rows.append([name,forecast,'HIT' if r['passed'] else 'MISS',
                         f'A={a} ns; B={b} ns; B/A={number(b,a)}; symmetric factor={number(max(a,b),min(a,b))}'])
    rows.append(['Kill','v1.5.4 FULL primary: median(B) <2×median(A)',
                 'TRIGGERED' if v['Kill']['triggered'] else 'NOT TRIGGERED',
                 'Remaining timing stopped; no fixed-in-core claim' if v['Kill']['triggered'] else 'Proceeding does not imply P1 HIT'])
    return rows


def archive_rows(data):
    rows = []
    for key,cell in data['cells'].items():
        core,scope,level,g = key
        for variant in ('A','B'):
            item = cell['variants'][variant]
            rows.append([core,scope,level,g,variant,item['archive_bytes'],item['archive_sha256'],link(cell['path'],'saved cell')])
    return rows


def point(cell):
    return f"{cell['corpus']}/L{cell['level']}/G{cell['g']}/"+('prefix16MiB' if cell['g'] in (256,1024) else 'full')


def tradeoff_ranges(data):
    groups = [('L3, all 14 corpus/frame cells (tiny frames use prefixes)',[c for c in data['tradeoffs'] if c['level']==3]),
              ('L10, full input at 4–256 KiB (8 cells)',[c for c in data['tradeoffs'] if c['level']==10 and 4096<=c['g']<=262144]),
              ('L19, full input at 4–256 KiB (8 cells)',[c for c in data['tradeoffs'] if c['level']==19 and 4096<=c['g']<=262144])]
    rows = []
    for label,cells in groups:
        time_ratio = lambda c: Fraction(c['A']['median_ns'],c['B']['median_ns'])
        size_change = lambda c: Fraction(100*(c['A']['archive_bytes']-c['B']['archive_bytes']),c['B']['archive_bytes'])
        lo,hi = min(cells,key=time_ratio),max(cells,key=time_ratio)
        small,large = min(cells,key=size_change),max(cells,key=size_change)
        def fmt(value):
            return number(value.numerator,value.denominator)
        rows.append([label,fmt(time_ratio(lo))+' … '+fmt(time_ratio(hi)),point(lo)+' … '+point(hi),
                     fmt(size_change(small))+' … '+fmt(size_change(large)),point(small)+' … '+point(large)])
    return table(['Saved 1d scope','Hint time A/B range','Time extrema point IDs','Hint archive Δ vs B % range','Size extrema point IDs'],rows)


def tradeoff_table(data):
    rows = []
    for c in data['tradeoffs']:
        a,b = c['A'],c['B']
        rows.append([point(c),a['archive_bytes'],b['archive_bytes'],a['archive_bytes']-b['archive_bytes'],
                     number(100*(a['archive_bytes']-b['archive_bytes']),b['archive_bytes'],4),ms(a['median_ns']),ms(b['median_ns']),
                     number(a['median_ns'],b['median_ns']),link(c['path'],'saved cell'),c['summary_sha256']])
    return table(['1d point / input scope','Hint A B','Zero-hint B B','A−B bytes','A size ΔB %','Hint A median ms',
                  'Zero-hint B median ms','Hint time A/B','Source','Cell JSON SHA-256'],rows)


def count_table(data):
    rows = []
    for core in CORES:
        for kind in ('AA method','A/B grid'):
            cells = [data['methods'][core]] if kind=='AA method' and core in data['methods'] else (
                [c for key,c in data['cells'].items() if key[0]==core] if kind=='A/B grid' else [])
            counters = {k:sum(c['counters'][k] for c in cells) for k in ('logical_repeats','attempts','retaken','loaded_attempts')}
            maximum = [max((c['maximum'][i] for c in cells),default=Decimal(0)) for i in (0,1)]
            rows.append([core,kind,counters['logical_repeats'],counters['retaken'],counters['attempts'],counters['loaded_attempts'],
                         str(maximum[0]) if cells else 'NOT RUN: Kill',str(maximum[1]) if cells else 'NOT RUN: Kill'])
    return table(['Core','Stage','M logical rounds','N retaken rounds','All attempts','LOADED attempts','Max start load1','Max end load1'],rows)


def search_text(data):
    search = data['search']
    if search is None:
        return 'Core search was **NOT ADMITTED**: it requires both primary P1 and P2 HIT. A P1 MISS between 2× and 5× permits the fixed grid but does not permit a search.'
    parts = [f"Search result: **{search['status']}**; {search['build_count']}/12 total core builds, including the two endpoints. "
             'The prefix16MiB search is distinct from the full-input primary gates; its fresh endpoint bracket/classifier has its own protocol and audit.',
             link('search/result.json')+', '+link('search/audit.json')+'. Global first-fast claim: **false**.']
    s1 = search['_audit']['S1']
    parts.append(table(['New forecast','Exact tested pair','Verdict','Observed classifications'],[[s1['forecast'],
        s1['slow_commit']+' → '+s1['fast_commit'],s1['verdict'],
        str(s1.get('slow_classification'))+' → '+str(s1.get('fast_classification'))]]))
    if search['status'] == 'ADJACENT TRANSITION':
        t = search['transition']
        parts.append(f"Observed adjacent first-parent boundary: `{t['slow_commit']}` → `{t['fast_commit']}` ({t['fast_title']}). "
                     'This is a measured transition on the chosen path, not proof of the earliest fast commit anywhere in the DAG or attribution of a merge to one side-branch patch.')
    elif search['status'] == 'NARROWED RANGE':
        r = search['remaining_range']
        parts.append(f"Remaining slow-to-fast range: `{r['slow']}` → `{r['fast']}`; no adjacent transition is claimed.")
    else:
        parts.append('The prefix endpoint observations did not establish the required bracket; no candidate transition or fixed-in-commit claim follows.')
    rows = []
    for r in search['tested']:
        stats = search['_pairs'][r['pair_summary']['path']]
        min_c = stats['min_ref_ns'] if r.get('role') == 'endpoint_reference' else stats['min_C_ns']
        rows.append([r['commit'],r['title'],r['classifier'],r['median_C_ns'],min_c,r['median_ref_ns'],stats['min_ref_ns'],
                     link(r['pair_summary']['path'],'saved pairs')])
    if rows:
        parts.append(table(['Core commit','Title','Classification','Candidate median ns','Candidate min ns','Reference median ns','Reference min ns','Evidence'],rows))
        parts.append('The two tag endpoint rows share one fresh five-pair stage; the modern endpoint row reports that stage\'s actual R observations, not an extra R/R timing.')
    totals = {key:sum(s[key] for s in search['_pairs'].values()) for key in ('logical_repeats','attempts','retaken','loaded_attempts')}
    parts.append(f"Search rounds (deduplicating shared endpoint evidence): {totals['retaken']} retaken / {totals['logical_repeats']} logical, "
                 f"{totals['attempts']} total attempts, {totals['loaded_attempts']} LOADED. Every raw attempt is retained.")
    return '\n\n'.join(parts)


def outcome_text(data):
    v = data['verdicts']
    if v['Kill']['triggered']:
        return ('The old-core full-input pair was below 2×: this harness did not reproduce the reported severe tiny-frame slowdown. '
                'The preregistered Kill stopped all remaining timing. The modern version and auxiliary cells are NOT RUN; '
                'there is no claim that a core change fixed the Pijul case. The host is EPYC rather than the historical M1, '
                'and the resident native bridge is not the original Pijul/Rust application; the full enwik8 input is explicit.')
    if v['P1']['passed'] and v['P2']['passed']:
        return ('Both full-input primary predictions HIT: the severe old-core slowdown is reproducible in this controlled native harness, '
                'and the modern pair differs by less than 1.2×. With identical seekable writer/decoder/header/bridge across the tags, '
                'this supports a core-version effect in this harness. The bounded prefix search below qualifies its transition/range; '
                'no global first-fast or original-Pijul application claim is made.')
    return ('The literal primary predictions above determine the result. A result between 2× and 5× in the old core is a P1 MISS without Kill; '
            'a modern symmetric difference of at least 1.2× is a P2 MISS. These outcomes do not support the combined historical-slowdown-gone '
            'claim and do not admit core search. Auxiliary/prefix observations do not replace either full-input primary.')


def results_text(data):
    parts = ['# HW-GIFT-1e results',outcome_text(data),
        'Independent saved-data audit: '+link('audit/final.json')+f" (SHA-256 `{sha(data['audit_path'])}`). "
        'All predicates use integer nanoseconds before display rounding. Compression times below are median/minimum of five CLEAN rounds; '
        'there is no decode timing. P1 uses an inclusive 5× boundary, P2 a strict symmetric <1.2× boundary, and Kill a strict <2× boundary.',
        table(['Gate','Preregistered condition','Verdict','Full-input fact'],forecast_rows(data)),
        '## Version / scope / configuration grid',
        'A has the PR #3544 assert and source-size hint setter; B literally omits the setter. Full enwik8 is 100,000,000 bytes; '
        'prefix is exactly its first 16,777,216 bytes. No full/prefix observations or A/A and A/B observations are pooled. '
        'Archive sizes include the complete seek table with checksums. Missing Kill cells contain no fabricated zero/timing/size.',
        table(['Core','Input scope','L','G B','A archive B','B archive B','A median ms','A min ms','B median ms','B min ms',
               'B/A median','Symmetric factor','Status/source'],cell_rows(data)),
        'All five integer compression observations, complete archive SHA values, input SHA and raw-result references appear in '+link('TABLE.csv')+'.',
        table(['Core','Scope','L','G B','Variant','Complete archive B','Complete archive SHA-256','Source'],archive_rows(data)),
        '## Method and retained attempts']
    method_rows = []
    for core in CORES:
        m = data['methods'].get(core)
        method_rows.append([core,'NOT RUN: Kill','—','—'] if m is None else
                           [core,m['median_first_ns'],m['median_second_ns'],link(m['path'],'PASS: strict <5%')])
    parts.extend([table(['Core','A/A first median ns','A/A second median ns','Admission'],method_rows),
        'Each method gate is five fresh full/L10/G256 A/A rounds and uses `20*abs(second-first)<first`; it is never retried for elapsed-time instability. '
        'Untimed positive/changed-input/corrupt-magic checks, runtime CLI/library versions, known saved 1d prefix bytes, all frame checksums '
        'and legitimate terminal empty-frame checks passed before main use. See '+link('method-controls.json')+'.',
        count_table(data),
        'All CLEAN and LOADED requests/results/receipts/stdout/stderr are retained. Only successful rounds with load1>2.0 at either boundary '
        'are mechanically retaken, immediately, at most three attempts; first CLEAN wins. ERROR is fatal. These maxima include loaded attempts. '
        'Other-core /proc/stat deltas are observations, not exclusion rules.',
        '## Conditional core search',search_text(data),
        '## Saved HW-GIFT-1d hint trade-offs',
        'These are separate saved v1.5.7 observations. 1d B calls the setter with zero; 1e B omits the call. Exact prefix archive equality '
        'is a known answer, not permission to pool their timings. Here hint time A/B means median(hint)/median(zero setter). '
        'Hint archive ΔB% is `100*(hint bytes − zero-hint bytes)/zero-hint bytes`: negative means hinting is smaller. '
        'Ranges use exact fractions and name their extreme points; the scoped summaries do not hide the other points.',
        tradeoff_ranges(data),
        'All 42 baseline 1d points follow, including tiny prefixes, the 512 KiB points outside the scoped 4–256 KiB summaries, '
        'opposite-direction outcomes, and exact byte-sized differences:',tradeoff_table(data),
        'Saved 1d audit: '+link(data['prior_audit']['path'])+f"; SHA-256 `{data['prior_audit']['sha256']}`. "
        'Each displayed cell SHA binds its five original raw compression results. No 1d archive was regenerated.',
        '## Scope and source controls',
        'ace-core, AMD EPYC 4344P, Linux, pinned CPU 0, schedutil; one thread, input/output resident in RAM. Both cores were built with the same '
        'compiler and `-O3 -fPIC -fno-lto`; shared libraries use `-Bsymbolic` and RTLD_LOCAL. Each core supplies its own headers/static library. '
        'The v1.5.4 seekable writer/decoder/header and the retained resident bridge are frozen across cores; A adds only the two PR lines. '
        'The untimed checksum/terminal-frame validation helpers are identical across libraries and outside encode intervals. '
        'Fresh contexts and prefaulted outer buffers precede timers; codec first-use allocation remains inside. No universal-machine, process-RSS '
        'or original-application performance claim follows from this native harness.',
        'The final independent native verifier performed zero encodings and read no clocks; '+
        str(data['audit']['native_proof']['archive_paths_verified'])+' actual archive paths and '+
        str(data['audit']['native_proof']['unique_archives_verified'])+' distinct archives were checked, with '+
        str(data['audit']['native_proof']['frame_decodes_verified'])+' frame decodes. See '+link('audit/native.json')+'.',
        'Builds, annotated tag/source/binary/header hashes, linked version numbers/strings and `zstd -V`: '+link('setup.json')+', '+link('SOURCE_PATHS.md')+'. '
        'The 2023 M1 35 s→2.5 s observations are attributed to the PR description; the later reproducer confirms L10/256-byte settings. '
        'Later core optimizations are source context, not a substitute for these measured gates or an unmeasured ablation.',
        'Draft PR #94 remains draft. '+link('ZSTD_ISSUE_DRAFT.md')+' is unsent; no upstream issue/comment or merge is performed.'])
    return '\n\n'.join(parts)+'\n'


def csv_text(data):
    fields = ['core','scope','level','frame_bytes','status','input_bytes','input_sha256','full_corpus_bytes','full_corpus_sha256',
              'variant','hint_policy','archive_bytes','archive_sha256']+[f'compression_ns_{i}' for i in range(5)]+[
              'compression_median_ns','compression_min_ns','ratio_B_over_A_exact','symmetric_factor_exact','cell_summary','cell_summary_sha256']+[
              f'raw_repeat_{i}' for i in range(5)]
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream,fieldnames=fields,lineterminator='\n')
    writer.writeheader()
    for core in CORES:
        for scope in SCOPES:
            for level,g in CASES:
                cell = data['cells'].get((core,scope,level,g))
                for variant in ('A','B'):
                    row = dict(core=core,scope=scope,level=level,frame_bytes=g,variant=variant,
                               hint_policy='setter=maxFrameSize' if variant=='A' else 'setter absent',
                               status='COMPLETE' if cell is not None else 'NOT RUN: Kill')
                    if cell is not None:
                        s,m = cell['summary'],cell['variants'][variant]
                        a,b = cell['variants']['A']['median_ns'],cell['variants']['B']['median_ns']
                        for key in ('input_bytes','input_sha256','full_corpus_bytes','full_corpus_sha256'):
                            row[key] = s[key]
                        row.update(archive_bytes=m['archive_bytes'],archive_sha256=m['archive_sha256'],
                                   compression_median_ns=m['median_ns'],compression_min_ns=m['min_ns'],
                                   ratio_B_over_A_exact=str(Fraction(b,a)),symmetric_factor_exact=str(Fraction(max(a,b),min(a,b))),
                                   cell_summary=cell['path'],cell_summary_sha256=sha(HERE/cell['path']))
                        row.update({f'compression_ns_{i}':n for i,n in enumerate(m['compression_ns'])})
                        row.update({f'raw_repeat_{i}':r['selected_result']['path'] for i,r in enumerate(s['repeats'])})
                    writer.writerow(row)
    return stream.getvalue()


def issue_text(data):
    v = data['verdicts']
    parts = ['[PR #3544](https://github.com/meta/zstd/pull/3544) intentionally improved ingestion of very small seekable frames by providing a source-size hint.',
        '# Draft: historical tiny-frame slowdown and the current hint trade-off',
        '**UNSENT DRAFT.** No upstream issue/comment has been sent.',
        'The PR description reports historical M1 enwik8 L10/256-byte times of 35 s→2.5 s. The '
        '[original Pijul comment](https://github.com/meta/zstd/issues/2662#issuecomment-1443836186) reports the regression; the '
        '[later reproducer](https://github.com/meta/zstd/issues/2662#issuecomment-1457696603) supplies the L10/256-byte scenario. '
        'Those historical observations are distinct from the present host and native harness.',
        outcome_text(data),table(['Gate','Full-input condition','Verdict','Observed fact'],forecast_rows(data)),
        'The primary question uses full enwik8 (100,000,000 bytes), not a substituted 16 MiB prefix. The entire version/scope grid, '
        'including explicit NOT RUN: Kill entries, medians/minima, complete archive bytes/SHA and five raw observations, is in '+link('RESULTS.md')+' and '+link('TABLE.csv')+'.',
        search_text(data),
        '## What the saved v1.5.7 hint trade-off costs by level',
        'Separate HW-GIFT-1d data: A sets hint=maxFrameSize; B calls the setter with zero. HW-GIFT-1e B omits the call, '
        'so timing observations from these studies are not pooled. The time ratio is hint/zero-hint; the signed archive percentage '
        'is `100*(hint bytes − zero-hint bytes)/zero-hint bytes`. Negative size percentages mean the hint produces a smaller archive.',
        tradeoff_ranges(data),
        'These scoped ranges are derived from saved integer medians and byte counts, rather than copied approximate forecasts. '
        'L3 includes all 14 points and explicitly includes 16 MiB prefixes at 256/1024-byte frames. L10/L19 summaries cover the eight '
        'full-input 4–256 KiB points on two corpora. All tiny, 512 KiB, opposite-direction and exact-byte differences remain in the '
        'complete 42-point table with source SHA in '+link('RESULTS.md')+'. A conditional rule need not be a free win: hint speed and density can change in either direction.',
        'ace-core AMD EPYC 4344P, Linux CPU 0, schedutil, RAM input/output, one thread; exact v1.5.4/v1.5.7 sources and equal compiler flags, '
        'fixed historical seekable writer/decoder/header/bridge, matching per-core headers/static libraries. Five interleaved A/B rounds; '
        'fresh contexts and prefaulted outer buffers outside the encode timer, internal first-use allocation inside. Full byte/checksum/empty-frame '
        'checks are untimed. Both actually linked versions and CLI versions are recorded. This is not the original Pijul application or a universal-machine result.',
        'Executed full-input A/A gates ('+', '.join(data['methods'])+') passed strict <5% before their grids; '
        'a version stopped by Kill has no substituted method observation. Mechanically excluded load rounds and all raw attempts are retained. '
        'Independent controller: '+link('audit/final.json')+'. Source/history and primary URLs: '+link('SOURCE_PATHS.md')+'. '
        'No global first-fast, universal threshold, or individual side-branch causal claim follows from a bounded path search.']
    if v['Kill']['triggered'] or not v['P1']['passed']:
        question = 'Which additional details of the original Pijul/Rust reproducer would be needed to distinguish its historical slowdown from this full-input native-harness result?'
    elif v['P2']['passed']:
        question = 'Given this version-specific result and the saved level-dependent size/speed trade-offs, would you prefer an explicit configurable source-size-hint policy for the seekable writer?'
    else:
        question = 'Which intended small-frame workload should determine whether the seekable writer keeps an unconditional source-size hint or exposes a configurable policy?'
    parts.append(question)
    return '\n\n'.join(parts)+'\n'


def clean(text):
    return '\n'.join(line.rstrip() for line in text.splitlines()).rstrip()+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit',type=Path,default=HERE/'audit/final.json')
    parser.add_argument('--output-dir',type=Path,default=HERE)
    args = parser.parse_args()
    try:
        data = load_all(args.audit)
        outputs = {'RESULTS.md':clean(results_text(data)), 'TABLE.csv':csv_text(data), 'ZSTD_ISSUE_DRAFT.md':clean(issue_text(data))}
        args.output_dir.mkdir(parents=True,exist_ok=True)
        for name,text in outputs.items():
            destination = args.output_dir/name
            pending = destination.with_name(destination.name+'.writing')
            pending.write_text(text,encoding='utf-8',newline='\n')
            pending.replace(destination)
        print(json.dumps(dict(status='PASS',verified_cells=len(data['cells']),not_run_cells=len(data['missing']),files=list(outputs)),sort_keys=True))
        return 0
    except (OSError,ValueError,KeyError,TypeError,StopIteration) as error:
        print(json.dumps(dict(status='INCOMPLETE',reason=str(error)),sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
