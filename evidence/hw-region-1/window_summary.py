"""Exact saved-data window counts/density summaries; no codecs or clocks.

The old all-stage audit remains unchanged. This posthoc descriptive summary
records its own source and every case SHA; it introduces no forecast or fit.
"""
import argparse
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GRIDS = (4096, 16384, 65536)
CODECS = ('aceapex', 'zstd_seekable', 'bgzip')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def unique(pairs):
    result = {}
    for key, item in pairs:
        require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = item
    return result


def load(path):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


class Saved:
    def __init__(self, audit_path):
        path = Path(audit_path).resolve()
        require(path.is_relative_to((HERE / 'audit').resolve()), 'audit escaped this study')
        self.audit = load(path)
        require(self.audit.get('schema') == 'hw-region-1-independent-audit-v1'
                and self.audit.get('status') == 'PASS' and self.audit.get('stage') == 'all'
                and self.audit.get('saved_data_only') is True and self.audit.get('no_codecs') is True
                and self.audit.get('no_clocks') is True and self.audit.get('private_artifacts_unavailable') == 0
                and self.audit.get('private_bytes_verified_on_this_host') is True, 'complete original all-stage PASS required')
        self.bindings = {}
        for item in self.audit['source_bindings']:
            name, digest = item['path'], item['sha256']
            source = (HERE / name).resolve()
            require(source.is_relative_to(ROOT.resolve()) and not source.is_relative_to((ROOT / '.work').resolve()), 'audit binding escaped public repository')
            require(name not in self.bindings and sha(source) == digest, 'original audit source closure changed: ' + name)
            self.bindings[name] = digest
        require(self.bindings and self.audit['counts']['logical_units'] == 292, 'incomplete original numerical run')
        self.audit_reference = dict(path=path.relative_to(HERE).as_posix(), sha256=sha(path))

    def document(self, name):
        path = (HERE / name).resolve()
        require(path.is_relative_to(HERE.resolve()) and self.bindings.get(name) == sha(path), 'unbound numerical input: ' + name)
        return load(path)

    def reference(self, record):
        require(set(record) == {'path', 'sha256'} and self.bindings.get(record['path']) == record['sha256'], 'invalid/unbound numerical reference')
        return self.document(record['path'])


def fraction_median(values):
    values = sorted(values)
    require(values, 'empty median')
    n = len(values)
    return values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2


def exact_stats(entries):
    """Entries retain window IDs; all summaries use rational arithmetic."""
    ordered = sorted(entries, key=lambda row: (Fraction(row['ratio']), row['case_id']))
    if not ordered:
        return dict(count=0, minimum=None, maximum=None, mean=None, median=None, by_ratio=[])
    values = [Fraction(row['ratio']) for row in ordered]
    return dict(count=len(values), minimum=str(values[0]), maximum=str(values[-1]),
                mean=str(sum(values, Fraction(0)) / len(values)), median=str(fraction_median(values)), by_ratio=ordered)


def read_case(saved, name):
    path = 'cases/' + name + '.json'
    value = saved.document(path)
    require(value['schema'] == 'hw-region-1-case-v1' and value['status'] == 'COMPLETE'
            and value['case_id'] == name and set(value['formats']) == set(CODECS), 'incomplete saved case: ' + name)
    archives = saved.reference(value['archives'])
    require(archives['case_id'] == name and archives['corpus'] == value['corpus'] and archives['g'] == value['g'], 'case/archive coordinate differs')
    for codec in CODECS:
        item, artifact = value['formats'][codec], archives['formats'][codec]
        require(type(item['p50_ns']) is int and item['p50_ns'] > 0 and type(item['p99_ns']) is int and item['p99_ns'] > 0,
                'invalid integer latency summary')
        require(item['stored_bytes'] == artifact['bytes'] + sum(index['bytes'] for index in artifact['indexes']) == artifact['stored_bytes']
                and item['input_bytes'] == archives['input']['bytes']
                and Fraction(item['ratio']) == Fraction(item['input_bytes'], item['stored_bytes']), 'complete density accounting differs')
    return value, dict(path=path, sha256=saved.bindings[path])


