"""Untimed method controls; no clock is imported or called."""
import argparse
import ctypes as ct
import hashlib
import json
from pathlib import Path
import sys

import instrument as codec

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'evidence/hw-gift-1b'))
import ovh_bench
sys.path.insert(0, str(ROOT / 'evidence/hw-gift-1c'))
from seekable import parse_archive


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cell', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    check(not args.output.exists(), 'method controls are immutable')
    cell = json.loads(args.cell.read_bytes())
    check(cell['corpus'] == 'enwik8' and cell['level'] == 3 and cell['g'] == 262144,
          'known-answer cell required')
    positive = codec.evaluate(cell, ['original', 'original'], clock=None)
    a, b = positive['results']
    check(positive['clock_calls'] == 0 and a['archive_sha256'] == b['archive_sha256']
          and a['archive_bytes'] == b['archive_bytes'], 'positive equality failed')
    both = codec.evaluate(cell, ['original', 'nohint'], clock=None)
    known = json.loads((ROOT / 'evidence/hw-gift-1c/cases/enwik8-L3-262144.json').read_bytes())
    for result in both['results']:
        prior = known['archives']['original' if result['variant'] == 'original' else 'patched']
        check(result['archive_bytes'] == prior['bytes'] and result['archive_sha256'] == prior['sha256'],
              'known 1c complete archive mismatch')
    changed = bytearray(Path(cell['input_path']).read_bytes())
    changed[0] ^= 0xFF
    negative = codec.evaluate(cell, ['original'], clock=None, input_override=bytes(changed))
    check(negative['clock_calls'] == 0 and negative['results'][0]['archive_sha256'] != a['archive_sha256'],
          'changed input was not detected')
    data = Path(a['archive_path']).read_bytes()
    frame = parse_archive(data)['frames'][0]
    damaged = bytearray(data[frame['offset']:frame['offset'] + frame['compressed_bytes']])
    damaged[0] ^= 0xFF
    source = ct.create_string_buffer(bytes(damaged), len(damaged))
    restored = ct.create_string_buffer(frame['decompressed_bytes'])
    lib = codec.load('original')
    answer = lib.ZSTD_decompress(restored, len(restored), source, len(damaged))
    check(bool(lib.ZSTD_isError(answer)), 'corrupt magic silently decoded')
    gate_cases = []
    for first, last, expected in [('1.00', '1.00', False), ('2.00', '2.00', False),
                                  ('2.01', '0.00', True), ('0.00', '2.01', True)]:
        observed = ovh_bench.is_loaded({'loadavg_raw': first + ' 0 0 1/1 1'},
                                       {'loadavg_raw': last + ' 0 0 1/1 1'})
        check(observed == expected, 'load threshold known answer failed')
        gate_cases.append(dict(start=first, end=last, expected_loaded=expected, actual_loaded=observed))
    start = {'proc_stat_raw': 'cpu0 1 0 0 9 0 0 0 0\ncpu1 2 0 0 8 0 0 0 0\n', 'proc_stat_error': None}
    end = {'proc_stat_raw': 'cpu0 2 0 0 18 0 0 0 0\ncpu1 5 0 0 15 0 0 0 0\n', 'proc_stat_error': None}
    delta = ovh_bench.other_cpu_delta(start, end)
    check(delta['status'] == 'ok' and delta['cpus']['cpu1']['busy_jiffies'] == 3
          and delta['cpus']['cpu1']['total_jiffies'] == 10, 'CPU-delta known answer failed')
    check(all(x['bit_perfect'] for value in (positive, both, negative) for x in value['results']),
          'a control did not restore bit for bit')
    result = dict(status='PASS', clock_calls=0, measurements_of_time=False,
                  calibration_sha256=sha(HERE / 'CALIBRATION.md'),
                  instrument_sha256=sha(HERE / 'instrument.py'), controls_sha256=sha(__file__),
                  cell_sha256=sha(args.cell), known_answer_sha256=sha(ROOT / 'evidence/hw-gift-1c/cases/enwik8-L3-262144.json'),
                  positive=positive, known_answer=both, negative_changed_input=negative,
                  corrupt_magic_rejected=True, load_gate_cases=gate_cases, other_cpu_known_answer=delta)
    codec.save(args.output, result)
    print('METHOD_CONTROLS_PASS clock_calls=0', flush=True)


if __name__ == '__main__':
    main()
