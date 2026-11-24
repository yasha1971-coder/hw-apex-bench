"""Synthetic C-baseline orchestration tests; never compile or invoke a codec."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('gift1b_c_baseline', Path(__file__).with_name('c_baseline.py'))
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


class BusyHost(RuntimeError):
    pass


def snapshot(busy=False, governor='schedutil'):
    return dict(hostname='ace-core', cpu='AMD EPYC 4344P 8-Core Processor', kernel='synthetic',
                governor=governor, pinned_core=0, other_load=dict(busy=busy))


def fake_guard(values):
    snapshots = iter(values)
    def require_idle(value):
        if value['other_load']['busy']:
            raise BusyHost('synthetic foreign load')
    return SimpleNamespace(BusyHost=BusyHost, snapshot=lambda **kwargs: next(snapshots), require_idle=require_idle)


class HostPatchTests(unittest.TestCase):
    def test_original_timed_worker_is_not_rewritten(self):
        original = (Path(__file__).parents[1] / 'hw-gift-1/chunks.py').read_bytes().replace(b'\r\n', b'\n')
        result = baseline.patch_chunks(original).decode()
        self.assertIn("'AMD EPYC 4344P' in model", result)
        self.assertIn("platform.node() == 'ace-core'", result)
        self.assertIn('_gift_module.boundary(main, HERE', result)
        # Everything between checkpoint measurement entry and final report is exact.
        begin, end = 'def run(chunk, state, inputs):', 'def final_report():'
        old = original.decode().split(begin)[1].split(end)[0]
        new = result.split(begin)[1].split(end)[0]
        self.assertEqual(old, new)
        compile(result, 'copied-chunks.py', 'exec')

    def test_unknown_upstream_source_stops(self):
        with self.assertRaisesRegex(ValueError, 'host gate changed'):
            baseline.patch_chunks(b'not original source')


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

    def exercise(self, starts, *, should_reject):
        with tempfile.TemporaryDirectory(prefix='gift1b-c-test-') as temp:
            state = Path(temp)
            here = state / 'runner/evidence/hw-gift-1'
            cstate = state / 'c-state'
            chunk = 'enwik8-L3'
            baseline.write(state / 'c-runner-manifest.json', baseline.packed({'amendment_commit': baseline.AMENDMENT}))
            calls = []
            def original_main():
                calls.append('ran')
                baseline.write(here / chunk / 'run.json', baseline.packed({'host': {'os': 'Ubuntu synthetic', 'host_boot_sha256': 'a' * 64}}))
                baseline.write(here / chunk / 'SHA256SUMS', b'synthetic sums\n')
                baseline.write(cstate / chunk / 'samples.json', b'synthetic rejected samples\n')
            with patch.object(baseline, 'STATE', state), patch.object(baseline, 'guard', return_value=fake_guard(starts)), patch.object(os, 'environ', dict(os.environ, GIFT1B_TARGET=chunk)):
                if should_reject:
                    with self.assertRaises(SystemExit) as stopped:
                        baseline.boundary(original_main, here, cstate, ['run', chunk])
                    self.assertEqual(stopped.exception.code, 76)
                    self.assertFalse((here / chunk).exists())
                    rejected = list((state / 'c-rejected' / chunk).iterdir())
                    self.assertEqual(len(rejected), 1)
                    self.assertTrue((rejected[0] / 'checkpoint/run.json').exists())
                    self.assertTrue((rejected[0] / 'state/samples.json').exists())
                    self.assertFalse((state / f'c-boundaries/{chunk}.json').exists())
                else:
                    baseline.boundary(original_main, here, cstate, ['run', chunk])
                    result = json.loads((state / f'c-boundaries/{chunk}.json').read_bytes())
                    self.assertTrue(result['load_accepted'])
                    self.assertEqual(result['host']['cpu_affinity'], [0])
                    self.assertEqual(result['original_sha256sums_sha256'], baseline.sha(here / chunk / 'SHA256SUMS'))
            self.assertEqual(calls, ['ran'])

    def test_foreign_end_load_preserves_but_quarantines_entire_attempt(self):
        self.exercise([snapshot(), snapshot(True)], should_reject=True)

    def test_governor_change_rejects_quiet_attempt(self):
        self.exercise([snapshot(), snapshot(governor='performance')], should_reject=True)

    def test_quiet_same_host_receipt_is_accepted(self):
        self.exercise([snapshot(), snapshot()], should_reject=False)

    def test_foreign_start_load_never_invokes_worker(self):
        with tempfile.TemporaryDirectory(prefix='gift1b-c-test-') as temp:
            state = Path(temp)
            baseline.write(state / 'c-runner-manifest.json', b'{}')
            with patch.object(baseline, 'STATE', state), patch.object(baseline, 'guard', return_value=fake_guard([snapshot(True)])), patch.object(os, 'environ', dict(os.environ, GIFT1B_TARGET='enwik8-L3')):
                with self.assertRaises(SystemExit) as stopped:
                    baseline.boundary(lambda: self.fail('worker started under foreign load'), state / 'runner', state / 'partial', ['run', 'enwik8-L3'])
                self.assertEqual(stopped.exception.code, 76)
            self.assertEqual(len(list((state / 'c-boundaries').glob('*-rejected-start-*.json'))), 1)

    def test_interrupted_attempt_retains_original_start_and_resume_admission(self):
        with tempfile.TemporaryDirectory(prefix='gift1b-c-test-') as temp:
            state, chunk = Path(temp), 'enwik8-L3'
            here = state / 'runner/evidence/hw-gift-1'
            baseline.write(state / 'c-runner-manifest.json', b'{}')
            first, resumed, end = snapshot(), snapshot(), snapshot()
            first['sample_start_utc'] = 'first'
            resumed['sample_start_utc'] = 'resumed'
            def interrupted():
                raise KeyboardInterrupt('synthetic interruption')
            def completed():
                baseline.write(here / chunk / 'run.json', baseline.packed({'host': {'os': 'Ubuntu synthetic', 'host_boot_sha256': 'a' * 64}}))
                baseline.write(here / chunk / 'SHA256SUMS', b'synthetic sums\n')
            with patch.object(baseline, 'STATE', state), patch.object(os, 'environ', dict(os.environ, GIFT1B_TARGET=chunk)):
                with patch.object(baseline, 'guard', return_value=fake_guard([first])):
                    with self.assertRaises(KeyboardInterrupt):
                        baseline.boundary(interrupted, here, state / 'partial', ['run', chunk])
                with patch.object(baseline, 'guard', return_value=fake_guard([resumed, end])):
                    baseline.boundary(completed, here, state / 'partial', ['run', chunk])
            receipt = json.loads((state / f'c-boundaries/{chunk}.json').read_bytes())
            self.assertEqual(receipt['load_start'], first)
            self.assertEqual(receipt['load_resume_starts'], [resumed])
            self.assertTrue(receipt['load_accepted'])

    def test_busy_resume_quarantines_prior_partial_samples(self):
        with tempfile.TemporaryDirectory(prefix='gift1b-c-test-') as temp:
            state, chunk = Path(temp), 'enwik8-L3'
            here = state / 'runner/evidence/hw-gift-1'
            cstate = state / 'partial'
            baseline.write(state / 'c-runner-manifest.json', b'{}')
            baseline.write(state / f'c-pending/{chunk}.json', baseline.packed(dict(load_start=snapshot(), load_accepted=False)))
            baseline.write(cstate / chunk / 'raw.json', b'synthetic interrupted sample')
            with patch.object(baseline, 'STATE', state), patch.object(os, 'environ', dict(os.environ, GIFT1B_TARGET=chunk)), patch.object(baseline, 'guard', return_value=fake_guard([snapshot(True)])):
                with self.assertRaises(SystemExit) as stopped:
                    baseline.boundary(lambda: self.fail('busy resume executed'), here, cstate, ['run', chunk])
                self.assertEqual(stopped.exception.code, 76)
            rejected = list((state / 'c-rejected' / chunk).iterdir())
            self.assertEqual(len(rejected), 1)
            self.assertTrue((rejected[0] / 'state/raw.json').exists())
            self.assertTrue((rejected[0] / 'pending.json').exists())
            self.assertFalse((state / f'c-pending/{chunk}.json').exists())


if __name__ == '__main__':
    unittest.main()
