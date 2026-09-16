#!/usr/bin/env python3
"""Check published sweep evidence; optionally verify its complete archive bundle."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile
from sweep import ROOT, PRIOR, GRID, ace_geometry, zstd_geometry

e = ROOT / 'evidence/t2t-granularity-20260916'
sha = lambda data: hashlib.sha256(data).hexdigest()
rows = [json.loads(l) for l in (e / 'results.jsonl').read_text().splitlines()]
windows = json.loads((PRIOR / 'manifest.json').read_text())['windows']
old = {(r['file'], r['codec']): r for r in map(json.loads, (PRIOR / 'results.jsonl').read_text().splitlines())}
assert len(rows) == 300
assert {(r['file'], r['codec'], r['granularity']) for r in rows} == {
    (w['file'], c, g) for w in windows for c in ('aceapex', 'zstd-seekable') for g in GRID}
for r in rows:
    w = next(w for w in windows if w['file'] == r['file'])
    assert all(r[k] == v for k, v in w.items())
    assert r['input_bytes'] == 2097152 and r['verified'] == 'byte-exact'
    assert r['ratio'] == r['input_bytes'] / r['stored_bytes']
    assert sha((e / 'logs' / r['log']).read_bytes()) == r['log_sha256']
    assert r['bgzf_reference_bytes'] == old[r['file'], 'bgzip']['stored_bytes']
    geo = r['geometry']
    if r['codec'] == 'aceapex':
        assert geo['header_bytes'] == 68
        assert geo['block_table_bytes'] == 64 * (2097152 // r['granularity'])
        assert geo['metadata_bytes'] == geo['header_bytes'] + geo['block_table_bytes']
        assert geo['stream_bytes'] == sum(geo['streams'].values())
        assert r['stored_bytes'] == geo['metadata_bytes'] + geo['stream_bytes']
    else:
        assert r['stored_bytes'] == geo['seek_table_bytes'] + geo['empty_frame_bytes'] + geo['nonempty_frame_bytes']
    if r['granularity'] == 16384:
        assert next(iter(old[r['file'], r['codec']]['archive_artifacts'].values())) == {
            'bytes': r['stored_bytes'], 'sha256': r['archive_sha256']}
summary = json.loads((e / 'summary.json').read_text())
assert len(summary) == 30
for s in summary:
    rs = [r for r in rows if all(r[k] == s[k] for k in ('group', 'granularity', 'codec'))]
    assert len(rs) == 10
    assert s['stored_bytes'] == sum(r['stored_bytes'] for r in rs)
    assert s['ratio'] == sum(r['input_bytes'] for r in rs) / s['stored_bytes']
    assert s['archive_size_vs_bgzf'] == s['stored_bytes'] / sum(r['bgzf_reference_bytes'] for r in rs)
if len(sys.argv) > 1:
    path = Path(sys.argv[1])
    receipt = json.loads((e / 'archive-bundle.json').read_text())
    assert sha(path.read_bytes()) == receipt['sha256'] and path.stat().st_size == receipt['bytes']
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        for w in windows:
            assert sha(z.read('windows/' + w['file'])) == w['input_sha256']
        for r in rows:
            data = z.read('measurement/' + r['archive'])
            assert len(data) == r['stored_bytes'] and sha(data) == r['archive_sha256']
            parse = ace_geometry if r['codec'] == 'aceapex' else zstd_geometry
            assert parse(data, r['input_bytes'], r['granularity']) == r['geometry']
print('PASS: 300 rows/logs, 30 aggregates, 60 historical archive matches' +
      ('; 300 bundled archives and 30 inputs verified' if len(sys.argv) > 1 else ''))
