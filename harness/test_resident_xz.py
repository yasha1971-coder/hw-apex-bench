"""Small native correctness tests, no timing collection or historical row writes."""
import os
from pathlib import Path
import random
import subprocess
import tempfile
import unittest
from resident_probe import Context, capabilities, probe

ROOT=Path(__file__).resolve().parents[1]
LIB=os.environ.get('HB_CONTEXT_LIBRARY')

class Capabilities(unittest.TestCase):
    def test_exhaustive_reasons_from_each_adapter(self):
        for adapter in (ROOT/'codecs').glob('*.sh'):
            with self.subTest(adapter=adapter.name):
                axes=capabilities(adapter)
                self.assertEqual(axes['region'],'available')
                self.assertEqual(axes['decode'],'available')

@unittest.skipUnless(LIB, 'set HB_CONTEXT_LIBRARY to the built xz context library')
class XzContext(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()
    def archive(self,data,g):
        source=self.root/'input'; target=self.root/'archive.xz'
        source.write_bytes(data)
        subprocess.run(['bash',str(ROOT/'codecs/xz.sh'),'compress',str(source),str(target),str(g)],check=True)
        return source,target
    def test_five_granularities_and_single_block(self):
        data=random.Random(332).randbytes(65539)+b'ACGT'*120000
        for g in (4096,16384,65536,262144,1048576,len(data)):
            with self.subTest(g=g):
                source,target=self.archive(data,g)
                listing=subprocess.check_output(['xz','--robot','-lv',str(target)],text=True)
                blocks=[s.split('\t') for s in listing.splitlines() if s.startswith('block\t')]
                sizes=[int(s[7]) for s in blocks]
                self.assertEqual(sizes,[min(g,len(data)-p) for p in range(0,len(data),g)])
                result=probe(LIB,target,source,g)
                self.assertEqual(result['full_restore'],'byte-exact')
                self.assertFalse(result['timings_collected'])
    def test_empty_one_byte_and_exact_block(self):
        for data in (b'',b'X',bytes(range(256))*64):
            with self.subTest(size=len(data)):
                source,target=self.archive(data,16384)
                probe(LIB,target,source,16384)
    def test_footer_index_header_truncation_and_wrong_size(self):
        data=b'ACGT'*20000
        _,target=self.archive(data,16384); original=target.read_bytes()
        variants=[original[:-1],original+b'\0'*4,original+original]
        for pos in (0,len(original)-1,len(original)-13):
            v=bytearray(original); v[pos]^=1; variants.append(bytes(v))
        for bad in variants:
            with self.subTest(bytes=len(bad)):
                with self.assertRaisesRegex(ValueError,'rejected'):
                    Context(LIB,bad,len(data))
        with self.assertRaises(ValueError): Context(LIB,original,len(data)+1)
    def test_block_damage_rejected_by_decode(self):
        data=random.Random(55).randbytes(70000)
        _,target=self.archive(data,16384); damaged=bytearray(target.read_bytes())
        damaged[100]^=1
        ctx=Context(LIB,bytes(damaged),len(data))
        try: self.assertLess(ctx.region(0,16384)[0],0)
        finally: ctx.close()
    def test_two_contexts_and_archive_removed_after_open(self):
        _,target=self.archive(b'A'*40000,4096)
        first=Context(LIB,target.read_bytes(),40000)
        _,target=self.archive(b'B'*40000,4096)
        second=Context(LIB,target.read_bytes(),40000)
        target.unlink()
        try:
            for ctx,byte in ((first,b'A'),(second,b'B'),(first,b'A')):
                n,data=ctx.region(4095,20000)
                self.assertEqual((n,data),(20000,byte*20000))
        finally:
            first.close(); second.close()

if __name__=='__main__': unittest.main()
