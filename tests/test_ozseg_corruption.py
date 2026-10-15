import argparse,copy,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from subprocess import CompletedProcess
P=Path(__file__).resolve().parents[1]/'review/axis3/openzl_segmented.py'
spec=importlib.util.spec_from_file_location('ozseg_qa',P);oz=importlib.util.module_from_spec(spec);spec.loader.exec_module(oz)
def mock_codec(argv,**kw):
    Path(argv[-1]).write_bytes(Path(argv[-2]).read_bytes());return CompletedProcess(argv,0,stdout='',stderr='')
class Test(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.arc=self.root/'good.ozseg';self.src=self.root/'src.fa'
        self.src.write_bytes(b'>chr\n'+b'ACGT'*40000+b'\n')
        with patch.object(oz.subprocess,'run',mock_codec):
            oz.build(argparse.Namespace(variant='l1_w64k',helper='mock',input=self.src,output=self.arc))
        f,self.meta,self.base=oz.read_container(self.arc);f.close();self.bytes=self.arc.read_bytes()
    def tearDown(self):self.tmp.cleanup()
    def check_refused(self,data):
        path=self.root/'bad';path.write_bytes(data)
        with self.assertRaises(ValueError):
            f,_,_=oz.read_container(path);f.close()
    def test_production_mock_roundtrip(self):
        out=self.root/'out'
        with patch.object(oz.subprocess,'run',mock_codec):oz.decode(argparse.Namespace(archive=self.arc,helper='mock',output=out))
        self.assertEqual(out.read_bytes(),b'ACGT'*40000)
    def test_truncated_header(self):
        for n in (0,7,8,15,47):
            with self.subTest(n=n):self.check_refused(self.bytes[:n])
    def test_truncated_table(self):self.check_refused(self.bytes[:self.base-1])
    def test_truncated_payload(self):self.check_refused(self.bytes[:-1])
    def test_wrong_table_checksum(self):
        b=bytearray(self.bytes);b[16]^=1;self.check_refused(bytes(b))
    def test_corrupted_table(self):
        b=bytearray(self.bytes);b[48]^=1;self.check_refused(bytes(b))
    def test_overlap_even_with_valid_checksum(self):
        meta=copy.deepcopy(self.meta);meta['frames'][1]['coff']=0
        path=self.root/'overlap';oz.write_container(path,json.dumps(meta).encode(),self.bytes[self.base:]);self.check_refused(path.read_bytes())
    def test_gap_even_with_valid_checksum(self):
        meta=copy.deepcopy(self.meta);meta['frames'][1]['uoff']+=1
        path=self.root/'gap';oz.write_container(path,json.dumps(meta).encode(),self.bytes[self.base:]);self.check_refused(path.read_bytes())
    def test_negative_length_even_with_valid_checksum(self):
        meta=copy.deepcopy(self.meta);meta['frames'][0]['clen']=-1
        path=self.root/'negative';oz.write_container(path,json.dumps(meta).encode(),self.bytes[self.base:]);self.check_refused(path.read_bytes())
    def test_trailing_garbage_refused(self):self.check_refused(self.bytes+b'x')
if __name__=='__main__':unittest.main()
