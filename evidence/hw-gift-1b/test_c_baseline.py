"""Synthetic orchestration checks; no compiler, codec or real timing is used."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('gift1b_c_baseline', Path(__file__).with_name('c_baseline.py'))
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


def snapshot(busy=False, governor='schedutil'):
    return dict(hostname='ace-core', cpu='AMD EPYC 4344P 8-Core Processor', kernel='synthetic',
                governor=governor, pinned_core=0, other_load=dict(busy=busy))


def fake_guard(values):
    snapshots = iter(values)
    def require_idle(value):
        raise AssertionError('obsolete zero-activity gate called')
    return SimpleNamespace(snapshot=lambda **kwargs: next(snapshots), require_idle=require_idle)


def logical(cstate, chunk, g=65536, n=4096, rep=0, statuses=('CLEAN',)):
    attempts = [dict(attempt=i, status=status, receipt=dict(status=status, ps_top8='synthetic ps top8'),
                     row_sha256='b' * 64 if status == 'CLEAN' else None)
                for i, status in enumerate(statuses, 1)]
    clean = statuses[-1] == 'CLEAN'
    record = dict(g=g, n=n, rep=rep, status='CLEAN' if clean else 'BLOCKED',
                  returncode=0 if clean else 78, receipt=attempts[-1]['receipt'],
                  row_sha256=attempts[-1]['row_sha256'], attempts=attempts)
    baseline.write(cstate / chunk / 'ovh-repeats' / f'{g}-{n}-{rep}/metadata.json', baseline.packed(record))
    return record


def write_repeats(cstate, chunk):
    for g in baseline.GS:
        for n in (4096, 65536):
            for rep in range(5):
                logical(cstate, chunk, g, n, rep)


def write_host(path):
    baseline.write(path, baseline.packed({'host': {'os': 'Ubuntu synthetic', 'host_boot_sha256': 'a' * 64}}))


def fake_artifacts():
    def pack(source, output):
        output.mkdir(parents=True, exist_ok=True)
        baseline.write(output / 'attempts.tar.gz', b'synthetic packed bytes')
        result = dict(schema='hw-gift-1b-attempts-v1', archive_sha256=baseline.sha(output / 'attempts.tar.gz'), files=[])
        baseline.write(output / 'attempts.json', baseline.packed(result))
        return result
    return SimpleNamespace(pack_attempts=pack)


class HostPatchTests(unittest.TestCase):
    def test_original_timed_worker_is_not_rewritten(self):
        original = (Path(__file__).parents[1] / 'hw-gift-1/chunks.py').read_bytes().replace(b'\r\n', b'\n')
        result = baseline.patch_chunks(original).decode()
        self.assertIn("'AMD EPYC 4344P' in model", result)
        self.assertIn("platform.node() == 'ace-core'", result)
        self.assertIn("sys.executable = os.environ['GIFT1B_PYTHON_SHIM']", result)
        begin, end = 'def run(chunk, state, inputs):', 'def final_report():'
        self.assertEqual(original.decode().split(begin)[1].split(end)[0], result.split(begin)[1].split(end)[0])
        compile(result, 'copied-chunks.py', 'exec')

    def test_unknown_source_stops(self):
        with self.assertRaisesRegex(ValueError, 'host gate changed'):
            baseline.patch_chunks(b'not original source')

    def test_accepted_export_has_all_attempt_artifacts(self):
        self.assertEqual(len(baseline.PUBLIC_FILES), 13)
        self.assertIn('attempts.tar.gz', baseline.PUBLIC_FILES)
        self.assertIn('attempts.json', baseline.PUBLIC_FILES)


class BoundaryTests(unittest.TestCase):
    def test_next_chunk_stops_before_snapshot_or_measurement(self):
        with patch.object(os, 'environ', dict(os.environ, GIFT1B_TARGET='enwik8-L3')), patch.object(baseline, 'guard') as load:
            with self.assertRaises(SystemExit) as stopped:
                baseline.boundary(lambda: self.fail('next chunk started'), Path('unused'), Path('unused'), ['run', 'enwik8-L19'])
            self.assertEqual(stopped.exception.code, 75)
            load.assert_not_called()

    def test_non_run_calls_original_without_load_or_timing(self):
        calls = []
        with patch.object(baseline, 'guard') as load:
            baseline.boundary(lambda: calls.append('verify'), Path('unused'), Path('unused'), ['verify', 'enwik8-L3'])
            load.assert_not_called()
        self.assertEqual(calls, ['verify'])

    def exercise(self, starts, reject=False):
        with tempfile.TemporaryDirectory(prefix='gift1b-c-test-') as temp:
            state, chunk = Path(temp), 'enwik8-L3'
            here, cstate = state / 'runner/evidence/hw-gift-1', state / 'c-state'
            baseline.write(state / 'c-runner-manifest.json', b'{}')
            def original_main():
                write_host(here / chunk / 'run.json')
                baseline.write(here / chunk / 'SHA256SUMS', b'synthetic sums\n')
                baseline.write(cstate / chunk / 'samples.json', b'synthetic preserved samples')
                write_repeats(cstate, chunk)
            with patch.object(baseline, 'STATE', state), patch.object(baseline, 'guard', return_value=fake_guard(starts)), patch.object(os, 'environ', dict(os.environ, GIFT1B_TARGET=chunk)):
                if reject:
                    with self.assertRaises(SystemExit) as stopped:
                        baseline.boundary(original_main, here, cstate, ['run', chunk])
                    self.assertEqual(stopped.exception.code, 76)
                else:
                    baseline.boundary(original_main, here, cstate, ['run', chunk])
                    result = json.loads((state / f'c-boundaries/{chunk}.json').read_bytes())
                    self.assertTrue(result['load_accepted'])
                    self.assertEqual(result['host']['cpu_affinity'], [0])
                    self.assertEqual(len(result['benchmark_runs']), 60)

    def test_foreign_activity_is_observational(self):
        self.exercise([snapshot(True), snapshot(True)])

    def test_governor_change_rejects_different_conditions(self):
        self.exercise([snapshot(), snapshot(governor='performance')], reject=True)

    def test_interruption_retains_original_start_and_resume_admission(self):
        with tempfile.TemporaryDirectory(prefix='gift1b-c-test-') as temp:
            state, chunk = Path(temp), 'enwik8-L3'
            here = state / 'runner/evidence/hw-gift-1'
            baseline.write(state / 'c-runner-manifest.json', b'{}')
            first, resumed, end = snapshot(), snapshot(), snapshot()
            first['sample_start_utc'], resumed['sample_start_utc'] = 'first', 'resumed'
            def interrupted():
                raise KeyboardInterrupt('synthetic interruption')
            def completed():
                write_host(here / chunk / 'run.json')
                baseline.write(here / chunk / 'SHA256SUMS', b'synthetic sums\n')
                write_repeats(state / 'partial', chunk)
            with patch.object(baseline, 'STATE', state), patch.object(os, 'environ', dict(os.environ, GIFT1B_TARGET=chunk)):
                with patch.object(baseline, 'guard', return_value=fake_guard([first])):
                    with self.assertRaises(KeyboardInterrupt):
                        baseline.boundary(interrupted, here, state / 'partial', ['run', chunk])
                with patch.object(baseline, 'guard', return_value=fake_guard([resumed, end])):
                    baseline.boundary(completed, here, state / 'partial', ['run', chunk])
            receipt = json.loads((state / f'c-boundaries/{chunk}.json').read_bytes())
            self.assertEqual(receipt['load_start'], first)
            self.assertEqual(receipt['load_resume_starts'], [resumed])

    def test_three_loaded_attempts_block_but_keep_clean_state_and_raw_bytes(self):
        with tempfile.TemporaryDirectory(prefix='gift1b-c-test-') as temp:
            state, chunk = Path(temp), 'enwik8-L3'
            here, cstate = state / 'runner', state / 'partial'
            baseline.write(state / 'c-runner-manifest.json', b'{}')
            def blocked():
                write_host(cstate / chunk / 'run.json')
                logical(cstate, chunk, rep=0)
                logical(cstate, chunk, rep=1)
                logical(cstate, chunk, rep=2, statuses=('LOADED', 'LOADED', 'LOADED'))
                baseline.write(cstate / chunk / 'raw.stdout', b'raw LOADED data')
                raise subprocess.CalledProcessError(78, ['synthetic', 'sweep.py'])
            with patch.object(baseline, 'HERE', state / 'public'), patch.object(baseline, 'STATE', state), patch.object(baseline, 'guard', return_value=fake_guard([snapshot(), snapshot()])), patch.object(baseline, 'artifacts', return_value=fake_artifacts()), patch.object(os, 'environ', dict(os.environ, GIFT1B_TARGET=chunk)):
                with self.assertRaises(SystemExit) as stopped:
                    baseline.boundary(blocked, here, cstate, ['run', chunk])
                self.assertEqual(stopped.exception.code, 78)
            self.assertTrue((cstate / chunk / 'raw.stdout').exists())
            self.assertFalse((state / 'c-rejected').exists())
            result = json.loads((state / 'public/blocked' / f'c-{chunk}/BLOCKED.json').read_bytes())
            self.assertEqual((result['planned_repeats'], result['started_repeats'], result['retaken_repeats'], result['loaded_attempts']), (60, 3, 1, 3))
            self.assertEqual((result['status'], result['reader'], result['chunk']), ('BLOCKED: load', 'c', chunk))
            self.assertEqual(len(result['benchmark_runs']), 2)
            self.assertEqual(result['ps_top8'], 'synthetic ps top8')


class ShimTests(unittest.TestCase):
    RAW = b'{"samples":[[12,34,56]],"peak_kib":7}\n'

    def args(self):
        return ['-E', '-B', str(baseline.RUNNER / 'evidence/hw-gift-1/sweep.py'), 'enwik8', '65536', '4096', '0']

    def fake_helper(self, values, calls):
        results = iter(values)
        def run_locked(command, receipt_path, stdout_path=None):
            calls.append(command)
            status, raw, code = next(results)
            receipt = dict(status=status, returncode=code if status == 'ERROR' else 0,
                           command_started=bool(raw), ps_top8='synthetic ps top8')
            baseline.write(receipt_path, baseline.packed(receipt))
            baseline.write(stdout_path, raw)
            baseline.write(Path(str(receipt_path) + '.stdout'), raw)
            baseline.write(Path(str(receipt_path) + '.stderr'), b'synthetic stderr')
            return code
        return SimpleNamespace(run_locked=run_locked)

    def invoke(self, cstate, helper):
        output = io.BytesIO()
        real_sha = baseline.sha
        def pin_sha(path):
            return 'c' * 64 if Path(path).name == 'ovh_bench.py' else real_sha(path)
        with patch.object(baseline, 'CSTATE', cstate), patch.object(baseline, 'ovh', return_value=helper), patch.object(baseline, 'sha', side_effect=pin_sha), patch.object(os, 'environ', dict(os.environ, GIFT1B_TARGET='enwik8-L3')), patch.object(baseline.sys, 'stdout', SimpleNamespace(buffer=output)):
            code = baseline.python_shim(self.args(), '/synthetic/python')
        return code, output.getvalue()

    def metadata(self, cstate):
        return json.loads(next(cstate.glob('enwik8-L3/ovh-repeats/*/metadata.json')).read_bytes())

    def test_negative_control_and_metadata_do_not_take_shared_lock(self):
        sweep = baseline.RUNNER / 'evidence/hw-gift-1/sweep.py'
        for args in (['-B', str(sweep), 'enwik8', '65536', '4096', '-1'], ['-B', 'chunks.py', 'verify', 'enwik8-L3']):
            with patch.object(baseline, 'ovh') as lock, patch.object(baseline.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as process:
                self.assertEqual(baseline.python_shim(args, '/synthetic/python'), 0)
                lock.assert_not_called()
                process.assert_called_once_with(['/synthetic/python', *args])

    def test_first_clean_has_full_row_hash_and_is_never_retimed(self):
        with tempfile.TemporaryDirectory(prefix='gift1b-c-shim-') as temp:
            state, calls = Path(temp), []
            code, output = self.invoke(state, self.fake_helper([('CLEAN', self.RAW, 0)], calls))
            self.assertEqual((code, output, len(calls)), (0, self.RAW, 1))
            row = dict(src='enwik8', level=3, g=65536, n=4096, rep=0, **json.loads(self.RAW))
            self.assertEqual(self.metadata(state)['row_sha256'], baseline.digest(baseline.packed(row)))
            with patch.object(baseline, 'ovh') as unused:
                code, output = self.invoke(state, self.fake_helper([], []))
                unused.assert_not_called()
            self.assertEqual((code, output), (0, self.RAW))

    def test_loaded_is_retried_alone_with_identical_arguments_until_first_clean(self):
        with tempfile.TemporaryDirectory(prefix='gift1b-c-shim-') as temp:
            state, calls = Path(temp), []
            code, output = self.invoke(state, self.fake_helper([('LOADED', b'', 77), ('CLEAN', self.RAW, 0)], calls))
            self.assertEqual((code, output), (0, self.RAW))
            self.assertEqual(calls[0], calls[1])
            meta = self.metadata(state)
            self.assertEqual([a['status'] for a in meta['attempts']], ['LOADED', 'CLEAN'])
            self.assertIsNone(meta['attempts'][0]['row_sha256'])
            self.assertEqual(meta['load_amendment_commit'], baseline.LOAD_AMENDMENT)
            for attempt in meta['attempts']:
                self.assertTrue((state / 'enwik8-L3' / attempt['receipt_path']).is_file())
                self.assertTrue((state / 'enwik8-L3' / attempt['raw_stdout_path']).is_file())

    def test_three_loaded_attempts_block_and_a_fourth_is_never_started(self):
        with tempfile.TemporaryDirectory(prefix='gift1b-c-shim-') as temp:
            state, calls = Path(temp), []
            code, output = self.invoke(state, self.fake_helper([('LOADED', b'', 77)] * 3, calls))
            self.assertEqual((code, output, len(calls)), (78, b'', 3))
            meta = self.metadata(state)
            self.assertEqual(meta['status'], 'BLOCKED')
            self.assertEqual(len(meta['attempts']), 3)
            code, output = self.invoke(state, self.fake_helper([], []))
            self.assertEqual((code, output), (78, b''))

    def test_error_stops_without_retry_even_if_the_host_is_loaded(self):
        with tempfile.TemporaryDirectory(prefix='gift1b-c-shim-') as temp:
            state, calls = Path(temp), []
            code, output = self.invoke(state, self.fake_helper([('ERROR', b'bad child output', 9)], calls))
            self.assertEqual((code, output, len(calls)), (9, b'', 1))
            self.assertEqual(self.metadata(state)['status'], 'ERROR')
            self.assertEqual(self.invoke(state, self.fake_helper([], [])), (9, b''))

    def test_attempt_counts_count_logical_keys_and_every_loaded_attempt(self):
        records = [dict(attempts=[dict(status='CLEAN')]),
                   dict(attempts=[dict(status='LOADED'), dict(status='CLEAN')])]
        self.assertEqual(baseline.repeat_counts(records), dict(planned_repeats=60, started_repeats=2, retaken_repeats=1, loaded_attempts=1))


if __name__ == '__main__':
    unittest.main()
