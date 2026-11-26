# SPDX-License-Identifier: Apache-2.0
"""Saved-data mask-table geometry; no reader, native code, clocks or network.

The linear count includes the entry which triggers softMask's break. Binary
search counts are abstract end comparisons plus subsequent body entries, not
elapsed time, unique cache lines or a model of CPU cycles.
"""
import argparse
from bisect import bisect_left, bisect_right
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASEFIX = HERE.parent / 'casefix'
CORPORA = ('chr1',) + tuple(f't2t-{i:02d}' for i in range(30))
PIN = '58e20daa898a6fc338eae82e5d2ef7108d4fc07f'
UPSTREAM_SHA = '9e41b65b0842bf541518bd785e7ca35c51f3fe5183676cbb62f96e4c96710318'
BINDS = {}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


def read(path, expected_sha=None, expected_bytes=None):
    path = path.resolve()
    require(path.is_relative_to(ROOT) and not path.is_relative_to(ROOT / '.work'), 'public evidence only')
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    require(expected_sha is None or digest == expected_sha, 'SHA differs: ' + str(path))
    require(expected_bytes is None or len(raw) == expected_bytes, 'byte count differs: ' + str(path))
    name = path.relative_to(ROOT).as_posix()
    require(BINDS.setdefault(name, digest) == digest, 'source changed during analysis: ' + name)
    return raw


def load(path, expected_sha=None, expected_bytes=None):
    return json.loads(read(path, expected_sha, expected_bytes), object_pairs_hook=unique)


