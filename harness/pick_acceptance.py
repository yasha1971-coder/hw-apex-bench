"""Offline synthetic pick acceptance; never uses real benchmark corpora."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time

from native_execution import digest
from pick import table, verify_regions


def campaign(root, source, count=1000):
    receipt = json.loads((root/'pick.json').read_text())
    if digest(source) != receipt['input_sha256']:
        raise ValueError('frozen input SHA mismatch')
    rows = [r for r in receipt['rows'] if r['status'] == 'measured']
    if collections.Counter(r['codec'] for r in rows) != {'bgzip': 1, 'xz': 3, 'zstd_seekable': 3}:
        raise ValueError('all three qualified codecs and seven configurations required')
    if (root/'pick.md').read_text() != table(receipt['rows']):
        raise ValueError('JSON and table differ')
    states = []
    for row in rows:
        directory = root/(row['codec']+'-'+str(row['g']))
        state = json.loads((directory/'archive-state.json').read_text())
        state['archive'] = Path(state['archive'])
        query = [{'byte_offset': 0, 'requested_bytes': 16384}]
        verify_regions(state, source, query)  # Positive control uses real decoder.
        states.append((row, state, state['archive'].read_bytes()))
    rng = random.Random(20261105)
    counts = collections.Counter()
    records = []
    with tempfile.TemporaryDirectory(dir=root, prefix='corrupt-') as tmp:
        path = Path(tmp)/'archive'
        for i in range(count):
            row, original, raw = states[i % len(states)]
            blob = bytearray(raw)
            kind = ('bit', 'byte', 'truncate')[i % 3]
            offset = rng.randrange(len(blob))
            if kind == 'truncate':
                del blob[offset:]
            else:
                blob[offset] ^= (1 << rng.randrange(8)) if kind == 'bit' else 255
            path.write_bytes(blob)
            state = dict(original, archive=path)
            state['artifacts'] = dict(original['artifacts'])
            pinned = state['artifacts'].pop(str(original['archive']))
            state['artifacts'][str(path)] = pinned
            try:
                verify_regions(state, source, [{'byte_offset': 0, 'requested_bytes': 16384}])
            except ValueError as exc:
                if 'archive artifact SHA mismatch' not in str(exc):
                    raise
                outcome = 'rejected_by_pinned_archive_sha'
            else:
                raise AssertionError('mutated archive accepted')
            counts[row['codec']] += 1
            records.append(dict(case=i, codec=row['codec'], g=row['g'], kind=kind,
                                offset=offset, mutated_sha256=hashlib.sha256(blob).hexdigest(),
                                outcome=outcome))
    if digest(source) != receipt['input_sha256']:
        raise ValueError('input changed during campaign')
    report = dict(cases=len(records), rejected=len(records), false_successes=0,
                  seed=20261105, by_codec=dict(counts),
                  boundary='pick pinned-archive SHA guard, not codec corruption detection',
                  input_sha256=receipt['input_sha256'], records=records)
    (root/'corruption.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'records'}, sort_keys=True))
    for codec, seconds in sorted(receipt['codec_seconds'].items()):
        print(f'PICK_SECONDS codec={codec} seconds={seconds:.9f}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    root = args.directory.resolve()
    root.mkdir(parents=True, exist_ok=False)
    source = root/'input.bin'
    # Mixed deterministic alphabet and pseudo-random bytes; maximum input 100 MB.
    rng = random.Random(20261105)
    block = b'ACGTNacgt'*65536 + rng.randbytes(65536)
    remaining = 100_000_000
    with source.open('wb') as stream:
        while remaining:
            part = block[:remaining]
            stream.write(part)
            remaining -= len(part)
    print(f'INPUT bytes={source.stat().st_size} sha256={digest(source)}', flush=True)
    out = root/'pick'
    subprocess.run(['bash', 'run.sh', '--pick', str(source), '--output-dir', str(out)], check=True)
    campaign(out, source)
    extended = root/'pick-extended'
    started = time.monotonic()
    subprocess.run(['bash', 'run.sh', '--pick', str(source), '--g', '64K,1M,16M',
                    '--output-dir', str(extended)], check=True)
    elapsed = time.monotonic() - started
    result = json.loads((extended/'pick.json').read_text())
    expected = {('bgzip', 65280)} | {(c, g) for c in ('xz', 'zstd_seekable')
                                   for g in (65536, 1048576, 16777216)}
    if (result['g_set'] != [65536, 1048576, 16777216]
            or len(result['rows']) != 7
            or {(r['codec'], r['g']) for r in result['rows'] if r['status'] == 'measured'} != expected
            or result['input_sha256'] != digest(source)
            or (extended/'pick.md').read_text() != table(result['rows'])):
        raise ValueError('extended grid acceptance failed')
    print(f'EXTENDED_PICK_SECONDS g=64K,1M,16M seconds={elapsed:.9f}', flush=True)
    for codec, seconds in sorted(result['codec_seconds'].items()):
        print(f'EXTENDED_CODEC_SECONDS codec={codec} seconds={seconds:.9f}', flush=True)


if __name__ == '__main__':
    main()
