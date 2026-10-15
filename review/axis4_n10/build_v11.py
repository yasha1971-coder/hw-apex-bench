#!/usr/bin/env python3
"""PROTOCOL_AXIS4_N10 v1.1 input builder (section 3). Run from the repository root; heavy steps are invoked by
run_n10.sh under `flock ~/pubrepo/.wk/measure.lock`. Every step refuses on any identity mismatch.

  static            libraries + receipts, T2T, refrel3 archives, and the four reused FASTA / BGZF / zstd inputs
                    (hard links; SHA-256 checked against vB and against the v1.1 prepared truth identities)
  fasta AID         gzip -dc of the local source -> fa/AID.fa; bytes == MANIFEST fasta_bytes, SHA-256 ==
                    prepared truth.uncompressed_sha256, XXH3 == MANIFEST fasta_xxh3
  fai               FASTA.fai for all 10 through the pinned htslib shim (hwa_bgzf_index)
  bgzf AID          review/axis3/bgzf_adapter.create(mode=default) -> bgzf/AID.fa.bgz(+.fai/.gzi), receipt
  zstd AID          canon.py -> FIFO -> seekable_compression <fifo> 16384 3 -> zstd/AID.seq.zst + map.json
  agc MODE          one agc_adapter.create (t2t | noref) over the 10 in cohort order, 16 build threads
  agclib            library receipt for the AGC_PLATFORM=native build
  plans             axis4-plan-v1 files for every row + the method check
"""
import argparse, ctypes, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from review.axis3 import agc_adapter, bgzf_adapter  # noqa: E402

HERE = Path(__file__).resolve().parent
WK = Path.home() / 'pubrepo/.wk'
VB = WK / 'vB'
NATIVE = WK / 'hwnative'
GOLDEN_T2T = Path.home() / 'golden/genome/t2t.fa'
T2T_SHA = '51ab7d3c2a375ecff53ee2a1be03e58d57cc1601c948a860c03a78d724f26e4c'
REUSED = ['y1_HG00438.1', 'y1_HG00438.2', 'y1_HG00621.1', 'y1_HG00621.2']


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def ref(root, p):
    p = Path(p)
    return {'path': p.relative_to(root).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}


def tsv(p):
    lines = Path(p).read_text().splitlines()
    head = lines[0].split('\t')
    return [dict(zip(head, l.split('\t'))) for l in lines[1:] if l]


def write_json(p, v):
    with open(p, 'x') as f:
        json.dump(v, f, indent=2, sort_keys=True)
        f.write('\n')


def prepared(root):
    return json.loads((root / 'prepared-v11/prepared.json').read_text())


def selection():
    return tsv(HERE / 'inputs/selection_n10.tsv')


def link(src, dst, want=None):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if os.stat(dst).st_ino != os.stat(src).st_ino:
            raise SystemExit(f'{dst} exists and is not a hard link of {src}')
    else:
        os.link(src, dst)
    if want is not None:
        got = sha(dst)
        if got != want:
            raise SystemExit(f'{dst}: sha256 {got} != {want}')
    return dst


