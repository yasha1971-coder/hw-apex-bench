import importlib.util,tempfile,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'review/axis3/q3_plan.py'
s=importlib.util.spec_from_file_location('q3_plan',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Q3PlanTests(unittest.TestCase):
 def test_target_over_limit(self):self.assertGreater(m.BASES,1717986918)
 def test_small_stream_exact(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.fa';m.generate(p,16);self.assertEqual(p.read_bytes(),b'>q3_synthetic\nACGTACGTACGTACGT\n')
 def test_no_overwrite(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.fa';m.generate(p,4)
   with self.assertRaises(FileExistsError):m.generate(p,4)
 def test_bad_length(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):m.generate(Path(d)/'x',5)
