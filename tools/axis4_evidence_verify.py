#!/usr/bin/env python3
"""Independent streaming FASTA judge for Axis 4. Never opens a codec.

The caller supplies the prepare SHA from outside the evidence directory.
Hashes bind bytes, not authorship or machine telemetry authenticity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random

from review.axis3.verdict_data import checked_file, load_json, sha256_file
from tools.silence_contract import judge

REPO = Path(__file__).resolve().parents[1]
SCHEMA = REPO / 'schemas/axis4-evidence-v3.schema.json'
DOMAIN = 'uppercase-sequence-without-FASTA-framing'
TIMING = 'complete group: native fetch, uppercase normalization, SHA-256 judgement and translation; response file writes outside timer'


def sample_ids(count, seed):
    return sorted(random.Random(seed).sample(range(count), min(32, count)))


def validate_schema(data):
    import jsonschema
    version = data.get('schema')
    if version == 'axis4-evidence-v5':
        jsonschema.Draft202012Validator(load_json(REPO/'schemas/axis4-evidence-v5.schema.json')).validate(data)
        return
    schema = SCHEMA if version in ('axis4-prepared-v1', 'axis4-evidence-v3') else REPO/'schemas/axis4-evidence-v4.schema.json'
    jsonschema.Draft202012Validator(load_json(schema)).validate(data)


def refs_in(value):
    if isinstance(value, dict):
        if set(value) == {'path', 'bytes', 'sha256'}:
            yield value
        else:
            for child in value.values():
                yield from refs_in(child)
    elif isinstance(value, list):
        for child in value:
            yield from refs_in(child)


def verify_translation(translated, q, assemblies):
    if (translated.get('assembly_id'), translated.get('contig_id')) != (q['assembly_id'], q['contig_id']):
        raise ValueError('translation assembly/contig mismatch')
    convention = translated.get('convention')
    if convention == '0-based-half-open':
        valid = (translated.get('start0'), translated.get('end0')) == (q['start0'], q['end0'])
    elif convention == '0-based-inclusive':
        valid = (translated.get('start'), translated.get('end')) == (q['start0'], q['end0'] - 1)
    elif convention == 'canonical-sequence-offset':
        assembly = next(a for a in assemblies if a['assembly_id'] == q['assembly_id'])
        prefix = 0
        for contig in assembly['contigs']:
            if contig['contig_id'] == q['contig_id']:
                break
            prefix += contig['length']
        else:
            raise ValueError('translation contig missing')
        valid = (translated.get('offset'), translated.get('length')) == (prefix + q['start0'], q['end0'] - q['start0'])
    else:
        valid = False
    if not valid:
        raise ValueError('translation coordinates mismatch')


def independent_truth(path, queries, sampled, identity=None):
    """Scan FASTA once, without FastaTruth, faidx, or a native reader.

    Memory is O(requests + sampled response bytes); no whole genome is loaded.
    Coordinates are intersected with sequence lines, independent of line width.
    """
    if identity is not None:
        return independent_stream_truth(path, queries, sampled, identity)
    pending = {}
    hashes, lengths, buffers = {}, {}, {}
    for rid, q in queries:
        pending.setdefault(q['contig_id'], []).append((q['start0'], q['end0'], rid))
        hashes[rid] = hashlib.sha256()
        lengths[rid] = 0
        if rid in sampled:
            buffers[rid] = bytearray()
    for rows in pending.values():
        rows.sort()
    seen = set()
    current, offset, todo, cursor, active = None, 0, [], 0, []
    with Path(path).open('rb') as f:
        for raw in f:
            if raw.startswith(b'>'):
                words = raw[1:].split()
                if not words:
                    raise ValueError('empty FASTA contig')
                current = words[0].decode('utf-8')
                if current in seen:
                    raise ValueError('duplicate FASTA contig')
                seen.add(current)
                offset, todo, cursor, active = 0, pending.get(current, []), 0, []
                continue
            seq = raw.rstrip(b'\r\n').upper()
            if current is None or not seq or any(c in seq for c in (b' ', b'\t', b'>')):
                raise ValueError('malformed FASTA')
            end = offset + len(seq)
            while cursor < len(todo) and todo[cursor][0] < end:
                active.append(todo[cursor])
                cursor += 1
            remaining = []
            for start, stop, rid in active:
                part = seq[max(start, offset) - offset:min(stop, end) - offset]
                hashes[rid].update(part)
                lengths[rid] += len(part)
                if rid in buffers:
                    buffers[rid].extend(part)
                if stop > end:
                    remaining.append((start, stop, rid))
            active = remaining
            offset = end
    for rid, q in queries:
        if lengths[rid] != q['end0'] - q['start0']:
            raise ValueError('truth request outside FASTA')
    return {rid: h.hexdigest() for rid, h in hashes.items()}, buffers


def independent_stream_truth(path, queries, sampled, identity):
    """Independent coordinate intersection and complete source identity judge.

    Shares only gzip transport/FASTA framing, never prepare_truth or its hashes.
    Unlike prepare's active-window sweep, intersect each request with each piece.
    """
    from tools.axis4_stream import source_stream, segments, CHUNK
    raw, canonical, count = hashlib.sha256(), hashlib.sha256(), [0]
    hashes = {rid: hashlib.sha256() for rid, _ in queries}
    lengths = {rid: 0 for rid, _ in queries}
    buffers = {rid: bytearray() for rid, _ in queries if rid in sampled}
    contigs, seen, offset, total, current = [], set(), 0, 0, None
    with source_stream(path) as (stream, encoding):
        for kind, value in segments(stream, raw, count):
            if kind == 'header':
                if value in seen:
                    raise ValueError('duplicate FASTA contig')
                seen.add(value)
                current, offset = value, 0
                contigs.append({'contig_id': value, 'length': 0})
                continue
            if current is None:
                raise ValueError('FASTA sequence before header')
            canonical.update(value)
            total += len(value)
            contigs[-1]['length'] += len(value)
            for rid, q in queries:
                if q['contig_id'] != current:
                    continue
                left, right = max(offset, q['start0']), min(offset+len(value), q['end0'])
                if left < right:
                    part = value[left-offset:right-offset]
                    hashes[rid].update(part)
                    lengths[rid] += len(part)
                    if rid in buffers:
                        buffers[rid].extend(part)
            offset += len(value)
    actual = {'encoding': encoding, 'uncompressed_bytes': count[0],
              'uncompressed_sha256': raw.hexdigest(), 'chunk_bytes': CHUNK}
    if (actual != identity['truth'] or contigs != identity['contigs'] or
            total != identity['canonical_bytes'] or canonical.hexdigest() != identity['canonical_sha256']):
        raise ValueError('decompressed FASTA identity differs from prepare')
    for rid, q in queries:
        if lengths[rid] != q['end0']-q['start0']:
            raise ValueError('truth request outside FASTA')
    return {rid: h.hexdigest() for rid, h in hashes.items()}, buffers


def verify(path, input_root, expected_prepared_sha256):
    p = Path(path).resolve(strict=True)
    root = p.parent
    data = load_json(p)
    validate_schema(data)
    if data['status'] != 'PASS':
        raise ValueError('run failed: ' + str(data['error']))
    prepared_path = checked_file(root, data['prepared'])
    if sha256_file(prepared_path) != expected_prepared_sha256:
        raise ValueError('prepare SHA differs from external anchor')
    prepared = load_json(prepared_path)
    validate_schema(prepared)
    streamed = data['schema'] == 'axis4-evidence-v4' or (data['schema'] == 'axis4-evidence-v5' and 'truth_sources' in data)
    if streamed != (prepared['schema'] == 'axis4-prepared-v2'):
        raise ValueError('evidence/prepare schema version mismatch')
    if streamed and data['truth_sources'] != [
            {'assembly_id': a['assembly_id'], 'source': a['fasta'], **a['truth']}
            for a in prepared['assemblies']]:
        raise ValueError('truth source ledger differs from prepare')
    plan = load_json(checked_file(root, data['plan']))
    if set(plan) != {'schema', 'prepared', 'reader'} or plan['schema'] != 'axis4-plan-v1':
        raise ValueError('plan schema')
    if data['schema'] == 'axis4-evidence-v5':
        from tools.axis4_threads import capability
        expected_cap = capability(plan['reader']['family'], data['decoder_threads'])
        if {k:data['threading'][k] for k in expected_cap} != expected_cap:
            raise ValueError('decoder thread capability mismatch')
        affinity = data['threading']['affinity']
        if affinity is not None and (not affinity or affinity != sorted(affinity)):
            raise ValueError('noncanonical CPU affinity')
        if data['threading']['cpu_models'] != sorted(data['threading']['cpu_models']):
            raise ValueError('noncanonical CPU models')
    if plan['prepared']['sha256'] != expected_prepared_sha256:
        raise ValueError('plan prepare SHA mismatch')
    if data['evidence_kind'] != prepared['evidence_kind']:
        raise ValueError('evidence kind mismatch')
    if data['sample_seed'] != prepared['sample_seed']:
        raise ValueError('sample seed differs from prepare')
    assemblies = prepared['assemblies']
    aids = [a['assembly_id'] for a in assemblies]
    if len(set(aids)) != len(aids):
        raise ValueError('duplicate assembly')
    expected = []
    for gid, group in enumerate(prepared['groups']):
        if set(group) != set(aids):
            raise ValueError('group must cover every assembly')
        for aid in aids:
            q = group[aid]
            if q['assembly_id'] != aid or not 0 <= q['start0'] < q['end0']:
                raise ValueError('invalid canonical mapping')
            expected.append((gid, aid, q))
    if data['verified'] != len(expected) or len(data['rows']) != len(expected):
        raise ValueError('row count')
    chosen = sample_ids(len(expected), prepared['sample_seed'])
    if data['sample_ids'] != chosen:
        raise ValueError('sample selection differs from seed')
    by_assembly = {a: [] for a in aids}
    for rid, ((gid, aid, q), row) in enumerate(zip(expected, data['rows'])):
        if (row['id'], row['group_id'], row['assembly']) != (rid, gid, aid):
            raise ValueError('duplicate, missing or reordered response')
        canonical = {k: q[k] for k in ('assembly_id', 'contig_id', 'start0', 'end0')}
        if row['canonical'] != canonical:
            raise ValueError('response coordinates differ from prepare')
        verify_translation(row['translated'], q, assemblies)
        if row['length'] != q['end0'] - q['start0'] or row['status'] != 'PASS':
            raise ValueError('response length/status')
        if (row['response_file'] is not None) != (rid in chosen):
            raise ValueError('sample byte coverage')
        by_assembly[aid].append((rid, q))
    for a in assemblies:
        source = checked_file(input_root, a['fasta'])
        hashes, buffers = independent_truth(source, by_assembly[a['assembly_id']], set(chosen), a if streamed else None)
        for rid, q in by_assembly[a['assembly_id']]:
            row = data['rows'][rid]
            if q['sha256'] != hashes[rid] or row['observed_sha256'] != hashes[rid]:
                raise ValueError('response SHA differs from independently extracted FASTA')
            if rid in buffers:
                observed = checked_file(root, row['response_file']).read_bytes()
                if observed != buffers[rid] or hashlib.sha256(observed).hexdigest() != row['observed_sha256']:
                    raise ValueError('sample bytes differ from FASTA')
        checked_file(input_root, a['fasta'])
    expected_inputs = {r['path']: r for r in refs_in([plan, prepared])}
    observed_inputs = {r['path']: r for r in data['input_files']}
    if len(observed_inputs) != len(data['input_files']):
        raise ValueError('duplicate input identity')
    if any(observed_inputs.get(name) != ref for name, ref in expected_inputs.items()):
        raise ValueError('input ledger differs from frozen plan/prepare')
    extra = [r for name, r in observed_inputs.items() if name not in expected_inputs]
    if len(extra) != 1 or any(extra[0][key] != data['plan'][key] for key in ('sha256', 'bytes')):
        raise ValueError('original plan identity missing or extra inputs')
    for ref in data['input_files']:
        checked_file(input_root, ref)
    storage = data['storage_files']
    spec = plan['reader']
    required_storage = [spec[k] for k in ('archive', 'reference') if k in spec]
    for arc in spec.get('archives', []):
        required_storage.extend(arc[k] for k in ('archive', 'fai', 'gzi', 'index', 'contig_map') if k in arc)
    if {r['path']: r for r in storage} != {r['path']: r for r in required_storage}:
        raise ValueError('storage ledger differs from decoder inputs')
    if data['reader_build'] != load_json(checked_file(input_root, spec['build_receipt'])):
        raise ValueError('reader provenance differs from frozen receipt')
    paths = [checked_file(input_root, ref) for ref in storage]
    if len(set(paths)) != len(paths) or data['stored_bytes'] != sum(r['bytes'] for r in storage):
        raise ValueError('storage ledger')
    if data['seconds'] != sum(g['elapsed_ns'] for g in data['group_times']) / 1e9:
        raise ValueError('group timing sum')
    if [g['group_id'] for g in data['group_times']] != list(range(len(prepared['groups']))):
        raise ValueError('group timing coverage')
    for ref in (data['silence_before'], data['silence_after']):
        record = load_json(checked_file(root, ref))
        if data['evidence_kind'] == 'official':
            if record != judge(record['snapshot']) or record['status'] != 'PASS':
                raise ValueError('silence gate')
        elif record != {'status': 'NOT_APPLICABLE', 'reason': 'synthetic correctness only'}:
            raise ValueError('synthetic gate label')
    return {'status': 'PASS', 'verified': len(expected), 'sample_bytes_verified': len(chosen),
            'evidence_kind': data['evidence_kind'], 'prepared_sha256': expected_prepared_sha256}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence')
    parser.add_argument('--input-root', required=True)
    parser.add_argument('--prepared-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.evidence, args.input_root, args.prepared_sha256), sort_keys=True))


if __name__ == '__main__':
    main()
