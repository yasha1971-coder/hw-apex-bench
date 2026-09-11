"""Verify retained curve bytes and raw samples against the original CI ZIP."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from cg_curve import validate


def audit(artifact, results, receipt_path):
    receipt = json.loads(receipt_path.read_text())
    raw = results.read_bytes()
    if hashlib.sha256(artifact.read_bytes()).hexdigest() != receipt['artifact_sha256']:
        raise ValueError('Original curve artifact digest mismatch')
    if hashlib.sha256(raw).hexdigest() != receipt['results_sha256']:
        raise ValueError('Retained curve result bytes differ from the receipt')
    prior = b''.join(raw.splitlines(keepends=True)[:receipt['prior_records_preserved']])
    if hashlib.sha256(prior).hexdigest() != receipt['prior_results_sha256']:
        raise ValueError('Historical prefix was changed')
    rows = [json.loads(line) for line in raw.splitlines()]
    curve = [r for r in rows if r.get('evidence_group') == 'cg-five-point-v1']
    validate(curve)
    total = 0
    with zipfile.ZipFile(artifact) as z:
        if z.read('results.jsonl') != raw:
            raise ValueError('JSONL does not match original CI bytes')
        for row in curve:
            point = row['point']
            if point is None:
                continue
            name = f".work/cg-curve/{row['codec']}-{row['g']}-regions.jsonl"
            samples = z.read(name)
            if hashlib.sha256(samples).hexdigest() != point['samples_sha256']:
                raise ValueError('Raw region sample digest mismatch: ' + name)
            parsed = [json.loads(line) for line in samples.splitlines()]
            if parsed != point['region_samples']:
                raise ValueError('Embedded samples differ from original samples')
            for record in (point, row['baseline']):
                if record and record['total_bytes'] != record['archive_bytes'] + record['index_bytes']:
                    raise ValueError('Archive/index accounting mismatch')
            total += len(parsed)
    if total != receipt['verified_timed_region_samples']:
        raise ValueError('Wrong verified sample count')
    return {'positions': len(curve), 'verified_samples': total,
            'prior_rows_byte_identical': receipt['prior_records_preserved'],
            'full_restores': 'runner-verified; archives are not present in this ZIP'}


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.artifact, root / 'results.jsonl',
                           root / 'evidence/cg-curve-20260910/receipt.json'), sort_keys=True))
