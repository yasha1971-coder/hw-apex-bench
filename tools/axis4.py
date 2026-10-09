#!/usr/bin/env python3
"""Axis 4: prepare -> silence gate -> persistent native run -> independent verify."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

from tools.axis3_window_engine import Window
from tools.axis4_evidence_verify import DOMAIN, TIMING, sample_ids, validate_schema, verify
from review.axis3.verdict_data import (
    FastaTruth, capture_silence, checked_file, file_ref, load_json, resolve,
    verify_protocol, write_json,
)
from review.axis3 import verdict_readers as native

REPO = Path(__file__).resolve().parents[1]
COORDS = ('assembly_id', 'contig_id', 'start0', 'end0')


def collect_refs(value):
    if isinstance(value, dict):
        if set(value) == {'path', 'bytes', 'sha256'}:
            yield value
        else:
            for child in value.values():
                yield from collect_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from collect_refs(child)


def unique_refs(refs):
    result = {}
    for ref in refs:
        if ref['path'] in result and result[ref['path']] != ref:
            raise ValueError('conflicting file identities')
        result[ref['path']] = ref
    return list(result.values())


def storage_refs(spec):
    """Only decoder-required archives/reference/indexes, each distinct path once."""
    refs = []
    for key in ('archive', 'reference'):
        if key in spec:
            refs.append(spec[key])
    for arc in spec.get('archives', []):
        for key in ('archive', 'fai', 'gzi', 'index', 'contig_map'):
            if key in arc:
                refs.append(arc[key])
    return unique_refs(refs)


def new_output(root, name):
    p = Path(name)
    if p.is_absolute() or '..' in p.parts or str(p) in ('.', ''):
        raise ValueError('output must be a new root-relative directory')
    out = root / p
    if not out.parent.resolve().is_relative_to(root):
        raise ValueError('output escapes input root')
    out.mkdir(parents=True, exist_ok=False)
    return out


def prepare(root, manifest_name, groups_name, out_name, seed=20261003):
    root = Path(root).resolve(strict=True)
    manifest_path = resolve(root, manifest_name)
    groups_path = resolve(root, groups_name)
    manifest = load_json(manifest_path)
    if manifest.get('schema') != 'axis4-corpus-v1':
        raise ValueError('axis4-corpus-v1 manifest required')
    kind = manifest.get('evidence_kind')
    if kind not in ('official', 'synthetic'):
        raise ValueError('explicit evidence_kind required')
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError('sample seed must be uint64')
    rows = manifest['assemblies']
    if not rows:
        raise ValueError('empty cohort')
    sources = []
    for row in rows:
        if not row.get('source_url') or not isinstance(row['source_url'], str):
            raise ValueError('source URL required')
        sources.append((row['assembly_id'], checked_file(root, row['fasta'])))
    input_refs = unique_refs([file_ref(root, manifest_path), file_ref(root, groups_path),
                             *[r['fasta'] for r in rows]])
    truth = FastaTruth(sources)
    try:
        assemblies = []
        for row in rows:
            aid = row['assembly_id']
            assemblies.append({**row, 'contigs': [
                {'contig_id': c, 'length': n} for a, c, n in truth.contigs() if a == aid],
                **truth.full_identity(aid)})
        aids = [a['assembly_id'] for a in assemblies]
        explicit = load_json(groups_path)
        if not isinstance(explicit, list) or not explicit:
            raise ValueError('nonempty explicit cohort group list required')
        frozen = []
        for group in explicit:
            if not isinstance(group, dict) or set(group) != set(aids):
                raise ValueError('every group must explicitly cover the cohort')
            g = {}
            for aid in aids:
                q = group[aid]
                if set(q) != set(COORDS) or q['assembly_id'] != aid:
                    raise ValueError('canonical mapping must contain only the four coordinates')
                data = truth.fetch(aid, q['contig_id'], q['start0'], q['end0'])
                g[aid] = {**q, 'sha256': hashlib.sha256(data).hexdigest()}
            frozen.append(g)
        if kind == 'synthetic' and (sum(a['canonical_bytes'] for a in assemblies) > 8*1024*1024
                                    or len(frozen)*len(aids) > 1024):
            raise ValueError('synthetic mode is bounded to 8 MiB and 1024 responses')
        prepared = {
            'schema': 'axis4-prepared-v1', 'evidence_kind': kind, 'domain': DOMAIN,
            'coordinate_convention': '0-based-half-open',
            'protocol_sha256': verify_protocol(REPO)['sha256'],
            'sample_seed': seed, 'sample_algorithm': 'python.random.Random/MT19937/sample',
            'sample_limit': 32, 'assemblies': assemblies, 'groups': frozen,
            'input_files': input_refs,
        }
        validate_schema(prepared)
        for ref in input_refs:
            checked_file(root, ref)
        out = new_output(root, out_name)
        write_json(out / 'prepared.json', prepared)
        return file_ref(root, out / 'prepared.json')
    finally:
        truth.close()


def open_reader(root, spec, corpus):
    if spec['family'] == 'agc':
        # Axis 4 does not use Q or D_Q; do not demand B's instrumented geometry.
        libpath, build = native._check_receipt(root, spec)
        aids = [a['assembly_id'] for a in corpus['assemblies']]
        if (spec['variant'] not in ('t2t', 'noref') or build.get('mode') != spec['variant']
                or build.get('create_calls') != 1 or build.get('append_calls') != 0
                or build.get('cohort_order') != aids):
            raise ValueError('AGC requires the frozen cohort and one stock create')
        if spec['variant'] == 't2t':
            checked_file(root, spec['reference'])
        elif 'reference' in spec:
            raise ValueError('AGC noref cannot add an external reference')
        archive = checked_file(root, spec['archive'])
        if build.get('archive_sha256') != spec['archive']['sha256']:
            raise ValueError('AGC creation receipt archive mismatch')
        inner = native.AgcReader(libpath, archive)
        try:
            adapter = native.native.AgcReaderAdapter(inner)
            singles = []
            for assembly in corpus['assemblies']:
                for c in assembly['contigs']:
                    if inner.contig_length(assembly['assembly_id'], c['contig_id']) != c['length']:
                        raise ValueError('AGC contig differs from frozen source')
                singles.append(native.Single(assembly, adapter, None, close=lambda: None))
            reader = native.CohortReader(singles, None, [], build, 'unused')
            reader.close = inner.close
            return reader
        except Exception:
            inner.close()
            raise
    if spec['family'] != 'fasta-faidx':
        return native.open_reader(root, spec, corpus)
    if spec['variant'] != 'plain':
        raise ValueError('fasta-faidx variant must be plain')
    # Same pinned htslib shim, opening an already indexed plain FASTA.
    libpath, build = native._check_receipt(root, {**spec, 'family': 'bgzf'})
    assemblies = corpus['assemblies']
    if [a['assembly_id'] for a in spec['archives']] != [a['assembly_id'] for a in assemblies]:
        raise ValueError('faidx archive order differs from cohort')
    singles = []
    try:
        for assembly, arc in zip(assemblies, spec['archives']):
            path = checked_file(root, arc['archive'])
            if arc['archive'] != assembly['fasta']:
                raise ValueError('plain faidx archive must be the frozen FASTA')
            if checked_file(root, arc['fai']) != Path(str(path) + '.fai'):
                raise ValueError('faidx sidecar path mismatch')
            inner = native.BgzfReader(libpath, path)
            reader = native.native.BgzfReaderAdapter(inner, assembly['assembly_id'])
            singles.append(native.Single(assembly, reader, None, close=inner.close))
            for contig in assembly['contigs']:
                if reader.contig_length(assembly['assembly_id'], contig['contig_id']) != contig['length']:
                    raise ValueError('faidx contig length mismatch')
        return native.CohortReader(singles, None, [], build, 'unused')
    except Exception:
        for single in singles:
            single.close()
        raise


def load_plan(root, plan_name):
    path = resolve(root, plan_name)
    plan = load_json(path)
    if set(plan) != {'schema', 'prepared', 'reader'} or plan['schema'] != 'axis4-plan-v1':
        raise ValueError('axis4-plan-v1 requires prepared and reader')
    prepared_path = checked_file(root, plan['prepared'])
    prepared = load_json(prepared_path)
    validate_schema(prepared)
    if prepared['schema'] != 'axis4-prepared-v1':
        raise ValueError('not an Axis 4 prepare')
    if prepared['protocol_sha256'] != verify_protocol(REPO)['sha256']:
        raise ValueError('protocol drift')
    refs = unique_refs([file_ref(root, path), *collect_refs(plan), *collect_refs(prepared)])
    for ref in refs:
        checked_file(root, ref)
    return path, plan, prepared, refs


def run(root, plan_name, out_name, *, clock=time.perf_counter_ns):
    root = Path(root).resolve(strict=True)
    plan_path, plan, prepared, inputs = load_plan(root, plan_name)
    out = new_output(root, out_name)
    shutil.copyfile(checked_file(root, plan['prepared']), out / 'prepared.json')
    shutil.copyfile(plan_path, out / 'plan.json')
    (out / 'responses').mkdir()
    kind = prepared['evidence_kind']
    aids = [a['assembly_id'] for a in prepared['assemblies']]
    chosen = sample_ids(len(aids)*len(prepared['groups']), prepared['sample_seed'])
    storage = storage_refs(plan['reader'])
    result = {
        'schema': 'axis4-evidence-v3', 'axis': 4, 'status': 'FAILED', 'error': None,
        'evidence_kind': kind, 'performance_valid': False, 'domain': DOMAIN,
        'timing_boundary': TIMING, 'scope': 'cpu-in-process', 'decoder_threads': 1,
        'command': [sys.executable, '-m', 'tools.axis4', 'run', '--root', str(root),
                    '--plan', plan_name, '--out', out_name],
        'prepared': file_ref(out, out / 'prepared.json'), 'plan': file_ref(out, out / 'plan.json'),
        'input_files': inputs, 'storage_files': storage, 'stored_bytes': sum(r['bytes'] for r in storage),
        'sample_seed': prepared['sample_seed'], 'sample_ids': chosen,
        'silence_before': None, 'silence_after': None, 'rows': [], 'group_times': [],
        'seconds': None, 'verified': 0, 'reader_build': None,
        'implementation': {p: file_ref(REPO, REPO / p)['sha256'] for p in (
            'tools/axis4.py', 'tools/axis4_evidence_verify.py',
            'review/axis3/native_readers.py', 'review/axis3/verdict_readers.py',
            'review/axis3/verdict_data.py')},
    }
    reader = None

    def gate(label):
        record = capture_silence(out) if kind == 'official' else {
            'status': 'NOT_APPLICABLE', 'reason': 'synthetic correctness only'}
        target = out / ('silence-' + label + '.json')
        write_json(target, record)
        result['silence_' + label] = file_ref(out, target)
        if kind == 'official' and record['status'] != 'PASS':
            raise ValueError('silence gate refused: ' + label)

    try:
        gate('before')
        reader = open_reader(root, plan['reader'], {'assemblies': prepared['assemblies']})
        if reader.scope != 'cpu-in-process' or reader.decoder_threads != 1:
            raise ValueError('persistent one-thread in-process reader required')
        result['reader_build'] = reader.build
        for gid, group in enumerate(prepared['groups']):
            samples = []
            started = clock()
            for aid in aids:
                q = group[aid]
                rid = len(result['rows'])
                w = Window(rid, aid, q['contig_id'], q['start0'], q['end0'], q['sha256'])
                answer = reader.fetch(aid, w.contig, w.start0, w.end0)
                if not isinstance(answer, bytes):
                    raise ValueError('native response must be bytes')
                answer = answer.upper()
                observed = hashlib.sha256(answer).hexdigest()
                row = {
                    'id': rid, 'group_id': gid, 'assembly': aid,
                    'canonical': {key: q[key] for key in COORDS},
                    'translated': reader.translated(w), 'length': len(answer),
                    'observed_sha256': observed, 'status': 'PASS', 'response_file': None,
                }
                result['rows'].append(row)
                if len(answer) != w.length or observed != q['sha256']:
                    row['status'] = 'FAILED'
                    raise ValueError('native response differs from prepare at id=' + str(rid))
                result['verified'] += 1
                if rid in chosen:
                    samples.append((row, answer))
            elapsed = clock() - started
            if elapsed <= 0:
                raise ValueError('nonpositive group interval')
            result['group_times'].append({'group_id': gid, 'elapsed_ns': elapsed})
            for row, answer in samples:
                target = out / 'responses' / (str(row['id']) + '.bin')
                with target.open('xb') as f:
                    f.write(answer)
                row['response_file'] = file_ref(out, target)
        reader.close()
        reader = None
        # Sample host before expensive final re-hashing, which itself consumes CPU.
        gate('after')
        for ref in inputs:
            checked_file(root, ref)
        result['seconds'] = sum(g['elapsed_ns'] for g in result['group_times']) / 1e9
        result['status'] = 'PASS'
        result['performance_valid'] = kind == 'official'
    except Exception as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc)
        result['seconds'] = None
        result['performance_valid'] = False
    finally:
        if reader is not None:
            try:
                reader.close()
            except Exception as exc:
                result.update(status='FAILED', error='close: ' + str(exc),
                              seconds=None, performance_valid=False)
    validate_schema(result)
    write_json(out / 'evidence.json', result)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='operation', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--root', required=True)
    p.add_argument('--manifest', required=True)
    p.add_argument('--groups', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--sample-seed', type=int, default=20261003)
    p = sub.add_parser('run')
    p.add_argument('--root', required=True)
    p.add_argument('--plan', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('verify')
    p.add_argument('--evidence', required=True)
    p.add_argument('--input-root', required=True)
    p.add_argument('--prepared-sha256', required=True)
    args = ap.parse_args()
    try:
        if args.operation == 'prepare':
            result = {'prepared': prepare(args.root, args.manifest, args.groups, args.out, args.sample_seed)}
        elif args.operation == 'run':
            data = run(args.root, args.plan, args.out)
            result = {k: data[k] for k in ('status', 'error', 'verified', 'evidence_kind')}
        else:
            result = verify(args.evidence, args.input_root, args.prepared_sha256)
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get('status', 'PASS') == 'PASS' else 1
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'FAILED', 'error': type(exc).__name__ + ': ' + str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
