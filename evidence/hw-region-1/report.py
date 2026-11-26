"""Render HW-REGION-1 from a complete, source-bound saved-data audit only.

No experiment imports, subprocesses, native libraries, clocks or network.
The CSV preserves integer/fraction values; rounding is presentation only.
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
ROOT = HERE.parents[1]
SIGNATURE = "[written by ChatGPT (AI) at the author's request; checked by the author]"
CODECS = ('aceapex', 'zstd_seekable', 'bgzip')
LABELS = dict(aceapex='ACEAPEX', zstd_seekable='zstd-seekable', bgzip='BGZF')
SIZES = (4096, 16384, 65536, 262144)
CSV_COLUMNS = (
    'case_id', 'corpus', 'nominal_g_bytes', 'effective_g_bytes', 'codec',
    'input_bytes', 'input_sha256', 'archive_bytes', 'index_bytes', 'stored_bytes',
    'compression_ratio_fraction', 'p50_ns', 'p99_ns', 'materialized_bytes_total',
    'requested_bytes_total', 'amplification_mean_fraction', 'amplification_p50_fraction',
    'zstd_calls_total', 'zstd_output_bytes_total', 'zstd_calls_mean_fraction',
    'zstd_output_bytes_mean_fraction', 'archive_sha256', 'index_sha256s',
    'case_path', 'latency_unit_path', 'selected_result_path', 'counter_path', 'trace_path')


def require(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'duplicate JSON key: ' + key)
        value[key] = item
    return value


def load(path):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


def number(value, places=6):
    value = Fraction(value)
    with localcontext() as ctx:
        ctx.prec = 60
        return format(Decimal(value.numerator) / Decimal(value.denominator), '.' + str(places) + 'f')


def percent(value, places=3):
    return number(Fraction(value) * 100, places) + '%'


def ordered_cases():
    return (['chr1-g16384', 'chr1-g4096', 'chr1-g65536']
            + [f't2t-{i:02d}-g{g}' for i in range(30) for g in (4096, 16384, 65536)]
            + ['enwik8-g16384', 'silesia-g16384'])


def load_all(audit_path):
    """Refuse partial/stale proofs before reading comparative results."""
    audit_path = Path(audit_path).resolve()
    require(audit_path.is_relative_to((HERE / 'audit').resolve()), 'audit escaped experiment audit directory')
    audit = load(audit_path)
    require(audit.get('schema') == 'hw-region-1-independent-audit-v1'
            and audit.get('status') == 'PASS' and audit.get('stage') == 'all'
            and audit.get('saved_data_only') is True and audit.get('no_codecs') is True
            and audit.get('no_clocks') is True, 'complete independent all-stage PASS required')
    require(audit.get('private_artifacts_unavailable') == 0
            and audit.get('private_bytes_verified_on_this_host') is True,
            'all private inputs, archives, libraries and captures must have been available to the auditor')
    bindings = {}
    require(isinstance(audit.get('source_bindings'), list) and audit['source_bindings'], 'empty audit source closure')
    for item in audit['source_bindings']:
        name, digest = item['path'], item['sha256']
        path = (HERE / name).resolve()
        require(path.is_relative_to(ROOT.resolve()) and not path.is_relative_to((ROOT / '.work').resolve()), 'audit source escaped repository')
        require(name not in bindings and sha(path) == digest, 'stale/duplicate audit binding: ' + name)
        bindings[name] = digest
    require(bindings.get('report.py') == sha(__file__), 'renderer source is not bound by final audit')

    def document(name):
        path = (HERE / name).resolve()
        require(path.is_relative_to(HERE.resolve()) and bindings.get(name) == sha(path), 'report input not bound by final audit: ' + name)
        return load(path)

    def reference(value):
        require(isinstance(value, dict) and set(value) == {'path', 'sha256'}, 'invalid report reference')
        require(bindings.get(value['path']) == value['sha256'], 'reference outside final proof closure: ' + value['path'])
        return document(value['path'])

    setup = document('setup.json')
    decision = document('decision.json')
    fit = document('model/fit.json')
    primary_model = document('model/cases/chr1-g16384.json')
    controls = document('controls.json')
    method = document('method-check.json')
    require(setup['schema'] == 'hw-region-1-setup-v1' and decision['status'] == 'COMPLETE'
            and len(setup['inputs']) == 33 and set(setup['cases']) == set(ordered_cases()), 'fixed corpus/grid scope differs')
    require(set((HERE / 'cases').glob('*.json')) == {HERE / 'cases' / (name + '.json') for name in ordered_cases()}, 'all 95 case summaries required')
    require(audit['counts'] == decision['counts'] and audit['counts']['logical_units'] == 292
            and audit['counts']['accepted_timing_observations'] == 295000, 'complete timing counts differ')
    literal = audit['literal_verdicts']
    require(all(decision[key] == literal[key] for key in ('P1', 'P2', 'P3', 'Kill', 'outcome', 'dominant_primary_component')),
            'decision differs from independent exact forecast verdicts')
    require(audit['primary'] == decision['primary'], 'primary decision differs from audit')
    require(audit['output_proof_final']['path'] == 'audit/outputs-final.json', 'final independent output proof absent')
    output_proof = document('audit/outputs-final.json')
    require(output_proof['status'] == 'PASS' and output_proof['stage'] == 'all'
            and audit['output_proof_final']['sha256'] == sha(HERE / 'audit/outputs-final.json'), 'stale independent output proof')
    cases, rows = {}, []
    for name in ordered_cases():
        case = document('cases/' + name + '.json')
        require(case['status'] == 'COMPLETE' and case['case_id'] == name and set(case['formats']) == set(CODECS), 'incomplete case: ' + name)
        archive = reference(case['archives'])
        cases[name] = case
        for codec in CODECS:
            item, stored = case['formats'][codec], archive['formats'][codec]
            request = reference(item['request'])
            unit = reference(item['latency_unit'])
            require(unit['status'] == 'COMPLETE' and unit['kind'] == 'latency' and unit['codec'] == codec, 'invalid selected latency unit')
            timed = reference(unit['selected'])
            require(unit['selected'] == unit['attempts'][-1]['observation'] and unit['attempts'][-1]['status'] == 'CLEAN', 'first CLEAN selection differs')
            values = [r['elapsed_ns'] for r in timed['rows']]
            require(len(values) == 1000 and all(type(v) is int and v > 0 for v in values)
                    and sorted(values)[499] == item['p50_ns'] and sorted(values)[989] == item['p99_ns'], 'raw quantile differs')
            require(stored['stored_bytes'] == stored['bytes'] + sum(v['bytes'] for v in stored['indexes']) == item['stored_bytes']
                    and Fraction(item['ratio']) == Fraction(item['input_bytes'], item['stored_bytes']), 'archive/index/density accounting differs')
            require(item['effective_g'] == (min(case['g'], 65280) if codec == 'bgzip' else case['g']), 'actual block size differs')
            rows.append(dict(case_id=name, corpus=case['corpus'], nominal_g_bytes=case['g'], effective_g_bytes=item['effective_g'], codec=codec,
                input_bytes=item['input_bytes'], input_sha256=archive['input']['sha256'], archive_bytes=stored['bytes'],
                index_bytes=sum(v['bytes'] for v in stored['indexes']), stored_bytes=item['stored_bytes'], compression_ratio_fraction=item['ratio'],
                p50_ns=item['p50_ns'], p99_ns=item['p99_ns'], materialized_bytes_total=item['decoded_bytes_total'],
                requested_bytes_total=item['requested_bytes_total'], amplification_mean_fraction=item['amplification'],
                amplification_p50_fraction=item['amplification_p50'], zstd_calls_total=item['zstd_calls_total'], zstd_output_bytes_total=item['zstd_bytes_total'],
                zstd_calls_mean_fraction=item['zstd_calls_mean'], zstd_output_bytes_mean_fraction=item['zstd_bytes_mean'], archive_sha256=stored['sha256'],
                index_sha256s=';'.join(v['sha256'] for v in stored['indexes']), case_path='cases/' + name + '.json',
                latency_unit_path=item['latency_unit']['path'], selected_result_path=unit['selected']['path'], counter_path=item['counter']['path'], trace_path=request['trace']['path']))
    require(len(rows) == 285 and len({(r['case_id'], r['codec']) for r in rows}) == 285, 'full 285-row table required')
    if decision['Kill']['triggered']:
        # Kill permits only the already-declared primary fitted decomposition.
        require(set((HERE / 'model/cases').glob('*.json')) == {HERE / 'model/cases/chr1-g16384.json'}, 'decomposition continued after Kill')
        require(decision['P2']['verdict'] == 'NOT TESTED: Kill' and decision['P2']['passed'] is None, 'Kill must not imply a P2 HIT')
    require(all(primary_model[k] == v for k, v in audit['models']['chr1-g16384'].items()), 'primary model differs from independent result')
    require([p['decoded_bytes'] for p in fit['points']] == list(SIZES), 'four standalone fit points required')
    require(sum(Fraction(primary_model[k]) for k in ('calls_term_ns', 'bytes_term_ns', 'residual_ns')) == primary_model['observed_p50_ns'], 'model terms are not additive')
    require(sum(Fraction(primary_model[k]) for k in ('calls_share', 'bytes_share', 'residual_share')) == 1, 'signed model shares do not sum to one')
    admission = dict(loaded_before_worker=0, loaded_after_worker=0, retaken_units=[])
    units = sorted((HERE / 'units').rglob('*.json'))
    require(len(units) == 292, 'exactly 292 logical timing unit summaries required')
    for path in units:
        name = path.relative_to(HERE).as_posix()
        unit = document(name)
        require(unit['status'] == 'COMPLETE' and 1 <= len(unit['attempts']) <= 3, 'incomplete retry history')
        if unit['retaken']:
            admission['retaken_units'].append(name)
        for attempt in unit['attempts']:
            if attempt['status'] == 'LOADED':
                receipt = reference(attempt['receipt'])
                admission['loaded_after_worker' if receipt['command_started'] else 'loaded_before_worker'] += 1
    require(len(admission['retaken_units']) == decision['counts']['retaken']
            and admission['loaded_before_worker'] + admission['loaded_after_worker'] == decision['counts']['loaded_attempts'], 'admission counts differ')
    return dict(audit=audit, audit_path=audit_path.relative_to(HERE).as_posix(), audit_sha256=sha(audit_path), setup=setup,
                decision=decision, fit=fit, primary_model=primary_model, controls=controls, method=method,
                output_proof=output_proof, cases=cases, rows=rows, admission=admission)


def table(rows):
    lines = ['| Corpus | g nominal / actual B | Codec | Archive B | Index B | Stored B | Ratio | p50 µs | p99 µs | Amp mean / p50 | Zstd calls/request | Zstd output B/request | Raw |',
             '|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for row in rows:
        lines.append('| ' + ' | '.join((row['corpus'], str(row['nominal_g_bytes']) + ' / ' + str(row['effective_g_bytes']), LABELS[row['codec']],
            str(row['archive_bytes']), str(row['index_bytes']), str(row['stored_bytes']), number(row['compression_ratio_fraction']),
            number(Fraction(row['p50_ns'], 1000), 3), number(Fraction(row['p99_ns'], 1000), 3),
            number(row['amplification_mean_fraction']) + ' / ' + number(row['amplification_p50_fraction']),
            number(row['zstd_calls_mean_fraction']), number(row['zstd_output_bytes_mean_fraction'], 3), '[cell](' + row['case_path'] + ')')) + ' |')
    return '\n'.join(lines)


def line_number(path, needle):
    for index, line in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), 1):
        if needle in line:
            return index
    raise ValueError('foundation reference missing: ' + needle)


def render(data):
    audit, decision, fit, model = (data[k] for k in ('audit', 'decision', 'fit', 'primary_model'))
    setup, rows = data['setup'], data['rows']
    primary = [r for r in rows if r['case_id'] == 'chr1-g16384']
    lookup = {r['codec']: r for r in primary}
    ace, zstd, bgzf = (lookup[k] for k in CODECS)
    ratio = Fraction(ace['p50_ns'], zstd['p50_ns'])
    p99_ratio = Fraction(ace['p99_ns'], zstd['p99_ns'])
    counterexample = {r['codec']: r for r in rows if r['case_id'] == 't2t-00-g16384'}
    example = ('The primary outcome does not generalize to the window set. For example, the frozen t2t-00/g16384 cell has '
               + ', '.join(LABELS[k] + ' p50 ' + str(counterexample[k]['p50_ns']) + ' ns / stored '
                           + str(counterexample[k]['stored_bytes']) + ' B' for k in CODECS)
               + '. Every window result remains visible below; no pooled window latency replaces these comparisons.')
    lead = ('The primary chr1/g=16 KiB measurement selects outcome **(' + decision['outcome'] + ')**. '
            'ACEAPEX p50 is ' + number(Fraction(ace['p50_ns'], 1000), 3) + ' µs versus '
            + number(Fraction(zstd['p50_ns'], 1000), 3) + ' µs for zstd-seekable (ratio ' + number(ratio) + '); '
            + 'its p99 is ' + number(Fraction(ace['p99_ns'], 1000), 3) + ' versus ' + number(Fraction(zstd['p99_ns'], 1000), 3)
            + ' µs (ratio ' + number(p99_ratio) + '). ACE stores ' + str(ace['stored_bytes']) + ' bytes including indexes, '
            + 'zstd-seekable ' + str(zstd['stored_bytes']) + ', and BGZF ' + str(bgzf['stored_bytes']) + '. '
            + '**P1 ' + decision['P1']['verdict'] + '; Kill ' + ('TRIGGERED' if decision['Kill']['triggered'] else 'NOT TRIGGERED')
            + '; P2 ' + decision['P2']['verdict'] + '; P3 ' + decision['P3']['verdict'] + '.**')
    snapshots = ROOT / 'docs/RESULTS/ACEAPEX_SNAPSHOTS.md'
    old_line = line_number(snapshots, '## Historical chr1 snapshot')
    refresh_line = line_number(snapshots, '## Same-run chr1 refresh')
    matched_line = line_number(snapshots, '## Matched-g refresh:')
    # README is refreshed after this report; cite its immutable pre-study row.
    readme_line = 26
    lit_path = ROOT / 'docs/RESULTS/CHR1_LIT16_20260918.md'
    lit_ratio_line = line_number(lit_path, '| complete ratio |')
    lit_p50_line = line_number(lit_path, '| p50 region latency |')
    dctx_line = line_number(lit_path, '## DCtx audit')
    closed_line = line_number(HERE / 'PROTOCOL.md', 'No persistent-DCtx')
    source_line = line_number(HERE / 'SOURCE_PATHS.md', '## Actual persistent read path')
    lines = [SIGNATURE, '', '# HW-REGION-1', '', lead, '',
        'These results apply to the measured **ace-core / AMD EPYC 4344P host, one pinned CPU0, and resident archives in RAM**. '
        'They do not establish cross-host or historical-version speedups. The input is byte ranges, including the FASTA bytes where present; R=16384 B.', '',
        'The zero call coefficient is an **NNLS boundary result**, not evidence that real API calls are free. '
        'The primary fitted prediction is ' + number(model['predicted_p50_ns'], 3) + ' ns versus measured '
        + str(model['observed_p50_ns']) + ' ns, an absolute relative error of ' + percent(model['relative_error']) + '. '
        + ('It fails' if not model['within_twenty_percent'] else 'It passes') + ' the local ±20% check. '
        'The byte term is model-attributed ' + percent(model['bytes_share']) + ' and the residual is ' + percent(model['residual_share'])
        + '; these signed additive shares are **not fractions of measured CPU time**. A negative residual denotes overprediction. '
        'No refit, tuning, or additional ACE decomposition was used to repair this result.', '',
        '## Preregistered decisions', '',
        '| Gate | Exact rule | Result |', '|---|---|---|',
        '| P1 | 7/5 ≤ primary ACE p50 / zstd p50 ≤ 11/5 | ' + decision['P1']['verdict'] + '; ' + str(ratio) + ' |',
        '| Kill | 10 × ACE p50 < 11 × zstd p50 | ' + ('TRIGGERED' if decision['Kill']['triggered'] else 'NOT TRIGGERED') + ' |',
        '| Outcome (a) | ACE p50 / zstd p50 ≤ 11/10 | ' + ('YES' if decision['outcome'] == 'a' else 'NO') + ' |',
        '| P2 | Every one of 93 chr1/T2T ACE targets within ±20%; references excluded | ' + decision['P2']['verdict'] + ' |',
        '| Primary local model check | 5 × abs(predicted − measured) ≤ measured | ' + ('PASS' if model['within_twenty_percent'] else 'FAIL') + ' |',
        '| P3 | Primary model call term ≥ half measured p50 | ' + decision['P3']['verdict'] + '; share ' + model['calls_share'] + ' |', '',
        'Kill stops decomposition beyond the primary cell. The three-format comparative grid still completes: '
        'chr1 and thirty frozen 2 MiB T2T windows at g=4096/16384/65536 B, plus enwik8 and silesia at g=16384 B. '
        'This is 95 archive cases and 285 codec rows. P2 remains NOT TESTED when Kill triggers; the failing primary local prediction is reported separately.', '',
        '## Primary measured tradeoff', '', table(primary), '',
        'ACEAPEX has lower p50 and fewer stored bytes in this cell; its p99 and physical amplification are higher than both alternatives. '
        'The full grid below is retained without pooling windows into a new forecast HIT.', '', example, '',
        '## Two-constant calibration and the one permitted decomposition', '',
        'Only four standalone zstd L3 frames from the first chr1 bytes enter the fit. Each uses one persistent ZSTD_DCtx, twelve warmups '
        'and 1000 individual frame decodes. Coefficients use deterministic nonnegative exact least squares; no ACE latency enters the fit.', '',
        '| Decoded frame B | Observed p50 ns | Predicted ns, exact | Residual ns, exact | Raw timing |', '|---:|---:|---:|---:|---|']
    for point, observation in zip(fit['points'], fit['observations']):
        lines.append('| ' + ' | '.join((str(point['decoded_bytes']), str(point['observed_median_ns']), point['predicted_ns'], point['residual_ns'],
                                       '[raw](' + observation['path'] + ')')) + ' |')
    lines += ['', '`c_call = ' + fit['c_call_ns'] + ' ns/call`; `c_byte = ' + fit['c_byte_ns'] + ' ns/B`; '
              'exact squared residual sum `' + fit['squared_error_ns2'] + ' ns²`. '
              'The fitted call coefficient lies on its nonnegative boundary.', '',
        'For each of 1000 primary queries, mᵢ=Kᵢ×c_call+Dᵢ×c_byte using actual zstd invocation/output-byte counters. '
        'Sort by (mᵢ,query id) and take rank 500; query **' + str(model['representative_query']) + '** is the representative '
        + '(' + str(model['representative_zstd_calls']) + ' call, ' + str(model['representative_zstd_output_bytes']) + ' zstd output B). '
        'This is the median of joint per-query predictions, not a sum of independent medians. The signed residual is measured p50 minus predicted p50.', '',
        '| Primary component | Exact ns | Exact signed share | Display share |', '|---|---:|---:|---:|']
    for name, nskey, sharekey in (('Calls (model)', 'calls_term_ns', 'calls_share'), ('Zstd output bytes (model)', 'bytes_term_ns', 'bytes_share'),
                                  ('Residual (model overprediction if negative)', 'residual_ns', 'residual_share')):
        lines.append('| ' + ' | '.join((name, model[nskey], model[sharekey], percent(model[sharekey]))) + ' |')
    lines += ['', 'Exact additive total: ' + str(model['observed_p50_ns']) + ' ns and share 1. '
        'These values do not isolate causal decoder costs; the primary calibration failure limits such an interpretation.', '',
        '## Method, admission and correctness', '',
        'Each timed pass opens one fresh persistent reader handle outside the per-query timer, runs the same twelve warmups and 1000 uniform requests, '
        'and checks every returned byte outside the interval. Requests use the frozen per-corpus seeded trace shared across all g values and codecs. '
        'p50 and p99 are nearest ranks 500 and 990; all gates compare integer/fraction values before rounding. '
        'The separate counter build follows the same trace/cache lifecycle without timing-counter work in the published latency interval.', '',
        '| AA method gate, chr1/g16384 | First p50 ns | Second p50 ns | abs difference / first | Strict <5% |', '|---|---:|---:|---:|---|']
    for codec in CODECS:
        item = audit['method'][codec]
        lines.append('| ' + ' | '.join((LABELS[codec], str(item['first_p50_ns']), str(item['second_p50_ns']), percent(item['relative_difference']), 'PASS')) + ' |')
    lines += ['', 'The aligned/crossing negative controls use fresh handles and the first usable actual native boundary chosen from archive metadata. '
        'Materialized bytes increased as follows:', '', '| Codec | Aligned B | Crossing B |', '|---|---:|---:|']
    for codec in CODECS:
        item = audit['controls']['codecs'][codec]
        lines.append('| ' + LABELS[codec] + ' | ' + str(item['aligned_materialized_bytes']) + ' | ' + str(item['crossing_materialized_bytes']) + ' |')
    count = decision['counts'];proof = data['output_proof']
    lines += ['', 'Known API controls restore one frame with exactly one DCtx call / 4096 output bytes, one one-shot call / 4096 output bytes, '
        'and zero API calls for plain copy. ACE cache-hit work is zero; two distinct misses and invalid-range/corrupt-magic rejection also pass. '
        '[Controls](controls.json) · [AA method](method-check.json).', '',
        'All actual timing units use blocking `flock /run/lock/ovh-bench.lock`, worker CPU0 and T=1. '
        'LOADED means load1−1>1 at either boundary or a foreign live process consuming strictly >10% of one CPU at admission, '
        'derived from a retained ≥1-second tick delta. Exactly load1=2.00 and foreign CPU=10% pass. '
        'Other-core raw CPU accounting is observational. Each logical unit accepts its first CLEAN, retains every LOADED attempt, '
        'allows at most three attempts and never retries a worker error or a slow elapsed result.', '',
        '| Saved trial accounting | Count |', '|---|---:|',
        '| Accepted logical timing units (285 cells + 3 AA + 4 constants) | ' + str(count['logical_units']) + ' |',
        '| Total attempts | ' + str(count['attempts']) + ' |', '| Units retaken due to load | ' + str(count['retaken']) + ' |',
        '| LOADED attempts, excluded from timing results | ' + str(count['loaded_attempts']) + ' |',
        '| LOADED admissions before worker start (no benchmark timer) | ' + str(data['admission']['loaded_before_worker']) + ' |',
        '| LOADED attempts after worker start | ' + str(data['admission']['loaded_after_worker']) + ' |',
        '| Accepted per-query timing observations, including both AA passes | ' + str(count['accepted_timing_observations']) + ' |',
        '| Main-grid untimed counter requests | ' + str(count['counter_requests']) + ' |',
        '| Independent GNU dd+cmp observation documents | ' + str(proof['observation_references']) + ' |',
        '| Independently compared returned regions, including retained duplicate/control captures | ' + str(proof['returned_regions']) + ' |', '',
        'The final auditor checked every referenced private artifact on the measured host: zero unavailable files. '
        'GNU dd extracts the exact source slices and cmp checks captures independently, including every retained LOADED result when present. '
        '[Full output proof](audit/outputs-final.json) · [Independent final audit](' + data['audit_path'] + ') '
        '(SHA256 `' + data['audit_sha256'] + '`). The audit binds this generator and the numerical run inputs; '
        'historical document line references below provide context rather than new numerical evidence.', '',
        '## Corpus and version provenance', '',
        'ACEAPEX tag v2.6.5 points to `' + setup['deps']['aceapex']['commit'] + '`. '
        'Its actual CLI string is `' + setup['deps']['aceapex']['cli_version'].replace('|', '\\|') + '`, '
        'public API header 2.6.5, and literal C99 decoder header **2.6.4**. '
        'The linked zstd API is 10507 / 1.5.7. Preserve those distinct identities rather than patching upstream version strings. '
        'ACE interactive L2 uses one encoder thread, LIT_CHUNK=65536, FSE_CHUNK=4096; zstd-seekable is L3; BGZF is L6. '
        'The timed production readers are unchanged; counters are separate builds.', '',
        '| Dependency | Exact source commit |', '|---|---|']
    for name in ('aceapex', 'zstd', 'htslib', 'libdeflate'):
        lines.append('| ' + name + ' | `' + setup['deps'][name]['commit'] + '` |')
    lines += ['', 'Chr1 retains the complete supplied FASTA bytes (MD5 `' + setup['inputs']['chr1']['md5'] + '`). '
        'The thirty windows are the pre-existing 2 MiB manifest selection; their exact bytes were recovered from the verified canonical FASTA, '
        'not resampled. Reference corpora are held outside the P2 target grid. All input SHA256 values follow.', '',
        '| Corpus | Input B | SHA256 |', '|---|---:|---|']
    for name in ['chr1'] + [f't2t-{i:02d}' for i in range(30)] + ['enwik8', 'silesia']:
        item = setup['inputs'][name]
        lines.append('| ' + name + ' | ' + str(item['bytes']) + ' | `' + item['sha256'] + '` |')
    lines += ['', '[Setup and origin coordinates](setup.json) · [Native build](native/build.json) · [Frozen manifest](../t2t-regions-20260916/manifest.json). '
        'The prior v2.2.0 adapter remains as `codecs/aceapex_v220.sh`; the active adapter changes only its release pin, label and version.', '',
        'Source foundations: [SOURCE_PATHS.md:' + str(source_line) + '](SOURCE_PATHS.md#actual-persistent-read-path-and-work-counters) '
        'documents the persistent decoder/cache and actual API counters. '
        '[ACEAPEX_SNAPSHOTS.md:' + str(refresh_line) + '](../../docs/RESULTS/ACEAPEX_SNAPSHOTS.md#same-run-chr1-refresh--2026-11-26) '
        'contains this same-run refresh; [the preserved historical chr1 table, line ' + str(old_line)
        + '](../../docs/RESULTS/ACEAPEX_SNAPSHOTS.md#historical-chr1-snapshot--2026-09-10-aceapex-before-v210) '
        'belongs to its older sources/host and supports no numerical cross-host speedup claim here.', '',
        '## Foundations and closed directions', '',
        '- [README.md@e8aa8488:' + str(readme_line)
        + '](https://github.com/yasha1971-coder/hw-apex-bench/blob/e8aa8488310d8cb7d5793f2e49a707c67f80b689/README.md#L26) is the retained chrX pick example, '
        'a separate corpus/evidence scope linked to the snapshot collection.',
        '- [ACEAPEX_SNAPSHOTS.md:' + str(matched_line)
        + '](../../docs/RESULTS/ACEAPEX_SNAPSHOTS.md#matched-g-refresh-aceapex-v210--main-open-vs-bgzf--2026-09-30) '
        'retains the 2026-09-30 thirty-window v2.1.0 matched-g refresh: at 16 KiB, ACE/BGZF p50 were 0.074632/0.065482 ms; '
        'that table has no zstd row. Its values are not pooled with this host or used as a measured old/new speedup.',
        '- [CHR1_LIT16_20260918.md:' + str(lit_ratio_line) + ',' + str(lit_p50_line)
        + '](../../docs/RESULTS/CHR1_LIT16_20260918.md#result) retains the earlier literal-layer tradeoff (p50 −14.86%, ratio −3.319%). '
        '[Its DCtx audit, line ' + str(dctx_line) + '](../../docs/RESULTS/CHR1_LIT16_20260918.md#dctx-audit) describes an older one-shot path; '
        'the present pinned C99 reader already reuses DCtx and caches.',
        '- [PROTOCOL.md:' + str(closed_line) + '](PROTOCOL.md#pins-inputs-and-grid) closes persistent-DCtx, literal-chunk and '
        'FSE-chunk optimization in this task; [SOURCE_PATHS.md:24](SOURCE_PATHS.md#what-was-already-measured) also records the closed FSE/DCtx retry directions. '
        'Those levers were not reopened to rescue the forecasts.', '',
        '## Complete comparative grid', '',
        'Ratio is input bytes / (archive + every required index). BGZF at nominal g=65536 B has actual cap **65280 B**; '
        'the required `.gzi` bytes are included separately and in stored bytes. '
        'Physical amplification is materialized bytes / requested bytes; it includes non-zstd paths and remains separate from actual zstd output bytes. '
        'Per-request call and byte columns are means, including legitimate cache-hit/bypass zeros. '
        'The CSV keeps exact ns, bytes, totals, fractions, archive/index SHA256 values and raw links; only this Markdown display is rounded. '
        '[TABLE.csv](TABLE.csv).', '', table(rows), '',
        '[Unchanged calibration](CALIBRATION.md) · [Execution protocol](PROTOCOL.md) · [Exact decision](decision.json) · [Exact fit](model/fit.json) · '
        '[Only primary decomposition](model/cases/chr1-g16384.json).', '']
    return '\n'.join(line.rstrip() for line in lines).rstrip() + '\n'


def csv_text(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, default=HERE / 'audit/final.json')
    parser.add_argument('--outputdir', type=Path, default=HERE)
    args = parser.parse_args()
    output = args.outputdir.resolve()
    require(output.is_relative_to(HERE.resolve()), 'report output must stay in experiment evidence')
    data = load_all(args.audit)
    markdown, csv_data = render(data), csv_text(data['rows'])
    output.mkdir(parents=True, exist_ok=True)
    (output / 'RESULTS.md').write_bytes(markdown.encode('utf-8'))
    (output / 'TABLE.csv').write_bytes(csv_data.encode('utf-8'))
    print('REPORT_COMPLETE', len(data['rows']), sha(output / 'RESULTS.md'), sha(output / 'TABLE.csv'))


if __name__ == '__main__':
    main()
