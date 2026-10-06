import importlib.util,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def module(name):
    s=importlib.util.spec_from_file_location(name,ROOT/'tools'/f'{name}.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=module('run_contract');gate=module('silence_contract')
class Tests(unittest.TestCase):
    def test_freeze_verify_and_no_silent_rewrite(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);inputs={k:k+'.txt' for k in ('protocol','runbook','corpus_manifest','requests')}
            for k,p in inputs.items():(root/p).write_text(k)
            out=root/'lock.json';m.freeze(root,inputs,out);m.verify(root,out);m.freeze(root,inputs,out)
            (root/'protocol.txt').write_text('changed')
            with self.assertRaises(ValueError):m.verify(root,out)
            with self.assertRaises(ValueError):m.freeze(root,inputs,out)
    def test_no_absolute_paths(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):m.file_ref(Path(td),'/tmp/example')
    def snapshot(self):return dict(host='ace-core',load1=.49,disk_available_bytes=20000000001,sampling_seconds=1,processes=[])
    def test_quiet(self):self.assertEqual(gate.judge(self.snapshot())['status'],'PASS')
    def test_load_boundary_refused(self):
        s=self.snapshot();s['load1']=.5;self.assertEqual(gate.judge(s)['status'],'FAILED')
    def test_disk_boundary_refused(self):
        s=self.snapshot();s['disk_available_bytes']=20000000000;self.assertEqual(gate.judge(s)['status'],'FAILED')
    def test_wrong_host_refused(self):
        s=self.snapshot();s['host']='github-runner';self.assertEqual(gate.judge(s)['status'],'FAILED')
    def test_foreign_process_refused(self):
        s=self.snapshot();s['processes']=[dict(cpu_percent=10,own_process=False)];self.assertEqual(gate.judge(s)['status'],'FAILED')
    def test_short_sampling_refused(self):
        s=self.snapshot();s['sampling_seconds']=.1;self.assertEqual(gate.judge(s)['status'],'FAILED')
if __name__=='__main__':unittest.main()
