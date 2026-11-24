"""OVH lock/receipt contracts with mocked commands, no real measurements."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('gift1b_ovh', Path(__file__).with_name('ovh_bench.py'))
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def observation(load):
    return dict(timestamp_utc='2026-11-24T18:00:00+00:00', date_u='synthetic UTC',
                loadavg_raw=load + ' 0.01 0.01 1/100 123', nproc=16)


class OVHTests(unittest.TestCase):
    def test_threshold_one_is_included_and_above_one_is_loaded(self):
        self.assertFalse(bench.is_loaded(observation('1.00'), observation('0.99')))
        self.assertTrue(bench.is_loaded(observation('1.01'), observation('0.99')))
        self.assertTrue(bench.is_loaded(observation('0.99'), observation('1.000001')))

    def test_invalid_load_is_rejected(self):
        for value in ('NaN', 'Infinity', '-0.1'):
            with self.assertRaises(ValueError):
                bench.load_one(value)

    def inside(self, start, end, child_code=0):
        with tempfile.TemporaryDirectory(prefix='gift1b-ovh-test-') as directory:
            receipt = Path(directory) / 'receipt.json'
            receipt.write_bytes(bench.packed(dict(status='WAITING', command=['synthetic'], lock_path=bench.LOCK_PATH)))
            result = SimpleNamespace(returncode=child_code, stdout=b'synthetic raw output', stderr=b'')
            with patch.object(bench, '_assert_flock_parent'), patch.object(bench, 'boundary', side_effect=[observation(start), observation(end)]), patch.object(bench.subprocess, 'check_output', return_value=' PID USER %CPU COMMAND\n 1 synthetic 0.0 process\n') as ps, patch.object(bench.subprocess, 'run', return_value=result) as command:
                code = bench._inside(receipt, ['synthetic'])
                if start == '1.01' or (end == '1.01' and child_code == 0):
                    ps.assert_called_once_with(['bash', '-c', 'ps -eo pid,user,pcpu,comm --sort=-pcpu | head -8'], text=True)
            return code, json.loads(receipt.read_bytes()), command.call_count, Path(str(receipt) + '.stdout').read_bytes()

    def test_loaded_start_never_runs_the_measurement(self):
        code, receipt, calls, output = self.inside('1.01', '0.99')
        self.assertEqual((code, receipt['status'], calls, output), (77, 'LOADED', 0, b''))

    def test_loaded_end_retains_raw_output(self):
        code, receipt, calls, output = self.inside('0.99', '1.01')
        self.assertEqual((code, receipt['status'], calls), (77, 'LOADED', 1))
        self.assertEqual(output, b'synthetic raw output')

    def test_clean_at_boundary_and_child_failure(self):
        self.assertEqual(self.inside('1.00', '1.00')[:1], (0,))
        code, receipt, _, _ = self.inside('0.99', '0.99', 4)
        self.assertEqual((code, receipt['status']), (4, 'ERROR'))
        code, receipt, _, _ = self.inside('0.99', '1.10', 4)
        self.assertEqual((code, receipt['status']), (4, 'ERROR'))

    def test_cached_clean_output_is_not_timed_again(self):
        with tempfile.TemporaryDirectory(prefix='gift1b-ovh-test-') as directory:
            receipt = Path(directory) / 'receipt.json'
            output, errors = b'saved output', b''
            Path(str(receipt) + '.stdout').write_bytes(output)
            Path(str(receipt) + '.stderr').write_bytes(errors)
            receipt.write_bytes(bench.packed(dict(status='CLEAN', command=['synthetic'], helper_sha256=bench.sha(Path(bench.__file__).read_bytes()), stdout_sha256=bench.sha(output), stderr_sha256=bench.sha(errors))))
            with patch.object(bench.sys, 'platform', 'linux'), patch.object(bench.subprocess, 'run') as command:
                self.assertEqual(bench.run_locked(['synthetic'], receipt, Path(directory) / 'output'), 0)
                command.assert_not_called()

    def test_only_blocking_shared_flock_invocation_is_used(self):
        with tempfile.TemporaryDirectory(prefix='gift1b-ovh-test-') as directory:
            receipt = Path(directory) / 'receipt.json'
            def complete(invocation, **kwargs):
                self.assertEqual(invocation[:2], ['flock', '/run/lock/ovh-bench.lock'])
                self.assertNotIn('-n', invocation[:2])
                record = json.loads(receipt.read_bytes())
                record.update(status='CLEAN', returncode=0, stdout_sha256=bench.sha(b''), stderr_sha256=bench.sha(b''))
                receipt.write_bytes(bench.packed(record))
                Path(str(receipt) + '.stdout').write_bytes(b'')
                Path(str(receipt) + '.stderr').write_bytes(b'')
                return SimpleNamespace(returncode=0)
            with patch.object(bench.sys, 'platform', 'linux'), patch.object(bench.subprocess, 'run', side_effect=complete):
                self.assertEqual(bench.run_locked(['synthetic'], receipt, Path(directory) / 'output'), 0)

    def test_cli_preserves_worker_options_after_separator(self):
        args = ['ovh_bench.py', '_inside', '--receipt', 'receipt.json', '--', 'python', '-E', '-B', 'worker.py']
        with patch.object(bench.sys, 'argv', args), patch.object(bench, '_inside', return_value=0) as inside:
            self.assertEqual(bench.main(), 0)
            inside.assert_called_once_with(Path('receipt.json'), ['python', '-E', '-B', 'worker.py'])


if __name__ == '__main__':
    unittest.main()
