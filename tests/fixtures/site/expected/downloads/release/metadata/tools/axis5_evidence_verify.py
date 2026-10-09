"""Axis 5 independent truth/classification judge; never opens a native codec."""
from pathlib import Path

from review.axis3.verdict_data import checked_file, load_json, sha256_file
from tools.axis5 import KINDS, OUTCOMES, PER_KIND, REPO, SEED, TIMEOUT, digest, mutation


def reference(root, prepared):
    """Independent bounded FASTA scanner, unrelated to prepare's interval scanner."""
    parts = []
    spec = prepared['reader']
    chosen = prepared['corpus']['assemblies'] if spec['family'] == 'agc' else prepared['corpus']['assemblies'][:1]
    queries = []
    for assembly in chosen:
        contigs, name = {}, None
        with checked_file(root, assembly['fasta']).open('rb') as f:
            for line in f:
                if line.startswith(b'>'):
                    name = line[1:].split()[0].decode('utf-8')
                    if name in contigs:
                        raise ValueError('duplicate contig')
                    contigs[name] = bytearray()
                else:
                    seq = line.rstrip(b'\r\n').upper()
                    if name is None or not seq or b' ' in seq or b'\t' in seq:
                        raise ValueError('malformed FASTA')
                    contigs[name].extend(seq)
        if [(k, len(v)) for k, v in contigs.items()] != [(c['contig_id'], c['length']) for c in assembly['contigs']]:
            raise ValueError('FASTA contigs differ from prepare')
        for name, seq in contigs.items():
            parts.append(bytes(seq))
            queries.append({'assembly_id': assembly['assembly_id'], 'contig_id': name,
                            'start0': 0, 'end0': len(seq)})
    if queries != prepared['queries']:
        raise ValueError('coordinates differ from frozen full-contig requests')
    return b''.join(parts)


def judge_raw(root, raw, truth, *, enabled, archive_sha, original_sha):
    """Separate judge; deliberately does not call runner classify()."""
    if enabled:
        if (archive_sha == original_sha or raw != {
                'decoder_started': False, 'timed_out': False, 'returncode': None,
                'signal': None, 'validation': 'original_sha_mismatch'}):
            raise ValueError('invalid explicit validation observation')
        return 'detected'
    if raw['decoder_started'] is not True or raw['validation'] != 'disabled':
        raise ValueError('OFF must start native worker')
    rc = raw['returncode']
    if type(rc) is not int or raw['signal'] != (-rc if rc < 0 else None):
        raise ValueError('returncode/signal inconsistency')
    output = checked_file(root, raw['output']).read_bytes()
    checked_file(root, raw['stderr'])
    if raw['timed_out']:
        # Leader can finish concurrently with process-group kill; rc need not be -9.
        return 'hang'
    if rc < 0:
        return 'crash'
    if rc != 0:
        return 'refusal'
    return 'harmless' if len(output) == len(truth) and output == truth else 'silent_error'


