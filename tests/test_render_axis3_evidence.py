import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
T=Path(__file__).resolve().parents[1]/'tools';sys.path.insert(0,str(T))
import render_axis3_evidence as m
class Test(unittest.TestCase):
    def row(self):return dict(format='test',variant='v',status='PASS',kind='synthetic',scope='cpu-in-process',hardware={'machine_id':'mock'},protocol={'sha256':'p'},runbook={'sha256':'r'},corpus_manifest={'sha256':'c'},requests={'sha256':'q'},window_bytes=1024,n_assemblies=4,samples=2,metrics=dict(bytes_per_assembly=100,p50_us=1,p95_us=2,p99_us=2,windows_per_second=2e9/3000),raw_logs=[{'path':'raw.jsonl','sha256':'a'*64}])
    def test_recompute_from_raw(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'raw.jsonl';p.write_text('\n'.join(json.dumps(dict(request_id=i,status='PASS',expected_sha256='x',observed_sha256='x',returned_bytes=1024,elapsed_ns=n)) for i,n in enumerate((1000,2000))))
            r=m.recompute(self.row(),Path(td));self.assertEqual(r['metrics']['p50_us'],1)
    def test_reject_invented_summary(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'raw.jsonl';p.write_text('\n'.join(json.dumps(dict(request_id=i,status='PASS',expected_sha256='x',observed_sha256='x',returned_bytes=1024,elapsed_ns=n)) for i,n in enumerate((1000,2000))))
            r=self.row();r['metrics']['p50_us']=7
            with self.assertRaises(ValueError):m.recompute(r,Path(td))
    def test_report_has_required_provenance_and_loss_section(self):
        text=m.render([self.row()],'BGZF')
        self.assertIn('Where we lose',text);self.assertIn('a'*64,text);self.assertIn('synthetic',text)
if __name__=='__main__':unittest.main()
