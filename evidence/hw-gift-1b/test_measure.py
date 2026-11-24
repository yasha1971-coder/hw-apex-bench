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
        self.assertEqual(len(worker.verify_protocol_bytes(original, amended, policy, policy)), 64)
        for changed in (amended.replace(b'unchanged\n', b'changed\n'), amended + b'new text\n'):
            with self.assertRaises(ValueError):
                worker.verify_protocol_bytes(original, changed, policy, policy)
        with self.assertRaises(ValueError):
            worker.verify_protocol_bytes(original, amended, policy, original)

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
    def test_saved_pairs_are_reused_without_opening_reader(self):
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
        def save(path, data):
            path.write_bytes(data)
        with tempfile.TemporaryDirectory(prefix='hw-gift-1b-test-') as directory:
            part = Path(directory)
            with patch.dict(sys.modules, {'resource': resource}), patch.object(worker, 'write', save), patch.object(worker.time, 'perf_counter_ns', side_effect=count(100, 10)):
                first = worker.repeat(SimpleNamespace(SeekableZstdFile=Reader), part, b'test', info, io.BytesIO(content), 'synthetic', 3, 4, 0, [0, 3])
                self.assertEqual(Reader.opens, 2)
                def forbidden(*args):
                    raise AssertionError('completed pair was timed again')
                second = worker.repeat(SimpleNamespace(SeekableZstdFile=forbidden), part, b'test', info, io.BytesIO(content), 'synthetic', 3, 4, 0, [0, 3])
                self.assertEqual(first['samples'], second['samples'])

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

    def test_each_repeat_uses_helper_then_replays_clean_without_timing(self):
        info = dict(g=65536, frame='65536', bytes=12, sha256='a' * 64)
        row = dict(src='enwik8', level=3, g=65536, n=4096, rep=0,
                   archive_bytes=12, archive_sha256='a' * 64, samples=[[0, 1, 2, 3]])
        calls = []
        def save(path, data):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        def locked(command, receipt_path):
            calls.append(command)
            self.assertEqual(command[3], 'worker')
            request_path = Path(command[-1])
            request = worker.json.loads(request_path.read_bytes())
            self.assertEqual((request['g'], request['n'], request['rep']), (65536, 4096, 0))
            save(Path(request['row_path']), worker.packed(row))
            save(receipt_path, worker.packed(dict(status='CLEAN', command=command,
                 policy_commit=worker.POLICY, lock_path='/run/lock/ovh-bench.lock')))
            return 0
        with tempfile.TemporaryDirectory(prefix='hw-gift-1b-flock-test-') as directory:
            part = Path(directory)
            with patch.dict(sys.modules, {'ovh_bench': SimpleNamespace(run_locked=locked)}), \
                    patch.object(worker, 'write', save):
                args = (part, 'enwik8-L3', 65536, 4096, 0, part / 'input', part / 'archive',
                        info, part / 'installation.json', {}, [0])
                first, receipt = worker.timed_repeat(*args)
                second, replay = worker.timed_repeat(*args)
            self.assertEqual(len(calls), 1)
            self.assertEqual(first, second)
            self.assertEqual(receipt, replay)
            self.assertEqual(receipt['row_sha256'], worker.hashlib.sha256(worker.packed(row)).hexdigest())

    def test_loaded_boundary_receipt_is_retained_and_excluded(self):
        def save(path, data):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        def locked(command, receipt_path):
            save(receipt_path, worker.packed(dict(status='LOADED', command=command)))
            return 77
        with tempfile.TemporaryDirectory(prefix='hw-gift-1b-loaded-test-') as directory:
            part = Path(directory)
            with patch.dict(sys.modules, {'ovh_bench': SimpleNamespace(run_locked=locked)}), \
                    patch.object(worker, 'write', save):
                with self.assertRaises(worker.LoadedAttempt):
                    worker.timed_repeat(part, 'enwik8-L3', 65536, 4096, 0,
                        part / 'input', part / 'archive', {}, part / 'installation.json', {}, [0])
            self.assertTrue((part / 'repeats/65536-4096-0/ovh-bench.json').exists())
            self.assertFalse((part / 'repeats/65536-4096-0/row.json').exists())

    def test_loaded_attempt_retained_after_encoding_without_publishing(self):
        host = dict(hostname='ace-core', cpu='AMD EPYC 4344P', kernel='test',
                    pinned_core=0, governor='performance')
        # Other activity no longer blocks correctness/encoding or admission.
        observed = dict(host, other_load=dict(busy=True, active_processes=[{'pid': 100}],
                                              inspection_errors=[]))
        snapshots = []
        def snapshot(cpu):
            snapshots.append(cpu)
            return observed
        guard = SimpleNamespace(snapshot=snapshot)
        lock = SimpleNamespace(flock=lambda *_: None, LOCK_EX=1, LOCK_NB=2)
        report = SimpleNamespace(verify_chunk=lambda *_args, **_kwargs: None)
        def save(path, data):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        with tempfile.TemporaryDirectory(prefix='hw-gift-1b-load-test-') as directory:
            root = Path(directory)
            here = root / 'evidence/hw-gift-1b'
            here.mkdir(parents=True)
            for name in ('CALIBRATION.md', 'measure.py', 'report.py', 'load_guard.py', 'ovh_bench.py'):
                (here / name).write_bytes(b'synthetic source only')
            inputs = root / '.work/inputs'
            inputs.mkdir(parents=True)
            (inputs / 'input').write_bytes(b'input')
            digest = worker.sha(inputs / 'input')
            state = root / '.work/hw-gift-1b'
            offsets = {65536: {(4096, rep): [0] for rep in range(5)}}
            with patch.dict(sys.modules, {'load_guard': guard, 'fcntl': lock, 'report': report}), \
                    patch.multiple(worker, HERE=here, ROOT=root, STATE=state,
                        INPUT={'input': (5, digest)}, CHUNKS={'synthetic-L3': ('input', 3)},
                        GS=(65536,), NS=(4096,)), \
                    patch.object(worker, 'preflight', return_value=(object(), host)), \
                    patch.object(worker, 'offset_lists', return_value=(offsets, {})), \
                    patch.object(worker, 'git', return_value=b'0' * 40), \
                    patch.object(worker, 'write', save), \
                    patch.object(worker, 'archive_once', return_value=(b'test', {})) as encoder, \
                    patch.object(worker, 'control', return_value={}), \
                    patch.object(worker, 'timed_repeat', side_effect=worker.LoadedAttempt('boundary load > 1.0')):
                with self.assertRaises(worker.LoadedAttempt):
                    worker._run('synthetic-L3', inputs, root / 'not-used.json', 0, 1)
                rejected = state / 'attempts/001/synthetic-L3/REJECTED'
                self.assertTrue(rejected.exists())
                self.assertEqual(worker.json.loads(rejected.read_bytes())['status'], 'LOADED')
                self.assertFalse((here / 'synthetic-L3').exists())
                with self.assertRaises(worker.LoadedAttempt):
                    worker._run('synthetic-L3', inputs, root / 'not-used.json', 0, 1)
                self.assertEqual(snapshots, [0])
                self.assertEqual(encoder.call_count, 1)
                self.assertTrue(rejected.exists())


if __name__ == '__main__':
    unittest.main()
