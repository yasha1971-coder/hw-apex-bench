#!/usr/bin/env python3
"""Complete local-window c(g) using verified one-whole-window baselines."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import zipfile
from sweep import ROOT, PRIOR, GRID, ace_geometry, zstd_geometry

E = ROOT / 'evidence/t2t-window-cg-20260916'
S = ROOT / 'evidence/t2t-granularity-20260916'
REPORT = ROOT / 'docs/RESULTS/T2T_WINDOW_CG_20260916.md'
GROUPS = ('centromeric_HOR', 'annotation_complement', 'telomere_context')
CODECS = ('aceapex', 'zstd-seekable')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_rows(path):
    return [json.loads(l) for l in path.read_text().splitlines()]


def calculate(bases):
    points = read_rows(S / 'results.jsonl')
    windows = json.loads((PRIOR / 'manifest.json').read_text())['windows']
    by = {(r['file'], r['codec']): r for r in bases}
    assert len(bases) == len(by) == 60
    assert set(by) == {(w['file'], c) for w in windows for c in CODECS}
    for w in windows:
        for c in CODECS:
            b = by[w['file'], c]
            assert all(b[k] == v for k, v in w.items())
            assert b['granularity'] == b['input_bytes'] == 2097152
            assert b['verified'] == 'byte-exact'
            assert b['ratio'] == b['input_bytes']/b['stored_bytes']
            if c == 'aceapex':
                assert b['geometry']['block_count'] == 1
                assert b['geometry']['metadata_bytes'] == 132
                assert b['geometry']['literal_chunk_bytes'] == 65536
            else:
                assert b['geometry']['indexed_frames'] == 2
                assert b['geometry']['empty_frames'] == 1
    derived = []
    for p in points:
        b = by[p['file'], p['codec']]
        assert p['input_sha256'] == b['input_sha256']
        assert p['codec'] in CODECS and p['granularity'] in GRID
        if p['codec'] == 'aceapex':
            assert p['geometry']['literal_chunk_bytes'] == b['geometry']['literal_chunk_bytes']
        value = 1 - b['stored_bytes']/p['stored_bytes']
        assert abs(value - (b['ratio']-p['ratio'])/b['ratio']) < 1e-12
        derived.append({'file': p['file'], 'chromosome': p['chromosome'],
                        'group': p['group'], 'codec': p['codec'], 'granularity': p['granularity'],
                        'input_sha256': p['input_sha256'], 'input_bytes': p['input_bytes'],
                        'point_bytes': p['stored_bytes'], 'baseline_bytes': b['stored_bytes'],
                        'point_archive_sha256': p['archive_sha256'],
                        'baseline_archive_sha256': b['archive_sha256'],
                        'c_g': value, 'unit': 'fraction', 'baseline_scope': 'one 2 MiB window'})
    assert len(derived) == 300
    summaries = []
    paired = []
    for c in CODECS:
        for g in sorted(GRID):
            for group in GROUPS:
                rs = [r for r in derived if (r['codec'], r['granularity'], r['group']) == (c, g, group)]
                assert len(rs) == 10
                baseline = sum(r['baseline_bytes'] for r in rs)
                point = sum(r['point_bytes'] for r in rs)
                summaries.append({'codec': c, 'granularity': g, 'group': group,
                                  'n_windows': 10, 'point_bytes': point, 'baseline_bytes': baseline,
                                  'c_g': 1-baseline/point,
                                  'per_window_min': min(r['c_g'] for r in rs),
                                  'per_window_median': statistics.median(r['c_g'] for r in rs),
                                  'per_window_max': max(r['c_g'] for r in rs)})
            h = {r['chromosome']: r['c_g'] for r in derived if (r['codec'], r['granularity'], r['group']) == (c, g, GROUPS[0])}
            control = {r['chromosome']: r['c_g'] for r in derived if (r['codec'], r['granularity'], r['group']) == (c, g, GROUPS[1])}
            delta = {chrom: h[chrom]-control[chrom] for chrom in h}
            paired.append({'codec': c, 'granularity': g, 'hor_minus_control': delta,
                           'positive_pairs': sum(v>0 for v in delta.values()),
                           'median_difference': statistics.median(delta.values()),
                           'min_difference': min(delta.values()), 'max_difference': max(delta.values())})
    return derived, summaries, paired


def report(summary, paired):
    lines = ['# T2T window-local c_window(g) — 2026-09-16', '',
             'A completed local curve, not a whole-T2T curve. Sixty new one-whole-window',
             'baselines complete the retained 300 measurements without rerunning them.',
             'Each baseline restores byte-exactly; a second encoding reproduced all 60 hashes.', '',
             '[c_window(g), distinct from historical c_file(g)](../CG_SCOPES.md), is ratio loss relative to one block covering the same 2 MiB window:',
             '`(ratio_whole - ratio_g) / ratio_whole = 1 - bytes_whole / bytes_g`.',
             'The aggregate uses sums of stored bytes, not mean per-window c(g).',
             'Its baseline is ten separate one-window archives, never a concatenated 20 MiB file.', '']
    for c in CODECS:
        lines += ['## '+c, '', '| g | HOR c_window(g) | Control c_window(g) | Terminal-context c_window(g) | HOR > control, paired |',
                  '|---|---:|---:|---:|---:|']
        for g in sorted(GRID):
            ss = [next(s for s in summary if (s['codec'],s['granularity'],s['group']) == (c,g,group)) for group in GROUPS]
            pp = next(p for p in paired if (p['codec'],p['granularity']) == (c,g))
            lines.append(f"| {g//1024} KiB | {100*ss[0]['c_g']:.3f}% | {100*ss[1]['c_g']:.3f}% | {100*ss[2]['c_g']:.3f}% | {pp['positive_pairs']}/10 |")
        lines += ['']
    lines += ['BGZF c(g): **n/a — no comparable single-parameter whole-window baseline**.',
              'Its verified fixed-block density comparison remains in the',
              '[granularity report](T2T_GRANULARITY_20260916.md); no synthetic BGZF baseline is used.', '',
              'BGZF blocks are 65,280 bytes; ACE at 64 KiB uses 65,536 bytes (0.392% larger).',
              'The comparison is close in granularity, not identical.', '',
              '## What this establishes', '',
              'See [HWB-001 (measured) and HWB-002 (mechanism unproven)](../CLAIM_LEDGER.md).', '',
              'Relative to its own one-window baseline, each tested codec loses substantially',
              'more density on these selected HOR windows at small blocks than on controls.',
              'This is a granularity penalty, not an absolute density weakness: ACEAPEX can',
              'beat BGZF around 64 KiB while still paying a large penalty relative to its own baseline.',
              'The local c(g) is not a latency, amplification or throughput measurement.', '',
              'The retained paired differences and per-window ranges matter: ten selected',
              'long-HOR autosomes do not establish a genome-wide effect size or significance.',
              'Negative individual values and nonmonotonicity are not clipped or smoothed.', '',
              '## Baseline audit', '',
              'Same binaries, input hashes, level and requested encoder threads as the sweep.',
              'ACEAPEX4915321: one 2 MiB LZ block, default level2, eight requested threads.',
              'LIT_CHUNK/FSE_CHUNK/MIN_MATCH remain unset. Every parsed ACE archive has',
              '64 KiB literal chunks on both sides; FSE defaults to512KiB in the pinned source.',
              'DNA/zstd decisions within chunks remain automatic. Only requested LZ block size changes.',
              'One LZ block is not one entropy chunk, and actual parallel work changes with block count.',
              'zstd1.5.7 reference seekable encoder: level3, one thread; one nonempty frame',
              'plus one terminal empty frame and seek table. Complete stored files are counted.',
              'Frame-size-induced internal parameter changes remain part of the operational curve.', '',
              '## Whole-T2T comparison: next gate, not a completed claim', '',
              'No matched whole-T2T curve exists in the retained evidence. The historical',
              'c(g) curve uses hg38 chr1 and ACEAPEXee5a37e, not T2T and4915321.',
              'Owner-provided whole-T2T CLI ratio is stream-only, not a complete-file c(g) baseline.', '',
              'Do not overlay these as one measured curve. Before a whole-T2T run:', '',
              '1. Fix representation: these windows contain bases only, case preserved;',
              '   FASTA headers/wrapping and cross-chromosome concatenation require explicit handling.',
              '2. Freeze the same codec commits, level, overrides, thread policy and five granularities.',
              '3. Verify whole-input single-block support and resource bounds before a full run.',
              '   ACE uses a32-bit block-size header and source-size-dependent hash sizing;',
              '   inspect offset/length limits and memory, not just environment acceptance.',
              '4. Retain complete-file sizes and byte-exact restores; do not substitute CLI stream ratios.',
              '5. Treat genome-vs-window differences as scale/composition effects as well as locality.',
              '   A size-matched representative-window stratum is cleaner for region attribution.', '',
              'Recommended next experiment: preregister a uniformly sampled, length-matched',
              'T2T window stratum (including repeats rather than annotation-excluded controls),',
              'then compare local curves. Keep full-FASTA operational c(g) separate.',
              'No additional windows or whole-genome measurements were run in this stage.', '',
              '## Evidence', '',
              '[Baselines](../../evidence/t2t-window-cg-20260916/baselines.jsonl) ·',
              '[300 derived points](../../evidence/t2t-window-cg-20260916/derived.jsonl) ·',
              '[Summary and paired differences](../../evidence/t2t-window-cg-20260916/summary.json) ·',
              '[Audit](../../evidence/t2t-window-cg-20260916/audit.json) ·',
              '[Reproduction](../../review/t2t_regions/README.md).', '',
              'The historical435 records, prior pilot/sweep, DOI and tag remain unchanged.',
              'Generated and verified with review/t2t_regions/window_cg.py.', '']
    return '\n'.join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--baseline-dir', type=Path)
    p.add_argument('--repeat-dir', type=Path)
    p.add_argument('--bundle', type=Path)
    p.add_argument('--verify', action='store_true')
    a = p.parse_args()
    if a.verify:
        bases = read_rows(E/'baselines.jsonl')
    else:
        assert a.baseline_dir and a.repeat_dir and a.bundle
        bases = read_rows(a.baseline_dir/'results.jsonl')
        repeated = {(r['file'],r['codec']): r for r in read_rows(a.repeat_dir/'results.jsonl')}
        original_prov = json.loads((S/'provenance.json').read_text())
        prov = json.loads((a.baseline_dir/'provenance.json').read_text())
        repeat_prov = json.loads((a.repeat_dir/'provenance.json').read_text())
        for k in ('binary_sha256','pins','manifest_sha256','ace_threads','ace_level','zstd_threads','zstd_level','libzstd','other_ace_overrides'):
            assert prov[k] == original_prov[k] == repeat_prov[k], k
        for b in bases:
            r = repeated[b['file'],b['codec']]
            assert b['archive_sha256'] == r['archive_sha256'] and b['stored_bytes'] == r['stored_bytes']
            for root, row in ((a.baseline_dir,b),(a.repeat_dir,r)):
                data = (root/row['archive']).read_bytes()
                assert sha(data) == row['archive_sha256'] and len(data) == row['stored_bytes']
                parse = ace_geometry if row['codec']=='aceapex' else zstd_geometry
                assert parse(data,2097152,2097152) == row['geometry']
                assert sha((root/row['log']).read_bytes()) == row['log_sha256']
    derived, summary, paired = calculate(bases)
    outputs = {'derived.jsonl': ''.join(json.dumps(r,sort_keys=True)+'\n' for r in derived),
               'summary.json': json.dumps({'groups':summary,'paired_hor_control':paired},indent=2)+'\n'}
    if a.verify:
        for name, content in outputs.items():
            assert (E/name).read_text() == content
        assert REPORT.read_text() == report(summary,paired)
        for b in bases:
            assert sha((E/'logs'/b['log']).read_bytes()) == b['log_sha256']
        if a.bundle:
            audit = json.loads((E/'audit.json').read_text())
            assert sha(a.bundle.read_bytes()) == audit['bundle_sha256']
            with zipfile.ZipFile(a.bundle) as z:
                assert z.testzip() is None
                for b in bases:
                    data = z.read('measurement/'+b['archive'])
                    assert sha(data)==b['archive_sha256'] and len(data)==b['stored_bytes']
        print('PASS: 60 baseline identities/logs; 300 c(g) points; 30 summaries; 100 paired differences; generated report')
        return
    E.mkdir(exist_ok=False)
    (E/'logs').mkdir()
    shutil.copyfile(a.baseline_dir/'results.jsonl',E/'baselines.jsonl')
    shutil.copyfile(a.baseline_dir/'provenance.json',E/'provenance.json')
    for b in bases:
        shutil.copyfile(a.baseline_dir/b['log'],E/'logs'/b['log'])
    for name,content in outputs.items():
        (E/name).write_text(content)
    REPORT.write_text(report(summary,paired))
    with zipfile.ZipFile(a.bundle,'x',compression=zipfile.ZIP_STORED) as z:
        for b in bases:
            z.write(a.baseline_dir/b['archive'],'measurement/'+b['archive'])
    audit = {'baseline_count':60,'byte_exact_restores_per_run':60,'independent_repeat_hash_matches':60,
             'prior_sweep_sha256':sha((S/'results.jsonl').read_bytes()),
             'repeat_results_sha256':sha((a.repeat_dir/'results.jsonl').read_bytes()),
             'accepted_results_sha256':sha((E/'baselines.jsonl').read_bytes()),
             'bundle_filename':a.bundle.name,'bundle_bytes':a.bundle.stat().st_size,
             'bundle_sha256':sha(a.bundle.read_bytes()),'whole_T2T_measured':False,
             'baseline_scope':'one block/frame per same frozen 2 MiB window',
             'bgzf_cg':'n/a — no comparable single-parameter whole-window baseline'}
    (E/'audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps(audit))


if __name__ == '__main__':
    main()
