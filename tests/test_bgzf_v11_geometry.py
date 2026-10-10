"""A13b: BGZF canonical geometry under truth v1.1 comes from the BGZF archive and its .fai,
never from the compressed truth source. Pure Python: BGZF members are written here."""
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from review.axis3.verdict_readers import bgzf_canonical_sizes, bgzf_canonical_sizes_fai, fai_records


def bgzf_member(raw):
    comp = zlib.compressobj(6, zlib.DEFLATED, -15)
    body = comp.compress(raw) + comp.flush()
    size = 12 + 6 + len(body) + 8
    header = bytes.fromhex('1f8b0804') + b'\0\0\0\0' + b'\0\xff' + struct.pack('<H', 6)
    return header + b'BC' + struct.pack('<HH', 2, size - 1) + body + struct.pack('<II', zlib.crc32(raw), len(raw))


def write_bgzf(path, raw, step):
    with open(path, 'wb') as f:
        for i in range(0, len(raw), step):
            f.write(bgzf_member(raw[i:i + step]))
        f.write(bgzf_member(b''))


def fasta_and_fai(contigs, width):
    out, fai, offset = bytearray(), [], 0
    for name, seq in contigs:
        header = ('>' + name + ' desc\n').encode()
        out += header
        offset = len(out)
        for i in range(0, len(seq), width):
            out += seq[i:i + width].encode() + b'\n'
        fai.append(f'{name}\t{len(seq)}\t{offset}\t{width}\t{width + 1}')
    return bytes(out), '\n'.join(fai) + '\n'


def native_v11_exercise(libpath, root):
    """End-to-end truth v1.1 BGZF row with the real htslib shim: .fa.gz truth, BGZF + .fai/.gzi,
    prepare -> run (1 and 2 decoder threads) -> independent verify. Returns the verify results."""
    import ctypes, gzip, hashlib, json, shutil
    from review.axis3.bgzf_adapter import HTS_PIN
    from review.axis3.verdict_data import file_ref
    from tools import axis4
    root = Path(root)
    lib = root / 'libhwa_bgzf.so'
    shutil.copyfile(libpath, lib)
    native = ctypes.CDLL(str(lib))
    assemblies, archives = [], []
    for aid, seq in (('a', 'ACGTNacgtn' * 40), ('b', 'TTGCAGG' * 50)):
        fasta, _ = fasta_and_fai([('chr1', seq), ('chr2', seq[::-1][:77])], 60)
        (root / f'{aid}.fa.gz').write_bytes(gzip.compress(fasta, mtime=0))
        write_bgzf(root / f'{aid}.fa.bgz', fasta, 101)
        if native.hwa_bgzf_index(str(root / f'{aid}.fa.bgz').encode()) != 0:
            raise AssertionError('hwa_bgzf_index failed')
        assemblies.append({'assembly_id': aid, 'source_url': 'synthetic:unit-' + aid,
                           'fasta': file_ref(root, root / f'{aid}.fa.gz')})
        archives.append({'assembly_id': aid, 'archive': file_ref(root, root / f'{aid}.fa.bgz'),
                         'fai': file_ref(root, root / f'{aid}.fa.bgz.fai'),
                         'gzi': file_ref(root, root / f'{aid}.fa.bgz.gzi')})
    (root / 'cohort.json').write_text(json.dumps({'schema': 'axis4-corpus-v1.1', 'evidence_kind': 'synthetic',
                                                  'assemblies': assemblies}))
    groups = [{a: {'assembly_id': a, 'contig_id': c, 'start0': s, 'end0': e} for a in ('a', 'b')}
              for c, s, e in (('chr1', 0, 61), ('chr1', 59, 300), ('chr2', 3, 70))]
    (root / 'groups.json').write_text(json.dumps(groups))
    prepared = axis4.prepare(root, 'cohort.json', 'groups.json', 'prepared', truth_version='1.1')
    (root / 'build.json').write_text(json.dumps({
        'source_commit': HTS_PIN, 'codec_version': '1.24', 'compiler': 'unit', 'flags': ['-O3'],
        'dependencies': {'htslib': HTS_PIN}, 'library_sha256': hashlib.sha256(lib.read_bytes()).hexdigest(),
        'decoder_threads': 1}))
    plan = {'schema': 'axis4-plan-v1', 'prepared': prepared,
            'reader': {'family': 'bgzf', 'variant': 'default', 'library': file_ref(root, lib),
                       'build_receipt': file_ref(root, root / 'build.json'), 'archives': archives}}
    (root / 'plan.json').write_text(json.dumps(plan))
    results = []
    for out, threads in (('run1', None), ('run2', 2)):
        data = axis4.run(root, 'plan.json', out, decoder_threads=threads)
        if data['status'] != 'PASS':
            raise AssertionError(data['error'])
        results.append(axis4.verify(root / out / 'evidence.json', root, prepared['sha256']))
    return results


class TestBgzfTruthV11Geometry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        contigs = [('chrA', 'ACGTN' * 41 + 'acg'), ('chrB', 'TTGCA' * 17), ('chrC', 'G' * 61)]
        self.fasta, fai = fasta_and_fai(contigs, 60)
        (self.root / 'a.fa').write_bytes(self.fasta)
        write_bgzf(self.root / 'a.fa.bgz', self.fasta, 97)
        (self.root / 'a.fa.bgz.fai').write_text(fai)
        self.assembly = {'assembly_id': 'a', 'contigs': [{'contig_id': n, 'length': len(s)} for n, s in contigs]}

    def test_fai_geometry_equals_plain_fasta_geometry(self):
        old = bgzf_canonical_sizes(self.root / 'a.fa.bgz', self.root / 'a.fa', 'a')
        new = bgzf_canonical_sizes_fai(self.root / 'a.fa.bgz', self.root / 'a.fa.bgz.fai', self.assembly,
                                       len(self.fasta))
        self.assertEqual(new, old)
        self.assertEqual(sum(new), sum(c['length'] for c in self.assembly['contigs']))

    def test_fai_geometry_refuses_identity_and_size_mismatch(self):
        archive, fai = self.root / 'a.fa.bgz', self.root / 'a.fa.bgz.fai'
        with self.assertRaises(ValueError):
            bgzf_canonical_sizes_fai(archive, fai, self.assembly, len(self.fasta) + 1)
        swapped = {**self.assembly, 'contigs': list(reversed(self.assembly['contigs']))}
        with self.assertRaises(ValueError):
            bgzf_canonical_sizes_fai(archive, fai, swapped, len(self.fasta))
        shorter = {**self.assembly, 'contigs': self.assembly['contigs'][:2]}
        with self.assertRaises(ValueError):
            bgzf_canonical_sizes_fai(archive, fai, shorter, len(self.fasta))

    def test_fai_parser_refuses_duplicates_and_bad_widths(self):
        bad = self.root / 'bad.fai'
        bad.write_text('x\t10\t3\t60\t61\nx\t10\t20\t60\t61\n')
        with self.assertRaises(ValueError):
            fai_records(bad)
        bad.write_text('x\t10\t3\t61\t60\n')
        with self.assertRaises(ValueError):
            fai_records(bad)
        bad.write_text('x\t10\t3\n')
        with self.assertRaises(ValueError):
            fai_records(bad)


if __name__ == '__main__':
    unittest.main()
