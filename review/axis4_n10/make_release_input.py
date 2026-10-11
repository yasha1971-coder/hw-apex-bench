#!/usr/bin/env python3
"""Real release input (Unreleased, PR #63): axis 3 = window-law-B verdict evidence (tar 3fb7aa62...),
axis 4 = Axis 4 N10 v1.2 official evidence (leaderboard representatives from summarize_n10.py),
axis 5 = A7 synthetic evidence, explicitly synthetic. Data are hard links (0 new bytes); every
hard-linked tree is checked against its source identity first. Writes CONFIG_ROOT (must not exist).

Usage: make_release_input.py --out CONFIG_ROOT --results SUMMARY/results_n10.json --commit SHA40
"""
import argparse, hashlib, json, os, tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WK = Path.home() / 'pubrepo/.wk'
N10 = WK / 'axis4n10'
WLB_TAR = Path.home() / 'outgoing/window-law-B-0ace54d-2026-10-08.tar'
WLB_TAR_SHA = '3fb7aa62d745e795f08e39049d68f3d51ee2494ff2a51400e0324b4ae30dd15a'
WLB_BASE = WK / 'vB_evidence'           # the tar holds window-law-B/, rehearsal-small/ and logs
WLB_DIR = WLB_BASE / 'window-law-B'
A7_FIXTURE = REPO / 'tests/fixtures/leaderboard/input'
METADATA = ['CITATION.cff', '.zenodo.json', 'METHODOLOGY.md', 'CHANGELOG.md', 'RELEASE_NOTES_v0.2.0.md',
            'PROTOCOL_AXIS5.md', 'review/axis4_n10/PROTOCOL_AXIS4_N10.md']
N10_SHARED = ['cohort.json', 'groups_n10.json', 'prepared-v11/prepared.json', 'src', 'fa', 'ref', 'rr3', 'bgzf',
              'zstd', 'agc', 'lib', 'plans']


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def ref(root, p):
    return {'path': Path(p).relative_to(root).as_posix(), 'bytes': Path(p).stat().st_size, 'sha256': sha(p)}


