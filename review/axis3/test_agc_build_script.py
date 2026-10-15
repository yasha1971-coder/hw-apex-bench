"""build_agc_v324.sh refuses a missing or unknown AGC_PLATFORM before cloning or building anything."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "build_agc_v324.sh"


def run(platform):
    env = {k: v for k, v in os.environ.items() if k != "AGC_PLATFORM"}
    if platform is not None:
        env["AGC_PLATFORM"] = platform
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        cp = subprocess.run(["bash", str(SCRIPT), str(out)], env=env, capture_output=True, text=True, timeout=60)
        return cp, out.exists()


class BuildScriptPlatform(unittest.TestCase):
    def test_unset_is_an_error(self):
        cp, created = run(None)
        self.assertEqual(cp.returncode, 2)
        self.assertIn("AGC_PLATFORM must be set", cp.stderr)
        self.assertFalse(created)

    def test_empty_is_an_error(self):
        cp, created = run("")
        self.assertEqual(cp.returncode, 2)
        self.assertIn("AGC_PLATFORM must be set", cp.stderr)
        self.assertFalse(created)

    def test_unknown_is_an_error(self):
        for value in ("bogus", "AVX2", "x86-64-v3", "avx512", "march=native"):
            with self.subTest(value=value):
                cp, created = run(value)
                self.assertEqual(cp.returncode, 2)
                self.assertIn("unknown AGC_PLATFORM", cp.stderr)
                self.assertFalse(created)

    def test_no_implicit_native(self):
        text = SCRIPT.read_text()
        self.assertIn('AGC_PLATFORM=${AGC_PLATFORM:-}', text)
        self.assertNotIn("${AGC_PLATFORM:-native}", text)
        self.assertNotIn("${AGC_PLATFORM:=native}", text)


if __name__ == "__main__":
    unittest.main()
