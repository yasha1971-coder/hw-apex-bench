# SPDX-License-Identifier: Apache-2.0
"""Render the separately audited reader addition from saved evidence only."""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASEFIX = HERE.parent / 'casefix'
FROZEN = 'd8a77912bade66ce03d665e3afc5cd76465dcbb5'
LABEL = 'lib2bit-casefix + binary search (reader change, not upstream)'
SIG = "[written by ChatGPT (AI) at the author's request; checked by the author]"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def ref(path):
    return dict(path=Path(path).relative_to(ROOT).as_posix(), sha256=sha(path))


def median(values):
    values = sorted(values)
    middle = len(values) // 2
    return Fraction(values[middle]) if len(values) % 2 else Fraction(values[middle-1] + values[middle], 2)


def number(value):
    value = Fraction(value)
    return str(value.numerator) if value.denominator == 1 else str(float(value))


def write(path, value):
    Path(path).write_text(value, encoding='utf-8', newline='\n')


def build():
    audit_path = HERE / 'audit.json'
    audit = load(audit_path)
    require(audit['status'] == 'PASS', 'independent complete audit required')
    bindings = audit['source_bindings']
    if isinstance(bindings, dict):
        bindings = [dict(path=k, sha256=v) for k, v in bindings.items()]
    for record in bindings:
        path = (ROOT / record['path']).resolve()
        require(path.is_relative_to(ROOT) and sha(path) == record['sha256'], 'audited source changed: '+record['path'])
    old = load(CASEFIX / 'summary.json')
    require(old['status'] == 'COMPLETE' and len(old['rows']) == 186 and len(old['completed_corpora']) == 31,
            'original comparison must remain complete')
    require({k:v['verdict'] for k,v in old['forecasts'].items()} == {'P1':'HIT','P2':'MISS','P3':'HIT'}
            and old['forecasts']['P3']['wins'] == 30, 'registered forecasts changed')
    row = audit['main']
    require(row['label'] == LABEL and row['corpus'] == 'chr1' and row['stored_bytes'] == 64895635,
            'unexpected supplementary row')
    forecast = audit['B1']
    verdict = 'HIT' if 4*row['p50_ns'] <= 88965 else 'MISS'
    require(forecast['verdict'] == verdict, 'separate forecast verdict differs')
    counts = load(HERE / 'mask-counts.json')
    require(counts['status'] == 'PASS', 'mask geometry required')
    chr1 = next(r for r in counts['corpora'] if r['corpus'] == 'chr1')
    t2t = {}
    for profile in ('aceapex','zstd_seekable','bgzip','twobit_casefix_mask1'):
        rows = [r for r in old['rows'] if r['corpus'].startswith('t2t-') and r['profile'] == profile]
        require(len(rows) == 30, 'complete saved window set required')
        t2t[profile] = {field:number(median([r[field] for r in rows])) for field in ('stored_bytes','p50_ns','p99_ns')}
    summary = dict(schema='hw-region-2-binary-search-summary-v1', status='COMPLETE',
                   saved_data_only=True, no_clocks=True, no_codecs=True, date_label='2026-11-26',
                   renderer_sha256=sha(Path(__file__)), audit=ref(audit_path), original_summary=ref(CASEFIX/'summary.json'),
                   mask_counts=ref(HERE/'mask-counts.json'), main=row, B1=forecast,
                   original_forecasts=old['forecasts'], T2T_median_per_window=t2t,
                   counts=audit['counts'], AA=audit['AA'], boundary=audit['boundary'])
    write(HERE/'summary.json', json.dumps(summary,sort_keys=True,separators=(',',':'))+'\n')
    scope = ('ace-core AMD EPYC 4344P, CPU0, one timed thread; the identical archive and indexes warm in RAM/page cache. '
             'The original worker/native wrapper, compiler flags, chr1 reference, 12 warmups and 1000 offsets are retained. '
             'This reader addition was measured after the original grid; the two rows are separate clean passes, not interleaved pairs.')
    conclusion = ('On the measured chr1 workload, the .2bit latency penalty is driven by lib2bit\'s linear mask lookup, '
                  'not a requirement of the format; the T2T windows show the same format with much smaller mask tables.'
                  if verdict == 'HIT' else
                  'The linear lookup is present, but the separate reader result does not support the preregistered dominant-cost claim; '
                  'the observed workload and reader remain part of every .2bit timing.')
    paragraph = (f'On chr1, lib2bit-casefix/storeMasked=1 has p50 **88.965 µs**, versus **6.823 µs** with storeMasked=0 '
                 '(case-folded output, not equivalent). Pinned [softMask(), 2bit.c:139]('
                 'https://github.com/dpryan79/lib2bit/blob/58e20daa898a6fc338eae82e5d2ef7108d4fc07f/2bit.c#L133-L158) '
                 'starts its mask-table scan at index 0 for every query and skips ended blocks until the query; '
                 'its work therefore grows with the number of preceding mask blocks. '
                 f'The unchanged chr1 archive has **{chr1["mask_blocks"]:,}** mask blocks; the 30 T2T windows have '
                 f'median **{counts["T2T"]["median_decimal"]}**, range **{counts["T2T"]["min"]:,}–{counts["T2T"]["max"]:,}** '
                 '(middle windows: 7,994 and 9,025 blocks). Static replay of the frozen chr1 requests gives median '
                 '**184,885** old loop entries versus **43** search-plus-body inspections; these are operation counts, not timed components. '
                 f'The separate binary-search reader returns identical case-preserved bytes, with p50/p99 '
                 f'**{row["p50_ns"]/1000:.3f} / {row["p99_ns"]/1000:.3f} µs** and unchanged archive bytes. '+conclusion)
    primary = old['primary']
    table = ['| chr1 reader | Stored B incl. indexes | p50 / p99 µs |', '|---|---:|---:|']
    for profile in ('aceapex','zstd_seekable','bgzip','twobit_casefix_mask1'):
        r=primary[profile]
        table.append(f'| {r["label"]} | {r["stored_bytes"]} | {r["p50_ns"]/1000:.3f} / {r["p99_ns"]/1000:.3f} |')
    table.append(f'| {LABEL} | {row["stored_bytes"]} | {row["p50_ns"]/1000:.3f} / {row["p99_ns"]/1000:.3f} |')
    report = (SIG+'\n\n# HW-REGION-2: separate binary-search reader result\n\n'
              '## Why chr1 differs from the T2T windows\n\n'+paragraph+'\n\n'+scope+'\n\n'+'\n'.join(table)+'\n\n'
              'P1 **HIT**, P2 **MISS**, P3 **HIT (30/30)** remain evaluated on the original casefix row. '
              f'Separate B1: `4 × {row["p50_ns"]} ≤ 88965` — **{verdict}**. '
              'No original CLEAN cell or T2T timing was repeated. All new attempts, including LOADED, are retained.\n\n'
              'The ordinary casefix adapter remains unchanged. The lower_bound patch is reader development, not an upstream lib2bit release. '
              'A/A and the unchanged fresh-handle mask-boundary control passed; byte equality passed before and during timing. '
              'Open time is n=1 and peak RSS is whole-process, including preparation/capture buffers. '
              'These finite sampled observations do not establish cross-host speed or a format-only latency constant.\n\n'
              '[Calibration](CALIBRATION.md) · [Protocol](PROTOCOL.md) · [Patch](lib2bit-binary-search.patch) · '
              '[Raw-data audit](audit.json) · [Mask counts and static replay](mask-counts.json) · '
              '[Machine-readable result](summary.json) · [Original complete comparison](../casefix/RESULTS.md).\n')
    write(HERE/'RESULTS.md', report)
    original = subprocess.check_output(['git','-C',str(ROOT),'show',FROZEN+':evidence/hw-region-2/RESULTS.md']).decode('utf-8')
    marker='## Owner-authorized continuation'
    require(original.count(marker)==1, 'original report structure changed')
    addition=('## Why chr1 differs from the T2T windows\n\n'+paragraph+'\n\n'
              '[Separately preregistered reader addition, method checks and raw audit](binary-search/RESULTS.md). '
              f'B1 **{verdict}**; the supplementary row below is excluded from original P1-P3.\n\n')
    updated=original.replace(marker,addition+marker)
    updated=updated.replace('All 31 corpora / 186 main rows passed the resumed saved-data audit;',
                            'All 31 corpora / 186 registered main rows passed the resumed saved-data audit; one supplementary chr1 reader row is separately audited;')
    lines=updated.splitlines()
    indices=[i for i,line in enumerate(lines) if line.startswith('| chr1 | lib2bit-casefix (storeMasked=1) |')]
    require(len(indices)==1, 'original chr1 casefix row missing/duplicated')
    lines.insert(indices[0]+1,f'| chr1 | {LABEL} | {row["stored_bytes"]} | {row["p50_ns"]/1000:.3f} | {row["p99_ns"]/1000:.3f} | {row["open_ns"]/1000:.3f} | {row["open_rss_delta_kib"]} | {row["peak_process_rss_kib"]} |')
    write(HERE.parent/'RESULTS.md','\n'.join(lines)+'\n')
    return dict(status='COMPLETE', B1=verdict, p50_ns=row['p50_ns'], p99_ns=row['p99_ns'], original_forecasts='P1 HIT / P2 MISS / P3 HIT (30/30)')


if __name__ == '__main__':
    print(json.dumps(build(),sort_keys=True))
