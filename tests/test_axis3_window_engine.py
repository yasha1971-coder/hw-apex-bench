import hashlib,importlib.util,sys,unittest
from pathlib import Path
from dataclasses import replace
p=Path(__file__).resolve().parents[1]/'tools/axis3_window_engine.py'
s=importlib.util.spec_from_file_location('window_engine',p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
class Truth:
    scope='cpu-in-process';decoder_threads=1
    def fetch(self,a,c,s,e):
        seq=b'ACGT'*20000
        if not 1<=s<=e<=len(seq):raise ValueError('bounds')
        return seq[s-1:e]
class Tests(unittest.TestCase):
    def requests(self):return m.freeze_windows(m.sample_coordinates([('a','chr',80000)],1024,count=10),Truth())
    def clock(self):
        values=iter(range(0,100000000,1000));return lambda:next(values)
    def test_deterministic_coordinates(self):
        x=[('a','chr',80000),('b','chr',90000)]
        self.assertEqual(m.sample_coordinates(x,8192),m.sample_coordinates(x,8192))
    def test_official_count(self):self.assertEqual(len(m.sample_coordinates([('a','chr',65536)],65536)),10000)
    def test_no_eligible_contigs(self):
        with self.assertRaises(ValueError):m.sample_coordinates([('a','empty',0)],1024)
    def test_bounds_generation(self):
        for _,a,c,s,e in m.sample_coordinates([('a','chr',8192)],8192,count=20):self.assertEqual((s,e),(1,8192))
    def test_duplicate_contig(self):
        with self.assertRaises(ValueError):m.sample_coordinates([('a','chr',80000)]*2,1024)
    def test_all_sha_checked(self):
        summary,raw=m.run_windows(Truth(),self.requests(),expected_count=10,clock=self.clock())
        self.assertEqual(summary['status'],'PASS');self.assertEqual(summary['verified'],10)
        self.assertTrue(all(r['expected_sha256']==r['observed_sha256'] for r in raw))
        self.assertEqual(summary['p50_us'],1)
    def test_mismatch_suppresses_timing(self):
        class Bad(Truth):
            def fetch(self,*args):return b'N'*1024
        summary,raw=m.run_windows(Bad(),self.requests(),expected_count=10,clock=self.clock())
        self.assertEqual(summary['status'],'FAILED');self.assertIsNone(summary['windows_per_second'])
    def test_scope_mismatch_rejected(self):
        r=Truth();r.scope='cli'
        with self.assertRaises(ValueError):m.run_windows(r,self.requests(),expected_count=10)
    def test_wrong_count_rejected(self):
        with self.assertRaises(ValueError):m.run_windows(Truth(),self.requests())
    def test_short_read(self):
        class Short(Truth):
            def fetch(self,*args):return b'A'
        r,_=m.run_windows(Short(),self.requests(),expected_count=10,clock=self.clock());self.assertEqual(r['status'],'FAILED')
if __name__=='__main__':unittest.main()
