#!/usr/bin/env python3
"""PROTOCOL_AXIS4_N10 inputs: deterministic cohort selection, request/truth restriction, A6 groups, disk budget.

Reads only small metadata files (no FASTA, no archive, no codec). Writes into --out (must not exist):
  selection_n10.tsv        the 10 assemblies, frozen order, provenance (source URL/hash, FASTA bytes/xxh3, rr3 SHAs)
  requests_n10.tsv         the PROTOCOL_COHORT_REGION requests restricted to the 10 (20 x 10 = 200 rows)
  truth_n10_case.tsv       the matching PROTOCOL_COHORT_REGION truth rows (case as in FASTA)
  groups_n10.json          A6 groups: region j -> one coordinate tuple per assembly (20 groups)
  groups_n10_check.json    method check: the first 2 groups (10 % of the 200 requests)
  budget_n10.json          disk budget (exact where the bytes exist, upper estimates where a build is still needed)
"""
import argparse, hashlib, json, math, os, shutil, sys
from pathlib import Path

REQ_SHA = '2eacaa0b76cabccfa875a045a9fe64ff8e634cf83deab859f383c2e7526b8d22'
TRUTH_SHA = '136c688fd06855f22c50de53252c03d5182c22c6093f6a19dd0ef76328c1b1fe'
N = 10
REGIONS = 20
CHECK_GROUPS = 2          # 10 % of 20 groups = 20 of 200 requests
GATE_DISK = 20_000_000_000


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def tsv(p):
    lines = Path(p).read_text().splitlines()
    head = lines[0].split('\t')
    return [dict(zip(head, l.split('\t'))) for l in lines[1:] if l]