def encoded(v):
    return (json.dumps(v, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()


def link_tree(src, dst):
    src, dst = Path(src), Path(dst)
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            if os.stat(dst).st_ino != os.stat(src).st_ino:
                raise SystemExit(f'{dst} exists and is not a hard link of {src}')
            return  # the same file referenced twice (e.g. one receipt for two variants)
        os.link(src, dst)
        return
    for p in sorted(src.rglob('*')):
        if p.is_symlink():
            raise SystemExit(f'symlink refused: {p}')
        if p.is_file():
            t = dst / p.relative_to(src)
            t.parent.mkdir(parents=True, exist_ok=True)
            os.link(p, t)


def check_window_law_tree():
    """window-law-B/ in the extracted vB_evidence must equal the 3fb7aa62 tar member by member."""
    if sha(WLB_TAR) != WLB_TAR_SHA:
        raise SystemExit('window-law-B tar sha differs')
    seen = {}
    with tarfile.open(WLB_TAR) as t:
        for m in t:
            if m.isfile():
                h = hashlib.sha256()
                f = t.extractfile(m)
                for b in iter(lambda: f.read(1 << 22), b''):
                    h.update(b)
                if m.name.startswith('window-law-B/'):
                    seen[m.name.split('/', 1)[1]] = h.hexdigest()
            elif not m.isdir():
                raise SystemExit('unexpected tar member type ' + m.name)
    have = {p.relative_to(WLB_DIR).as_posix(): p for p in WLB_DIR.rglob('*') if p.is_file()}
    missing = sorted(set(seen) - set(have))
    extra = sorted(set(have) - set(seen))
    bad = sorted(n for n in set(seen) & set(have) if sha(have[n]) != seen[n])
    return seen, missing, extra, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--results', required=True)
    ap.add_argument('--commit', required=True)
    a = ap.parse_args()
    root = Path(a.out)
    root.mkdir(parents=True, exist_ok=False)
    report = {}
    # axis 3: window-law-B
    seen, missing, extra, bad = check_window_law_tree()
    report['window_law_B'] = {'tar_sha256': WLB_TAR_SHA, 'tar_files': len(seen), 'missing_in_dir': missing,
                              'extra_in_dir': extra, 'sha_mismatch': bad}
    c3 = root / 'catalogs/axis3-window-law-B'
    if missing or bad:
        c3.mkdir(parents=True)
        with tarfile.open(WLB_TAR) as t:
            t.extractall(c3, members=[m for m in t if m.name.startswith('window-law-B/')], filter='data')
        report['window_law_B']['source'] = 'extracted from tar'
    else:
        for n in sorted(seen):
            link_tree(WLB_DIR / n, c3 / 'window-law-B' / n)
        report['window_law_B']['source'] = 'hard links of the tar-identical extracted directory (extra files not linked)'
    # The verdict evidence references its inputs (plan, prepared, runbook, archives, libraries, reference,
    # source FASTA) by path/bytes/sha256 relative to the original vB data root: hard-link each one, SHA-checked,
    # so every evidence file reference is hash-bound in the release (DATA_ROOT listing) and on the site.
    results = json.loads((c3 / 'window-law-B/results.json').read_text())
    vb = WK / 'vB'
    n_inputs = 0
    for r in results['input_references']:
        src = vb / r['path']
        if src.is_symlink() or not src.is_file() or src.stat().st_size != r['bytes'] or sha(src) != r['sha256']:
            raise SystemExit(f'window-law-B input reference changed or missing: {r["path"]}')
        link_tree(src, c3 / 'vB' / r['path'])
        n_inputs += 1
    report['window_law_B']['input_references_linked'] = n_inputs
    (c3 / 'leaderboard-input.json').write_bytes(encoded({'schema': 'leaderboard-input-v1', 'records': [
        {'evidence': ref(c3, c3 / 'window-law-B/results.json'), 'input_root': '.'}]}))
    # axis 4: N10 v1.2 representatives
    res = json.loads(Path(a.results).read_text())
    prepared_sha = sha(N10 / 'prepared-v11/prepared.json')
    if res['prepared_sha256'] != prepared_sha:
        raise SystemExit('results/prepared mismatch')
    c4 = root / 'catalogs/axis4-n10'
    for name in N10_SHARED:
        link_tree(N10 / name, c4 / 'root' / name)
    records = []
    for row in res['rows']:
        ev = Path(row['leaderboard_evidence'])
        link_tree(N10 / ev.parent, c4 / 'root' / ev.parent)
        records.append({'evidence': ref(c4, c4 / 'root' / ev), 'input_root': 'root', 'prepared_sha256': prepared_sha})
    (c4 / 'leaderboard-input.json').write_bytes(encoded({'schema': 'leaderboard-input-v1', 'records': records}))
    # axis 5: A7 synthetic (explicitly synthetic; its own table, machine unrecorded)
    golden = json.loads((A7_FIXTURE / 'leaderboard-input.json').read_text())
    a7 = [r for r in golden['records'] if r['evidence']['path'] == 'data/a7-run/evidence.json']
    if len(a7) != 1 or json.loads((A7_FIXTURE / a7[0]['evidence']['path']).read_text())['evidence_kind'] != 'synthetic':
        raise SystemExit('A7 synthetic record not found')
    c5 = root / 'catalogs/axis5-a7-synthetic'
    link_tree(A7_FIXTURE / 'data', c5 / 'data')
    (c5 / 'leaderboard-input.json').write_bytes(encoded({'schema': 'leaderboard-input-v1', 'records': a7}))
    # metadata artifacts (copies; small)
    arts = []
    import re
    from urllib.parse import unquote, urlsplit
    method = (REPO / 'METHODOLOGY.md').read_text()
    linked = sorted({unquote(urlsplit(x).path) for x in re.findall(r'\[[^\]]*\]\(([^)#]+)', method)
                     if not urlsplit(x).scheme and (REPO / unquote(urlsplit(x).path)).is_file()})
    for name in [n for n in linked if n not in METADATA] + METADATA + ['RESULTS_N10.md']:
        src = REPO / name if name != 'RESULTS_N10.md' else Path(a.results).parent / 'RESULTS_N10.md'
        dst = root / (name if name != 'RESULTS_N10.md' else 'review/axis4_n10/RESULTS_N10.md')
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        arts.append(ref(root, dst))
    config = {'schema': 'release-input-v1', 'commit': a.commit,
              'catalogs': [ref(root, p) for p in sorted(root.glob('catalogs/*/leaderboard-input.json'))],
              'artifacts': arts}
    (root / 'release-input.json').write_bytes(encoded(config))
    report['config'] = ref(root, root / 'release-input.json')
    report['native_so'] = sorted(str(p) for p in root.rglob('*.so'))
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
