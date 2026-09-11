#!/usr/bin/env python3
"""Read-only audit of the retained five-point curve; never invokes codecs."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shlex

GRID = [4096, 16384, 65536, 262144, 1048576]
SIZE = 253935557
MD5 = '9465e0f0df6e2c6eb39729c39cee5465'
CODECS = ('aceapex-cg-default', 'zstd-seekable-cg')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def normalize_command(command, codec, g):
    """Allow only the independent-unit parameter and ACE output path to differ."""
    args = shlex.split(command)
    require(args[:1] == ['cd'] and args[2:4] == ['&&', 'env'], 'unexpected command structure')
    if codec == CODECS[0]:
        parameter = f'ACEAPEX_BS={g}'
        require(args.count(parameter) == 1, 'wrong ACEAPEX block parameter')
        args[args.index(parameter)] = 'ACEAPEX_BS=<g>'
        require(args.count('--out') == 1, 'missing/duplicate output path')
        i = args.index('--out') + 1
        require(Path(args[i]).name == f'{codec}-{g}.archive', 'unexpected ACEAPEX output name')
        args[i] = str(Path(args[i]).with_name(f'{codec}-<g>.archive'))
        require(args[-2:] == ['--threads', '8'], 'wrong ACEAPEX requested threads')
    else:
        require(args[-2:] == [str(g), '3'], 'wrong zstd frame size or level')
        require(Path(args[-4]).name == 'seekable_compression', 'wrong zstd compressor')
        args[-2] = '<g>'
    return args


def geometry(record, codec, g):
    geo = record['geometry']
    expected = (SIZE + g - 1) // g
    require(geo['actual_max_block_bytes'] == min(g, SIZE), 'wrong maximum data-unit size')
    if codec == CODECS[0]:
        require(geo['block_size'] == g and geo['num_blocks'] == expected, 'wrong ACEAPEX block geometry')
        require(geo['header_bytes'] == 68 and geo['block_offsets_bytes'] == expected*64, 'wrong ACEAPEX header/table size')
        require(geo['archive_bytes'] == record['archive_bytes'] and geo['archive_sha256'] == record['archive_sha256'], 'header/archive receipt mismatch')
    else:
        hist = {int(k): v for k, v in geo['block_size_histogram'].items()}
        require(all(k >= 0 and type(v) is int and v > 0 for k, v in hist.items()), 'invalid frame histogram')
        require(sum(k*v for k, v in hist.items()) == SIZE, 'frames do not cover the complete corpus')
        require(sum(v for k, v in hist.items() if k) == expected == geo['nonempty_blocks'], 'wrong nonempty-frame count')
        require(sum(hist.values()) == geo['num_blocks'], 'wrong physical-frame count')
        require(max(hist) == min(g, SIZE) and hist.get(0, 0) <= 1, 'unexpected frame geometry')
        require(geo['seek_table_checksums'] is True and geo['seek_table_bytes'] == 17+12*geo['num_blocks'], 'seek table policy changed')
    require(record['full_restore_byte_equal'] is True and record['restore_md5'] == MD5, 'restore not verified')
    require(record['index_bytes'] == 0 and record['total_bytes'] == record['archive_bytes'], 'unexpected sidecar/accounting')
    require(math.isclose(record['ratio'], SIZE/record['total_bytes'], rel_tol=1e-12), 'bad ratio')


def audit(rows):
    rows = [r for r in rows if r.get('evidence_group') == 'cg-five-point-v1']
    require(len(rows) == 15, 'expected fifteen curve positions')
    output = []
    for codec in CODECS:
        curve = sorted((r for r in rows if r['codec'] == codec), key=lambda r:r['g'])
        require([r['g'] for r in curve] == GRID, 'incomplete codec grid')
        for field in ('baseline', 'configuration', 'versions', 'source_provenance', 'hardware', 'corpus', 'run_id', 'benchmark_commit', 'cleared_environment'):
            require(len({json.dumps(r[field], sort_keys=True) for r in curve}) == 1, 'changed '+field)
        first = curve[0]
        require(first['corpus']['bytes'] == SIZE and first['corpus']['md5'] == MD5, 'wrong corpus')
        baseline = first['baseline']
        geometry(baseline, codec, SIZE)
        command = normalize_command(baseline['commands'][0], codec, SIZE)
        points = []
        for row in curve:
            point = row['point']; g = row['g']
            geometry(point, codec, g)
            require(normalize_command(point['commands'][0], codec, g) == command, 'encoder command differs beyond granularity/output')
            cost = 100*(1-baseline['total_bytes']/point['total_bytes'])
            require(row['status'] == 'measured' and math.isclose(row['value'], cost, abs_tol=1e-10), 'c(g) mismatch')
            points.append(dict(g=g, c_g_percent=cost, total_bytes=point['total_bytes'],
                               data_units=point['geometry'].get('nonempty_blocks', point['geometry']['num_blocks']),
                               indexed_units=point['geometry']['num_blocks'],
                               empty_units=int(point['geometry'].get('block_size_histogram', {}).get('0', 0))))
        output.append(dict(codec=codec, baseline_bytes=baseline['total_bytes'],
                           baseline_sha256=baseline['archive_sha256'],
                           baseline_data_units=1, baseline_physical_units=baseline['geometry']['num_blocks'],
                           baseline_empty_units=int(baseline['geometry'].get('block_size_histogram', {}).get('0', 0)),
                           command_changes='granularity and ACEAPEX output filename only', points=points))
    bgzf = sorted((r for r in rows if r['codec'] == 'bgzip-cg'), key=lambda r:r['g'])
    require([r['g'] for r in bgzf] == GRID, 'missing BGZF positions')
    for row in bgzf:
        require(row['baseline'] is None and row['status'] == 'n/a' and row['value'] is None and bool(row['reason']), 'invented BGZF baseline')
    return dict(schema='cabench-cg-baseline-review-v1', timed=False, result='PASS',
                scope='retained commands, geometry and provenance; no fresh archive decoding', codecs=output,
                bgzf='n/a — no comparable single-parameter baseline')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    raw = args.results.read_bytes()
    result = audit([json.loads(line) for line in raw.splitlines()])
    result['results_sha256'] = hashlib.sha256(raw).hexdigest()
    if args.out:
        args.out.write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: 10 matched c(g) points; one data unit per baseline; BGZF explicitly n/a')


if __name__ == '__main__':
    main()
