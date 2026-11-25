"""Untimed HW-GIFT-1e method gates; this module never reads a clock.

Build setup/native libraries first. Full A/B selfchecks provide the AA input
receipts; small deterministic controls use the first 256 KiB of the same source.
"""
import argparse
import ctypes as C
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

import instrument as codec

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = ROOT / '.work/hw-gift-1e'
HELPER = ROOT / 'evidence/hw-gift-1b/ovh_bench.py'
CONTROL_BYTES = 262144


def check(ok, why):
    if not ok:
        raise ValueError(why)


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def ref(path):
    path = Path(path).resolve()
    check(path.is_relative_to(HERE), 'public method reference escaped evidence')
    return dict(path=path.relative_to(HERE).as_posix(), sha256=file_sha(path))


def bindings():
    for path in (Path(__file__), HERE / 'CALIBRATION.md', HERE / 'PROTOCOL.md',
                 HERE / 'instrument.py', HERE / 'setup.py', HELPER):
        codec.committed(path)
    private = STATE / 'setup.json'
    check(private.read_bytes() == (HERE / 'setup.json').read_bytes(), 'public/private setup bytes differ')
    return dict(calibration_sha256=file_sha(HERE / 'CALIBRATION.md'),
                protocol_sha256=file_sha(HERE / 'PROTOCOL.md'),
                instrument_sha256=file_sha(HERE / 'instrument.py'),
                controls_sha256=file_sha(__file__), setup_sha256=file_sha(private),
                ovh_helper_sha256=file_sha(HELPER))


def request_and_check(core, scope):
    name = scope + '-L10-G256.json'
    request_path = HERE / 'requests' / core / name
    selfcheck_path = HERE / 'selfchecks' / core / name
    cell = codec.request(core, scope, 10, 256)
    codec.save(request_path, cell)
    result = codec.untimed_selfcheck(cell)
    check(result['status'] == 'PASS' and result['clock_calls'] == 0
          and result['measurements_of_time'] is False
          and result['cell_sha256'] == file_sha(request_path)
          and all(row['bit_perfect'] for row in result['results']), 'untimed A/B selfcheck failed')
    codec.save(selfcheck_path, result)
    return cell, dict(request=ref(request_path), selfcheck=ref(selfcheck_path))


def versions(core):
    setup = load(STATE / 'setup.json')['cores'][core]
    libraries = {}
    for variant in codec.VARIANTS:
        native = codec.load(core, variant)
        number, text = native.ZSTD_versionNumber(), native.ZSTD_versionString().decode()
        check(number == codec.VERSIONS[core] and text == core.removeprefix('v'), 'actually linked version differs')
        libraries[variant] = dict(number=number, string=text)
    return dict(libraries=libraries, cli_version=setup['cli_version'],
                cli_sha256=setup['cli_sha256'], static_library_sha256=setup['library_sha256'])


def validate_saved(value, identity):
    check(value['bindings'] == identity and value['status'] == 'PASS' and value['clock_calls'] == 0,
          'saved method controls no longer bind these sources')
    request = HERE / value['request']['path']
    selfcheck = HERE / value['selfcheck']['path']
    check(file_sha(request) == value['request']['sha256']
          and file_sha(selfcheck) == value['selfcheck']['sha256'], 'method request/selfcheck changed')
    cell = load(request)
    codec.untimed_selfcheck(cell)  # Replays only the already retained selfcheck.
    for group in (value['positive'], value['negative_changed_input']):
        for row in group['results']:
            check(file_sha(row['archive_path']) == row['archive_sha256'] and row['bit_perfect'], 'saved control archive changed')
    check(value['runtime_versions'] == versions(cell['core']), 'saved runtime version evidence changed')