def reference(path):
    raw = read(path)
    return dict(path=path.relative_to(ROOT).as_posix(), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def valid_runs(runs, length, label):
    require(isinstance(runs, list), label + ': interval list required')
    previous_end = 0
    for index, row in enumerate(runs):
        require(isinstance(row, list) and len(row) == 2 and integer(row[0]) and integer(row[1], 1), label + ': invalid run')
        start, size = row
        require(start >= previous_end and start + size <= length, label + ': unsorted/overlapping/out-of-range run')
        previous_end = start + size
    return [s for s, n in runs], [s + n for s, n in runs]


def lower_bound_end(ends, start):
    """First exclusive end > start, with the exact abstract probe count."""
    low, high, comparisons = 0, len(ends), 0
    while low < high:
        middle = low + (high - low) // 2
        comparisons += 1
        if ends[middle] <= start:
            low = middle + 1
        else:
            high = middle
    return low, comparisons


def query_geometry(starts, ends, start, size, query):
    end = start + size
    first, comparisons = lower_bound_end(ends, start)
    require(first == bisect_right(ends, start), 'independent lower_bound disagreement')
    after = bisect_left(starts, end)
    require(first <= after, 'invalid disjoint-run intersection geometry')
    stop = int(after < len(starts))
    intersections = list(range(first, after))
    masked = sum(min(ends[i], end) - max(starts[i], start) for i in intersections)
    # Pinned softMask: blockEnd<=start -> continue, then blockStart>=end ->
    # break. Every previous entry and the stopping entry are examined.
    linear = after + stop
    body = after - first + stop
    return dict(query=query, start0=start, end0=end, first_candidate_index0=first,
        linear_skipped_ended_entries=first, linear_entries_examined=linear,
        stopping_entry_index0=after if stop else None,
        binary_search_end_comparisons=comparisons, binary_body_entries_examined=body,
        binary_entry_inspections=comparisons + body,
        intersecting_mask_indices0=intersections, intersecting_mask_blocks=len(intersections), intersecting_mask_bases=masked)


def nearest(values, percent):
    require(values and all(integer(x) for x in values), 'nonnegative integer geometry samples required')
    return sorted(values)[(len(values) * percent + 99) // 100 - 1]


def geometry_summary(rows):
    fields = ('first_candidate_index0', 'linear_skipped_ended_entries', 'linear_entries_examined',
              'binary_search_end_comparisons', 'binary_body_entries_examined', 'binary_entry_inspections',
              'intersecting_mask_blocks', 'intersecting_mask_bases')
    return {field: dict(min=min(r[field] for r in rows), p50=nearest([r[field] for r in rows], 50),
        p99=nearest([r[field] for r in rows], 99), max=max(r[field] for r in rows),
        total=sum(r[field] for r in rows), mean=str(Fraction(sum(r[field] for r in rows), len(rows)))) for field in fields}


def build():
    BINDS.clear()
    read(Path(__file__).resolve())
    read(HERE / 'CALIBRATION.md')
    audit_path = CASEFIX / 'audit/resumed-all.json'
    audit = load(audit_path)
    require(audit['status'] == 'PASS' and audit['stage'] == 'resumed-all' and audit['completion'] == 'COMPLETE'
            and audit['full_comparison_complete'] is True and audit['counts']['cases'] == 31 and audit['counts']['rows'] == 186,
            'complete retained casefix audit required')
    anchors = {r['path']: r['sha256'] for r in audit['source_bindings']}
    require(len(anchors) == len(audit['source_bindings']), 'duplicate parent audit binding')

    def anchored(path):
        name = path.relative_to(ROOT).as_posix()
        require(name in anchors, 'numerical input absent from parent audit: ' + name)
        return load(path, anchors[name])

    setup = anchored(CASEFIX / 'setup.json')
    library = setup['lib2bit']
    require(library['commit'] == PIN and library['original_source']['sha256'] == UPSTREAM_SHA
            and library['original_source']['bytes'] == 23182, 'wrong pinned softMask source identity')
    rows, chr1_runs, chr1_case = [], None, None
    for corpus in CORPORA:
        archive_path = CASEFIX / 'archives' / (corpus + '.json')
        case = anchored(archive_path)
        require(case['schema'] == 'hw-region-2-casefix-archives-v1' and case['corpus'] == corpus, 'archive-case identity differs')
        metadata_path = CASEFIX / 'writer-metadata' / (corpus + '.json.gz')
        metadata_ref = case['writer_metadata']
        require(metadata_path.relative_to(ROOT).as_posix() in anchors
                and anchors[metadata_path.relative_to(ROOT).as_posix()] == metadata_ref['sha256'], 'metadata not bound by parent audit')
        meta = json.loads(gzip.decompress(read(metadata_path, metadata_ref['sha256'], metadata_ref['bytes'])), object_pairs_hook=unique)
        table = meta['archive']; length = table['length']
        require(integer(length, 1) and length == case['sequence']['bytes'] and meta['structural_check']['status'] == 'PASS'
                and meta['structural_check']['sha256'] == case['sequence']['sha256']
                and meta['structural_check']['case_preserved'] is True and table['sha256'] == case['formats']['twobit']['sha256']
                and table['bytes'] == case['formats']['twobit']['bytes'], 'metadata/archive/structural identity differs')
        starts, ends = valid_runs(table['mask_blocks'], length, corpus + ' mask')
        valid_runs(table['n_blocks'], length, corpus + ' N')
        rows.append(dict(corpus=corpus, sequence_bases=length, sequence_sha256=case['sequence']['sha256'],
            archive_sha256=table['sha256'], mask_blocks=len(starts), N_blocks=len(table['n_blocks']),
            masked_bases=sum(n for s, n in table['mask_blocks']), N_bases=sum(n for s, n in table['n_blocks']),
            mask_table_bytes=8 * len(starts), runs_sorted_positive_disjoint=True,
            archive_case=reference(archive_path), writer_metadata=reference(metadata_path)))
        if corpus == 'chr1':
            chr1_runs, chr1_case = (starts, ends), case
    windows = rows[1:]; ranked = sorted(windows, key=lambda r: (r['mask_blocks'], r['corpus']))
    median = Fraction(ranked[14]['mask_blocks'] + ranked[15]['mask_blocks'], 2)
    typical = dict(definition='arithmetic median of the 30 per-window interval counts; not a selected window',
        count=30, median=str(median), median_decimal=str(median.numerator / median.denominator),
        middle_two=[dict(corpus=r['corpus'], mask_blocks=r['mask_blocks']) for r in ranked[14:16]],
        min=ranked[0]['mask_blocks'], max=ranked[-1]['mask_blocks'],
        minimum_corpora=[r['corpus'] for r in windows if r['mask_blocks'] == ranked[0]['mask_blocks']],
        maximum_corpora=[r['corpus'] for r in windows if r['mask_blocks'] == ranked[-1]['mask_blocks']],
        chr1_count_to_median=str(Fraction(rows[0]['mask_blocks'], median)))
    trace_path = CASEFIX / 'traces/chr1.json'; trace = anchored(trace_path)
    require(reference(trace_path)['sha256'] == chr1_case['trace']['sha256'] and trace['corpus'] == 'chr1'
            and trace['request_bases'] == 16384 and trace['sequence_length'] == chr1_case['sequence']['bytes']
            and trace['resampled'] is False, 'wrong frozen chr1 coordinate trace')
    groups = {}
    for group, count in (('warmups', 12), ('requests', 1000)):
        item = trace[group]; offsets = item['offsets']
        require(len(offsets) == count and all(integer(s) and s + 16384 <= trace['sequence_length'] for s in offsets), 'invalid trace starts')
        raw = b''.join(struct.pack('<Q', s) for s in offsets)
        require(len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256'], 'frozen binary trace SHA differs')
        samples = [query_geometry(*chr1_runs, start, 16384, query) for query, start in enumerate(offsets)]
        groups[group] = dict(count=count, summary=geometry_summary(samples), rows=samples)
    result = dict(schema='hw-region-2-mask-counts-v1', status='PASS', saved_data_only=True, no_clocks=True,
        native_calls=0, query_calls=0, measurements_of_time=False, private_paths_required=False,
        parent_audit=reference(audit_path), source=reference(Path(__file__).resolve()), corpora=rows,
        mask_table_bytes_definition='8 bytes per stored interval (uint32 start and size); excludes other archive/index bytes and is not RSS',
        T2T=typical, chr1_static_geometry=dict(trace=reference(trace_path), request_bases=16384, groups=groups,
            quantile_definition='nearest rank: requests p50 index499 and p99 index989; these rank geometry counts, not latency',
            intervals='zero-based half-open [start,start+size); lower_bound finds first exclusive mask end > request start',
            linear_count='all body entries from index0 through first mask start>=request end, inclusive; no stopping entry if exhausted',
            binary_count='end comparisons in the documented lower_bound plus body entries after its returned index; not unique entries or CPU time'),
        mechanism_source=dict(upstream_commit=PIN, original_source_sha256=UPSTREAM_SHA,
            casefix_source_sha256=library['variants']['casefix']['source_sha256'],
            url='https://github.com/dpryan79/lib2bit/blob/' + PIN + '/2bit.c#L133',
            continue_predicate='blockEnd <= start', break_predicate='blockStart >= end',
            source_lookup='linear scan starts at index0; casefix only removes the skip-N guard from the lowercase loop'),
        limitations='Static interval geometry only: no elapsed-time attribution, causal percentage, cache simulation, codec execution or new forecast; original P1-P3 unchanged.')
    result['source_binding_base'] = 'repository'
    result['source_bindings'] = [dict(path=name, sha256=value) for name, value in sorted(BINDS.items())]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'mask-counts.json')
    args = parser.parse_args()
    result = build()
    output = args.output.resolve()
    require(output.parent == HERE.resolve() and output.suffix == '.json', 'output must be a JSON file in the new binary-search stage')
    output.write_bytes(packed(result))
    stats = result['chr1_static_geometry']['groups']['requests']['summary']
    print(json.dumps(dict(status=result['status'], output=str(output), chr1_mask_blocks=result['corpora'][0]['mask_blocks'],
        T2T_median=result['T2T']['median_decimal'], T2T_range=[result['T2T']['min'], result['T2T']['max']],
        request_geometry=stats), sort_keys=True))


if __name__ == '__main__':
    main()