def summarize_grid(cases, g):
    require(len(cases) == 30 and {value['corpus'] for value in cases} == {f't2t-{i:02d}' for i in range(30)}
            and all(value['g'] == g and all(item['input_bytes'] == 2097152 for item in value['formats'].values()) for value in cases), 'exact frozen 30-window grid required')
    comparisons = (
        ('ace_p50_lt_zstd', lambda f: f['aceapex']['p50_ns'] < f['zstd_seekable']['p50_ns']),
        ('ace_p50_lt_bgzf', lambda f: f['aceapex']['p50_ns'] < f['bgzip']['p50_ns']),
        ('ace_p99_lt_zstd', lambda f: f['aceapex']['p99_ns'] < f['zstd_seekable']['p99_ns']),
        ('ace_stored_lt_zstd', lambda f: f['aceapex']['stored_bytes'] < f['zstd_seekable']['stored_bytes']))
    wins = {key: [value['case_id'] for value in cases if predicate(value['formats'])] for key, predicate in comparisons}
    slower = [value for value in cases if value['formats']['aceapex']['p50_ns'] > value['formats']['zstd_seekable']['p50_ns']]
    others = [value for value in cases if value['formats']['aceapex']['p50_ns'] <= value['formats']['zstd_seekable']['p50_ns']]
    ties = [value['case_id'] for value in cases if value['formats']['aceapex']['p50_ns'] == value['formats']['zstd_seekable']['p50_ns']]
    ratios = [dict(case_id=value['case_id'], ratio=str(Fraction(value['formats']['aceapex']['p50_ns'], value['formats']['zstd_seekable']['p50_ns']))) for value in cases]
    def group(values):
        return dict(case_ids=[value['case_id'] for value in values], count=len(values),
                    density={codec: exact_stats([dict(case_id=value['case_id'], ratio=str(Fraction(value['formats'][codec]['ratio']))) for value in values]) for codec in CODECS})
    slow_group, other_group = group(slower), group(others)
    sample = next(value for value in cases if value['corpus'] == 't2t-00')
    sample_ratio = Fraction(sample['formats']['aceapex']['ratio'])
    baseline = other_group['density']['aceapex']['median']
    slow_median = slow_group['density']['aceapex']['median']
    a, b = slow_group['density']['aceapex'], other_group['density']['aceapex']
    overlap = (bool(a['count'] and b['count']) and max(Fraction(a['minimum']), Fraction(b['minimum']))
               <= min(Fraction(a['maximum']), Fraction(b['maximum'])))
    return dict(g_bytes=g, windows=30, counts={key: len(ids) for key, ids in wins.items()}, winning_case_ids=wins,
        ace_zstd_p50_individual_ratios=ratios,
        mean_individual_ace_zstd_p50_ratio=str(sum((Fraction(row['ratio']) for row in ratios), Fraction(0)) / 30),
        density_groups=dict(slow_definition='ACE p50 > zstd p50 (strict)', other_definition='ACE p50 <= zstd p50; ties retained',
                            ties=ties, slow=slow_group, other=other_group, ace_density_ranges_overlap=overlap),
        t2t00=dict(case_id=sample['case_id'], slow=sample in slower, ace_density_ratio=str(sample_ratio),
                   other_ace_density_median=baseline, slow_ace_density_median=slow_median,
                   above_other_density_median=baseline is not None and sample_ratio > Fraction(baseline),
                   slow_group_median_above_other=baseline is not None and slow_median is not None and Fraction(slow_median) > Fraction(baseline)))


