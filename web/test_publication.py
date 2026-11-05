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


class ManifestRefreshTests(unittest.TestCase):
    def test_generated_readme_refresh_and_determinism(self):
        import json
        import subprocess
        import sys
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            clone = Path(directory) / "repo"
            subprocess.run(["git", "clone", "--quiet", "--local", str(root), str(clone)],
                           check=True, capture_output=True)
            def run(*args):
                return subprocess.run([sys.executable, *args], cwd=clone,
                                      text=True, capture_output=True)
            manifest = clone / "evidence/published-results.json"
            before = manifest.read_bytes()
            self.assertEqual(run("web/refresh_manifest.py").returncode, 0)
            self.assertEqual(before, manifest.read_bytes())
            data = (clone / "results.jsonl").read_bytes()
            source = clone / "harness/presentation.py"
            text = source.read_text()
            self.assertIn("Measure access to a region", text)
            source.write_text(text.replace("Measure access to a region",
                                          "Measure byte access to a region", 1))
            report = run("harness/report.py")
            self.assertEqual(report.returncode, 0, report.stderr)
            refused = run("web/validate_publication.py")
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("Publication integrity mismatch: README.md", refused.stderr)
            result = run("web/refresh_manifest.py")
            self.assertEqual(result.returncode, 0, result.stderr)
            accepted = run("web/validate_publication.py")
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            expected = json.loads(before)
            actual = json.loads(manifest.read_bytes())
            self.assertEqual(set(expected["files"]), set(actual["files"]))
            for name in actual["files"]:
                for key in ("bytes", "sha256"):
                    actual["files"][name][key] = expected["files"][name][key]
            self.assertEqual(actual, expected)
            self.assertEqual(data, (clone / "results.jsonl").read_bytes())
            subprocess.run(["git", "-C", str(clone), "add",
                            "evidence/published-results.json"], check=True)
            first = manifest.read_bytes()
            self.assertEqual(run("web/refresh_manifest.py").returncode, 0)
            self.assertEqual(first, manifest.read_bytes())
            subprocess.run(["git", "-C", str(clone), "diff", "--exit-code",
                            "--", "evidence/published-results.json"], check=True)

    def test_missing_input_leaves_manifest_unchanged(self):
        import json
        from refresh_manifest import refresh
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "evidence").mkdir()
            target = root / "evidence/published-results.json"
            target.write_text(json.dumps({"schema": "cabench-publication-v1",
                "files": {"missing": {"bytes": 0, "sha256": ""}}}))
            before = target.read_bytes()
            with self.assertRaises(FileNotFoundError):
                refresh(root)
            self.assertEqual(before, target.read_bytes())


if __name__ == "__main__":
    unittest.main()
