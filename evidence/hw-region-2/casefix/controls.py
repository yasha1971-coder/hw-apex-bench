# SPDX-License-Identifier: Apache-2.0
"""Prespecified fresh-handle boundary controls; no work on import.

prepare: metadata-only selection, synthetic writer and untimed equality checks.
run: four load-admitted timed units through drive.timed_unit, first CLEAN only.
No candidate is selected or retried because of its elapsed time.
"""
import argparse
from bisect import bisect_right
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
STATE = ROOT / '.work/hw-region-2/casefix'
R = 16384
PROFILES = ('aceapex', 'zstd_seekable', 'bgzip', 'twobit_casefix_mask1')


def require(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def load(path):
    return json.loads(Path(path).read_bytes())


def module(path, label):
    spec = importlib.util.spec_from_file_location(label, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def driver(value=None):
    return value if value is not None else module(HERE / 'drive.py', '_region2_controls_drive')


def artifact(path):
    path = Path(path).resolve()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def immutable(path, raw):
    path = Path(path).resolve()
    require(path.is_relative_to(STATE.resolve()) or path.is_relative_to(HERE.resolve()), 'control output escaped owned stage')
    if path.exists():
        require(path.read_bytes() == raw, 'retained control changed: ' + str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)


def checked_file(record):
    path = Path(record['path'])
    require(path.is_file() and path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], 'control input artifact changed')
    return path


def paired_offsets(aligned, crossing, count):
    offsets, roles = [], []
    for pair in range(count):
        order = (('aligned', aligned), ('crossing', crossing)) if pair % 2 == 0 else (('crossing', crossing), ('aligned', aligned))
        for role, offset in order:
            offsets.append(offset)
            roles.append(role)
    return offsets, roles


def make_trace(profile, aligned, crossing, case):
    warmups, warmup_roles = paired_offsets(aligned, crossing, 12)
    requests, roles = paired_offsets(aligned, crossing, 1000)
    records = {}
    for key, offsets in (('warmups', warmups), ('requests', requests)):
        path = STATE / 'controls/traces' / profile / (key + '.bin')
        immutable(path, b''.join(struct.pack('<Q', off) for off in offsets))
        records[key] = dict(**artifact(path), offsets=offsets)
    trace = dict(schema='hw-region-2-casefix-control-trace-v1', request_bases=R, corpus=case['corpus'], profile=profile,
                 sequence_length=case['sequence']['bytes'], fai_geometry=case['fai']['geometry'],
                 fresh_per_request=True, probe=True, pairs=1000, pair_order='AB for even pair_index, BA for odd; A=aligned/B=crossing',
                 aligned_base=aligned, crossing_base=crossing, warmup_pairs=12,
                 warmup_roles=warmup_roles, roles=roles, **records)
    public = HERE / 'control-traces' / (profile + '.json')
    immutable(public, packed(trace))
    return trace, public


def byte_at(fai, base):
    return fai['offset'] + base // fai['line_bases'] * fai['line_width'] + base % fai['line_bases']


def byte_span(fai, start):
    require(0 <= start and start + R < fai['length'], 'control must be valid and nonterminal')
    return byte_at(fai, start), byte_at(fai, start + R - 1) + 1


def first_base_on_or_after(fai, position):
    delta = position - fai['offset']
    if delta <= 0:
        return 0
    row, column = divmod(delta, fai['line_width'])
    return row * fai['line_bases'] + min(column, fai['line_bases'])


def seekable_units(data, expected_size):
    require(len(data) >= 17, 'truncated seekable footer')
    count, flags, magic = struct.unpack('<IBI', data[-9:])
    require(count > 0 and flags == 128 and magic == 0x8f92eab1, 'unexpected seekable checksum/footer format')
    table = len(data) - 17 - count * 12
    require(table >= 0 and struct.unpack_from('<II', data, table) == (0x184d2a5e, 12 * count + 9), 'seekable table bounds differ')
    units, raw, compressed = [], 0, 0
    for index in range(count):
        cn, dn, checksum = struct.unpack_from('<III', data, table + 8 + 12 * index)
        require(cn > 0 and cn <= table - compressed and (dn > 0 or index == count - 1), 'seekable frame geometry differs')
        if dn:
            units.append(dict(index=index, start=raw, decoded_bytes=dn, compressed_start=compressed, compressed_bytes=cn))
        raw += dn
        compressed += cn
    require(raw == expected_size and compressed == table, 'seekable/source byte extent differs')
    return units


def bgzf_units(data, expected_size):
    units, position, raw, index = [], 0, 0, 0
    while position < len(data):
        require(len(data) - position >= 26 and data[position:position + 4] == b'\x1f\x8b\x08\x04', 'BGZF header differs')
        extra_bytes = struct.unpack_from('<H', data, position + 10)[0]
        extra_end = position + 12 + extra_bytes
        require(extra_end <= len(data), 'BGZF extra field escapes archive')
        cursor, block_bytes = position + 12, None
        while cursor < extra_end:
            require(cursor + 4 <= extra_end, 'truncated BGZF subfield')
            key = data[cursor:cursor + 2]
            width = struct.unpack_from('<H', data, cursor + 2)[0]
            require(width <= extra_end - cursor - 4, 'BGZF subfield escapes header')
            if key == b'BC':
                require(width == 2 and block_bytes is None, 'duplicate/invalid BGZF BC field')
                block_bytes = struct.unpack_from('<H', data, cursor + 4)[0] + 1
            cursor += 4 + width
        require(block_bytes is not None and block_bytes >= extra_end - position + 8 and block_bytes <= len(data) - position, 'BGZF compressed extent differs')
        decoded = struct.unpack_from('<I', data, position + block_bytes - 4)[0]
        require(decoded > 0 or position + block_bytes == len(data), 'nonterminal empty BGZF block')
        if decoded:
            units.append(dict(index=index, start=raw, decoded_bytes=decoded, compressed_start=position, compressed_bytes=block_bytes))
        raw += decoded
        position += block_bytes
        index += 1
    require(position == len(data) and raw == expected_size and decoded == 0, 'BGZF/source extent or EOF differs')
    return units


def covered_units(units, begin, end):
    starts = [unit['start'] for unit in units]
    first, last = bisect_right(starts, begin) - 1, bisect_right(starts, end - 1) - 1
    require(0 <= first <= last < len(units) and end <= units[last]['start'] + units[last]['decoded_bytes'], 'control span escapes units')
    selected = units[first:last + 1]
    return [unit['index'] for unit in selected], sum(unit['decoded_bytes'] for unit in selected)


def ace_cold(model, begin, end):
    # Reset model state only; these are metadata cursors, never codec contexts.
    model.last_block = None
    for cursor in model.streams.values():
        cursor.slots = [dict(index=None, age=0) for _ in range(4)]
        cursor.tick = 0
    value = model.request(begin, end - begin)
    return dict(native_units=value['covered'], cold_materialized_bytes=value['materialized'],
                chunk_misses=value['missed'], chunk_miss_bytes=value['missed_bytes'])


def select_real(profile, case):
    record = case['formats'][profile]
    path = checked_file(record)
    data = path.read_bytes()
    fai = case['fai']['geometry']
    model = None
    parser_source = None
    if profile == 'aceapex':
        tail_path = ROOT / 'evidence/hw-region-1/tail.py'
        parser = module(tail_path, '_region2_controls_ace_metadata')
        model = parser.Archive(data, case['input']['bytes'], case['g'])
        boundaries = [index * model.g for index in range(1, model.count)]
        parser_source = artifact(tail_path)
    else:
        units = (seekable_units if profile == 'zstd_seekable' else bgzf_units)(data, case['input']['bytes'])
        boundaries = [unit['start'] for unit in units[1:]]
    for boundary in boundaries:
        aligned = first_base_on_or_after(fai, boundary)
        crossing = aligned - 1
        if crossing < 0 or aligned + R >= fai['length']:
            continue
        a_begin, a_end = byte_span(fai, aligned)
        b_begin, b_end = byte_span(fai, crossing)
        if not (b_begin < boundary <= a_begin):
            continue
        if model is not None:
            a, b = ace_cold(model, a_begin, a_end), ace_cold(model, b_begin, b_end)
        else:
            a_ids, a_work = covered_units(units, a_begin, a_end)
            b_ids, b_work = covered_units(units, b_begin, b_end)
            a = dict(native_units=a_ids, cold_materialized_bytes=a_work)
            b = dict(native_units=b_ids, cold_materialized_bytes=b_work)
        if len(b['native_units']) <= len(a['native_units']) or b['cold_materialized_bytes'] <= a['cold_materialized_bytes']:
            continue
        return dict(rule='first actual boundary whose first base on/after it and preceding base add a native unit and cold work',
                    selected_by='archive metadata only; no timings', boundary_byte=boundary, aligned_base=aligned, crossing_base=crossing,
                    aligned_byte_span=[a_begin, a_end], crossing_byte_span=[b_begin, b_end],
                    aligned=a, crossing=b, archive=dict(path=record['path'], bytes=record['bytes'], sha256=record['sha256']),
                    fai_geometry=fai, metadata_parser=parser_source)
    raise ValueError('no eligible prespecified actual native-boundary control: ' + profile)


def synthetic_case(setup_sha):
    writer_path = PARENT / 'writer.py'
    writer = module(writer_path, '_region2_control_writer')
    folder = STATE / 'controls/mask-fixture'
    sequence = b'ACGT' * (R // 4) + b'acgt' * (R // 4) + b'ACGT' * ((R + 16) // 4)
    fasta = folder / 'source.fa'
    raw = b'>mask-control\n' + b''.join(sequence[i:i + 80] + b'\n' for i in range(0, len(sequence), 80))
    immutable(fasta, raw)
    metadata = writer.write_fasta(fasta, folder, hashlib.sha256(raw).hexdigest(), hashlib.sha256(sequence).hexdigest())
    require(metadata['archive']['n_blocks'] == [] and metadata['archive']['mask_blocks'] == [[R, R]]
            and metadata['sequence']['bytes'] == 3 * R + 16, 'synthetic mask geometry differs from protocol')
    public = HERE / 'control-writer-metadata/mask-fixture.json.gz'
    # GzipFile emits no variable filename/time and is reproducible on replay.
    import io
    stream = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as archive:
        archive.write(packed(metadata))
    immutable(public, stream.getvalue())
    archive = {k: v for k, v in metadata['archive'].items() if k not in ('n_blocks', 'mask_blocks')}
    archive.update(indexes=[], stored_bytes=metadata['archive']['bytes'], structural_bit_perfect=True,
                   sequence_sha256=metadata['sequence']['sha256'])
    case = dict(schema='hw-region-2-casefix-archives-v1', corpus='method-mask-fixture', g=R, request_bases=R,
                input=artifact(fasta), sequence=metadata['sequence'], fai=metadata['fai'], writer_metadata=artifact(public),
                formats=dict(twobit=archive), setup_sha256=setup_sha)
    selection = dict(rule='prespecified synthetic method fixture, not main corpus or a timing-selected candidate',
                     aligned_base=0, crossing_base=R // 2, aligned_base_span=[0, R], crossing_base_span=[R // 2, 3 * R // 2],
                     mask_boundary=R, mask_blocks=[[R, R]], aligned_masked_bases=0, crossing_masked_bases=R // 2,
                     same_packed_start_mod4=True, n_blocks=[], writer_source=artifact(writer_path))
    return case, selection


def identity(drive):
    drive.native_build()
    return dict(source_sha256=drive.source_map(), native_build_sha256=sha(HERE / 'native/build.json'), setup_sha256=sha(HERE / 'setup.json'))


def check_observation(observed, trace):
    summary, rows = observed['summary'], observed['rows']
    require(summary['status'] == 'PASS' and summary['semantics'] == 0 and summary['byte_equivalent'] is True
            and summary['fresh_per_request'] is True and summary['queries'] == summary['planned_queries'] == 2000
            and summary['warmups'] == 24 and summary['request_bases'] == R and len(rows) == 2000, 'fresh equivalent boundary observation incomplete')
    for i, row in enumerate(rows):
        require(row['query'] == i and row['start0'] == trace['requests']['offsets'][i] and row['requested_bases'] == R
                and row['verified'] is True and row['differences'] == row['permitted_n_to_N'] == 0, 'boundary coordinate/equality differs')
    return rows


def prepare(drive=None):
    drive = driver(drive)
    current = identity(drive)
    target = HERE / 'controls-plan.json'
    if target.exists():
        value = load(target)
        require(value['status'] == 'PREPARED' and all(value[k] == v for k, v in current.items()), 'saved control preparation cohort changed')
        for item in value['evidence_refs']:
            drive.deref(item)
        for item in value['controls'].values():
            for key in ('warmups', 'requests'):
                checked_file(item['trace'][key])
        return value
    case = drive.load_case('chr1')
    controls, evidence = {}, []
    for profile in PROFILES:
        if profile == 'twobit_casefix_mask1':
            used_case, selection = synthetic_case(current['setup_sha256'])
        else:
            used_case, selection = case, select_real(profile, case)
        trace, trace_path = make_trace(profile, selection['aligned_base'], selection['crossing_base'], used_case)
        observed, unit_path = drive.checked_unit('boundary-' + profile, profile, used_case, trace, fresh=True, probe=True)
        check_observation(observed, trace)
        require(observed['summary']['measurements_of_time'] is False and observed['summary']['query_clock_calls'] == 0
                and observed['summary']['open_clock_calls'] == 0, 'untimed control preparation read a clock')
        unit_ref = drive.ref(unit_path)
        evidence.append(unit_ref)
        controls[profile] = dict(case=used_case, trace=trace, trace_ref=drive.ref(trace_path), selection=selection, equality_unit=unit_ref)
    value = dict(schema='hw-region-2-casefix-controls-plan-v1', status='PREPARED', no_clocks=True, measurements_of_time=False,
                 profiles=list(PROFILES), **current, controls=controls, evidence_refs=evidence)
    immutable(target, packed(value))
    return value


def run(drive=None):
    drive = driver(drive)
    plan = prepare(drive)
    target = HERE / 'controls.json'
    if target.exists():
        value = load(target)
        require(value['plan']['sha256'] == sha(HERE / 'controls-plan.json')
                and all(value[k] == v for k, v in identity(drive).items()), 'saved control result cohort changed')
        for item in value['evidence_refs']:
            drive.deref(item)
        require((HERE / 'controls-summary.json').read_bytes() == target.read_bytes(), 'control summary replay differs')
        return value
    result = dict(schema='hw-region-2-casefix-controls-v1', status='PASS', **identity(drive), plan=drive.ref(HERE / 'controls-plan.json'),
                  profiles=list(PROFILES), controls={}, evidence_refs=[], rule='strict crossing nearest-rank p50 > aligned nearest-rank p50; no elapsed-based retry')
    for profile in PROFILES:
        control = plan['controls'][profile]
        observed, unit_path = drive.timed_unit('boundary', 'boundary-' + profile, profile, control['case'], control['trace'], fresh=True, probe=True)
        rows = check_observation(observed, control['trace'])
        require(observed['summary']['measurements_of_time'] is True and observed['summary']['query_clock_calls'] == 4000,
                'boundary query clock count differs')
        require(all(type(row['elapsed_ns']) is int and row['elapsed_ns'] > 0 for row in rows), 'boundary elapsed sample must be positive integer')
        aligned = sorted(row['elapsed_ns'] for row, role in zip(rows, control['trace']['roles']) if role == 'aligned')
        crossing = sorted(row['elapsed_ns'] for row, role in zip(rows, control['trace']['roles']) if role == 'crossing')
        require(len(aligned) == len(crossing) == 1000, 'balanced boundary pair roles differ')
        a, b = aligned[499], crossing[499]
        passed = b > a
        unit_ref = drive.ref(unit_path)
        result['controls'][profile] = dict(aligned_p50_ns=a, crossing_p50_ns=b, strictly_more_cost=passed,
            aligned_p99_ns=aligned[989], crossing_p99_ns=crossing[989], aligned_samples=1000, crossing_samples=1000,
            unit=unit_ref, trace=control['trace_ref'], selection=control['selection'])
        result['evidence_refs'].append(unit_ref)
        if not passed:
            result.update(status='METHODFAIL: crossing not strictly slower', first_failure_profile=profile,
                          not_run=[name for name in PROFILES if name not in result['controls']])
            break
    raw = packed(result)
    immutable(target, raw)
    immutable(HERE / 'controls-summary.json', raw)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run'))
    args = parser.parse_args()
    result = prepare() if args.action == 'prepare' else run()
    print(args.action.upper(), result['status'])
    return 0 if result['status'] in ('PASS', 'PREPARED') else 1


if __name__ == '__main__':
    raise SystemExit(main())
