"""Synthetic unit checks only: no codecs, corpus encoding or real timing."""
import importlib.util
import io
from itertools import count
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('gift1b_measure', Path(__file__).with_name('measure.py'))
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def archive(sizes, checksum=False):
    data = b''.join(b'\x28\xb5\x2f\xfd' + b'x' * 4 for _ in sizes)
    entries = b''.join(struct.pack('<II', 8, n) + (b'\0' * 4 if checksum else b'') for n in sizes)
    footer = struct.pack('<IBI', len(sizes), 128 if checksum else 0, 0x8F92EAB1)
    return data + struct.pack('<II', 0x184D2A5E, len(entries) + 9) + entries + footer


class ParserTests(unittest.TestCase):
    def test_exact_host_amendment_preserves_original_prefix(self):
        original = b'Prediction (not a measurement): unchanged\n'
        amended = original + b'\n' + worker.AMENDMENT_TEXT.encode() + b'\n'
        policy = amended + b'\n' + worker.POLICY_TEXT.encode() + b'\n'
        load = policy + b'\n' + worker.LOAD_AMENDMENT_TEXT.encode() + b'\n'
        self.assertEqual(len(worker.verify_protocol_bytes(original, amended, policy, load, load)), 64)
        for changed in (amended.replace(b'unchanged\n', b'changed\n'), amended + b'new text\n'):
            with self.assertRaises(ValueError):
                worker.verify_protocol_bytes(original, changed, policy, load, load)
        with self.assertRaises(ValueError):
            worker.verify_protocol_bytes(original, amended, policy, load, original)

    def test_amended_host_and_cpu_are_explicit(self):
        worker.require_amended_host(0, 'AMD EPYC 4344P 8-Core Processor', 'ace-core')
        for cpu, model, hostname in ((1, 'AMD EPYC 4344P', 'ace-core'),
                                     (0, 'AMD EPYC 9V74', 'ace-core'),
                                     (0, 'AMD EPYC 4344P', 'other-host')):
            with self.assertRaises(ValueError):
                worker.require_amended_host(cpu, model, hostname)

    def test_both_seek_table_layouts_and_complete_byte_accounting(self):
        for checksum in (False, True):
            blob = archive([65536, 7], checksum)
            result = worker.parse_archive(blob, 65536, 65543)
            self.assertEqual(result['frame_count'], 2)
            self.assertEqual(result['checksum_flag'], checksum)
            self.assertEqual(sum(f['compressed_bytes'] for f in result['frames']) + result['seek_table_bytes'], len(blob))

    def test_default_requires_one_frame(self):
        self.assertEqual(worker.parse_archive(archive([25]), None, 25)['frame_count'], 1)
        with self.assertRaises(ValueError):
            worker.parse_archive(archive([65536, 7]), None, 65543)

    def test_corrupt_magic_table_and_geometry_rejected(self):
        blob = archive([65536, 7])
        invalid = [b'BAD!' + blob[4:], blob[:-1], blob[:-9] + b'\0' * 9]
        for data in invalid:
            with self.assertRaises(ValueError):
                worker.parse_archive(data, 65536, 65543)
        with self.assertRaises(ValueError):
            worker.parse_archive(blob, 1048576, 65543)

    def test_wrong_platform_stops_before_git_or_codec(self):
        with patch.object(worker.sys, 'platform', 'win32'), patch.object(worker, 'git') as git:
            with self.assertRaisesRegex(ValueError, 'Linux CPython'):
                worker.preflight(Path('not-a-real-receipt'), 0)
            git.assert_not_called()


