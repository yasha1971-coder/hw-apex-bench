#!/usr/bin/env python3
"""PROTOCOL_AXIS4_N10 v1.1 truth equivalence check (independent of tools/axis4_stream.py).

stage   : streams every selected source .fa.gz once (zlib, all gzip members through EOF), checks the compressed
          SHA-256 against selection_n10.tsv (= MANIFEST source_hash), computes for each of the 200 requests the
          SHA-256 of the case-preserved bytes and of the upper-case bytes; requires 200/200 case-preserved SHA equal
          to truth_n10_case.tsv; writes truth_v11_check.tsv and the axis4-corpus-v1.1 manifest (cohort.json) for a
          data root that holds hard links src/<assembly_id>.fa.gz.
compare : requires every upper-case SHA (truth_v11_check.tsv) to equal the A6 axis4-prepared-v2 expected SHA
          (prepared.json groups), 200/200.
"""
import argparse, hashlib, json, os, sys, zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHUNK = 1 << 20


def tsv(p):
    lines = Path(p).read_text().splitlines()
    head = lines[0].split('\t')
    return [dict(zip(head, l.split('\t'))) for l in lines[1:] if l]


def gunzip_stream(path, src_hash):
    """Yield decompressed chunks of every gzip member through EOF; feed compressed bytes into src_hash.
    A member without its trailer (truncation) refuses."""
    with open(path, 'rb') as f:
        d, started = zlib.decompressobj(31), False
        buf = b''
        while True:
            if not buf:
                buf = f.read(CHUNK)
                if not buf:
                    break
                src_hash.update(buf)
            started = True
            out = d.decompress(buf)
            buf = b''
            if out:
                yield out
            if d.eof:
                buf = d.unused_data
                d, started = zlib.decompressobj(31), False
        if started and not d.eof:
            raise SystemExit(f'{path}: truncated gzip member')


def scan(path, windows):
    """windows: {contig: [(start0, end0, rid)]}. Returns (src_sha256, {rid: (case_sha, upper_sha, len)}, contig_len)."""
    src = hashlib.sha256()
    out, active = {}, {}
    contig, pos, header, lengths = None, 0, None, {}
    hs = {}

    def feed(seq):
        nonlocal pos
        if not seq:
            return
        a, b = pos, pos + len(seq)
        for (s, e, rid) in windows.get(contig, ()):
            lo, hi = max(s, a), min(e, b)
            if lo < hi:
                part = seq[lo - a:hi - a]
                h = hs.setdefault(rid, [hashlib.sha256(), hashlib.sha256(), 0])
                h[0].update(part); h[1].update(part.upper()); h[2] += len(part)
        pos = b

    for chunk in gunzip_stream(path, src):
        i = 0
        n = len(chunk)
        while i < n:
            if header is not None:
                j = chunk.find(b'\n', i)
                if j < 0:
                    header += chunk[i:]
                    if len(header) > 1 << 16:
                        raise SystemExit('oversized header')
                    break
                header += chunk[i:j]
                name = header[1:].split()[0].decode()
                if name in lengths:
                    raise SystemExit(f'duplicate contig {name}')
                contig, pos, header = name, 0, None
                i = j + 1
                continue
            j = chunk.find(b'>', i)
            if j < 0:
                feed(chunk[i:].translate(None, b'\r\n'))
                break
            feed(chunk[i:j].translate(None, b'\r\n'))
            if contig is not None:
                lengths[contig] = pos
            header, i = b'', j
    if contig is not None:
        lengths[contig] = pos
    for c, ws in windows.items():
        for (s, e, rid) in ws:
            if c not in lengths or e > lengths[c]:
                raise SystemExit(f'{rid}: window beyond contig')
            h = hs.get(rid)
            if h is None or h[2] != e - s:
                raise SystemExit(f'{rid}: incomplete window')
            out[rid] = (h[0].hexdigest(), h[1].hexdigest(), h[2])
    return src.hexdigest(), out


def stage(a):
    inputs = HERE / 'inputs'
    sel = tsv(inputs / 'selection_n10.tsv')
    reqs = tsv(inputs / 'requests_n10.tsv')
    truth = {r['id']: r['sha256'] for r in tsv(inputs / 'truth_n10_case.tsv')}
    root = Path(a.root)
    hprc50 = Path(a.hprc50)
    rows, results, cohort = [], {}, []
    for s in sel:
        aid = s['assembly_id']
        gz = (hprc50 / Path(s['local_source']).name).resolve(strict=True)
        link = root / 'src' / f'{aid}.fa.gz'
        if not link.exists():
            raise SystemExit(f'missing hard link {link} (stage_v11.sh)')
        if os.stat(link).st_ino != os.stat(gz).st_ino:
            raise SystemExit(f'{link} is not a hard link of {gz}')
        win = {}
        for r in reqs:
            if r['sample'] == aid:
                st = int(r['start'])
                win.setdefault(r['contig'], []).append((st, st + int(r['length']), r['id']))
        src_sha, got = scan(link, win)
        ok_src = src_sha == s['source_sha256']
        print(aid, 'source_sha256', src_sha, 'match' if ok_src else 'MISMATCH', flush=True)
        if not ok_src:
            raise SystemExit('source SHA-256 differs from the manifest')
        results.update(got)
        cohort.append({'assembly_id': aid, 'source_url': s['source_url'], 'source_sha256': src_sha,
                       'fasta': {'path': f'src/{aid}.fa.gz', 'bytes': link.stat().st_size, 'sha256': src_sha}})
    same = sum(results[r['id']][0] == truth[r['id']] for r in reqs)
    with open(a.out_tsv, 'x') as f:
        f.write('id\tcase_sha256\tupper_sha256\tlength\tcase_equals_truth_n10_case\n')
        for r in reqs:
            c, u, n = results[r['id']]
            f.write(f"{r['id']}\t{c}\t{u}\t{n}\t{int(c == truth[r['id']])}\n")
    (root / 'cohort.json').write_text(json.dumps({'schema': 'axis4-corpus-v1.1', 'evidence_kind': 'official',
                                                  'assemblies': cohort}, indent=1) + '\n')
    print(f'case-preserved SHA equal to truth_n10_case: {same}/{len(reqs)}')
    if same != len(reqs):
        raise SystemExit(1)


def compare(a):
    mine = {r['id']: r['upper_sha256'] for r in tsv(a.check_tsv)}
    prepared = json.loads(Path(a.prepared).read_text())
    if prepared.get('schema') != 'axis4-prepared-v2' or prepared.get('truth_version') != '1.1':
        raise SystemExit('axis4-prepared-v2 / truth_version 1.1 required')
    reqs = tsv(HERE / 'inputs' / 'requests_n10.tsv')
    by = {(r['sample'], int(r['id'].rsplit('#', 1)[1])): r['id'] for r in reqs}
    same = total = 0
    for j, group in enumerate(prepared['groups']):
        for aid, q in group.items():
            total += 1
            same += q['sha256'] == mine[by[(aid, j)]]
    print(f'upper-case SHA equal to axis4-prepared-v2: {same}/{total}')
    if same != total or total != len(reqs):
        raise SystemExit(1)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('stage')
    p.add_argument('--root', required=True)
    p.add_argument('--hprc50', default=os.path.expanduser('~/pubrepo/.wk/hprc50'))
    p.add_argument('--out-tsv', required=True)
    p = sub.add_parser('compare')
    p.add_argument('--check-tsv', required=True)
    p.add_argument('--prepared', required=True)
    a = ap.parse_args()
    stage(a) if a.cmd == 'stage' else compare(a)


if __name__ == '__main__':
    main()
