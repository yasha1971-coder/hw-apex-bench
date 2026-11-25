"""Choose the preregistered threshold from saved enwik8 data only; no codecs/clocks."""
import hashlib
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
FRAMES = (256, 1024, 4096, 16384, 65536, 262144, 524288)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    target = HERE / 'selection.json'
    if target.exists():
        raise ValueError('selection is immutable; never select again after holdout')
    if any((HERE / 'cells/holdout').glob('*.json')) or any((HERE / 'cells/validate').glob('*.json')):
        raise ValueError('selection must precede conditional validation and holdout')
    records, bindings = [], []
    for level in (3, 10, 19):
        for frame in FRAMES:
            path = HERE / 'cells/train' / f'L{level}-G{frame}.json'
            value = json.loads(path.read_bytes())
            assert value['status'] == 'COMPLETE' and value['corpus'] == 'enwik8'
            assert value['level'] == level and value['g'] == frame
            for variant in ('original', 'nohint'):
                samples = value['variants'][variant]['compression_ns']
                assert len(samples) == 5 and all(type(n) is int and n > 0 for n in samples)
                assert statistics.median(samples) == value['variants'][variant]['median_ns']
            records.append(value)
            bindings.append(dict(path=path.relative_to(HERE).as_posix(), sha256=sha(path)))
    candidates = []
    for threshold in (1024, 4096, 16384, 65536):
        failures = []
        for value in records:
            a, b = (value['variants'][name]['median_ns'] for name in ('original', 'nohint'))
            if value['g'] >= threshold and 10 * b > 11 * a:
                failures.append(dict(level=value['level'], g=value['g'], original_ns=a, nohint_ns=b))
        candidates.append(dict(threshold_bytes=threshold, eligible=not failures, failures=failures))
    chosen = next((c['threshold_bytes'] for c in candidates if c['eligible']), None)
    result = dict(status='SELECTED' if chosen is not None else 'NO SUPPORTED X',
                  threshold_bytes=chosen, candidates=candidates, training=bindings,
                  selection_rule='smallest preregistered grid X with nohint/original median <=1.10 for all enwik8 levels and G>=X',
                  training_only=True, holdout_inspected=False,
                  calibration_sha256=sha(HERE / 'CALIBRATION.md'), protocol_sha256=sha(HERE / 'PROTOCOL.md'),
                  selector_sha256=sha(__file__),
                  development_prediction={'compression': 'conditional/original median <=1.10 in every validation/holdout cell',
                                          'bytes': 'conditional identical to original below X and nohint at/above X',
                                          'kill': 'any holdout violation is a MISS; do not retune X'})
    data = (json.dumps(result, sort_keys=True, separators=(',', ':')) + '\n').encode()
    with target.open('xb') as stream:
        stream.write(data)
    print('THRESHOLD_SELECTION', result['status'], chosen, flush=True)


if __name__ == '__main__':
    main()
