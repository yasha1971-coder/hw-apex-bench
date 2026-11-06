#!/usr/bin/env python3
"""HWAB-PICK-3b gates b, c: silesia_tar and enwik8 against PR #78 (evidence/hwab-pick-2-20261105)."""
import json, sys
from pathlib import Path
OLD = Path('/home/aeterna/pubrepo/.wk/hwab-pick2/evidence/hwab-pick-2-20261105')
NEW = Path('/tmp/hwref/p3')
ok = True
for c in ('silesia.tar', 'enwik8'):
    po = json.load(open(OLD / c / 'pick.json')); pn = json.load(open(NEW / c / 'pick.json'))
    if po['input_sha256'] != pn['input_sha256']:
        print(c, 'INPUT SHA DIFF'); ok = False
    ro = {(r['codec'], r['g']): r for r in po['rows'] if r['status'] == 'measured'}
    rn = {(r['codec'], r['g']): r for r in pn['rows'] if r['status'] == 'measured'}
    if set(ro) != set(rn) or len(rn) != 7:
        print(c, 'ROW SET DIFF', sorted(ro), sorted(rn)); ok = False
    for k in sorted(rn):
        a, b = ro[k], rn[k]
        d = f"{k[0]}-{k[1]}"
        so = json.load(open(OLD / c / d / 'archive-state.json'))['artifacts']
        sn = json.load(open(NEW / c / d / 'archive-state.json'))['artifacts']
        # artifacts are keyed by path; compare by file name
        so = {Path(p).name: v for p, v in so.items()}; sn = {Path(p).name: v for p, v in sn.items()}
        art = so == sn
        rat = a['ratio'] == b['ratio']
        dp = b['p50_ms'] / a['p50_ms'] - 1
        p50 = abs(dp) <= 0.10
        ok &= art and rat and p50
        print(f"{c:12s} {d:20s} ratio {b['ratio']:.6f} {'==' if rat else '!='} {a['ratio']:.6f} | archives {'==' if art else 'DIFF'} ({len(sn)} files)"
              f" | p50 {b['p50_ms']:.4f} vs {a['p50_ms']:.4f} ms ({dp*100:+.1f} %) {'ok' if p50 else 'OUT'}")
print('gates b, c:', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