def static(root):
    (root / 'lib').mkdir(exist_ok=True)
    for name in ('libhwa_refrel3.so', 'libhwa_bgzf.so', 'libhwa_zstd_seekable.so'):
        for f in (name, name + '.receipt.json'):
            dst = root / 'lib' / f
            if not dst.exists():
                shutil.copyfile(VB / 'lib' / f, dst)
        rec = json.loads((root / 'lib' / (name + '.receipt.json')).read_text())
        if rec['library_sha256'] != sha(root / 'lib' / name):
            raise SystemExit(f'{name}: library sha differs from its receipt')
    for name in ('libhwa_refrel3.so', 'libhwa_bgzf.so'):
        if sha(root / 'lib' / name) != sha(NATIVE / ('refrel3' if 'refrel3' in name else 'bgzf') / name):
            raise SystemExit(f'{name}: differs from the hwnative build')
    if sha(root / 'lib/libhwa_zstd_seekable.so') != sha(NATIVE / 'libhwa_zstd_seekable.so'):
        raise SystemExit('zstd library differs from the hwnative build')
    link(VB / 'ref/t2t.fa', root / 'ref/t2t.fa', T2T_SHA)
    if os.stat(VB / 'ref/t2t.fa').st_ino != os.stat(GOLDEN_T2T).st_ino:
        raise SystemExit('vB/ref/t2t.fa is not the golden T2T')
    for s in selection():
        aid = s['assembly_id']
        for q in ('q4k', 'q16k'):
            link(WK / 'hprc_cohort/v1' / f'{aid}.{q}.rr3', root / 'rr3' / f'{aid}.{q}.rr3', s[f'{q}_sha256'])
    p = {a['assembly_id']: a for a in prepared(root)['assemblies']}
    vb_cohort = {a['assembly_id']: a for a in json.loads((VB / 'cohort.json').read_text())['assemblies']}
    vb_bgzf = json.loads((VB / 'bgzf_build.json').read_text())
    vb_plan = json.loads((VB / 'plan.json').read_text())
    vb_zstd = {a['assembly_id']: a for v in vb_plan['variants'] if v['family'] == 'zstd-seekable' for a in v['archives']}
    for aid in REUSED:
        want = p[aid]['truth']['uncompressed_sha256']
        if vb_cohort[aid]['fasta']['sha256'] != want:
            raise SystemExit(f'{aid}: vB FASTA identity differs from v1.1 truth')
        link(VB / 'fasta' / f'{aid}.fa', root / 'fa' / f'{aid}.fa', want)
        rec = vb_bgzf[f'{aid}:default']
        if (rec['mode'], rec['htslib_commit'], rec['libdeflate_commit'], rec['build_threads']) != \
                ('default', bgzf_adapter.HTS_PIN, bgzf_adapter.LIBDEFLATE_PIN, 1):
            raise SystemExit(f'{aid}: vB BGZF receipt differs from the protocol builder')
        for art in rec['artifacts']:
            link(VB / 'bgzf_default' / art['path'], root / 'bgzf' / art['path'], art['sha256'])
        write_json(root / 'bgzf' / f'{aid}.build.json', {**rec, 'reused_from': 'vB/bgzf_default'}) \
            if not (root / 'bgzf' / f'{aid}.build.json').exists() else None
        z = vb_zstd[aid]
        link(VB / z['archive']['path'], root / 'zstd' / f'{aid}.seq.zst', z['archive']['sha256'])
        link(VB / z['contig_map']['path'], root / 'zstd' / f'{aid}.map.json', z['contig_map']['sha256'])
    print('static OK')


def fasta(root, aid):
    s = {r['assembly_id']: r for r in selection()}[aid]
    p = {a['assembly_id']: a for a in prepared(root)['assemblies']}[aid]
    out = root / 'fa' / f'{aid}.fa'
    if out.exists():
        raise SystemExit(f'{out} exists')
    out.parent.mkdir(exist_ok=True)
    part = out.with_suffix('.fa.part')
    src = root / p['fasta']['path']
    with open(part, 'xb') as o:
        subprocess.run(['gzip', '-dc', str(src)], stdout=o, check=True)
    n, h = part.stat().st_size, sha(part)
    x = subprocess.run([str(WK / 'axis4n10_tools/xxh3sum'), str(part)], capture_output=True, text=True,
                       check=True).stdout.split()[0]
    ok = (n == int(s['fasta_bytes']) == p['truth']['uncompressed_bytes'] and h == p['truth']['uncompressed_sha256']
          and x == s['fasta_xxh3'])
    print(f'{aid} bytes={n} sha256={h} xxh3={x} manifest_bytes={s["fasta_bytes"]} manifest_xxh3={s["fasta_xxh3"]} '
          f'truth_sha256={p["truth"]["uncompressed_sha256"]} {"OK" if ok else "MISMATCH"}')
    if not ok:
        raise SystemExit('materialised FASTA identity mismatch; .part kept for inspection')
    part.rename(out)


def fai(root):
    lib = bgzf_adapter.library(root / 'lib/libhwa_bgzf.so')
    for s in selection():
        fa = root / 'fa' / f"{s['assembly_id']}.fa"
        if (Path(str(fa) + '.fai')).exists():
            raise SystemExit(f'{fa}.fai exists')
        if lib.hwa_bgzf_index(str(fa).encode()) != 0:
            raise SystemExit(f'{fa}: fai build failed')
        print(fa.name + '.fai', sha(str(fa) + '.fai'))


def bgzf(root, aid):
    out = root / 'bgzf' / f'{aid}.fa.bgz'
    rec = bgzf_adapter.create(NATIVE / 'bgzf/bgzip', root / 'lib/libhwa_bgzf.so', root / 'fa' / f'{aid}.fa', out)
    write_json(root / 'bgzf' / f'{aid}.build.json', {**rec, 'bgzip_sha256': sha(NATIVE / 'bgzf/bgzip')})
    print(aid, 'bgzf', rec['storage_bytes'], [a['sha256'] for a in rec['artifacts']])


