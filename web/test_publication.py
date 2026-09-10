"""Regression checks for evidence corruption at the publication boundary."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from validate_publication import load_jsonl, verify_files


class PublicationIntegrityTests(unittest.TestCase):
    def test_binary_corruption_is_rejected(self):
        with self.assertRaises(UnicodeDecodeError):
            load_jsonl(b"Y\xaa\xe7\x8ax-")

    def test_truncated_record_is_rejected(self):
        with self.assertRaises(ValueError):
            load_jsonl(b'{"value": 1')

    def test_nonfinite_and_duplicate_values_are_rejected(self):
        for data in (b'{"value": NaN}', b'{"value": Infinity}',
                     b'{"value": 1, "value": 2}'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                load_jsonl(data)

    def test_blank_lines_and_nonobjects_are_rejected(self):
        for data in (b'', b'{}\n\n{}\n', b'[]\n'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                load_jsonl(data)

    def test_valid_utf8_preserves_values(self):
        self.assertEqual(load_jsonl('{"label":"µs", "value":0.87}\n'.encode()),
                         [{"label": "µs", "value": 0.87}])

    def test_same_length_numeric_tampering_is_rejected(self):
        original = b'{"value":0.87}\n'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "results.jsonl"
            expected = {"results.jsonl": {"bytes": len(original),
                        "sha256": hashlib.sha256(original).hexdigest()}}
            path.write_bytes(original)
            verify_files(root, expected)
            path.write_bytes(b'{"value":1.87}\n')
            with self.assertRaisesRegex(ValueError, "integrity mismatch"):
                verify_files(root, expected)


if __name__ == "__main__":
    unittest.main()
