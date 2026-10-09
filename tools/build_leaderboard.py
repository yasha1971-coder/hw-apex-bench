#!/usr/bin/env python3
"""Verify Axis 3/4/5 evidence, then render deterministic, comparable tables.

Input directories contain leaderboard-input.json, with external evidence and
prepare SHA anchors. Never measure, open a codec, infer hardware, or fit numbers.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import hashlib
import html
import io
import json
from pathlib import Path, PurePosixPath
import re

from review.axis3.verdict_data import checked_file, load_json, sha256_file
from tools import axis4_evidence_verify, axis5_evidence_verify
from tools.render_axis3_evidence import recompute
from tools.validate_axis3_evidence import validate_record
from tools.silence_contract import judge

SCHEMAS = {'axis3-evidence-v1', 'window-law-verdict-v1',
           'axis4-evidence-v3', 'axis4-evidence-v4', 'axis4-evidence-v5', 'axis5-evidence-v1'}
METRICS = ('verified', 'stored_bytes', 'bytes_per_assembly', 'window_bytes',
           'Q_actual_bytes', 'Q_bytes', 'D_Q_Bps', 'p50_us', 'p95_us', 'p99_us',
           'windows_per_second', 'seconds', 'build_seconds', 'peak_rss_bytes',
           'detected', 'silent_error', 'refusal', 'hang', 'crash', 'harmless')
COLUMNS = ('table', 'axis', 'kind', 'format', 'variant', 'scope', 'machine',
           'hash_mode', 'status', *METRICS, 'evidence', 'evidence_sha256')
HASH = re.compile(r'^[0-9a-f]{64}$')
LABEL = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]*$')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def identity(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def relative(root, text):
    if not isinstance(text, str) or not text or '\\' in text or ':' in text or '\0' in text:
        raise ValueError('invalid root-relative input path')
    p = PurePosixPath(text)
    if p.is_absolute() or '..' in p.parts:
        raise ValueError('input path must be root-relative')
    path = (root/text).resolve(strict=True)
    if not path.is_relative_to(root):
        raise ValueError('input symlink escapes catalog root')
    return path


def corpus_identity(corpus):
    return [{'assembly_id': a['assembly_id'], 'fasta_sha256': a.get('truth', {}).get('uncompressed_sha256', a['fasta']['sha256']),
             'contigs': a['contigs']} for a in corpus['assemblies']]


def gate_machine(records, *, required):
    hosts = set()
    for record in records:
        if required:
            if record != judge(record['snapshot']) or record['status'] != 'PASS':
                raise ValueError('invalid measured silence gate')
            hosts.add(record['snapshot']['host'])
    if len(hosts) > 1:
        raise ValueError('different machines in one evidence')
    if required and not hosts:
        raise ValueError('measured evidence has no machine gate')
    return next(iter(hosts)) if hosts else None


def axis3(data, path, root, record):
    result = validate_record(data, root)
    recompute(result, root)  # Judge raw arithmetic; display only original summary values.
    if result['status'] == 'PASS' and result['verified'] != result['samples']:
        raise ValueError('Axis 3 verified count differs from raw samples')
    if result['kind'] == 'measured':
        gate = load_json(checked_file(root, result['silence_gate']))
        gate_machine([gate], required=True)
    condition = {k: result[k] for k in ('kind', 'scope', 'threads', 'window_bytes', 'n_assemblies')}
    condition.update(machine=result['hardware']['machine_id'], hardware=result['hardware'],
        protocol=result['protocol']['sha256'], runbook=result['runbook']['sha256'],
        corpus=result['corpus_manifest']['sha256'], requests=result['requests']['sha256'])
    row = {'format': result['format'], 'variant': result['variant'], 'status': result['status']}
    if result['metrics']:
        allowed = METRICS if result['kind'] == 'measured' else ('stored_bytes', 'bytes_per_assembly', 'Q_actual_bytes')
        row.update({k: result['metrics'][k] for k in allowed if k in result['metrics']})
    row.update(verified=result['verified'], window_bytes=result['window_bytes'])
    return 3, condition, [row]


def axis4(data, path, root, record):
    anchor = record.get('prepared_sha256')
    if not isinstance(anchor, str) or not HASH.fullmatch(anchor):
        raise ValueError('external prepare SHA required for Axis 4')
    axis4_evidence_verify.verify(path, root, anchor)
    prepared = load_json(checked_file(path.parent, data['prepared']))
    plan = load_json(checked_file(path.parent, data['plan']))
    gates = [load_json(checked_file(path.parent, data[k])) for k in ('silence_before', 'silence_after')]
    machine = gate_machine(gates, required=data['evidence_kind'] == 'official')
    condition = {'kind': data['evidence_kind'], 'machine': machine, 'scope': data['scope'],
        'threads': data['decoder_threads'], 'protocol': prepared['protocol_sha256'],
        'domain': data['domain'], 'timing_boundary': data['timing_boundary'],
        'corpus': identity(corpus_identity(prepared)), 'requests': identity(prepared['groups'])}
    if data['schema'] == 'axis4-evidence-v5':
        condition.update(cpu_models=data['threading']['cpu_models'], affinity=data['threading']['affinity'])
    row = {'format': plan['reader']['family'], 'variant': plan['reader']['variant'],
           'status': data['status'], 'verified': data['verified'], 'stored_bytes': data['stored_bytes']}
    if data['performance_valid']:
        row['seconds'] = data['seconds']
    return 4, condition, [row]


def axis5(data, path, root, record):
    anchor = record.get('prepared_sha256')
    if not isinstance(anchor, str) or not HASH.fullmatch(anchor):
        raise ValueError('external prepare SHA required for Axis 5')
    axis5_evidence_verify.verify(path, root, anchor)
    prepared = load_json(checked_file(root, data['prepared']))
    condition = {'kind': data['evidence_kind'], 'machine': None,
        'scope': None, 'protocol': prepared['protocol_sha256'],
        'corpus': identity(corpus_identity(prepared['corpus'])),
        'requests': identity(prepared['queries']), 'seed': prepared['seed'],
        'per_kind': prepared['per_kind'], 'timeout_seconds': prepared['timeout_seconds']}
    rows = [{'format': prepared['reader']['family'], 'variant': prepared['reader']['variant'],
             'hash_mode': mode, 'status': data['integrity'][mode], **data['counts'][mode]}
            for mode in ('on', 'off')]
    return 5, condition, rows


def window_law(data, path, root, record):
    from tools.verdict_refrel3 import verify_result
    if path.name != 'results.json':
        raise ValueError('window-law verifier requires results.json')
    result = verify_result(path.parent)
    if result['immutable_input_error'] is not None:
        raise ValueError('window-law immutable input failure')
    gates = [load_json(checked_file(path.parent, ref)) for ref in result['silence_logs']]
    machine = gate_machine(gates, required=result['kind'] == 'measured')
    condition = {k: result[k] for k in ('kind', 'scope', 'threads', 'seed', 'domain', 'samples_per_window')}
    condition.update(machine=machine, protocol=result['protocol_sha256'])
    rows, requests = [], {}
    for entry in result['entries']:
        if entry['data_status'] != 'PASS':
            rows.append({'format': entry['family'], 'variant': entry['variant'],
                         'status': entry['data_status']})
            continue
        current = {}
        for obs in entry['observations']:
            raw = load_json_lines(checked_file(path.parent/entry['id'], obs['raw_log']))
            current[str(obs['W_bytes'])] = [{k: r[k] for k in ('request_id', 'canonical', 'expected_sha256')}
                                           for r in raw]
            row = {'format': entry['family'], 'variant': entry['variant'],
                   'status': obs['verdict'], 'window_bytes': obs['W_bytes'],
                   'verified': obs['verified'], 'Q_bytes': entry['Q_bytes']}
            if result['kind'] == 'measured':
                row.update(D_Q_Bps=obs['D_Q_Bps'], p50_us=obs['measured_p50_us'],
                           p95_us=obs['p95_us'], p99_us=obs['p99_us'])
            rows.append(row)
        if requests and current != requests:
            raise ValueError('window-law formats have different request sets')
        requests = current
    condition['requests'] = identity(requests)
    return 3, condition, rows


def load_json_lines(path):
    from tools.validate_axis3_evidence import loads
    return [loads(line) for line in path.read_text().splitlines() if line.strip()]


def collect(directories):
    tables, seen, sources, snapshots = {}, set(), {}, []
    adapters = {'axis3-evidence-v1': axis3, 'axis4-evidence-v3': axis4, 'axis4-evidence-v4': axis4, 'axis4-evidence-v5': axis4,
                'axis5-evidence-v1': axis5, 'window-law-verdict-v1': window_law}
    for directory in directories:
        base = Path(directory).resolve(strict=True)
        catalog = load_json(base/'leaderboard-input.json')
        if set(catalog) != {'schema', 'records'} or catalog['schema'] != 'leaderboard-input-v1':
            raise ValueError('leaderboard-input-v1 catalog schema required')
        if not isinstance(catalog['records'], list) or not catalog['records']:
            raise ValueError('empty evidence catalog')
        for record in catalog['records']:
            if not isinstance(record, dict) or set(record) - {'evidence', 'input_root', 'prepared_sha256', 'table'} or not {'evidence', 'input_root'} <= set(record):
                raise ValueError('invalid catalog record')
            path = checked_file(base, record['evidence'])
            blob = path.read_bytes()
            sha = hashlib.sha256(blob).hexdigest()
            data = load_json(path)
            schema = data.get('schema')
            if schema not in SCHEMAS:
                raise ValueError('unsupported evidence schema')
            root = relative(base, record['input_root'])
            axis, condition, rows = adapters[schema](data, path, root, record)
            expanded = [(r['format'], r['variant'], r.get('hash_mode'), r.get('window_bytes')) for r in rows]
            if len(expanded) != len(set(expanded)):
                raise ValueError('duplicate format/variant observation within evidence')
            # Duplicate format/variant is an input error, including different conditions.
            pairs = {(r['format'], r['variant']) for r in rows}
            for family, variant in pairs:
                key = (axis, family, variant)
                if schema == 'axis4-evidence-v5':
                    key += (data['decoder_threads'],)
                if key in seen:
                    raise ValueError('duplicate format/variant evidence')
                seen.add(key)
            table = record.get('table')
            if table is not None and (not isinstance(table, str) or not LABEL.fullmatch(table)):
                raise ValueError('invalid stable table label')
            automatic = table is None
            if automatic:
                table = 'axis'+str(axis)
                if schema == 'axis4-evidence-v5':
                    table += '-threads-'+str(data['decoder_threads'])
                if condition['machine'] is None:
                    table += '-'+sha  # Unknown hardware can never imply comparability.
            for r in rows:
                suffix = ('-hash-'+r['hash_mode']) if 'hash_mode' in r else ''
                if schema == 'window-law-verdict-v1':
                    if automatic and condition['machine'] is None:
                        suffix += '-variant-'+identity([r['format'], r['variant']])
                    suffix += '-W'+str(r['window_bytes'])
                name = table+suffix
                signature = {'axis': axis, 'schema': schema, **condition}
                if name in tables:
                    prior = tables[name]
                    if prior['conditions'] != signature:
                        raise ValueError('mixed conditions, requests or machines in one table')
                    if condition['machine'] is None:
                        raise ValueError('machine unrecorded; multi-row comparison refused')
                else:
                    tables[name] = {'id': name, 'conditions': signature, 'rows': []}
                row = {'table': name, 'axis': axis, 'kind': condition['kind'],
                       'scope': condition['scope'], 'machine': condition['machine'], **r,
                       'evidence': 'evidence/'+sha+'/evidence.json', 'evidence_sha256': sha}
                tables[name]['rows'].append(row)
            sources[sha] = blob
            snapshots.append((path, sha))
    if not tables:
        raise ValueError('no evidence')
    for path, sha in snapshots:
        if sha256_file(path) != sha:
            raise ValueError('evidence changed while verifying')
    result = []
    for name in sorted(tables):
        table = tables[name]
        table['rows'].sort(key=lambda r: (r['format'], r['variant'], r.get('hash_mode', ''), r.get('window_bytes', 0)))
        result.append(table)
    return {'schema': 'leaderboard-v1', 'tables': result}, sources


def number(value):
    if value is None:
        return ''
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        result = format(Decimal(str(value)), 'f')
        if '.' in result:
            result = result.rstrip('0').rstrip('.')
        return '0' if result == '-0' else result
    return str(value)


def escaped(value):
    return html.escape(number(value), quote=False).replace('|', '&#124;').replace('\n', ' ').replace('\r', ' ').replace('[', '&#91;').replace(']', '&#93;').replace('`', '&#96;')


def render(data):
    rows = [r for table in data['tables'] for r in table['rows']]
    output = io.StringIO(newline='')
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow(COLUMNS)
    for row in rows:
        writer.writerow([number(row.get(c)) for c in COLUMNS])
    lines = ['# hw-apex-bench v0.2.0 leaderboard', '',
        'Verified evidence only. Synthetic tables establish correctness, not performance.',
        'Unknown machines remain in separate tables. Empty cells mean unreported, never zero.', '']
    for table in data['tables']:
        lines.extend(['## '+escaped(table['id']), ''])
        conditions = table['conditions']
        lines.append(' / '.join(escaped(x) for x in ('Axis '+str(conditions['axis']),
                                                   conditions['kind'], conditions['scope']) if x is not None))
        if conditions['machine'] is None:
            lines.append('Machine unrecorded: no cross-evidence comparison.')
        else:
            lines.append('Machine: '+escaped(conditions['machine']))
        cols = ['format', 'variant', 'status', *[k for k in METRICS if any(k in r for r in table['rows'])]]
        lines += ['', '| '+' | '.join(cols+['evidence', 'evidence_sha256'])+' |',
                  '| '+' | '.join(['---']*len(cols)+['---', '---'])+' |']
        for row in table['rows']:
            vals = [escaped(row.get(k)) for k in cols]
            vals += ['[JSON]('+row['evidence']+')', '`'+row['evidence_sha256']+'`']
            lines.append('| '+' | '.join(vals)+' |')
        lines.append('')
    return {'LEADERBOARD.md': '\n'.join(lines).encode('utf-8'),
            'leaderboard.csv': output.getvalue().encode('utf-8'),
            'leaderboard.json': (json.dumps(data, sort_keys=True, indent=2,
                 ensure_ascii=False, allow_nan=False)+'\n').encode('utf-8')}


def build(directories, output):
    data, sources = collect(directories)
    files = render(data)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    for name, blob in files.items():
        (out/name).write_bytes(blob)
    for sha in sorted(sources):
        target = out/'evidence'/sha/'evidence.json'
        target.parent.mkdir(parents=True)
        target.write_bytes(sources[sha])
    return {'tables': len(data['tables']), 'rows': sum(len(t['rows']) for t in data['tables']),
            'sha256': {name: hashlib.sha256(blob).hexdigest() for name, blob in files.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories', nargs='+', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build(args.directories, args.out)
    except Exception as exc:
        parser.exit(1, 'LEADERBOARD_FAILED '+type(exc).__name__+': '+str(exc)+'\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
