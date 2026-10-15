import argparse,importlib.util,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from subprocess import CompletedProcess
P=Path(__file__).resolve().parents[1]/'review/axis3/openzl_segmented.py'
spec=importlib.util.spec_from_file_location('ozseg_boundary',P);oz=importlib.util.module_from_spec(spec);spec.loader.exec_module(oz)
def codec(argv,**kw):
    Path(argv[-1]).write_bytes(Path(argv[-2]).read_bytes());return CompletedProcess(argv,0,stdout='',stderr='')
class Test(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.arc=self.root/'x'
        self.a=b'A'*65530+b'CGTACGTACGTACGT';self.b=b'T'*65545
        src=self.root/'in.fa';src.write_bytes(b'>a\n'+self.a+b'\n>empty\n>b\n'+self.b+b'\n')
        with patch.object(oz.subprocess,'run',codec):oz.build(argparse.Namespace(variant='l1_w64k',helper='mock',input=src,output=self.arc))
    def tearDown(self):self.tmp.cleanup()
    def fetch(self,region,short_write=False):
        output=bytearray()
        def write(fd,data):
            n=min(17,len(data)) if short_write else len(data)
            output.extend(data[:n]);return n
        with patch.object(oz.subprocess,'run',codec),patch.object(oz.os,'write',write):
            oz.fetch(argparse.Namespace(archive=self.arc,helper='mock',region=region))
        return bytes(output)
    def test_start_and_end(self):
        self.assertEqual(self.fetch('a:1-1'),b'A');self.assertEqual(self.fetch(f'a:{len(self.a)}-{len(self.a)}'),self.a[-1:])
    def test_cross_frame(self):self.assertEqual(self.fetch('a:65531-65545'),self.a[65530:65545])
    def test_second_contig(self):self.assertEqual(self.fetch('b:1-1024'),self.b[:1024])
    def test_empty_rejected(self):
        with self.assertRaises(ValueError):self.fetch('empty:1-1')
    def test_window_cannot_spill_to_next_contig(self):
        with self.assertRaises(ValueError):self.fetch(f'a:1-{len(self.a)+1}')
    def test_reverse_rejected(self):
        with self.assertRaises(ValueError):self.fetch('a:10-9')
    def test_zero_start_rejected(self):
        with self.assertRaises(ValueError):self.fetch('a:0-10')
    def test_short_os_write_completed(self):self.assertEqual(self.fetch('b:1-1024',True),self.b[:1024])
if __name__=='__main__':unittest.main()
