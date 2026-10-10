#!/usr/bin/env python3
"""PROTOCOL_AXIS4_N10 v1.1 section 4 reporting from retained evidence (no measurement, no decoder).

Per measured row (variant x decoder threads): the 9 recorded runs r1..r9 (accepted attempts; gate-refused attempts
are counted, retained, never used), seconds = A6 sum of group seconds; median / min / max / 9 raw; answers/s =
200 / seconds (median); storage bytes from evidence. Warm-ups w1..w3 are listed, not used. NOT_SUPPORTED rows are
listed. Leaderboard representative (one evidence per format/variant/threads, as build_leaderboard requires) = the
recorded run with the median seconds (5th of 9; ties by run index), declared here before the leaderboard is built.
Usage: summarize_n10.py --root DATA_ROOT --logs LOG_DIR --out OUT_DIR
"""
import argparse, hashlib, json, statistics
from pathlib import Path


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--logs', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--runs', default='runs12')
    ap.add_argument('--version', default='v1.2')
    a = ap.parse_args()
    root, logs, out = Path(a.root), Path(a.logs), Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    accepted = [l for l in (logs / 'accepted.txt').read_text().split() if not l.startswith(a.runs + '/check/')]
    ns = sorted(set((logs / 'not_supported.txt').read_text().split())) if (logs / 'not_supported.txt').exists() else []
    attempts = {}
    for d in sorted(root.glob(a.runs + '/*/t*/*_a*')):
        attempts.setdefault(str(d.relative_to(root)).rsplit('_a', 1)[0], []).append(d.name)
    rows = {}
    for rel in accepted:
        row, thr, slot = rel.split('/')[1:4]
        ev = json.loads((root / rel / 'evidence.json').read_text())
        assert ev['status'] == 'PASS' and ev['performance_valid'] and ev['verified'] == 200, rel
        rows.setdefault((row, thr), []).append({
            'slot': slot.split('_a')[0], 'evidence': rel + '/evidence.json',
            'evidence_sha256': sha(root / rel / 'evidence.json'), 'seconds': ev['seconds'],
            'stored_bytes': ev['stored_bytes'], 'decoder_threads': ev['decoder_threads'],
            'cpu_models': ev['threading']['cpu_models'], 'affinity': ev['threading']['affinity'],
            'family': json.loads((root / rel / 'plan.json').read_text())['reader']['family'],
            'variant': json.loads((root / rel / 'plan.json').read_text())['reader']['variant'],
            'attempts': len(attempts.get(rel.rsplit('_a', 1)[0], []))})
    result = {'schema': 'axis4-n10-results-v1', 'protocol_sha256': sha(Path(__file__).parent / 'PROTOCOL_AXIS4_N10.md'),
              'prepared_sha256': sha(root / 'prepared-v11/prepared.json'), 'rows': [], 'not_supported': []}
    md = [f'# Axis 4 N10 {a.version} results (ace-core)', '',
          f"Protocol SHA-256 {result['protocol_sha256']}; prepared-v2 SHA-256 {result['prepared_sha256']}.",
          '200 requests (20 groups x 10 assemblies); seconds = A6 sum of group times (fetch + upper-case + SHA-256 '
          '+ coordinate translation), one persistent in-process reader. 3 warm-ups + 9 recorded runs per row.', '',
          '| format | variant | decoder threads | median s | min s | max s | answers/s (median) | stored bytes | '
          'recorded runs | gate retries | leaderboard evidence |', '|---|---|---|---|---|---|---|---|---|---|---|']
    for (row, thr), runs in sorted(rows.items()):
        rec = sorted([r for r in runs if r['slot'].startswith('r')], key=lambda r: int(r['slot'][1:]))
        warm = [r for r in runs if r['slot'].startswith('w')]
        assert len(rec) == 9 and len(warm) == 3, (row, thr, len(rec), len(warm))
        assert len({r['stored_bytes'] for r in runs}) == 1 and len({json.dumps(r['cpu_models']) for r in runs}) == 1
        secs = [r['seconds'] for r in rec]
        med = statistics.median(secs)
        rep = sorted(rec, key=lambda r: (r['seconds'], int(r['slot'][1:])))[4]
        entry = {'row': row, 'threads': int(thr[1:]), 'family': rec[0]['family'], 'variant': rec[0]['variant'],
                 'median_seconds': med, 'min_seconds': min(secs), 'max_seconds': max(secs), 'raw_seconds': secs,
                 'answers_per_second_median': 200 / med, 'stored_bytes': rec[0]['stored_bytes'],
                 'cpu_models': rec[0]['cpu_models'], 'affinity': rec[0]['affinity'],
                 'recorded': [r['evidence'] for r in rec], 'warmups': [r['evidence'] for r in warm],
                 'gate_retries': sum(r['attempts'] - 1 for r in runs),
                 'leaderboard_evidence': rep['evidence'], 'leaderboard_evidence_sha256': rep['evidence_sha256']}
        result['rows'].append(entry)
        md.append(f"| {entry['family']} | {entry['variant']} | {entry['threads']} | {med:.6f} | {min(secs):.6f} | "
                  f"{max(secs):.6f} | {200 / med:.1f} | {entry['stored_bytes']} | 9 | {entry['gate_retries']} | "
                  f"`{rep['evidence_sha256'][:16]}` |")
    md += ['', 'NOT_SUPPORTED rows (16 decoder threads; A12.1 scalar reader API; no decoder started, no timing):', '']
    for rel in ns:
        ev = json.loads((root / rel / 'evidence.json').read_text())
        assert ev['status'] == 'NOT_SUPPORTED', rel
        fam = json.loads((root / rel / 'plan.json').read_text())['reader']
        result['not_supported'].append({'evidence': rel + '/evidence.json', 'family': fam['family'],
                                        'variant': fam['variant'], 'reason': ev['threading']['reason'],
                                        'evidence_sha256': sha(root / rel / 'evidence.json')})
        md.append(f"- {fam['family']} {fam['variant']}: {ev['threading']['reason']}")
    (out / 'results_n10.json').write_text(json.dumps(result, indent=1, sort_keys=True) + '\n')
    (out / 'RESULTS_N10.md').write_text('\n'.join(md) + '\n')
    print('\n'.join(md))


if __name__ == '__main__':
    main()