def core_controls(core, identity):
    progress = STATE / 'method-controls' / (core + '.json')
    if progress.exists():
        saved = load(progress)
        validate_saved(saved, identity)
        return saved
    cell, references = request_and_check(core, 'full')
    raw = Path(cell['input_path']).read_bytes()[:CONTROL_BYTES]
    check(len(raw) == CONTROL_BYTES, 'short deterministic control source')
    positive = codec.evaluate(cell, ['A', 'A'], clock=None, input_override=raw)
    a, b = positive['results']
    check(positive['clock_calls'] == 0, 'positive control read a timing clock')
    check((a['archive_bytes'], a['archive_sha256']) == (b['archive_bytes'], b['archive_sha256'])
          and Path(a['archive_path']).read_bytes() == Path(b['archive_path']).read_bytes(), 'same input/writer changed bytes')
    changed = bytes([raw[0] ^ 255]) + raw[1:]
    negative = codec.evaluate(cell, ['A'], clock=None, input_override=changed)
    check(negative['clock_calls'] == 0 and negative['input_sha256'] != positive['input_sha256']
          and negative['results'][0]['archive_sha256'] != a['archive_sha256'], 'changed-input control was not detected')
    check(all(row['bit_perfect'] and row['compression_ns'] is None
              for group in (positive, negative) for row in group['results']), 'control restoration/timing failure')
    archive = Path(a['archive_path']).read_bytes()
    count, descriptor, magic = struct.unpack('<IBI', archive[-9:])
    check(count > 0 and descriptor == 128 and magic == 0x8F92EAB1, 'control seek footer invalid')
    table = len(archive) - 17 - 12 * count
    check(table >= 0, 'control table outside archive')
    compressed, decompressed = struct.unpack_from('<II', archive, table + 8)
    check(0 < compressed <= table and decompressed == cell['g'], 'control frame 0 extent invalid')
    damaged = bytearray(archive[:compressed])
    damaged[0] ^= 255
    encoded, restored = C.create_string_buffer(bytes(damaged), len(damaged)), C.create_string_buffer(decompressed)
    native = codec.load(core, 'A')
    code = native.ZSTD_decompress(restored, decompressed, encoded, len(damaged))
    check(bool(native.ZSTD_isError(code)), 'corrupted magic silently decoded')
    value = dict(status='PASS', clock_calls=0, measurements_of_time=False, core=core,
                 bindings=identity, **references, control_input_bytes=CONTROL_BYTES,
                 control_input_sha256=hashlib.sha256(raw).hexdigest(),
                 positive=positive, negative_changed_input=negative,
                 corrupt_magic_rejected=True, runtime_versions=versions(core))
    codec.save(progress, value)
    return value


def load_gate_controls():
    spec = importlib.util.spec_from_file_location('_gift1e_ovh_method', HELPER)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    cases = []
    for start, end, expected in (('1.00', '1.00', False), ('2.00', '2.00', False),
                                 ('2.01', '0.00', True), ('0.00', '2.01', True)):
        actual = helper.is_loaded({'loadavg_raw': start + ' 0 0 1/1 1'},
                                  {'loadavg_raw': end + ' 0 0 1/1 1'})
        check(actual == expected, 'load threshold known answer failed')
        cases.append(dict(start=start, end=end, expected_loaded=expected, actual_loaded=actual))
    start = dict(proc_stat_raw='cpu0 1 0 0 9 0 0 0 0\ncpu1 2 0 0 8 0 0 0 0\n', proc_stat_error=None)
    end = dict(proc_stat_raw='cpu0 2 0 0 18 0 0 0 0\ncpu1 5 0 0 15 0 0 0 0\n', proc_stat_error=None)
    delta = helper.other_cpu_delta(start, end)
    check(delta['status'] == 'ok' and set(delta['cpus']) == {'cpu1'}
          and delta['cpus']['cpu1']['busy_jiffies'] == 3
          and delta['cpus']['cpu1']['total_jiffies'] == 10, 'other-core CPU delta known answer failed')
    return cases, delta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'method-controls.json')
    args = parser.parse_args()
    check(args.output.resolve().is_relative_to(HERE), 'public controls output escaped evidence')
    identity = bindings()
    if args.output.exists():
        saved = load(args.output)
        check(saved['schema'] == 'hw-gift-1e-method-controls-v1'
              and all(saved[key] == value for key, value in identity.items()), 'saved control source bindings changed')
        for value in saved['cores'].values():
            validate_saved(value, identity)
        known = saved['known_1d']
        check(file_sha(HERE / known['request']['path']) == known['request']['sha256']
              and file_sha(HERE / known['selfcheck']['path']) == known['selfcheck']['sha256'], 'saved known-answer receipt changed')
        codec.untimed_selfcheck(load(HERE / known['request']['path']))
        print('METHOD_CONTROLS_PASS clock_calls=0', file_sha(args.output), flush=True)
        return
    cases, delta = load_gate_controls()
    cores = {core: core_controls(core, identity) for core in codec.PINS}
    cell, known = request_and_check('v1.5.7', 'prefix')
    result = load(HERE / known['selfcheck']['path'])
    check(result['known_1d_checked'] is True and result['known_1d_source'] is not None,
          'v1.5.7 prefix did not bind the saved 1d known answer')
    value = dict(schema='hw-gift-1e-method-controls-v1', status='PASS', clock_calls=0,
                 measurements_of_time=False, **identity, cores=cores,
                 known_1d=dict(**known, source=result['known_1d_source'], cell_id=cell['cell_id']),
                 load_gate_cases=cases, other_cpu_known_answer=delta)
    codec.save(args.output, value)
    print('METHOD_CONTROLS_PASS clock_calls=0', file_sha(args.output), flush=True)


if __name__ == '__main__':
    main()
