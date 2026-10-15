#!/usr/bin/env python3
"""Bounded native corruption experiment: prepare, corrupt, run, verify."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys

from review.axis3.verdict_data import checked_file, file_ref, load_json, write_json
from tools.axis4 import collect_refs, new_output, unique_refs
from tools.axis4_evidence_verify import independent_truth

REPO = Path(__file__).resolve().parents[1]
SEED = 20261003
PER_KIND = 20
KINDS = ('bit', 'byte', 'truncate', 'swap', 'substitute')
OUTCOMES = ('detected', 'silent_error', 'refusal', 'hang', 'crash', 'harmless')
TIMEOUT = 10


def digest(data):
    return hashlib.sha256(data).hexdigest()


def mutation(clean, donor, kind, index):
    """Deterministic physical-byte mutations; never edit the source files."""
    if kind not in KINDS or type(index) is not int or not 0 <= index < PER_KIND:
        raise ValueError('mutation outside frozen population')
    if len(clean) < 2 or not donor:
        raise ValueError('nonempty donor and at least two target bytes required')
    h = hashlib.sha256(f'axis5-v1:{SEED}:{kind}:{index}'.encode('ascii')).digest()
    n = len(clean)
    pos = int.from_bytes(h[:8], 'big') * n // 2**64
    data = bytearray(clean)
    operation = {'kind': kind, 'index': index}
    if kind in ('bit', 'byte'):
        mask = 1 << (h[8] % 8) if kind == 'bit' else 1 + h[8]
        if mask > 255:
            raise ValueError('byte mask outside uint8')
        data[pos] ^= mask
        operation.update(offset=pos, xor=mask)
    elif kind == 'truncate':
        keep = 1 + pos % (n-1)
        del data[keep:]
        operation['keep'] = keep
    else:
        width = min(256, n//2, len(donor))
        count = n // width
        a = pos % count
        original = clean[a*width:(a+1)*width]
        if kind == 'swap':
            b = (a + 1 + h[9] % (count-1)) % count
            for step in range(count):
                candidate = (b+step) % count
                other = clean[candidate*width:(candidate+1)*width]
                if other != original:
                    b = candidate
                    break
            else:
                raise ValueError('no nonidentical block to swap')
            data[a*width:(a+1)*width], data[b*width:(b+1)*width] = other, original
        elif kind == 'substitute':
            donor_count = len(donor)//width
            b = h[9] % donor_count
            for step in range(donor_count):
                candidate = (b+step) % donor_count
                other = donor[candidate*width:(candidate+1)*width]
                if other != original:
                    b = candidate
                    break
            else:
                raise ValueError('no nonidentical donor block')
            data[a*width:(a+1)*width] = other
        else:
            raise ValueError('unknown kind')
        operation.update(width=width, target_block=a, other_block=b)
    if bytes(data) == clean:
        raise ValueError('mutation did not change bytes')
    return bytes(data), operation


def truth_bytes(root, prepared):
    result = bytearray()
    for assembly in prepared['corpus']['assemblies']:
        queries = [(i, q) for i, q in enumerate(prepared['queries'])
                   if q['assembly_id'] == assembly['assembly_id']]
        _, buffers = independent_truth(checked_file(root, assembly['fasta']), queries,
                                       {i for i, _ in queries})
        for i, _ in queries:
            result.extend(buffers[i])
    return bytes(result)


def prepare(root, plan_name, donor_name, out_name):
    root = Path(root).resolve(strict=True)
    plan_path = root / plan_name
    plan = load_json(plan_path)
    if plan.get('schema') != 'axis4-plan-v1':
        raise ValueError('Axis 4 native input plan required')
    corpus = load_json(checked_file(root, plan['prepared']))
    spec = plan['reader']
    if spec['family'] not in ('refrel3', 'zstd-seekable', 'bgzf', 'fasta-faidx', 'agc'):
        raise ValueError('unsupported Axis 5 native format')
    from tools.axis4 import open_reader
    # Verify pins/receipt/maps on clean inputs before freezing the experiment.
    reader = open_reader(root, spec, corpus)
    reader.close()
    target = spec['archive'] if spec['family'] == 'agc' else spec['archives'][0]['archive']
    donor = file_ref(root, root / donor_name)
    clean_path, donor_path = checked_file(root, target), checked_file(root, donor)
    if not 2 <= target['bytes'] <= 64*1024*1024 or not 1 <= donor['bytes'] <= 64*1024*1024:
        raise ValueError('archive size outside bounded protocol')
    if target['sha256'] == donor['sha256']:
        raise ValueError('donor must be another nonidentical archive')
    aids = [a['assembly_id'] for a in corpus['assemblies']]
    if spec['family'] != 'agc':
        aids = aids[:1]
    queries = [{'assembly_id': a['assembly_id'], 'contig_id': c['contig_id'],
                'start0': 0, 'end0': c['length']}
               for a in corpus['assemblies'] if a['assembly_id'] in aids for c in a['contigs']]
    if not queries or sum(q['end0'] for q in queries) > 8*1024*1024:
        raise ValueError('requested output outside bounded protocol')
    refs = unique_refs([file_ref(root, plan_path), *collect_refs(plan),
                        *collect_refs(corpus), donor])
    for ref in refs:
        checked_file(root, ref)
    prepared = {'schema': 'axis5-prepared-v1', 'evidence_kind': 'synthetic',
                'seed': SEED, 'per_kind': PER_KIND, 'timeout_seconds': TIMEOUT,
                'protocol_sha256': digest((REPO/'PROTOCOL_AXIS5.md').read_bytes()),
                'reader': spec, 'corpus': corpus, 'queries': queries,
                'target': target, 'donor': donor, 'inputs': refs}
    clean, donor_bytes = clean_path.read_bytes(), donor_path.read_bytes()
    prepared['cases'] = []
    for kind in KINDS:
        for i in range(PER_KIND):
            changed, operation = mutation(clean, donor_bytes, kind, i)
            prepared['cases'].append({'id': len(prepared['cases']), 'operation': operation,
                                      'bytes': len(changed), 'sha256': digest(changed)})
    truth = truth_bytes(root, prepared)
    prepared.update(truth_bytes=len(truth), truth_sha256=digest(truth))
    out = new_output(root, out_name)
    write_json(out/'prepared.json', prepared)
    return file_ref(root, out/'prepared.json')


def load_prepared(root, name):
    path = checked_file(root, file_ref(root, root/name))
    prepared = load_json(path)
    if prepared.get('schema') != 'axis5-prepared-v1':
        raise ValueError('Axis 5 prepared document required')
    if prepared['protocol_sha256'] != digest((REPO/'PROTOCOL_AXIS5.md').read_bytes()):
        raise ValueError('protocol drift')
    for ref in prepared['inputs']:
        checked_file(root, ref)
    return path, prepared


def corrupt(root, prepared_name, out_name):
    root = Path(root).resolve(strict=True)
    path, prepared = load_prepared(root, prepared_name)
    clean = checked_file(root, prepared['target']).read_bytes()
    donor = checked_file(root, prepared['donor']).read_bytes()
    out = new_output(root, out_name)
    rows = []
    for case in prepared['cases']:
        changed, op = mutation(
            clean, donor, case['operation']['kind'], case['operation']['index'])
        if op != case['operation'] or digest(changed) != case['sha256'] or len(changed) != case['bytes']:
            raise ValueError('prepared mutation drift')
        archive = out / f"{case['id']:03d}.archive"
        archive.write_bytes(changed)
        rows.append({'id': case['id'], 'archive': file_ref(root, archive)})
    manifest = {'schema': 'axis5-corrupt-v1', 'prepared': file_ref(root, path), 'rows': rows}
    write_json(out/'corrupt.json', manifest)
    return file_ref(root, out/'corrupt.json')


def observe(argv, output, errors, truth_length, timeout=TIMEOUT):
    """Raw OS result; no classification inferred from stderr strings."""
    def limits():
        resource.setrlimit(resource.RLIMIT_AS, (2048*1024*1024,)*2)
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (max(1024*1024, 2*truth_length+1024*1024),)*2)
    with output.open('xb') as stdout, errors.open('xb') as stderr:
        proc = subprocess.Popen(argv, stdout=stdout, stderr=stderr, start_new_session=True,
                                preexec_fn=limits, cwd=REPO)
        timed_out = False
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            rc = proc.wait()
    return {'decoder_started': True, 'timed_out': timed_out, 'returncode': rc,
            'signal': -rc if rc < 0 else None, 'validation': 'disabled'}


def classify(raw, actual, expected):
    if not raw['decoder_started']:
        return 'detected'
    if raw['timed_out']:
        return 'hang'
    if raw['returncode'] < 0:
        return 'crash'
    if raw['returncode'] > 0:
        return 'refusal'
    return 'harmless' if actual == expected else 'silent_error'


def run(root, corrupt_name, out_name):
    root = Path(root).resolve(strict=True)
    manifest_path = root / corrupt_name
    manifest = load_json(manifest_path)
    if manifest.get('schema') != 'axis5-corrupt-v1':
        raise ValueError('corruption manifest schema')
    path, prepared = load_prepared(root, manifest['prepared']['path'])
    checked_file(root, manifest['prepared'])
    if len(manifest['rows']) != len(prepared['cases']):
        raise ValueError('corruption count')
    for case, row in zip(prepared['cases'], manifest['rows']):
        if row['id'] != case['id'] or (row['archive']['bytes'], row['archive']['sha256']) != (case['bytes'], case['sha256']):
            raise ValueError('corruption identity')
        checked_file(root, row['archive'])
    expected = truth_bytes(root, prepared)
    out = new_output(root, out_name)
    def worker(archive, tag):
        # Private native input points at a copied target, with adjacent frozen sidecars.
        target = out / (tag+'.archive')
        target.write_bytes(archive.read_bytes())
        sidecars = []
        if prepared['reader']['family'] in ('bgzf', 'fasta-faidx'):
            entry = prepared['reader']['archives'][0]
            for key, suffix in (('fai', '.fai'), ('gzi', '.gzi')):
                if key in entry:
                    side = Path(str(target)+suffix)
                    side.write_bytes(checked_file(root, entry[key]).read_bytes())
                    sidecars.append(file_ref(root, side))
        output, errors = out/(tag+'.output'), out/(tag+'.stderr')
        argv = [sys.executable, '-m', 'tools.axis5_native_worker', str(root), str(path), str(target)]
        raw = observe(argv, output, errors, len(expected), prepared['timeout_seconds'])
        raw.update(output=file_ref(root, output), stderr=file_ref(root, errors),
                   worker_archive=file_ref(root, target), sidecars=sidecars)
        return raw, output.read_bytes()
    baseline, baseline_bytes = worker(checked_file(root, prepared['target']), 'baseline')
    if classify(baseline, baseline_bytes, expected) != 'harmless':
        raise ValueError('clean native baseline failed; inspect retained baseline files')
    rows = []
    for case, entry in zip(prepared['cases'], manifest['rows']):
        archive = checked_file(root, entry['archive'])
        for enabled in (True, False):
            if enabled:
                # This is the explicitly observed generic application integrity guard.
                if file_ref(root, archive)['sha256'] == prepared['target']['sha256']:
                    raise ValueError('corruption did not alter original SHA')
                raw = {'decoder_started': False, 'timed_out': False, 'returncode': None,
                       'signal': None, 'validation': 'original_sha_mismatch'}
                actual = b''
            else:
                raw, actual = worker(archive, f"{case['id']:03d}-off")
            rows.append({'id': case['id'], 'hash_enabled': enabled, 'archive': entry['archive'],
                         'raw': raw, 'classification': classify(raw, actual, expected)})
    counts = {mode: {k: sum(r['classification'] == k and r['hash_enabled'] == enabled for r in rows)
                     for k in OUTCOMES} for mode, enabled in (('on', True), ('off', False))}
    evidence = {'schema': 'axis5-evidence-v1', 'evidence_kind': 'synthetic',
                'prepared': file_ref(root, path), 'corrupt': file_ref(root, manifest_path),
                'baseline': baseline, 'rows': rows, 'counts': counts,
                'integrity': {m: 'FAIL' if c['silent_error'] else 'PASS' for m, c in counts.items()}}
    write_json(out/'evidence.json', evidence)
    return file_ref(root, out/'evidence.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'corrupt', 'run'):
        p = subs.add_parser(name)
        p.add_argument('--root', required=True)
        p.add_argument('--out', required=True)
        if name == 'prepare':
            p.add_argument('--plan', required=True)
            p.add_argument('--donor', required=True)
        else:
            p.add_argument('--'+('prepared' if name == 'corrupt' else 'corrupt'), required=True)
    p = subs.add_parser('verify')
    p.add_argument('--root', required=True)
    p.add_argument('--evidence', required=True)
    p.add_argument('--prepared-sha256', required=True)
    a = parser.parse_args()
    if a.command == 'prepare':
        result = prepare(a.root, a.plan, a.donor, a.out)
    elif a.command == 'corrupt':
        result = corrupt(a.root, a.prepared, a.out)
    elif a.command == 'run':
        result = run(a.root, a.corrupt, a.out)
    else:
        from tools.axis5_evidence_verify import verify
        result = verify(a.evidence, a.root, a.prepared_sha256)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
