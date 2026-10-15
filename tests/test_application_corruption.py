import hashlib,importlib.util,sys,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'tools/application_corruption.py'
s=importlib.util.spec_from_file_location('corruption',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.arc=self.root/'a';self.out=self.root/'o';self.arc.write_bytes(b'ACGTACGT');self.sha=m.sha256(self.arc)
    def tearDown(self):self.tmp.cleanup()
    def once(self,script,timeout=10):
        return m.decode_once([sys.executable,'-c',script,'{archive}','{output}'],self.arc,self.out,truth_sha256=self.sha,truth_bytes=8,timeout=timeout)
    def test_deterministic_100_positions(self):
        self.assertEqual(m.plan(5000),m.plan(5000));self.assertEqual(len(m.plan(5000)),100)
        self.assertTrue(all(0<=x['offset']<5000 and 0<=x['bit']<8 for x in m.plan(5000)))
    def test_same_normalized_bits(self):self.assertEqual([x['bit'] for x in m.plan(100)],[x['bit'] for x in m.plan(10000)])
    def test_harmless(self):self.assertEqual(self.once('import shutil,sys;shutil.copyfile(sys.argv[1],sys.argv[2])')['outcome'],'harmless')
    def test_silent(self):self.assertEqual(self.once('import pathlib,sys;pathlib.Path(sys.argv[2]).write_bytes(b"N")')['outcome'],'SILENT')
    def test_caught(self):self.assertEqual(self.once('raise SystemExit(2)')['outcome'],'caught')
    def test_crash(self):self.assertEqual(self.once('import os,signal;os.kill(os.getpid(),signal.SIGTERM)')['outcome'],'crash')
    def test_watchdog(self):self.assertEqual(self.once('import time;time.sleep(10)',timeout=.05)['outcome'],'hang')
    def test_immutable_production_probe(self):
        argv=[sys.executable,'-c','import shutil,sys;shutil.copyfile(sys.argv[1],sys.argv[2])','{archive}','{output}']
        rows=m.run_probes(argv,self.arc,self.arc,count=3)
        self.assertEqual(len(rows),3);self.assertTrue(all(r['outcome']=='SILENT' for r in rows));self.assertEqual(m.sha256(self.arc),self.sha)
if __name__=='__main__':unittest.main()