def build(saved):
    grids, case_bindings = [], []
    for g in GRIDS:
        cases = []
        for index in range(30):
            value, reference = read_case(saved, f't2t-{index:02d}-g{g}')
            require(value['corpus'] == f't2t-{index:02d}' and value['g'] == g, 'window coordinate differs')
            cases.append(value)
            case_bindings.append(reference)
        grids.append(summarize_grid(cases, g))
    references = {}
    reference_bindings = []
    for corpus in ('enwik8', 'silesia'):
        case, reference = read_case(saved, corpus + '-g16384')
        require(case['corpus'] == corpus and case['g'] == 16384, 'reference scope differs')
        formats = case['formats']
        references[corpus] = dict(case=reference, g_bytes=16384,
            ace_zstd_p50_ratio=str(Fraction(formats['aceapex']['p50_ns'], formats['zstd_seekable']['p50_ns'])),
            formats={codec: dict(p50_ns=formats[codec]['p50_ns'], p99_ns=formats[codec]['p99_ns'],
                                stored_bytes=formats[codec]['stored_bytes'], density_ratio=str(Fraction(formats[codec]['ratio']))) for codec in CODECS})
        reference_bindings.append(reference)
    return dict(schema='hw-region-1-window-summary-v1', status='PASS', saved_data_only=True, no_codecs=True, no_clocks=True,
        new_measurements=0, posthoc_descriptive=True, source_sha256=sha(__file__), final_audit=saved.audit_reference,
        final_audit_source_closure_sha256=hashlib.sha256(packed(saved.audit['source_bindings'])).hexdigest(),
        case_source_bindings=case_bindings, reference_source_bindings=reference_bindings,
        definitions=dict(strict_comparisons=True, latency_mean='arithmetic mean of 30 individual Fraction(ACE p50, zstd p50); not ratio of sums',
            density='input bytes / complete stored bytes including required indexes', median='mean of central two for even groups',
            groups='defined by saved ACE p50 versus zstd p50 at that g, not by density',
            inference='descriptive fixed-window group comparison; no causal or statistical significance test'),
        grids=grids, references=references)


def decimal(value, places=6):
    value = Fraction(value)
    with localcontext() as ctx:
        ctx.prec = 60
        return format(Decimal(value.numerator) / Decimal(value.denominator), '.' + str(places) + 'f')


def render(summary):
    require(summary['schema'] == 'hw-region-1-window-summary-v1' and summary['status'] == 'PASS'
            and [row['g_bytes'] for row in summary['grids']] == list(GRIDS), 'complete three-grid summary required')
    lines = ['| g B | ACE p50 < zstd /30 | ACE p50 < BGZF /30 | ACE p99 < zstd /30 | ACE stored < zstd /30 | Mean of 30 individual ACE/zstd p50 ratios | Slow / other n | ACE density median, slow / other |',
             '|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in summary['grids']:
        count = row['counts'];groups = row['density_groups']
        slow, other = groups['slow']['density']['aceapex']['median'], groups['other']['density']['aceapex']['median']
        lines.append('| ' + ' | '.join((str(row['g_bytes']), str(count['ace_p50_lt_zstd']), str(count['ace_p50_lt_bgzf']),
            str(count['ace_p99_lt_zstd']), str(count['ace_stored_lt_zstd']), decimal(row['mean_individual_ace_zstd_p50_ratio']),
            str(groups['slow']['count']) + ' / ' + str(groups['other']['count']),
            (decimal(slow) if slow is not None else 'n/a') + ' / ' + (decimal(other) if other is not None else 'n/a'))) + ' |')
    points = [row['t2t00'] for row in summary['grids']]
    slow_g = [str(g) for g, point in zip(GRIDS, points) if point['slow']]
    higher_g = [str(g) for g, point in zip(GRIDS, points) if point['slow_group_median_above_other']]
    overlap_g = [str(row['g_bytes']) for row in summary['grids'] if row['density_groups']['ace_density_ranges_overlap']]
    minority = all(row['density_groups']['slow']['count'] < row['density_groups']['other']['count'] for row in summary['grids'])
    sentence = ('t2t-00 is ' + ('a minority ' if minority else 'a ') + 'slower-than-zstd example at g=' + ('/'.join(slow_g) if slow_g else 'none')
                + ' B; slower groups have higher median ACE compression ratios at g=' + ('/'.join(higher_g) if higher_g else 'none')
                + ' B, but density ranges overlap at g=' + ('/'.join(overlap_g) if overlap_g else 'none')
                + ' B and this descriptive association does not establish a causal explanation.')
    return '\n'.join(lines) + '\n\n' + sentence + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, default=HERE / 'audit/final.json')
    parser.add_argument('--output', type=Path, default=HERE / 'window-summary.json')
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.is_relative_to(HERE.resolve()), 'summary output escaped experiment')
    summary = build(Saved(args.audit))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(packed(summary))
    print('WINDOW_SUMMARY_PASS', len(summary['case_source_bindings']), sha(output))
    print(render(summary), end='')


if __name__ == '__main__':
    main()