def select(manifest, hprc50):
    """Rule: walk MANIFEST.tsv in file order; keep a row when name = 'y1_' + ID, ID has a line in hprc50/list.tsv whose
    source hash equals the manifest source_hash, hprc50/ID.fa.gz exists, status == ok; take the first 10."""
    local = {}
    for line in (Path(hprc50) / 'list.tsv').read_text().splitlines():
        i, url, h = line.split('\t')
        local[i] = (url, h)
    out = []
    for row in tsv(manifest):
        name = row['name']
        if not name.startswith('y1_') or row['status'] != 'ok':
            continue
        i = name[3:]
        if i in local and local[i][1] == row['source_hash'] and local[i][0] == row['url'] \
                and (Path(hprc50) / f'{i}.fa.gz').exists():
            out.append(row)
        if len(out) == N:
            break
    if len(out) != N:
        raise SystemExit('fewer than 10 eligible assemblies')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', default=os.path.expanduser('~/panvram/MANIFEST.tsv'))
    ap.add_argument('--hprc50', default=os.path.expanduser('~/pubrepo/.wk/hprc50'))
    ap.add_argument('--cohort-region', default=os.path.expanduser('~/outgoing/cohort_region'))
    ap.add_argument('--reuse-root', default=os.path.expanduser('~/pubrepo/.wk/vB'),
                    help='existing verdict-B root: FASTA, BGZF default, zstd seekable for the first 4 (hard links)')
    ap.add_argument('--free-bytes', type=int, required=True, help='df -B1 available bytes on the data disk now')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    req_p, truth_p = Path(a.cohort_region) / 'requests.tsv', Path(a.cohort_region) / 'truth.tsv'
    if sha(req_p) != REQ_SHA or sha(truth_p) != TRUTH_SHA:
        raise SystemExit('cohort_region requests/truth SHA differ from the pins')

    sel = select(a.manifest, a.hprc50)
    ids = [r['name'] for r in sel]
    with open(out / 'selection_n10.tsv', 'w') as f:
        f.write('order\tassembly_id\tsource_url\tsource_sha256\tlocal_source\tfasta_bytes\tfasta_xxh3\t'
                'q4k_bytes\tq4k_sha256\tq16k_bytes\tq16k_sha256\n')
        for k, r in enumerate(sel):
            f.write('\t'.join([str(k), r['name'], r['url'], r['source_hash'], f"hprc50/{r['name'][3:]}.fa.gz",
                               r['fasta_bytes'], r['fasta_xxh3'], r['q4k_bytes'], r['q4k_sha256'],
                               r['q16k_bytes'], r['q16k_sha256']]) + '\n')

    reqs = [r for r in tsv(req_p) if r['sample'] in ids]
    by = {(r['sample'], int(r['id'].rsplit('#', 1)[1])): r for r in reqs}
    if len(reqs) != N * REGIONS or len(by) != N * REGIONS:
        raise SystemExit(f'expected {N * REGIONS} requests, got {len(reqs)}')
    order = [(s, j) for j in range(REGIONS) for s in ids]   # frozen: group j, then cohort order
    with open(out / 'requests_n10.tsv', 'w') as f:
        f.write('id\tsample\tcontig\tstart\tlength\n')
        for key in order:
            r = by[key]
            f.write('\t'.join([r['id'], r['sample'], r['contig'], r['start'], r['length']]) + '\n')
    truth = {r['id']: r['sha256'] for r in tsv(truth_p)}
    with open(out / 'truth_n10_case.tsv', 'w') as f:
        f.write('id\tsha256\n')
        for key in order:
            f.write(f"{by[key]['id']}\t{truth[by[key]['id']]}\n")

    groups = []
    for j in range(REGIONS):
        g = {}
        for s in ids:
            r = by[(s, j)]
            st = int(r['start'])
            g[s] = {'assembly_id': s, 'contig_id': r['contig'], 'start0': st, 'end0': st + int(r['length'])}
        groups.append(g)
    for name, gs in (('groups_n10.json', groups), ('groups_n10_check.json', groups[:CHECK_GROUPS])):
        (out / name).write_text(json.dumps(gs, indent=1, sort_keys=True) + '\n')

    # ---- disk budget -------------------------------------------------------------------------------------------
    reuse = Path(a.reuse_root)
    fb = {r['name']: int(r['fasta_bytes']) for r in sel}
    have_fa = {s for s in ids if (reuse / 'fasta' / f'{s}.fa').exists()}
    new = [s for s in ids if s not in have_fa]
    bgz_ratio = max((reuse / 'bgzf_default' / f'{s}.fa.bgz').stat().st_size / fb[s] for s in have_fa)
    gzi_ratio = max((reuse / 'bgzf_default' / f'{s}.fa.bgz.gzi').stat().st_size / fb[s] for s in have_fa)
    zst_ratio = max((reuse / 'zstd' / f'{s}.seq.zst').stat().st_size / fb[s] for s in have_fa)
    fai_max = max((reuse / 'bgzf_default' / f'{s}.fa.bgz.fai').stat().st_size for s in have_fa)
    zmap_max = max((reuse / 'zstd' / f'{s}.map.json').stat().st_size for s in have_fa)
    fa_new = sum(fb[s] for s in new)
    # AGC: N=4 t2t (vB/agc/t2t_4.agc) and N=5 (m6 agc5) are measured; the per-assembly increment N4->N5 is the
    # largest observed (N5->N50 is smaller), so 4 -> 10 at that rate is an upper estimate. noref is bounded by t2t
    # (noref_50 < t2t_50; it replaces the external T2T by the first member).
    agc4 = (reuse / 'agc' / 't2t_4.agc').stat().st_size
    agc5 = Path(os.path.expanduser('~/pubrepo/.wk/m6/N5/agc5.agc')).stat().st_size
    agc10 = agc4 + (N - 4) * max(agc5 - agc4, 0)
    items = {
        'fasta_uncompressed_new_exact': fa_new,
        'fasta_uncompressed_reused_hardlink': 0,
        'faidx_fai_all10_upper': N * fai_max,
        'bgzf_default_new_upper': sum(math.ceil(fb[s] * bgz_ratio) + math.ceil(fb[s] * gzi_ratio) + fai_max for s in new),
        'bgzf_default_reused_hardlink': 0,
        'zstd_seekable_new_upper': sum(math.ceil(fb[s] * zst_ratio) + zmap_max for s in new),
        'zstd_seekable_reused_hardlink': 0,
        'zstd_canonical_stream_fifo': 0,   # canon.py -> FIFO -> seekable_compression (fread loop), no temp file
        'agc_t2t_10_upper': agc10,
        'agc_noref_10_upper': agc10,
        'agc_native_build_dir_upper': 210_000_000,
        'refrel3_q4k_q16k_symlink': 0,
        't2t_reference_symlink': 0,
        'evidence_and_logs_upper': 200_000_000,
    }
    total = sum(items.values())
    need = total + GATE_DISK + 1
    budget = {
        'schema': 'axis4-n10-budget-v1', 'items_bytes': items, 'new_bytes_total_upper': total,
        'gate_disk_strictly_above_bytes': GATE_DISK, 'required_free_now_bytes': need,
        'free_now_bytes': a.free_bytes, 'shortfall_bytes': max(need - a.free_bytes, 0),
        'fits': a.free_bytes >= need,
        'ratios_from_reused_4': {'bgz': bgz_ratio, 'gzi': gzi_ratio, 'zst': zst_ratio},
        'agc_points_bytes': {'t2t_4': agc4, 'agc5_m6': agc5},
        'reused': sorted(have_fa), 'new': new,
    }
    (out / 'budget_n10.json').write_text(json.dumps(budget, indent=1) + '\n')
    print(json.dumps({'selected': ids, 'requests': len(order), 'groups': len(groups), 'check_requests':
                      CHECK_GROUPS * N, 'new_bytes_upper': total, 'required_free': need, 'free': a.free_bytes,
                      'shortfall': budget['shortfall_bytes']}, indent=1))


if __name__ == '__main__':
    main()
