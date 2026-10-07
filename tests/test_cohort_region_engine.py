import hashlib,importlib.util,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
p=Path(__file__).resolve().parents[1]/'tools/cohort_region_engine.py';s=importlib.util.spec_from_file_location('cohort_engine',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class R:
 scope='cpu-in-process';decoder_threads=1
 def fetch(self,a,c,s,e):return b'A'*(e-s)
class W(SimpleNamespace):
 @property
 def length(self):return self.end0-self.start0
 def canonical(self):return {'assembly_id':self.assembly,'contig_id':self.contig,'start0':self.start0,'end0':self.end0,'convention':'0-based-half-open'}
class Test(unittest.TestCase):
 def plan(self):return [{a:W(assembly=a,contig='chr_'+a,start0=0,end0=8,sha256=hashlib.sha256(b'A'*8).hexdigest()) for a in ('a','b')} for _ in range(3)]
 def test_full_cohort_verified(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'archive';p.write_bytes(b'archive');ticks=iter(range(0,10000,100));summary,raw=m.run_cohort(R(),self.plan(),['a','b'],[p],clock=lambda:next(ticks))
  self.assertEqual(summary['verified'],6);self.assertEqual(len(raw),6);self.assertEqual(summary['stored_bytes'],7)
 def test_missing_assembly_refused(self):
  plan=self.plan();del plan[0]['b']
  with self.assertRaises(ValueError):m.run_cohort(R(),plan,['a','b'],[])
 def test_duplicate_storage_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'x';p.write_bytes(b'x')
   with self.assertRaises(ValueError):m.storage_bytes([p,p])
 def test_bad_output_suppresses_seconds(self):
  class Bad(R):
   def fetch(self,*args):return b'N'*8
  ticks=iter(range(0,10000,100));r,_=m.run_cohort(Bad(),self.plan(),['a','b'],[],clock=lambda:next(ticks));self.assertEqual(r['status'],'FAILED');self.assertIsNone(r['seconds'])
if __name__=='__main__':unittest.main()
