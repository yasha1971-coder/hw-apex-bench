#!/usr/bin/env python3
"""HWAB-ZEEK-1b: gates a-e, then (only if all pass) the three ratios per corpus and the zstd_seekable table."""
import json, sys
from pathlib import Path
M = Path('/tmp/hwref/z1/main'); OLD = Path('/home/aeterna/pubrepo/.wk/hwab-pick2/evidence/hwab-pick-2-20261105')
TOL = {(r['codec'], r['g']): r['tolerance'] for r in json.load(open('/tmp/hwref/z1/calib/gate-c-tolerance.json'))['rows']}
ok = True; out = []
def J(p): return json.load(open(p))
def p(s): out.append(s); print(s)

# a) default grid in the same run: 7 measured rows on silesia_tar and enwik8; same host as every series
hosts = set()
for f in ['default/silesia.tar', 'default/enwik8', 'r4K/silesia.tar', 'r4K/enwik8', 'r4K/t2t_chrX.fa', 'r64K/silesia.tar', 'r64K/enwik8', 'r64K/t2t_chrX.fa']:
    s = J(M / (f + '.silence.json')); hosts.add(s['snapshot']['host'])
a_ok = all(len([r for r in J(M / f'default/{c}/pick.json')['rows'] if r['status'] == 'measured']) == 7 for c in ('silesia.tar', 'enwik8')) and hosts == {'ace-core'}
p(f"a) default grid 7/7 measured rows on silesia_tar and enwik8, one host {sorted(hosts)}: {'PASS' if a_ok else 'FAIL'}"); ok &= a_ok

# b) ratio and archive sha256 of the default grid == PR #78; c) p50 within the calibrated tolerance of PR #78
b_ok = c_ok = True
for c in ('silesia.tar', 'enwik8'):
    po, pn = J(OLD / c / 'pick.json'), J(M / f'default/{c}/pick.json')
    ro = {(r['codec'], r['g']): r for r in po['rows'] if r['status'] == 'measured'}
    rn = {(r['codec'], r['g']): r for r in pn['rows'] if r['status'] == 'measured'}
    for k in sorted(rn):
        d = f"{k[0]}-{k[1]}"
        so = {Path(q).name: v for q, v in J(OLD / c / d / 'archive-state.json')['artifacts'].items()}
        sn = {Path(q).name: v for q, v in J(M / f'default/{c}' / d / 'archive-state.json')['artifacts'].items()}
        same = so == sn and ro[k]['ratio'] == rn[k]['ratio']; b_ok &= same
        dp = rn[k]['p50_ms'] / ro[k]['p50_ms'] - 1; inside = abs(dp) <= TOL[k]; c_ok &= inside
        p(f"   {c:12s} {d:20s} ratio/archives {'==' if same else 'DIFF'} | p50 {rn[k]['p50_ms']:.4f} vs {ro[k]['p50_ms']:.4f} ({dp*100:+.1f} %, tol {TOL[k]*100:.0f} %) {'ok' if inside else 'OUT'}")
p(f"b) ratio and archive sha256 of the default grid == PR #78: {'PASS' if b_ok else 'FAIL'}"); ok &= b_ok
p(f"c) default p50 within max(10 %, 2 x spread) of PR #78: {'PASS' if c_ok else 'FAIL'}"); ok &= c_ok

# d) silence gate PASS before each corpus run
d_ok = True
for s in sorted(M.rglob('*.silence.json')):
    x = J(s); d_ok &= x['status'] == 'PASS'
    p(f"   {s.relative_to(M)}: {x['status']} load1 {x['snapshot']['load1']:.3f}")
p(f"d) silence gate PASS before every corpus run: {'PASS' if d_ok else 'FAIL'}"); ok &= d_ok

# e) zstd level 3 and the read size recorded in each series' pick.json
e_ok = True
for ser, want in (('r4K', 4096), ('r64K', 65536), ('default', 16384)):
    for f in sorted((M / ser).glob('*/pick.json')):
        x = J(f); good = x.get('zstd_level') == 3 and x.get('region_size_bytes') == want; e_ok &= good
        p(f"   {ser}/{f.parent.name}: zstd_level {x.get('zstd_level')} region_size_bytes {x.get('region_size_bytes')} {'ok' if good else 'WRONG'}")
p(f"e) zstd level 3 and read size recorded: {'PASS' if e_ok else 'FAIL'}"); ok &= e_ok

p(f"GATES: {'ALL PASS' if ok else 'FAIL - run invalid, prediction not evaluated'}")
json.dump({'gates_pass': ok, 'lines': out}, open('/tmp/hwref/z1/gates.json', 'w'), indent=1, ensure_ascii=False)
if not ok: sys.exit(1)

# only now: the zstd_seekable table and the three ratios
res = {}
for c in ('silesia.tar', 'enwik8', 't2t_chrX.fa'):
    r4 = {r['g']: r for r in J(M / f'r4K/{c}/pick.json')['rows'] if r['codec'] == 'zstd_seekable' and r['status'] == 'measured'}
    r64 = {r['g']: r for r in J(M / f'r64K/{c}/pick.json')['rows'] if r['codec'] == 'zstd_seekable' and r['status'] == 'measured'}
    print(f"\n{c}: zstd_seekable g | p50 4K ms | p50 64K ms | p99 4K ms | ratio (4K run / 64K run)")
    for g in sorted(r4):
        print(f"  {g//1024:6d} KiB | {r4[g]['p50_ms']:.4f} | {r64[g]['p50_ms']:.4f} | {r4[g].get('p99_ms') or float('nan'):.4f} | {r4[g]['ratio']:.4f} / {r64[g]['ratio']:.4f}")
    K256, K2M = 256 * 1024, 2 * 1024 * 1024
    q1 = r4[K2M]['p50_ms'] / r4[K256]['p50_ms']; q2 = r64[K2M]['p50_ms'] / r64[K256]['p50_ms']
    q3 = r4[K2M]['ratio'] / r4[K256]['ratio'] - 1
    res[c] = {'p50_2M_over_256K_4K': q1, 'p50_2M_over_256K_64K': q2, 'ratio_loss_256K_vs_2M': q3,
              'hit1': 5.5 <= q1 <= 8.5, 'hit2': 3.5 <= q2 <= 6.5, 'hit3': 0.010 <= q3 <= 0.060}
    print(f"  ratios: 4K {q1:.2f} [5.5, 8.5] {'in' if res[c]['hit1'] else 'OUT'} | 64K {q2:.2f} [3.5, 6.5] {'in' if res[c]['hit2'] else 'OUT'} | ratio loss {q3*100:.2f} % [1.0, 6.0] {'in' if res[c]['hit3'] else 'OUT'}")
hit = all(v['hit1'] and v['hit2'] and v['hit3'] for v in res.values())
print("\nPREDICTION:", "HIT" if hit else "MISS")
json.dump({'results': res, 'hit': hit}, open('/tmp/hwref/z1/ratios.json', 'w'), indent=1)
