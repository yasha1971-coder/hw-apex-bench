import importlib.util,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'tools/window_law.py';s=importlib.util.spec_from_file_location('w',P);w=importlib.util.module_from_spec(s);s.loader.exec_module(w)
class Test(unittest.TestCase):
 def test_c0_independent_probe(self):
  r=w.diagnose(1_000_000,1024,100,1123,200);self.assertEqual(r['c0_us'],100);self.assertEqual(r['primary_predicted_p50_us'],1223)
 def test_secondary_printed(self):self.assertEqual(w.diagnose(1_000_000,1024,100,1123,200)['secondary_predicted_p50_us'],1123)
 def test_negative_c0_fails(self):self.assertEqual(w.diagnose(1_000_000,1024,100,1023,50)['verdict'],'FAIL')
 def test_plus20_inclusive(self):self.assertEqual(w.diagnose(1_000_000,1024,100,'1467.6',200)['verdict'],'PASS')
 def test_minus20_inclusive(self):self.assertEqual(w.diagnose(1_000_000,1024,100,'978.4',200)['verdict'],'PASS')
 def test_above20_fails(self):self.assertEqual(w.diagnose(1_000_000,1024,100,'1467.6001',200)['verdict'],'FAIL')
 def test_w1_not_verdict(self):self.assertFalse(w.diagnose(1_000_000,1,100,200,200)['w1_in_verdict_set'])
 def test_no_fitting(self):self.assertFalse(w.diagnose(1_000_000,8192,100,8291,200)['coefficient_fitting'])
 def test_scope(self):
  with self.assertRaises(ValueError):w.process_record(dict(D_Q_Bps=1,W_bytes=1,Q_bytes=1,measured_p50_us=1,probe_w1_p50_us=1,scope='cli'))
 def test_threads(self):
  with self.assertRaises(ValueError):w.process_record(dict(D_Q_Bps=1,W_bytes=1,Q_bytes=1,measured_p50_us=1,probe_w1_p50_us=1,threads=2))
 def test_bad_numbers(self):
  for x in (0,-1,True,'NaN','Infinity'):
   with self.assertRaises(ValueError):w.diagnose(x,1024,100,100,100)
 def test_models_differ_by_c0(self):
  r=w.diagnose(1_000_000,65536,100,65635,200);self.assertEqual(r['primary_predicted_p50_us']-r['secondary_predicted_p50_us'],100)
 def test_primary_controls_verdict(self):
  r=w.diagnose(1_000_000,1024,100,1123,200);self.assertEqual(r['verdict'],'PASS')
 def test_probe_not_derived_from_windows(self):
  a=w.diagnose(1_000_000,1024,100,1123,200);b=w.diagnose(1_000_000,1024,100,1123,300);self.assertNotEqual(a['c0_us'],b['c0_us'])
 def test_exact_q_term(self):self.assertEqual(w.diagnose(1_000_000,1024,100,1123,200)['c0_us'],100)
 def test_schema_v2(self):self.assertEqual(w.diagnose(1_000_000,1024,100,1123,200)['schema'],'window-law-diagnostic-v2')
if __name__=='__main__':unittest.main()