def zstd(root, aid):
    d = root / 'zstd'
    d.mkdir(exist_ok=True)
    fifo, mp, out = d / f'{aid}.seq', d / f'{aid}.map.json', d / f'{aid}.seq.zst'
    if out.exists() or mp.exists() or fifo.exists():
        raise SystemExit(f'{aid}: zstd outputs exist')
    os.mkfifo(fifo)
    try:
        comp = subprocess.Popen([str(NATIVE / 'zstd/contrib/seekable_format/examples/seekable_compression'),
                                 str(fifo), '16384', '3'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        can = subprocess.run([sys.executable, str(WK / 'vB_canon/canon.py'), str(root / 'fa' / f'{aid}.fa'),
                              str(fifo), str(mp), aid], capture_output=True, text=True)
        o, e = comp.communicate()
        if can.returncode or comp.returncode:
            raise SystemExit(f'{aid}: canon rc={can.returncode} {can.stderr} compress rc={comp.returncode} {e}')
    finally:
        fifo.unlink()
    m = json.loads(mp.read_text())
    p = {a['assembly_id']: a for a in prepared(root)['assemblies']}[aid]
    if m['canonical_bytes'] != p['canonical_bytes'] or [c['contig_id'] for c in m['contigs']] != \
            [c['contig_id'] for c in p['contigs']]:
        raise SystemExit(f'{aid}: zstd canonical map differs from the prepared identity')
    write_json(d / f'{aid}.build.json', {
        'codec': 'zstd seekable', 'zstd_commit': 'f8745da6ff1ad1e7bab384bd1f9d742439278e99', 'level': 3,
        'frame_bytes': 16384, 'canon_py_sha256': sha(WK / 'vB_canon/canon.py'),
        'seekable_compression_sha256': sha(NATIVE / 'zstd/contrib/seekable_format/examples/seekable_compression'),
        'input': 'FIFO (no temporary file)', 'canon_stdout': can.stdout.strip(),
        'archive': ref(root, out), 'contig_map': ref(root, mp)})
    print(aid, 'zstd', out.stat().st_size)


def agclib(root, build_dir):
    build_dir = Path(build_dir)
    if (build_dir / 'AGC_PLATFORM').read_text().strip() != 'native':
        raise SystemExit('AGC build is not AGC_PLATFORM=native')
    so = root / 'lib/libhwa_agc.so'
    if not so.exists():
        shutil.copyfile(build_dir / 'libhwa_agc.so', so)
    if sha(so) != sha(build_dir / 'libhwa_agc.so'):
        raise SystemExit('AGC library copy differs')
    sums = (build_dir / 'SHA256SUMS').read_text()
    if sha(build_dir / 'libhwa_agc.so') not in sums or sha(build_dir / 'agc-cli') not in sums:
        raise SystemExit('AGC build SHA256SUMS mismatch')
    compiler = subprocess.run(['g++', '--version'], capture_output=True, text=True).stdout.splitlines()[0]
    subm = subprocess.run(['git', '-C', str(build_dir / 'agc'), 'submodule', 'status', '--recursive'],
                          capture_output=True, text=True, check=True).stdout
    lib = {'schema': 'axis4-n10-agc-library-receipt-v1', 'built_on': 'ace-core', 'codec_version': '3.2.4',
           'source_commit': agc_adapter.PIN, 'compiler': compiler,
           'flags': ['upstream makefile, AGC_PLATFORM=native (-march=native)', '-fPIC', '-shared'],
           'dependencies': {'agc': agc_adapter.PIN + ' libagc.a', 'submodules': subm,
                            'build_script': 'review/axis3/build_agc_v324.sh', 'shim': 'review/axis3/agc_shim.cpp',
                            'agc_platform': 'native', 'build_log_sha256': sha(build_dir / 'build.log')},
           'library_sha256': sha(so), 'agc_cli_sha256': sha(build_dir / 'agc-cli'), 'decoder_threads': 1}
    (root / 'lib/libhwa_agc.library.json').unlink(missing_ok=True)
    write_json(root / 'lib/libhwa_agc.library.json', lib)
    print('agc library receipt', lib['library_sha256'])


def agc(root, mode, build_dir):
    lib = json.loads((root / 'lib/libhwa_agc.library.json').read_text())
    out = root / 'agc' / f'{mode}_10.agc'
    rows = [(s['assembly_id'], root / 'fa' / f"{s['assembly_id']}.fa") for s in selection()]
    creation = agc_adapter.create(Path(build_dir) / 'agc-cli', rows, mode, out,
                                  root / 'ref/t2t.fa' if mode == 't2t' else None, threads=16)
    write_json(root / 'agc' / f'{mode}_10.receipt.json', {**lib, **creation})
    print(mode, creation['archive_bytes'], creation['archive_sha256'])


def plans(root):
    pr = ref(root, root / 'prepared-v11/prepared.json')
    pc = ref(root, root / 'prepared-v11-check/prepared.json')
    ids = [s['assembly_id'] for s in selection()]
    lib = lambda n: ref(root, root / 'lib' / n)  # noqa: E731
    specs = {
        'refrel3_q4k': {'family': 'refrel3', 'variant': 'q4k', 'library': lib('libhwa_refrel3.so'),
                        'build_receipt': lib('libhwa_refrel3.so.receipt.json'), 'reference': ref(root, root / 'ref/t2t.fa'),
                        'archives': [{'assembly_id': a, 'archive': ref(root, root / 'rr3' / f'{a}.q4k.rr3')} for a in ids]},
        'refrel3_q16k': {'family': 'refrel3', 'variant': 'q16k', 'library': lib('libhwa_refrel3.so'),
                         'build_receipt': lib('libhwa_refrel3.so.receipt.json'), 'reference': ref(root, root / 'ref/t2t.fa'),
                         'archives': [{'assembly_id': a, 'archive': ref(root, root / 'rr3' / f'{a}.q16k.rr3')} for a in ids]},
        'bgzf_default': {'family': 'bgzf', 'variant': 'default', 'library': lib('libhwa_bgzf.so'),
                         'build_receipt': lib('libhwa_bgzf.so.receipt.json'),
                         'archives': [{'assembly_id': a, 'archive': ref(root, root / 'bgzf' / f'{a}.fa.bgz'),
                                       'fai': ref(root, root / 'bgzf' / f'{a}.fa.bgz.fai'),
                                       'gzi': ref(root, root / 'bgzf' / f'{a}.fa.bgz.gzi')} for a in ids]},
        'zstd_seekable': {'family': 'zstd-seekable', 'variant': 'seekable_compression level 3, frame 16384 B',
                          'library': lib('libhwa_zstd_seekable.so'),
                          'build_receipt': lib('libhwa_zstd_seekable.so.receipt.json'),
                          'archives': [{'assembly_id': a, 'archive': ref(root, root / 'zstd' / f'{a}.seq.zst'),
                                        'contig_map': ref(root, root / 'zstd' / f'{a}.map.json')} for a in ids]},
        'faidx_plain': {'family': 'fasta-faidx', 'variant': 'plain', 'library': lib('libhwa_bgzf.so'),
                        'build_receipt': lib('libhwa_bgzf.so.receipt.json'),
                        'archives': [{'assembly_id': a, 'archive': ref(root, root / 'fa' / f'{a}.fa'),
                                      'fai': ref(root, root / 'fa' / f'{a}.fa.fai')} for a in ids]},
    }
    for mode in ('t2t', 'noref'):
        s = {'family': 'agc', 'variant': mode, 'library': lib('libhwa_agc.so'),
             'build_receipt': ref(root, root / 'agc' / f'{mode}_10.receipt.json'),
             'archive': ref(root, root / 'agc' / f'{mode}_10.agc')}
        if mode == 't2t':
            s['reference'] = ref(root, root / 'ref/t2t.fa')
        specs['agc_' + mode] = s
    (root / 'plans').mkdir(exist_ok=True)
    out = {}
    for name, spec in specs.items():
        write_json(root / 'plans' / f'{name}.json', {'schema': 'axis4-plan-v1', 'prepared': pr, 'reader': spec})
        out[name] = ref(root, root / 'plans' / f'{name}.json')
    write_json(root / 'plans/check_refrel3_q4k.json', {'schema': 'axis4-plan-v1', 'prepared': pc,
                                                       'reader': specs['refrel3_q4k']})
    out['check_refrel3_q4k'] = ref(root, root / 'plans/check_refrel3_q4k.json')
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=str(WK / 'axis4n10'))
    ap.add_argument('step')
    ap.add_argument('arg', nargs='?')
    ap.add_argument('--agc-build', default=str(WK / 'agc_native_v020'))
    a = ap.parse_args()
    root = Path(a.root).resolve(strict=True)
    {'static': lambda: static(root), 'fasta': lambda: fasta(root, a.arg), 'fai': lambda: fai(root),
     'bgzf': lambda: bgzf(root, a.arg), 'zstd': lambda: zstd(root, a.arg),
     'agclib': lambda: agclib(root, a.agc_build), 'agc': lambda: agc(root, a.arg, a.agc_build),
     'plans': lambda: plans(root)}[a.step]()


if __name__ == '__main__':
    main()
