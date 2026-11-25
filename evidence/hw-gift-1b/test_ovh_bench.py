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
                loadavg_raw=load + ' 0.01 0.01 1/100 123', nproc=16,
                proc_stat_raw='cpu0 10 0 3 50 0 0 0 0 0 0\ncpu1 20 0 3 40 0 0 0 0 0 0\n',
                proc_stat_error=None)


class OVHTests(unittest.TestCase):
    def test_threshold_two_is_included_and_above_two_is_loaded(self):
        self.assertFalse(bench.is_loaded(observation('2.00'), observation('1.08')))
        self.assertTrue(bench.is_loaded(observation('2.01'), observation('0.99')))
        self.assertTrue(bench.is_loaded(observation('0.99'), observation('2.00000000000000000001')))

    def test_proc_stat_delta_excludes_pinned_cpu_and_guest_double_count(self):
        first, last = observation('0.5'), observation('0.5')
        last['proc_stat_raw'] = 'cpu0 1000 0 30 50 0 0 0 0 0 0\ncpu1 25 1 5 47 3 1 1 2 4 1\n'
        result = bench.other_cpu_delta(first, last)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(set(result['cpus']), {'cpu1'})
        self.assertEqual(result['cpus']['cpu1'], dict(total_jiffies=22, busy_jiffies=12,
                         idle_jiffies=7, iowait_jiffies=3, busy_percent=100.0*12/22))

    def test_proc_stat_missing_or_regressing_is_observational(self):
        first, last = observation('1.08'), observation('1.08')
        last['proc_stat_raw'] = None
        self.assertEqual(bench.other_cpu_delta(first, last)['status'], 'unavailable')
        last['proc_stat_raw'] = 'cpu0 1 0 0 0 0 0 0 0\ncpu1 1 0 0 0 0 0 0 0\n'
        self.assertEqual(bench.other_cpu_delta(first, last)['status'], 'unavailable')
        self.assertFalse(bench.is_loaded(first, last))

    def test_cpu_observation_never_changes_a_clean_load_decision(self):
        observations = [dict(status='unavailable', pinned_core=0, cpus={}, error='synthetic read error'),
                        dict(status='ok', pinned_core=0, cpus={'cpu1': dict(total_jiffies=10,
                             busy_jiffies=10, idle_jiffies=0, iowait_jiffies=0, busy_percent=100.0)})]
        for delta in observations:
            with patch.object(bench, 'other_cpu_delta', return_value=delta):
                code, receipt, calls, _ = self.inside('1.08', '1.08')
            self.assertEqual((code, receipt['status'], calls), (0, 'CLEAN', 1))
            self.assertEqual(receipt['start']['other_cpu_delta'], delta)

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
                if start == '2.01' or (end == '2.01' and child_code == 0):
                    ps.assert_called_once_with(['bash', '-c', 'ps -eo pid,user,pcpu,comm --sort=-pcpu | head -8'], text=True)
            return code, json.loads(receipt.read_bytes()), command.call_count, Path(str(receipt) + '.stdout').read_bytes()

    def test_loaded_start_never_runs_the_measurement(self):
        code, receipt, calls, output = self.inside('2.01', '0.99')
        self.assertEqual((code, receipt['status'], calls, output), (77, 'LOADED', 0, b''))

    def test_loaded_end_retains_raw_output(self):
        code, receipt, calls, output = self.inside('0.99', '2.01')
        self.assertEqual((code, receipt['status'], calls), (77, 'LOADED', 1))
        self.assertEqual(output, b'synthetic raw output')

    def test_clean_at_boundary_and_child_failure(self):
        code, receipt, calls, _ = self.inside('2.00', '2.00')
        self.assertEqual((code, receipt['status'], calls), (0, 'CLEAN', 1))
        self.assertEqual(receipt['start']['other_cpu_delta'], receipt['end']['other_cpu_delta'])
        self.assertEqual(receipt['end']['other_cpu_delta']['status'], 'ok')
        code, receipt, _, _ = self.inside('0.99', '0.99', 4)
        self.assertEqual((code, receipt['status']), (4, 'ERROR'))
        code, receipt, _, _ = self.inside('0.99', '2.10', 4)
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
                self.assertEqual(record['schema'], 'ovh-bench-v2')
                self.assertEqual(record['load1_threshold'], '2.0')
                self.assertEqual(record['threshold_amendment_commit'], bench.THRESHOLD_AMENDMENT)
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
