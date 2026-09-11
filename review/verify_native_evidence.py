#!/usr/bin/env python3
"""Audit retained raw samples and traces without invoking any codec or timer."""
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys


def verify(path):
    path = Path(path)
    root = path.parent.resolve()
    manifest = json.loads(path.read_text())
    checked = {}

    def evidence(relative, expected):
        target = (root / relative).resolve()
        if not target.is_relative_to(root):
            raise ValueError('evidence path escapes run directory')
        blob = target.read_bytes()
        actual = hashlib.sha256(blob).hexdigest()
        if actual != expected:
            raise ValueError('evidence hash differs: ' + relative)
        checked[relative] = actual
        return blob

    def raw(node):
        samples = [json.loads(line) for line in evidence(node['raw_samples'], node['raw_sha256']).splitlines()]
        if not samples or not all(s['verified'] is True for s in samples):
            raise ValueError('unverified raw sample')
        return samples

    def equal(a, b):
        if not math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError(f'derived value differs: {a} != {b}')

    for adapter in manifest['adapters']:
        values = {v['axis']: v['value'] for v in adapter['measurements']}
        region = values['region']
        times = sorted(s['latency_ms'] for s in raw(region))
        equal(region['region_p50_ms'], times[math.ceil(len(times) * .5) - 1])
        equal(region['region_p99_ms'], times[math.ceil(len(times) * .99) - 1])
        amplification = values['amplification']
        samples = raw(amplification)
        equal(amplification['value'], sum(s['decoded_bytes'] for s in samples) / (len(samples) * 16384))
        for point in values['decode']['points']:
            samples = raw(point)
            if [s['wall_ms'] for s in samples] != point['sample_wall_ms']:
                raise ValueError('decode observations differ from raw samples')
            if not all(s['verified_bytes'] == point['input_bytes'] for s in samples):
                raise ValueError('decode verification covers wrong input length')
            equal(point['value'], point['input_bytes'] / statistics.median(s['wall_ms'] for s in samples) / 1000)
        for profile in values['h_alpha']['profiles']:
            trace = evidence(profile['trace'], profile['trace_sha256']).splitlines()
            if len(trace) != profile['count']:
                raise ValueError('trace request count differs')
            for line in trace:
                offset, length = map(int, line.split())
                if offset < 0 or length != 16384 or offset + length > manifest['corpus_bytes']:
                    raise ValueError('trace request out of bounds')
            distribution = profile['block_distribution']
            if sum(distribution.values()) != len(trace) or len(distribution) != profile['distinct_start_blocks']:
                raise ValueError('block distribution count differs')
            equal(profile['H_alpha_bits'], -sum((n / len(trace)) * math.log2(n / len(trace)) for n in distribution.values()))
        if values['batch']:
            for profile in values['batch']['profiles']:
                samples = raw(profile)
                if len(samples) != 6 or any(s['n'] != profile['count'] for s in samples):
                    raise ValueError('batch raw sample count differs')
                for method in ('loop', 'batch'):
                    subset = [s for s in samples if s['method'] == method]
                    if sorted(s['repeat'] for s in subset) != [0, 1, 2]:
                        raise ValueError('batch repeats differ')
                    equal(profile[method + '_ranges_s'], profile['count'] * 1000 / statistics.median(s['wall_ms'] for s in subset))
        breakeven = values['break_even']
        decode = breakeven['decode']
        samples = raw(decode)
        equal(decode['full_decode_median_ms'], statistics.median(s['wall_ms'] for s in samples))
        equal(breakeven['intersection_requests'], decode['full_decode_median_ms'] / region['region_p50_ms'])
        if breakeven['break_even_N'] != math.floor(breakeven['intersection_requests']) + 1:
            raise ValueError('break-even integer differs')
    return {'status': 'pass', 'evidence_files': len(checked), 'adapters': len(manifest['adapters']),
            'manifest_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'scope': 'raw region/counter/decode/batch samples, trace hashes and bounds, entropy and break-even arithmetic; no new measurements'}


if __name__ == '__main__':
    print(json.dumps(verify(sys.argv[1]), indent=2))
