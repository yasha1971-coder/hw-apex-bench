"""Synthetic bootstrap checks: no downloads, installs, builds or timings."""
import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('gift1b_prepare_host', Path(__file__).with_name('prepare_host.py'))
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def tar_payload(path, name='python/bin/test', link=None):
    with tarfile.open(path, 'w:gz') as stream:
        entry = tarfile.TarInfo(name)
        if link is None:
            data = b'synthetic payload only'
            entry.size, entry.mode = len(data), 0o755
            stream.addfile(entry, io.BytesIO(data))
        else:
            entry.type, entry.linkname = tarfile.SYMTYPE, link
            stream.addfile(entry)


class BootstrapTests(unittest.TestCase):
    def test_control_exception_never_permits_a_compiler(self):
        receipt = dict(hostname='ace-core', cpu='AMD EPYC 4344P', pinned_core=0,
                       interval_ns=2000000000,
                       other_load=dict(busy=True, inspection_errors=[], active_processes=[{'comm': '2.1.284'}]))
        prepare.require_preparation_admission(receipt, True)
        receipt['other_load']['active_processes'].append({'comm': 'cc1'})
        with self.assertRaises(prepare.BusyHost):
            prepare.require_preparation_admission(receipt, True)

    def test_regular_payload_extracts_only_inside_workspace(self):
        with tempfile.TemporaryDirectory(prefix='gift1b-bootstrap-test-') as directory:
            root = Path(directory)
            destination = root / '.work/extract'
            destination.mkdir(parents=True)
            archive = root / 'test.tar.gz'
            tar_payload(archive)
            with patch.object(prepare, 'ROOT', root):
                prepare.safe_tar(archive, destination)
            self.assertEqual((destination / 'python/bin/test').read_bytes(), b'synthetic payload only')

    def test_traversal_and_escaping_link_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix='gift1b-bootstrap-test-') as directory:
            root = Path(directory)
            destination = root / '.work/extract'
            destination.mkdir(parents=True)
            archive = root / 'test.tar.gz'
            with patch.object(prepare, 'ROOT', root):
                for name, link in (('../../escape', None), ('python/link', '../../../escape'), ('python/link', '/escape')):
                    tar_payload(archive, name, link)
                    with self.assertRaises(ValueError):
                        prepare.safe_tar(archive, destination)
            self.assertFalse((root / 'escape').exists())

    def test_cached_hash_mismatch_stops_without_network(self):
        with tempfile.TemporaryDirectory(prefix='gift1b-bootstrap-test-') as directory:
            path = Path(directory) / 'cached'
            path.write_bytes(b'changed')
            with patch.object(prepare.urllib.request, 'urlopen') as network:
                with self.assertRaisesRegex(ValueError, 'hash differs'):
                    prepare.download('https://unused.invalid', path, hashlib.sha256(b'original').hexdigest())
                network.assert_not_called()

    def test_busy_admission_prevents_all_dependency_preparation(self):
        with tempfile.TemporaryDirectory(prefix='gift1b-bootstrap-test-') as directory:
            state = Path(directory) / '.work/state'
            with patch.object(prepare, 'STATE', state), patch.object(prepare, 'snapshot', return_value={'synthetic': True}), patch.object(prepare, 'require_idle', side_effect=prepare.BusyHost('synthetic foreign load')), patch.object(prepare, 'prepare_python') as python, patch.object(prepare, 'prepare_corpora') as corpora, patch.object(prepare, 'prepare_zstd') as zstd, patch.object(prepare.sys, 'argv', ['prepare_host.py']):
                with self.assertRaises(prepare.BusyHost):
                    prepare.main()
                python.assert_not_called()
                corpora.assert_not_called()
                zstd.assert_not_called()
            self.assertTrue((state / 'prepare-load-start.json').exists())


if __name__ == '__main__':
    unittest.main()