def verify(evidence_path, input_root, expected_prepared_sha256):
    import jsonschema
    root = Path(input_root).resolve(strict=True)
    data = load_json(Path(evidence_path))
    jsonschema.Draft202012Validator(load_json(REPO/'schemas/axis5-evidence-v1.schema.json')).validate(data)
    path = checked_file(root, data['prepared'])
    if sha256_file(path) != expected_prepared_sha256:
        raise ValueError('prepare differs from external anchor')
    prepared = load_json(path)
    if (prepared['schema'], prepared['seed'], prepared['per_kind'], prepared['timeout_seconds'],
            prepared['evidence_kind']) != ('axis5-prepared-v1', SEED, PER_KIND, TIMEOUT, 'synthetic'):
        raise ValueError('frozen experiment parameters')
    if prepared['protocol_sha256'] != digest((REPO/'PROTOCOL_AXIS5.md').read_bytes()):
        raise ValueError('protocol drift')
    for ref in prepared['inputs']:
        checked_file(root, ref)
    # Check all decoder refs and all FASTA, including FASTA outside targeted assembly.
    from tools.axis4 import collect_refs
    for ref in [*collect_refs(prepared['reader']), *collect_refs(prepared['corpus'])]:
        checked_file(root, ref)
    target = prepared['reader'].get('archive') or prepared['reader']['archives'][0]['archive']
    if target != prepared['target']:
        raise ValueError('target differs from frozen reader')
    clean = checked_file(root, target).read_bytes()
    donor = checked_file(root, prepared['donor']).read_bytes()
    if digest(clean) == digest(donor):
        raise ValueError('identical donor')
    truth = reference(root, prepared)
    if (len(truth), digest(truth)) != (prepared['truth_bytes'], prepared['truth_sha256']):
        raise ValueError('prepare truth SHA mismatch')
    manifest = load_json(checked_file(root, data['corrupt']))
    if (manifest['schema'] != 'axis5-corrupt-v1' or manifest['prepared'] != data['prepared']
            or len(manifest['rows']) != len(KINDS)*PER_KIND
            or len(prepared['cases']) != len(KINDS)*PER_KIND):
        raise ValueError('corruption manifest identity/count')
    for cid, (case, row) in enumerate(zip(prepared['cases'], manifest['rows'])):
        changed, op = mutation(clean, donor, KINDS[cid//PER_KIND], cid % PER_KIND)
        if case != {'id': cid, 'operation': op, 'bytes': len(changed), 'sha256': digest(changed)}:
            raise ValueError('prepared mutation identity')
        if row['id'] != cid or checked_file(root, row['archive']).read_bytes() != changed:
            raise ValueError('mutation differs from regenerated bytes')
    baseline = data['baseline']
    def check_worker(raw, archive):
        target_path = checked_file(root, raw['worker_archive'])
        if target_path.read_bytes() != archive:
            raise ValueError('worker archive differs from expected bytes')
        expected_sides = []
        if prepared['reader']['family'] in ('bgzf', 'fasta-faidx'):
            arc = prepared['reader']['archives'][0]
            for key, suffix in (('fai', '.fai'), ('gzi', '.gzi')):
                if key in arc:
                    expected_sides.append((Path(str(target_path)+suffix), checked_file(root, arc[key])))
        if len(raw['sidecars']) != len(expected_sides):
            raise ValueError('worker sidecar count')
        for ref, (expected_path, original) in zip(raw['sidecars'], expected_sides):
            path = checked_file(root, ref)
            if path != expected_path or path.read_bytes() != original.read_bytes():
                raise ValueError('worker sidecar differs from original')
    check_worker(baseline, clean)
    if checked_file(root, baseline['worker_archive']).read_bytes() != clean:
        raise ValueError('baseline archive changed')
    if judge_raw(root, baseline, truth, enabled=False, archive_sha=digest(clean),
                 original_sha=digest(clean)) != 'harmless':
        raise ValueError('baseline not harmless')
    counts = {m: dict.fromkeys(OUTCOMES, 0) for m in ('on', 'off')}
    if len(data['rows']) != len(KINDS)*PER_KIND*2:
        raise ValueError('evidence observation count')
    for rid, row in enumerate(data['rows']):
        cid, enabled = rid//2, rid % 2 == 0
        arc = manifest['rows'][cid]['archive']
        if row['id'] != cid or row['hash_enabled'] is not enabled or row['archive'] != arc:
            raise ValueError('duplicate/reordered/changed case or hash mode')
        if not enabled:
            check_worker(row['raw'], checked_file(root, arc).read_bytes())
        outcome = judge_raw(root, row['raw'], truth, enabled=enabled,
                            archive_sha=arc['sha256'], original_sha=target['sha256'])
        if row['classification'] != outcome:
            raise ValueError('forged classification')
        counts['on' if enabled else 'off'][outcome] += 1
    integrity = {m: 'FAIL' if c['silent_error'] else 'PASS' for m, c in counts.items()}
    if data['counts'] != counts or data['integrity'] != integrity:
        raise ValueError('forged aggregate/verdict')
    return {'status': 'PASS', 'evidence_kind': 'synthetic', 'verified': len(data['rows']),
            'family': prepared['reader']['family'], 'variant': prepared['reader']['variant'],
            'counts': counts, 'integrity': integrity, 'prepared_sha256': expected_prepared_sha256}