class PairTests(unittest.TestCase):
    def test_pair_loop_retains_samples_in_ram_without_filesystem_writes(self):
        content = b'synthetic test bytes only'
        class Reader:
            opens = 0
            def __init__(self, stream, mode):
                Reader.opens += 1
                self.raw = io.BytesIO(content)
            def seek(self, off):
                return self.raw.seek(off)
            def read(self, n):
                return self.raw.read(n)
            def close(self):
                self.raw.close()
        info = dict(g=65536, frame='65536', bytes=12, sha256='a' * 64)
        resource = SimpleNamespace(RUSAGE_SELF=0, getrusage=lambda _: SimpleNamespace(ru_maxrss=1))
        with tempfile.TemporaryDirectory(prefix='hw-gift-1b-test-') as directory:
            part = Path(directory)
            with patch.dict(sys.modules, {'resource': resource}), patch.object(worker, 'write') as save, patch.object(worker.time, 'perf_counter_ns', side_effect=count(100, 10)):
                first = worker.repeat(SimpleNamespace(SeekableZstdFile=Reader), part, b'test', info, io.BytesIO(content), 'synthetic', 3, 4, 0, [0, 3])
                self.assertEqual(Reader.opens, 2)
                self.assertEqual([sample[0] for sample in first['samples']], [0, 3])
                save.assert_not_called()
                self.assertEqual(list(part.iterdir()), [])

    def test_repeat_mismatch_is_fatal_and_is_not_saved(self):
        class Reader:
            def __init__(self, stream, mode):
                self.reads = 0
            def seek(self, off):
                pass
            def read(self, n):
                self.reads += 1
                return b'abcd' if self.reads == 1 else b'WRONG'
            def close(self):
                pass
        info = dict(g=65536, frame='65536', bytes=12, sha256='a' * 64)
        resource = SimpleNamespace(RUSAGE_SELF=0, getrusage=lambda _: SimpleNamespace(ru_maxrss=1))
        with tempfile.TemporaryDirectory(prefix='hw-gift-1b-test-') as directory:
            part = Path(directory)
            with patch.dict(sys.modules, {'resource': resource}), patch.object(worker.time, 'perf_counter_ns', side_effect=count(100, 10)):
                with self.assertRaisesRegex(ValueError, 'restored byte/length mismatch'):
                    worker.repeat(SimpleNamespace(SeekableZstdFile=Reader), part, b'test', info, io.BytesIO(b'abcd'), 'synthetic', 3, 4, 0, [0])
            self.assertFalse(any(part.rglob('*.json')))


