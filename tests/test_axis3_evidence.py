import copy,hashlib,importlib.util,tempfile,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'tools/validate_axis3_evidence.py'
s=importlib.util.spec_from_file_location('validate_evidence',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        f=self.root/'fixture.txt';f.write_bytes(b'synthetic fixture, not measured')
        self.ref=dict(path='fixture.txt',bytes=f.stat().st_size,sha256=m.digest_file(f))
        self.row=dict(schema='axis3-evidence-v1',axis=3,kind='synthetic',run_id='unit-test',status='PASS',format='mock',variant='test',scope='cpu-in-process',threads=1,n_assemblies=4,window_bytes=1024,samples=10000,verified=10000,codec_commit='a'*40,protocol=self.ref,runbook=self.ref,corpus_manifest=self.ref,requests=self.ref,raw_logs=[self.ref],metrics=dict(stored_bytes=400,bytes_per_assembly=100,build_seconds=1,peak_rss_bytes=1000,p50_us=1,p95_us=2,p99_us=3,windows_per_second=100,Q_actual_bytes=4096),error=None)
        self.row.update(hardware=dict(machine_id='synthetic-only',cpu_model='mock',frequency_policy='mock'),build=dict(compiler='mock',flags=[],binary_sha256='b'*64,dependencies={'mock':'1'}),silence_gate=None)
    def tearDown(self):self.tmp.cleanup()
    def test_valid_synthetic_fixture(self):self.assertEqual(m.validate_record(self.row,self.root)['status'],'PASS')
    def test_hash_change_refused(self):
        (self.root/'fixture.txt').write_bytes(b'x')
        with self.assertRaises(ValueError):m.validate_record(self.row,self.root)
    def test_absolute_refused(self):
        r=copy.deepcopy(self.row);r['protocol']['path']='/tmp/x'
        with self.assertRaises(ValueError):m.validate_record(r,self.root)
    def test_traversal_refused(self):
        r=copy.deepcopy(self.row);r['protocol']['path']='../x'
        with self.assertRaises(ValueError):m.validate_record(r,self.root)
    def test_failed_cannot_retain_numbers(self):
        r=copy.deepcopy(self.row);r['status']='FAILED';r['error']='mismatch'
        with self.assertRaises(Exception):m.validate_record(r,self.root)
    def test_failed_record_without_numbers(self):
        r=copy.deepcopy(self.row);r.update(status='FAILED',metrics=None,error='mismatch',verified=0)
        self.assertEqual(m.validate_record(r,self.root)['status'],'FAILED')
    def test_incorrect_quantiles(self):
        r=copy.deepcopy(self.row);r['metrics']['p50_us']=9
        with self.assertRaises(ValueError):m.validate_record(r,self.root)
    def test_duplicate_key(self):
        with self.assertRaises(ValueError):m.loads('{"a":1,"a":2}')
    def test_nonfinite_json(self):
        with self.assertRaises(ValueError):m.loads('{"a":NaN}')
if __name__=='__main__':unittest.main()
