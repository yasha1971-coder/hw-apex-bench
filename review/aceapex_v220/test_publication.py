#!/usr/bin/env python3
"""Offline regression tests; never run an encoder, decoder, or benchmark."""
import importlib.util
import math
import os
from pathlib import Path
import shutil
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('frozen_publication', Path(__file__).with_name('publish.py'))
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Hardlinks keep the large raw samples cheap; mutations always replace a link.
        for relative in (p.EVIDENCE, Path('evidence/t2t-regions-20260916'),
                         Path('evidence/aceapex-v220-gpu-20260930'), Path('docs/RESULTS')):
            shutil.copytree(p.ROOT / relative, self.root / relative, copy_function=os.link)

    def replace(self, relative, data):
        path = self.root / relative
        path.unlink()
        path.write_bytes(data)

    def test_valid_frozen_publication(self):
        result = p.publish(self.root, True)
        self.assertEqual(result['region_samples'], 360000)
        self.assertFalse(result['measurements_repeated'])

    def test_changed_artifact_member_is_rejected(self):
        relative = p.EVIDENCE / 'c-g/results.json'
        data = (self.root / relative).read_bytes()
        self.replace(relative, data.replace(b'253935557', b'253935558', 1))
        with self.assertRaisesRegex(ValueError, 'member hash'):
            p.validate(self.root)

    def test_missing_artifact_member_is_rejected(self):
        (self.root / p.EVIDENCE / 'native/PINS').unlink()
        with self.assertRaisesRegex(ValueError, 'missing/size'):
            p.validate(self.root)

    def test_rewritten_receipt_is_rejected(self):
        relative = p.EVIDENCE / 'receipt.json'
        receipt = p.load(self.root / relative)
        receipt['files'][0]['sha256'] = '0' * 64
        self.replace(relative, p.formatted(receipt).encode())
        with self.assertRaisesRegex(ValueError, 'source receipt hash'):
            p.validate(self.root)

    def test_manual_table_edit_is_rejected(self):
        data = (self.root / p.REPORT).read_bytes()
        self.replace(p.REPORT, data.replace(b'5.028842', b'9.999999', 1))
        with self.assertRaisesRegex(ValueError, 'generated publication differs'):
            p.publish(self.root, True)

    def test_fabricated_gpu_import_is_rejected(self):
        relative = Path('evidence/aceapex-v220-gpu-20260930/results.json')
        gpu = p.load(self.root / relative)
        gpu['rows'][0]['on_device_ms'] = 0.001
        self.replace(relative, p.formatted(gpu).encode())
        d = p.load(self.root / p.EVIDENCE / 'results.json')
        summary = p.load(self.root / p.EVIDENCE / 'publication-check.json')
        with self.assertRaisesRegex(ValueError, 'GPU import values'):
            p.render(self.root, d, summary)

    def test_quantiles_and_nonfinite_numbers(self):
        self.assertEqual(p.nearest([4.0, 1.0, 3.0, 2.0], .5), 2.0)
        for value in (math.nan, math.inf, -math.inf):
            with self.assertRaises(ValueError):
                p.close(value, 1.0, 'finite')

    def test_import_never_overwrites_different_bytes(self):
        path = self.root / 'idempotent.txt'
        p.write_exact(path, b'original')
        p.write_exact(path, b'original')
        with self.assertRaisesRegex(ValueError, 'existing evidence differs'):
            p.write_exact(path, b'changed')
        self.assertEqual(path.read_bytes(), b'original')


if __name__ == '__main__':
    unittest.main(verbosity=2)