class ExecutionPolicyTests(unittest.TestCase):
    @staticmethod
    def save(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def fake_helper(self, statuses, calls):
        def locked(command, receipt_path):
            request_path = Path(command[-1])
            request = worker.json.loads(request_path.read_bytes())
            outcome = statuses[len(calls)]
            calls.append(request)
            self.assertEqual(command[3], 'worker')
            status = 'LOADED' if outcome in ('LOADED', 'LOADED_END', 'BROKEN_LOADED') else outcome
            started = outcome != 'LOADED'
            code = 1 if outcome in ('ERROR', 'BROKEN_LOADED') else (0 if started else None)
            if code == 0:
                row = dict(src='enwik8', level=3, g=65536, n=4096, rep=0,
                           archive_bytes=12, archive_sha256='a' * 64,
                           samples=[[off, 1, 2, 3] for off in request['offsets']])
                self.save(Path(request['row_path']), worker.packed(row))
            receipt = dict(status=status, command=command, returncode=code,
                command_started=started, policy_commit=worker.POLICY,
                lock_path='/run/lock/ovh-bench.lock', ps_top8=f'header\nlast {len(calls)}\n')
            self.save(receipt_path, worker.packed(receipt))
            self.save(Path(str(receipt_path) + '.stdout'), b'')
            self.save(Path(str(receipt_path) + '.stderr'), b'')
            return 0 if status == 'CLEAN' else (77 if status == 'LOADED' else 1)
        return locked

    @staticmethod
    def args(part):
        return (part, 'enwik8-L3', 65536, 4096, 0, part / 'input', part / 'archive',
                dict(g=65536, frame='65536', bytes=12, sha256='a' * 64),
                part / 'installation.json', {}, [0, 7])

    def test_foreign_activity_is_observational_but_governor_must_match(self):
        host = dict(hostname='ace-core', cpu='AMD EPYC 4344P', kernel='test',
                    pinned_core=0, governor='performance')
        worker.check_load_snapshot(dict(host, other_load={'busy': True}), host)
        with self.assertRaises(ValueError):
            worker.check_load_snapshot(dict(host, governor='powersave'), host)

    def test_direct_timed_worker_without_flock_marker_is_rejected(self):
        with patch.object(worker.os, 'environ', {}):
            with self.assertRaisesRegex(ValueError, 'flock wrapper'):
                worker.timed_worker(Path('never-read.json'))

    def test_first_clean_is_never_retried_and_replays_without_helper(self):
        calls = []
        with tempfile.TemporaryDirectory(prefix='hw-gift-1b-flock-test-') as directory:
            part = Path(directory)
            locked = self.fake_helper(['CLEAN'], calls)
            with patch.dict(sys.modules, {'ovh_bench': SimpleNamespace(run_locked=locked)}), \
                    patch.object(worker, 'write', self.save):
                first, receipt = worker.timed_repeat(*self.args(part))
                second, replay = worker.timed_repeat(*self.args(part))
            self.assertEqual(len(calls), 1)
            self.assertEqual(first, second)
            self.assertEqual(receipt, replay)
            self.assertEqual(len(receipt['attempts']), 1)
            self.assertFalse((part / 'repeats/65536-4096-0/attempt-2').exists())
            self.assertEqual(receipt['row_sha256'], worker.hashlib.sha256(worker.packed(first)).hexdigest())

    def test_only_loaded_repeat_is_retaken_immediately_same_offsets(self):
        calls = []
        with tempfile.TemporaryDirectory(prefix='hw-gift-1b-retry-test-') as directory:
            part = Path(directory)
            locked = self.fake_helper(['LOADED_END', 'CLEAN'], calls)
            with patch.dict(sys.modules, {'ovh_bench': SimpleNamespace(run_locked=locked)}), \
                    patch.object(worker, 'write', self.save), \
                    patch.object(worker.time, 'sleep', side_effect=AssertionError('retry slept')):
                row, receipt = worker.timed_repeat(*self.args(part))
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0]['offsets'], calls[1]['offsets'])
            self.assertEqual([p[0] for p in row['samples']], [0, 7])
            self.assertEqual([a['status'] for a in receipt['attempts']], ['LOADED', 'CLEAN'])
            self.assertTrue((part / 'repeats/65536-4096-0/attempt-1/row.json').exists())
            self.assertTrue((part / 'repeats/65536-4096-0/attempt-2/row.json').exists())
            self.assertFalse((part / 'repeats/65536-4096-0/attempt-3').exists())

    def test_three_total_loaded_attempts_block_and_cannot_make_fourth(self):
        calls = []
        with tempfile.TemporaryDirectory(prefix='hw-gift-1b-blocked-test-') as directory:
            part = Path(directory)
            locked = self.fake_helper(['LOADED'] * 3, calls)
            with patch.dict(sys.modules, {'ovh_bench': SimpleNamespace(run_locked=locked)}), \
                    patch.object(worker, 'write', self.save):
                for _ in range(2):
                    with self.assertRaises(worker.BlockedLoad) as caught:
                        worker.timed_repeat(*self.args(part))
                record = caught.exception.record
            self.assertEqual(len(calls), 3)
            self.assertEqual(len(record['attempts']), 3)
            self.assertEqual(record['ps_top8'], 'header\nlast 3\n')
            self.assertFalse((part / 'repeats/65536-4096-0/attempt-4').exists())
            self.assertEqual(worker.progress_counts([], record), dict(planned_repeats=70,
                started_repeats=1, retaken_repeats=1, loaded_attempts=3))

    def test_error_and_nonzero_child_are_fatal_even_if_classified_loaded(self):
        for status in ('ERROR', 'BROKEN_LOADED'):
            calls = []
            with tempfile.TemporaryDirectory(prefix='hw-gift-1b-error-test-') as directory:
                part = Path(directory)
                locked = self.fake_helper([status], calls)
                with patch.dict(sys.modules, {'ovh_bench': SimpleNamespace(run_locked=locked)}), \
                        patch.object(worker, 'write', self.save):
                    with self.assertRaises(ValueError):
                        worker.timed_repeat(*self.args(part))
                self.assertEqual(len(calls), 1)
                self.assertFalse((part / 'repeats/65536-4096-0/attempt-2').exists())

    def test_existing_public_blocked_marker_refuses_new_outer_attempt(self):
        report = SimpleNamespace(verify_chunk=lambda *_args, **_kwargs: None)
        with tempfile.TemporaryDirectory(prefix='hw-gift-1b-marker-test-') as directory:
            root = Path(directory)
            blocked = root / 'blocked/pyzstd-enwik8-L3/BLOCKED.json'
            self.save(blocked, worker.packed({'blocked_repeat': {'g': 65536, 'n': 4096, 'rep': 0}}))
            with patch.object(worker, 'HERE', root), \
                    patch.dict(sys.modules, {'report': report,
                        'load_guard': SimpleNamespace(snapshot=None),
                        'attempt_artifact': SimpleNamespace(pack_attempts=None)}), \
                    patch.object(worker, 'preflight', side_effect=AssertionError('blocked chunk started')):
                with self.assertRaises(worker.BlockedLoad):
                    worker._run('enwik8-L3', root, root / 'unused', 0, 4)

    def test_blocked_chunk_publishes_all_raw_attempts_and_no_complete_checkpoint(self):
        artifact_spec = importlib.util.spec_from_file_location('attempt_artifact',
            Path(__file__).with_name('attempt_artifact.py'))
        artifact = importlib.util.module_from_spec(artifact_spec)
        artifact_spec.loader.exec_module(artifact)
        host = dict(hostname='ace-core', cpu='AMD EPYC 4344P', kernel='test',
                    pinned_core=0, governor='performance')
        observation = dict(host, other_load={'busy': True})
        lock = SimpleNamespace(flock=lambda *_: None, LOCK_EX=1, LOCK_NB=2)
        calls = []
        with tempfile.TemporaryDirectory(prefix='hw-gift-1b-blocked-public-test-') as directory:
            root = Path(directory)
            here = root / 'evidence/hw-gift-1b'
            here.mkdir(parents=True)
            for name in ('CALIBRATION.md', 'measure.py', 'report.py', 'load_guard.py',
                         'ovh_bench.py', 'attempt_artifact.py'):
                (here / name).write_bytes(b'synthetic source only')
            inputs = root / '.work/inputs'
            inputs.mkdir(parents=True)
            (inputs / 'input').write_bytes(b'input')
            offsets = {65536: {(4096, rep): [0, 7] for rep in range(5)}}
            modules = {'report': SimpleNamespace(verify_chunk=None),
                'load_guard': SimpleNamespace(snapshot=lambda _: observation),
                'fcntl': lock, 'attempt_artifact': artifact,
                'ovh_bench': SimpleNamespace(run_locked=self.fake_helper(['LOADED'] * 3, calls))}
            with patch.dict(sys.modules, modules), \
                    patch.multiple(worker, ROOT=root, HERE=here, STATE=root / '.work/hw-gift-1b',
                        INPUT={'input': (5, worker.sha(inputs / 'input'))},
                        CHUNKS={'synthetic-L3': ('input', 3)}, GS=(65536,), NS=(4096,)), \
                    patch.object(worker, 'preflight', return_value=(object(), host)), \
                    patch.object(worker, 'offset_lists', return_value=(offsets, {})), \
                    patch.object(worker, 'git', return_value=b'0' * 40), \
                    patch.object(worker, 'write', self.save), \
                    patch.object(worker, 'fsync_dir'), \
                    patch.object(worker, 'archive_once', return_value=(b'test', {})), \
                    patch.object(worker, 'control', return_value={}):
                with self.assertRaises(worker.BlockedLoad):
                    worker._run('synthetic-L3', inputs, root / 'install.json', 0, 1)
            output = here / 'blocked/pyzstd-synthetic-L3'
            self.assertEqual({p.name for p in output.iterdir()},
                             {'BLOCKED.json', 'attempts.tar.gz', 'attempts.json'})
            summary = worker.json.loads((output / 'BLOCKED.json').read_bytes())
            self.assertEqual(summary['status'], 'BLOCKED: load')
            self.assertEqual(summary['started_repeats'], 1)
            self.assertEqual(summary['retaken_repeats'], 1)
            self.assertEqual(summary['loaded_attempts'], 3)
            self.assertEqual(summary['ps_top8'], 'header\nlast 3\n')
            manifest = worker.json.loads((output / 'attempts.json').read_bytes())
            self.assertEqual(len(manifest['files']), 12)
            self.assertEqual(manifest['archive_sha256'], worker.sha(output / 'attempts.tar.gz'))
            self.assertFalse((here / 'synthetic-L3').exists())


if __name__ == '__main__':
    unittest.main()
