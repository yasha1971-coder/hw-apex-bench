"""Synthetic attempt retention only; no benchmark execution."""
import hashlib
import importlib.util
from pathlib import Path
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('gift1b_attempt_artifact', Path(__file__).with_name('attempt_artifact.py'))
artifact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(artifact)


class ArtifactTests(unittest.TestCase):
    def test_raw_bytes_and_manifest_are_deterministic(self):
        with tempfile.TemporaryDirectory(prefix='gift1b-attempt-test-') as directory:
            root = Path(directory)
            source = root / 'raw'
            (source / 'repeat/attempt-001').mkdir(parents=True)
            data = b'{"status":"LOADED"}\r\n'
            (source / 'repeat/attempt-001/receipt.json').write_bytes(data)
            one = artifact.pack_attempts(source, root / 'one')
            two = artifact.pack_attempts(source, root / 'two')
            self.assertEqual(one, two)
            self.assertEqual((root / 'one/attempts.tar.gz').read_bytes(), (root / 'two/attempts.tar.gz').read_bytes())
            self.assertEqual(one['files'][0]['sha256'], hashlib.sha256(data).hexdigest())
            with tarfile.open(root / 'one/attempts.tar.gz', 'r:gz') as tar:
                self.assertEqual(tar.extractfile('repeat/attempt-001/receipt.json').read(), data)

    def test_output_inside_source_and_empty_state_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix='gift1b-attempt-test-') as directory:
            source = Path(directory) / 'raw'
            source.mkdir()
            with self.assertRaises(ValueError):
                artifact.pack_attempts(source, source / 'nested')
            with self.assertRaises(ValueError):
                artifact.pack_attempts(source, source.parent / 'out')


if __name__ == '__main__':
    unittest.main()
