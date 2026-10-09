#!/usr/bin/env python3
"""Offline release acceptance. Preserved native evidence; no codec execution.

Axis 3 is an explicit deterministic unit-contract fixture, not a native run.
Axis 4/5 files are original A6/A7 evidence. No downloads or package installation.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from review.axis3.verdict_data import file_ref
from tools import release_v020 as job

BASE_COMMIT = '8ff1080e513d29d8a9ea35b80c81346a4a1ae73b'


def axis3_fixture(root):
    root.mkdir(parents=True)
    (root/'fixture.txt').write_bytes(b'Axis 3 unit contract fixture, not a measurement\n')
    (root/'requests.json').write_bytes(b'{"kind":"unit-contract-fixture","window_bytes":1024}\n')
    raw = [{'request_id': i, 'status': 'PASS', 'expected_sha256': 'a'*64,
            'observed_sha256': 'a'*64, 'returned_bytes': 1024, 'elapsed_ns': 1000}
           for i in range(10000)]
    (root/'raw.jsonl').write_text(''.join(json.dumps(r, sort_keys=True)+'\n' for r in raw))
    ref = file_ref(root, root/'fixture.txt')
    data = {'schema': 'axis3-evidence-v1', 'axis': 3, 'kind': 'synthetic',
        'run_id': 'release-unit-contract', 'status': 'PASS',
        'format': 'unit-contract-fixture', 'variant': 'not-native',
        'scope': 'cpu-in-process', 'threads': 1, 'n_assemblies': 4,
        'window_bytes': 1024, 'samples': 10000, 'verified': 10000,
        'codec_commit': 'a'*40, 'protocol': ref, 'runbook': ref,
        'corpus_manifest': ref, 'requests': file_ref(root, root/'requests.json'),
        'raw_logs': [file_ref(root, root/'raw.jsonl')],
        'metrics': {'stored_bytes': 400, 'bytes_per_assembly': 100,
                    'build_seconds': 1, 'peak_rss_bytes': 1000,
                    'p50_us': 1, 'p95_us': 1, 'p99_us': 1,
                    'windows_per_second': 1000000, 'Q_actual_bytes': 4096},
        'error': None, 'hardware': {'machine_id': 'unit-contract-fixture',
                                   'cpu_model': 'unit', 'frequency_policy': 'unit'},
        'build': {'compiler': 'unit', 'flags': [], 'binary_sha256': 'b'*64,
                  'dependencies': {'unit': 'not-a-build'}}, 'silence_gate': None}
    (root/'evidence.json').write_bytes(job.encoded(data))
    (root/'leaderboard-input.json').write_bytes(job.encoded({
        'schema': 'leaderboard-input-v1', 'records': [
            {'evidence': file_ref(root, root/'evidence.json'), 'input_root': '.'}]}))


def prepare(root):
    """Create a relocatable, externally anchored single-input recipe."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    shutil.copytree(job.REPO/'tests/fixtures/leaderboard/input', root/'catalogs/golden')
    axis3_fixture(root/'catalogs/axis3-unit')
    paths = list(job.METADATA)
    for group in ('a7-synthetic', 'a8-acceptance'):
        paths.extend(p.relative_to(job.REPO).as_posix()
                     for p in sorted((job.REPO/'review/axis3/results'/group).iterdir()) if p.is_file())
    paths.append('PROTOCOL_AXIS5.md')
    for name in paths:
        target = root/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(job.REPO/name, target)
    config = {'schema': 'release-input-v1', 'commit': BASE_COMMIT,
              'catalogs': [file_ref(root, p) for p in sorted(root.glob('catalogs/*/leaderboard-input.json'))],
              'artifacts': [file_ref(root, root/name) for name in paths]}
    (root/'release-input.json').write_bytes(job.encoded(config))
    return root/'release-input.json'


def acceptance(output):
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    try:
        with tempfile.TemporaryDirectory(prefix='release-input-', dir=out.parent) as temp:
            config = prepare(Path(temp)/'input')
            first = job.release(config, out/'first')
            second = job.release(config, out/'second')
        one = {p.relative_to(out/'first').as_posix(): p.read_bytes() for p in job.files(out/'first')}
        two = {p.relative_to(out/'second').as_posix(): p.read_bytes() for p in job.files(out/'second')}
        if one != two or first != second:
            raise ValueError('release byte determinism mismatch')
        receipt = {'rerun': 'BYTE_IDENTICAL', 'native_execution': False,
                   'axis3': 'unit-contract-fixture', **first}
        (out/'acceptance.json').write_bytes(job.encoded(receipt))
        return receipt
    except Exception:
        shutil.rmtree(out)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(acceptance(args.out), sort_keys=True))


if __name__ == '__main__':
    main()
