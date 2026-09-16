#!/usr/bin/env python3
"""Validate frozen-window sweep artifacts and generate a standalone report."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from sweep import ROOT, PRIOR, GRID, ace_geometry, zstd_geometry


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--measurement', type=Path, required=True)
    p.add_argument('--inputs', type=Path, required=True)
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--report-only', action='store_true')
    a = p.parse_args()
    dest = ROOT / 'evidence/t2t-granularity-20260916'
    rows = [json.loads(l) for l in (a.measurement / 'results.jsonl').read_text().splitlines()]
    windows = json.loads((PRIOR / 'manifest.json').read_text())['windows']
    old = {(r['file'], r['codec']): r for r in
           map(json.loads, (PRIOR / 'results.jsonl').read_text().splitlines())}
    assert len(rows) == 300
    expected = {(w['file'], codec, g) for w in windows
                for codec in ('aceapex', 'zstd-seekable') for g in GRID}
    assert {(r['file'], r['codec'], r['granularity']) for r in rows} == expected
    by_file = {w['file']: w for w in windows}
    for w in windows:
        raw = (a.inputs / w['file']).read_bytes()
        assert len(raw) == 2097152 and sha(raw) == w['input_sha256']
    for r in rows:
        assert all(r[k] == v for k, v in by_file[r['file']].items())
        assert r['input_bytes'] == 2097152 and r['verified'] == 'byte-exact'
        data = (a.measurement / r['archive']).read_bytes()
        assert len(data) == r['stored_bytes'] and sha(data) == r['archive_sha256']
        assert r['ratio'] == r['input_bytes'] / len(data)
        geom = ace_geometry(data, r['input_bytes'], r['granularity']) if r['codec'] == 'aceapex' else zstd_geometry(data, r['input_bytes'], r['granularity'])
        assert geom == r['geometry']
        assert sha((a.measurement / r['log']).read_bytes()) == r['log_sha256']
        assert r['bgzf_reference_bytes'] == old[r['file'], 'bgzip']['stored_bytes']
        if r['granularity'] == 16384:
            prior = next(iter(old[r['file'], r['codec']]['archive_artifacts'].values()))
            assert prior == {'bytes': len(data), 'sha256': sha(data)}
    summary = []
    groups = ('centromeric_HOR', 'telomere_context', 'annotation_complement')
    for group in groups:
        for g in sorted(GRID):
            for codec in ('aceapex', 'zstd-seekable'):
                rs = [r for r in rows if (r['group'], r['granularity'], r['codec']) == (group, g, codec)]
                assert len(rs) == 10
                total = sum(r['stored_bytes'] for r in rs)
                base = sum(r['bgzf_reference_bytes'] for r in rs)
                rec = {'group': group, 'granularity': g, 'codec': codec,
                       'input_bytes': 10 * 2097152, 'stored_bytes': total,
                       'ratio': 10 * 2097152 / total,
                       'bgzf_ratio': 10 * 2097152 / base,
                       'archive_size_vs_bgzf': total / base,
                       'wins_vs_bgzf': sum(r['stored_bytes'] < r['bgzf_reference_bytes'] for r in rs)}
                if codec == 'aceapex':
                    meta = sum(r['geometry']['metadata_bytes'] for r in rs)
                    rec.update(metadata_bytes=meta, metadata_fraction=meta / total,
                               stream_bytes=total-meta)
                else:
                    rec.update(seek_table_bytes=sum(r['geometry']['seek_table_bytes'] for r in rs),
                               empty_frames=sum(r['geometry']['empty_frames'] for r in rs),
                               empty_frame_bytes=sum(r['geometry']['empty_frame_bytes'] for r in rs))
                summary.append(rec)
    get = lambda group, g, c: next(r for r in summary if (r['group'], r['granularity'], r['codec']) == (group, g, c))
    lines = ['# T2T frozen-window granularity sweep — 2026-09-16', '',
             '300 complete archives restored byte-exactly. All 60 archives at 16 KiB',
             'reproduce the earlier pilot byte-for-byte (SHA-256). No timing claims.', '',
             'The same thirty 2 MiB sequences are used at every size: ten annotated HOR',
             'windows, ten telomere-context windows and ten annotation-complement controls.',
             'Ratio is total input bytes / total stored bytes, not a mean of window ratios.',
             'BGZF is the fixed verified baseline from the previous pilot, including .gzi.', '']
    for group in groups:
        lines += ['## ' + group, '',
                  '| Block / frame | ACEAPEX ratio | zstd-seekable ratio | BGZF ratio (fixed) | ACE size vs BGZF | zstd size vs BGZF | ACE / zstd wins vs BGZF |',
                  '|---|---:|---:|---:|---:|---:|---:|']
        for g in sorted(GRID):
            x, z = get(group, g, 'aceapex'), get(group, g, 'zstd-seekable')
            lines += [f"| {g//1024} KiB | {x['ratio']:.3f} | {z['ratio']:.3f} | {x['bgzf_ratio']:.3f} | {100*(x['archive_size_vs_bgzf']-1):+.1f}% | {100*(z['archive_size_vs_bgzf']-1):+.1f}% | {x['wins_vs_bgzf']}/10 / {z['wins_vs_bgzf']}/10 |"]
        lines += ['']
    lines += ['## Exact ACEAPEX size accounting', '',
              'The format stores 68 header bytes plus 64 bytes per block. All remain',
              'in the reported ratio. “Streams” below means all four compressed streams;',
              'it is not a metadata-free payload comparable to another codec.', '',
              '| Block | Header + table / window | HOR metadata share | Control metadata share |',
              '|---|---:|---:|---:|']
    for g in sorted(GRID):
        h, c = get(groups[0], g, 'aceapex'), get(groups[2], g, 'aceapex')
        lines += [f"| {g//1024} KiB | {h['metadata_bytes']//10:,} B | {100*h['metadata_fraction']:.2f}% | {100*c['metadata_fraction']:.2f}% |"]
    x, y = get(groups[0], 16384, 'aceapex'), get(groups[0], 1048576, 'aceapex')
    saved = x['stored_bytes'] - y['stored_bytes']
    m = x['metadata_bytes'] - y['metadata_bytes']
    s = x['stream_bytes'] - y['stream_bytes']
    assert saved == m+s
    lines += ['', f'Across the ten HOR archives, moving from 16 KiB to 1 MiB saves {saved:,} bytes:',
              f'{m:,} bytes ({100*m/saved:.1f}%) from header/block-table accounting and',
              f'{s:,} bytes ({100*s/saved:.1f}%) from smaller compressed streams.', '',
              'At 16 KiB, even removing the entire header/table counterfactually leaves',
              f"ACE streams {100*(x['stream_bytes']/(x['stored_bytes']/x['archive_size_vs_bgzf'])-1):.1f}% larger than the complete BGZF baseline.",
              'This is a diagnostic accounting exercise, not a valid stripped-archive ratio.', '',
              'Metadata has a larger archive share on highly compressible inputs, not on',
              'poorly compressible inputs. Its input-byte fraction is fixed at a given block size.', '',
              '## Interpretation and limits', '',
              'At comparable approximately 64 KiB granularity, ACEAPEX has a 31.5%',
              'higher aggregate ratio than BGZF (54.721 vs 41.617), equivalent to a',
              '23.9% smaller complete stored representation, and wins on all ten HOR windows.',
              'ACEAPEX also has a higher aggregate ratio than zstd-seekable at each of',
              'the five tested granularities. These are density results on selected windows.', '',
              'The [BGZF specification](https://samtools.github.io/hts-specs/SAMv1.pdf)',
              'limits both compressed blocks and uncompressed contents to 65,536 bytes;',
              'it does not require fixed 64 KiB uncompressed blocks. Inspection of all',
              '30 actual baseline archives found 32 blocks of 65,280 bytes, an 8,192-byte',
              'tail and an empty EOF block per archive. ACE uses 65,536-byte blocks',
              '(0.392% larger). Thus granularity is comparable, not exactly matched.',
              'See the [block audit](../../evidence/t2t-granularity-20260916/bgzf-block-audit.json).', '',
              'The earlier +30.3% archive-size loss remains true for ACE at 16 KiB',
              'against native BGZF; it is not a codec-intrinsic centromere weakness.',
              'Do not replace that configuration-specific result with the 64 KiB result,',
              'or infer that centromeric weaknesses do not exist under other settings.', '',
              'Both codecs gain much more density on these HOR windows than on controls',
              'when blocks grow. Both exceed the fixed BGZF aggregate ratio at 64 KiB.',
              'This supports sensitivity to block/frame granularity shared by these two',
              'implementations on this selected input, not a universal law of seekable formats.', '',
              'The gap is not explained solely by the ACE block table. Larger blocks change',
              'match opportunities and compressed-stream statistics as well as overhead.',
              'This experiment cannot assign the stream improvement solely to long-distance',
              'HOR matches. A repeat of a few thousand bases is not inherently excluded by',
              'a 16 KiB block; match distance and block boundaries matter.', '',
              'No region latency, amplification or throughput was measured. Higher density',
              'with larger blocks does not establish a better random-access trade-off.',
              'This is not c(g): no single-block 2 MiB baseline is included.', '',
              'These are ten selected long-HOR autosomes, not a genome-wide estimate.',
              'Terminal windows contain mostly adjacent context, not pure telomeric repeats.',
              'Controls are not GC matched. See the [original sampling limitations](T2T_REGIONS_20260916.md).', '',
              '## Configuration and reproduction', '',
              '- ACEAPEX `4915321bf118e564ef3883e58927992c7f9d8dc3`, default level 2,',
              '  eight encoder threads, only ACEAPEX_BS changes. No profile or explicit',
              '  LIT_CHUNK/FSE_CHUNK/MIN_MATCH; automatic policy retained. Linked zstd 1.5.7.',
              '- zstd-seekable `f8745da6ff1ad1e7bab384bd1f9d742439278e99`, level 3,',
              '  one encoder thread. Only frame size changes. Complete seek table and',
              '  the reference encoder’s trailing empty frame remain included at every size.',
              '- BGZF: unchanged htslib 1.19 / libdeflate 1.19, level 6, eight threads,',
              '  native block ceiling 65,280 bytes, .gzi included; not a swept parameter.', '',
              'Each result retains commands, input/archive/log hashes, block/frame counts',
              'and archive decomposition. Build the original pinned dependencies, recover',
              'the frozen inputs, then use the [sweep instructions](../../review/t2t_regions/README.md).', '',
              '[300 rows](../../evidence/t2t-granularity-20260916/results.jsonl) ·',
              '[provenance](../../evidence/t2t-granularity-20260916/provenance.json) ·',
              '[summary](../../evidence/t2t-granularity-20260916/summary.json) ·',
              '[archive receipt](../../evidence/t2t-granularity-20260916/archive-bundle.json).', '',
              'The original 435 records, earlier 90 pilot records, DOI and release tag are unchanged.',
              'Generated by review/t2t_regions/summarize_sweep.py.', '']
    if a.report_only:
        (ROOT / 'docs/RESULTS/T2T_GRANULARITY_20260916.md').write_text('\n'.join(lines))
        print('Report regenerated; numerical evidence unchanged')
        return
    # Only copy validated evidence; original pilot files are never rewritten.
    dest.mkdir(exist_ok=True)
    (dest / 'logs').mkdir(exist_ok=True)
    for name in ('results.jsonl', 'provenance.json'):
        shutil.copyfile(a.measurement / name, dest / name)
    for r in rows:
        shutil.copyfile(a.measurement / r['log'], dest / 'logs' / r['log'])
    (dest / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (ROOT / 'docs/RESULTS/T2T_GRANULARITY_20260916.md').write_text('\n'.join(lines))
    with zipfile.ZipFile(a.bundle, 'x', compression=zipfile.ZIP_STORED) as z:
        for w in windows:
            z.write(a.inputs / w['file'], 'windows/' + w['file'])
        for r in rows:
            z.write(a.measurement / r['archive'], 'measurement/' + r['archive'])
    with zipfile.ZipFile(a.bundle) as z:
        assert z.testzip() is None
        for r in rows:
            assert sha(z.read('measurement/' + r['archive'])) == r['archive_sha256']
    receipt = {'filename': a.bundle.name, 'bytes': a.bundle.stat().st_size,
               'sha256': sha(a.bundle.read_bytes()), 'archives': 300, 'inputs': 30,
               'restores': 300, 'historical_byte_identical_archives': 60}
    (dest / 'archive-bundle.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
