#!/usr/bin/env python3
"""Before a re-measurement without rebuild: every file referenced by the N10 plans must still have the SHA-256
and size recorded in the plans, and agree with its build record (MANIFEST rr3 SHA, BGZF/zstd build receipts,
AGC creation receipts, v1.1 truth identity of the materialised FASTA, library receipts). Prints a JSON report;
exits 1 on any mismatch. Usage: check_inputs.py DATA_ROOT"""
import hashlib, json, sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
here = Path(__file__).resolve().parent


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def refs(v):
    if isinstance(v, dict):
        if set(v) == {'path', 'bytes', 'sha256'}:
            yield v
        else:
            for x in v.values():
                yield from refs(x)
    elif isinstance(v, list):
        for x in v:
            yield from refs(x)


bad, seen = [], {}
for plan in sorted((root / 'plans').glob('*.json')):
    for r in refs(json.loads(plan.read_text())):
        seen.setdefault(r['path'], r)
for path, r in sorted(seen.items()):
    p = root / path
    if not p.is_file() or p.stat().st_size != r['bytes'] or sha(p) != r['sha256']:
        bad.append(('plan-ref', path))
records = []
sel = {l.split('\t')[1]: l.split('\t') for l in (here / 'inputs/selection_n10.tsv').read_text().splitlines()[1:]}
for aid, cols in sel.items():
    for q, i in (('q4k', 8), ('q16k', 10)):
        records.append((f'rr3/{aid}.{q}.rr3', cols[i], 'MANIFEST'))
prepared = json.loads((root / 'prepared-v11/prepared.json').read_text())
for a in prepared['assemblies']:
    records.append((f"fa/{a['assembly_id']}.fa", a['truth']['uncompressed_sha256'], 'prepared truth v1.1'))
for b in sorted((root / 'bgzf').glob('*.build.json')):
    for art in json.loads(b.read_text())['artifacts']:
        records.append(('bgzf/' + art['path'], art['sha256'], b.name))
for z in sorted((root / 'zstd').glob('*.build.json')):
    d = json.loads(z.read_text())
    if 'archive' in d:
        records.append((d['archive']['path'], d['archive']['sha256'], z.name))
        records.append((d['contig_map']['path'], d['contig_map']['sha256'], z.name))
for mode in ('t2t', 'noref'):
    d = json.loads((root / 'agc' / f'{mode}_10.receipt.json').read_text())
    records.append((f'agc/{mode}_10.agc', d['archive_sha256'], f'{mode}_10.receipt.json'))
    records.append(('lib/libhwa_agc.so', d['library_sha256'], f'{mode}_10.receipt.json'))
for lib in ('libhwa_refrel3.so', 'libhwa_bgzf.so', 'libhwa_zstd_seekable.so'):
    records.append((f'lib/{lib}', json.loads((root / 'lib' / (lib + '.receipt.json')).read_text())['library_sha256'],
                    lib + '.receipt.json'))
for path, want, source in records:
    p = root / path
    got = seen[path]['sha256'] if path in seen else (sha(p) if p.is_file() else None)
    if got != want:
        bad.append(('build-record', path, source))
print(json.dumps({'plan_refs_checked': len(seen), 'build_records_checked': len(records),
                  'mismatches': bad, 'status': 'PASS' if not bad else 'FAIL'}, indent=1))
sys.exit(1 if bad else 0)
