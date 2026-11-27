"""Pure native-format tests and isolated fake-process supervision tests.

The integration cases use only temporary task-owned locks and sleeping Python
fixtures. They never load TurboBench, a codec, the OVH lock or the corpus.
"""
from datetime import timedelta
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

SPEC=importlib.util.spec_from_file_location('tb_runner',Path(__file__).with_name('runner.py'))
R=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(R)


def native_row(config=None,**updates):
    config=config or R.configuration('aceapex_fast',1)
    level,param=('0','e0') if config['codec']=='bsc' else (config['level'],'?')
    row=dict(dataset='silesia.ref.tar',size=str(R.N),csize=str(R.KNOWN),dtime='0.234567',ctime='1.234567',
        codec=config['codec'],level=level,param=param,cmem='0',dmem='0',cstack='0',dstack='0',time='2026-11-27.22:00:00',err='')
    row.update(updates)
    return (R.HEADER+'\n'+'\t'.join(row[k] for k in R.HEADER.split('\t'))+'\n').encode()


class NativeFormat(unittest.TestCase):
    def test_roundtrip_native_seconds_and_no_rounding(self):
        row=R.parse_tbb(native_row(),R.configuration('aceapex_fast',1))
        self.assertEqual(row['ctime_seconds'],'1.234567');self.assertEqual(row['dtime_seconds'],'0.234567')
        self.assertEqual(row['compressed_bytes'],R.KNOWN);self.assertTrue(row['roundtrip'])

    def test_freshness_and_error_fail_closed(self):
        for raw in (native_row(err='1'),native_row(size='211947519'),native_row(codec='aceapex'),
                    native_row(ctime='0.000000'),native_row(dtime='1.2'),native_row(param='t2'),
                    native_row()+native_row().split(b'\n',1)[1],b'size,csize,ratio,ctime,dtime,name,file\n'):
            with self.assertRaises(ValueError):R.parse_tbb(raw,R.configuration('aceapex_fast',1))

    def test_bsc_parameter_is_not_a_level_alias(self):
        c=R.configuration('bsc','0e0');self.assertEqual(R.parse_tbb(native_row(c),c)['native']['param'],'e0')
        with self.assertRaises(ValueError):R.parse_tbb(native_row(c,param='?'),c)

    def test_supported_grid_and_prespecified_three_orders(self):
        grid=R.canonical_grid();self.assertEqual(len(grid),50);self.assertEqual(len({c['id'] for c in grid}),50)
        ids=[x['id'] for x in grid]
        self.assertEqual([c['id'] for c in R.execution_order(grid,2)],ids[::-1])
        self.assertEqual([c['id'] for c in R.execution_order(grid,3)],ids[25:]+ids[:25])
        with self.assertRaises(ValueError):R.configuration('aceapex_fast',9)

    def test_native_argv_one_roundtrip_byte_check_and_priority(self):
        command=R.native_command('/binary',R.configuration('aceapex_fast',1))
        for flag in ('-i0,0','-C3','-D','-b1073741824B','-B211947520B'):self.assertIn(flag,command)
        self.assertNotIn('-p7',command);self.assertNotIn('-K',command)
        self.assertEqual(command[:3],['taskset','-c','0'])

    def test_deadline_and_synthetic_escape_guard(self):
        self.assertFalse(R.utc_deadline(R.stamp(R.POLICY['refuse'])-timedelta(microseconds=1)))
        self.assertTrue(R.utc_deadline(R.stamp(R.POLICY['refuse'])))
        with self.assertRaises(ValueError):R.request_policy(dict(synthetic=True,lock=R.LOCK,policy=R.POLICY))

    def test_exact_admission_thresholds_use_pure_original_helper(self):
        helper=R.observer();boundary=lambda value:dict(loadavg_raw=value+' 0.0 0.0 1/1 1')
        self.assertFalse(helper.loaded(boundary('2.0'),boundary('2.0'),dict(exceeded=[])))
        self.assertTrue(helper.loaded(boundary('2.01'),boundary('0.5'),dict(exceeded=[])))
        self.assertTrue(helper.loaded(boundary('0.5'),boundary('0.5'),dict(exceeded=[dict(pid=123)])))
        self.assertFalse(helper.foreign_exceeds(10,100,1000000000))
        self.assertTrue(helper.foreign_exceeds(11,100,1000000000))


@unittest.skipUnless(sys.platform=='linux' and shutil.which('flock'),'Linux temporary-lock supervision only')
class OwnedSupervision(unittest.TestCase):
    def make_request(self,folder,command,seconds=.8):
        now=R.utc();policy={key:(now+timedelta(seconds=value)).isoformat() for key,value in
            [('refuse',30),('term',seconds),('kill',seconds+.4),('release',seconds+3)]}
        # Refuse follows now but must precede TERM, just as in the real policy.
        policy['refuse']=(now+timedelta(seconds=.1)).isoformat()
        request=dict(synthetic=True,lock=str(folder/'temporary-test.lock'),policy=policy,folder=str(folder),command=command)
        path=folder/'request.json';path.write_text(json.dumps(request));return path

    def launch(self,path):
        return subprocess.Popen([sys.executable,'-B',str(Path(R.__file__)), '_session',str(path)],start_new_session=True,
            env=dict(os.environ,TB_LVL_0_ALLOW_SYNTHETIC_TESTS='1'),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)

    def assert_released(self,proc,lock):
        proc.wait(timeout=6)
        self.assertFalse(any(p['state']!='Z' for p in R.group_members(proc.pid)))
        check=subprocess.run(['flock','-n',str(lock),'true'],capture_output=True)
        self.assertEqual(check.returncode,0,check.stderr)

    def test_ignoring_worker_is_killed_and_lock_released(self):
        R.STATE.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=R.STATE) as td:
            f=Path(td);command=[sys.executable,'-c','import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)']
            request=self.make_request(f,command);proc=self.launch(request)
            try:self.assert_released(proc,f/'temporary-test.lock')
            finally:
                if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()

    def test_waiting_flock_cannot_start_after_deadline(self):
        import fcntl
        R.STATE.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=R.STATE) as td:
            f=Path(td);lock=f/'temporary-test.lock';marker=f/'must-not-start'
            with lock.open('a') as held:
                fcntl.flock(held,fcntl.LOCK_EX)
                request=self.make_request(f,[sys.executable,'-c',f'from pathlib import Path;Path({str(marker)!r}).write_text("bad")'])
                proc=self.launch(request)
                try:proc.wait(timeout=6);self.assertFalse(marker.exists())
                finally:
                    if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
            self.assert_released(proc,lock);self.assertFalse(marker.exists())

    def test_session_parent_loss_kills_owned_child_group(self):
        R.STATE.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=R.STATE) as td:
            f=Path(td);marker=f/'started'
            request=self.make_request(f,[sys.executable,'-c',f'import time;from pathlib import Path;Path({str(marker)!r}).write_text("yes");time.sleep(30)'],seconds=15)
            proc=self.launch(request)
            try:
                for _ in range(150):
                    if marker.exists():break
                    if proc.poll() is not None:self.fail('synthetic session exited before starting fixture')
                    time.sleep(.02)
                self.assertTrue(marker.exists());proc.kill();proc.wait(timeout=2)
                for _ in range(100):
                    if not any(p['state']!='Z' for p in R.group_members(proc.pid)):break
                    time.sleep(.02)
                self.assert_released(proc,f/'temporary-test.lock')
            finally:
                if any(p['state']!='Z' for p in R.group_members(proc.pid)):os.killpg(proc.pid,signal.SIGKILL)


if __name__=='__main__':unittest.main()
