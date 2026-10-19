#!/usr/bin/env python3
import importlib.util, pathlib, tempfile, unittest, json
P=pathlib.Path(__file__).with_name("corruption.py")
S=importlib.util.spec_from_file_location("corruption",P); M=importlib.util.module_from_spec(S); S.loader.exec_module(M)
class T(unittest.TestCase):
    def test_balance_and_determinism(self):
        ks=[M.mutation_plan(i,100000)[0] for i in range(10000)]
        counts={k:ks.count(k) for k in M.KINDS}
        self.assertLessEqual(max(counts.values())-min(counts.values()),1)
        self.assertEqual(M.mutation_plan(123,100000),M.mutation_plan(123,100000))
    def test_bounds(self):
        for i in range(10000):
            _,p,n,_=M.mutation_plan(i,4096)
            self.assertGreaterEqual(p,0); self.assertLess(p,4096); self.assertGreaterEqual(n,1)
    def test_prepare_exists_and_runs(self):
        with tempfile.TemporaryDirectory() as td:
            td=pathlib.Path(td); src=td/"in"; arc=td/"arc"; src.write_bytes(b"abc")
            adapter={"compress":["cp","{input}","{archive}"],"version":"fixture"}
            self.assertEqual(M.prepare(adapter,src,arc),"fixture")
            self.assertEqual(arc.read_bytes(),b"abc")
if __name__=="__main__": unittest.main()
