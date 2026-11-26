"""Regenerate the saved-data report plus the owner's p99/fairness follow-up.

The original source-bound renderer and its numerical audit remain unchanged.
No codec, native operation, subprocess or clock is used here.
"""
import argparse
import hashlib
import json
from pathlib import Path

import report
import tail

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, default=HERE / 'audit/final.json')
    args = parser.parse_args()
    data = report.load_all(args.audit)
    summary_path = HERE / 'tail/summary.json'
    summary = report.load(summary_path)
    report.require(summary['status'] == 'PASS' and summary['no_new_measurements'] is True
                   and summary['source_sha256'] == sha(tail.__file__)
                   and summary['counts']['requests'] == 95000
                   and summary['counts']['exact_materialized_byte_matches'] == 95000,
                   'complete source-bound saved-only tail proof required')
    report.require(summary['final_audit']['sha256'] == sha(args.audit), 'tail audit parent changed')
    for name in ('requests', 'geometry'):
        item = summary[name]
        report.require(sha(HERE / item['path']) == item['sha256'], 'tail artifact differs: ' + name)
    standalone = (HERE / 'TAIL.md').read_text(encoding='utf-8')
    report.require(standalone == tail.tail_text(summary), 'tail Markdown differs from saved summary')
    report.require(standalone.splitlines()[0] == report.SIGNATURE, 'tail signature differs')
    setup, audit = data['setup'], data['audit']
    report.require('v1.5.7' in setup['deps']['zstd']['cli_version']
                   and setup['deps']['htslib']['cli_version'].splitlines()[0] == 'bgzip (htslib) 1.24',
                   'measured dependency versions differ')
    aa = []
    negative = []
    for codec in report.CODECS:
        method = audit['method'][codec]
        report.require(20 * abs(method['second_p50_ns'] - method['first_p50_ns']) < method['first_p50_ns'],
                       'strict A/A gate differs')
        aa.append(report.LABELS[codec] + ' ' + report.percent(method['relative_difference']))
        control = audit['controls']['codecs'][codec]
        a, b = control['aligned_materialized_bytes'], control['crossing_materialized_bytes']
        report.require(b > a, 'negative boundary control differs')
        negative.append(report.LABELS[codec] + ' ' + str(a) + '→' + str(b) + ' B')
    for case in data['cases'].values():
        trace_paths = {row['trace_path'] for row in data['rows'] if row['case_id'] == case['case_id']}
        report.require(len(trace_paths) == 1, 'formats do not share the saved request trace')
    base = report.render(data)
    fairness = ('## Comparison fairness — saved evidence\n\n'
                '**PASS.** zstd-seekable uses zstd **1.5.7**; BGZF uses HTSlib **1.24**. '
                'Each pass keeps one persistent C99 ACEAPEX handle, one `ZSTD_seekable`, or one `BGZF` handle. '
                'The same twelve warmups and 1000 saved offsets are shared by all three formats at every corpus/g; '
                'one pinned CPU0 and RAM-resident archives apply throughout. '
                'Strict A/A p50 differences: ' + '; '.join(aa) + ', all <5%. '
                'The negative control crosses an actual archive boundary with fresh handles and increases materialized bytes: '
                + '; '.join(negative) + '. These are the original saved controls, not new runs. '
                '[Audit](audit/final.json) · [Versions](setup.json) · [Persistent readers](native/build.json) · '
                '[A/A](method-check.json) · [Boundary controls](controls.json).\n\n')
    body = '\n'.join(standalone.splitlines()[2:])
    if body.startswith('# '):
        body = '#' + body
    result = base.rstrip() + '\n\n' + fairness + body.rstrip() + '\n'
    (HERE / 'RESULTS.md').write_bytes(result.encode('utf-8'))
    receipt = dict(schema='hw-region-1-followup-render-v1', status='PASS', saved_data_only=True,
                   measurements_repeated=False, source_sha256=sha(__file__),
                   numerical_renderer_sha256=sha(report.__file__), tail_renderer_sha256=sha(tail.__file__),
                   numerical_audit_sha256=sha(args.audit), tail_summary_sha256=sha(summary_path),
                   base_report_sha256=hashlib.sha256(base.encode('utf-8')).hexdigest(),
                   result_sha256=sha(HERE / 'RESULTS.md'), fairness='PASS')
    (HERE / 'followup-render.json').write_bytes((json.dumps(receipt, sort_keys=True, indent=2) + '\n').encode())
    print('FOLLOWUP_REPORT_PASS', receipt['result_sha256'])


if __name__ == '__main__':
    main()
