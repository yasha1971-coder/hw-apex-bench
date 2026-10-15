#!/usr/bin/env python3
"""CI-oracle regression tests using the production OZSEG writer and reader."""
import copy
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import check_info as contract
import openzl_segmented as oz

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("workflow_syntax", ROOT / "tools/check_workflow_syntax.py")
syntax = importlib.util.module_from_spec(spec)
spec.loader.exec_module(syntax)


class InfoContractTest(unittest.TestCase):
    def archive(self, variant, n):
        """Exercise production build/decode with identity codec, never duplicate packing."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "truth.fa"
            archive = root / "data.ozseg"
            output = root / "decoded"
            truth = (b"ACGT" * ((n + 3) // 4))[:n]
            source.write_bytes(b">sample" + bytes([10]) + truth + bytes([10]))

            def mock_codec(argv, **kwargs):
                if argv[1] == "compress":
                    Path(argv[5]).write_bytes(Path(argv[4]).read_bytes())
                elif argv[1] == "decompress":
                    Path(argv[3]).write_bytes(Path(argv[2]).read_bytes())
                else:
                    self.fail("unexpected codec operation")
                return subprocess.CompletedProcess(argv, 0, "", "")

            with patch.object(oz.subprocess, "run", side_effect=mock_codec):
                oz.build(SimpleNamespace(variant=variant, input=source, output=archive, helper="mock"))
                oz.decode(SimpleNamespace(archive=archive, output=output, helper="mock"))
            self.assertEqual(output.read_bytes(), truth)
            self.assertEqual(archive.read_bytes()[:8], bytes.fromhex("4f5a534547310a01"))
            f, data, base = oz.read_container(archive)
            f.close()
            text = io.StringIO()
            with redirect_stdout(text):
                oz.info(SimpleNamespace(archive=archive))
            self.assertEqual(json.loads(text.getvalue()), data)
            return data, text.getvalue()

    def test_four_variants_production_mock(self):
        for variant, (q, wlog, level) in contract.OZSEG_VARIANTS.items():
            for n in (0, 1, q, 2 * q, 2 * q + 7):
                with self.subTest(variant=variant, bases=n):
                    data, text = self.archive(variant, n)
                    got = contract.check_ozseg(text, variant, n)
                    self.assertEqual(got["frames"], (n + q - 1) // q)
                    self.assertEqual(got["sum_ulen"], n)
                    self.assertEqual(got["windowLog"], wlog)
                    self.assertEqual(got["level"], level)
                    # Whitespace is not part of the JSON semantic contract.
                    self.assertEqual(got, contract.check_ozseg(json.dumps(data, indent=2), variant, n))

    def test_wrong_fields_are_rejected(self):
        data, _ = self.archive("l1_w64k", 65537)
        for key, value in (("Q", "65536"), ("Q", 65536.0), ("Q", True),
                           ("Q", 1048576), ("level", 3), ("level", True),
                           ("windowLog", 20), ("uncompressed_bases", 65536)):
            bad = copy.deepcopy(data)
            bad[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                contract.check_ozseg(json.dumps(bad), "l1_w64k", 65537)
        for field, value in (("ulen", 0), ("ulen", 65535), ("uoff", 1)):
            bad = copy.deepcopy(data)
            bad["frames"][0][field] = value
            with self.assertRaises(ValueError):
                contract.check_ozseg(json.dumps(bad), "l1_w64k", 65537)
        data["frames"].pop()
        with self.assertRaises(ValueError):
            contract.check_ozseg(json.dumps(data), "l1_w64k", 65537)

    def test_duplicate_json_and_trailing_garbage_rejected(self):
        for text in ('{"Q": 1, "Q": 2}', '{} garbage', '[]'):
            with self.assertRaises(ValueError):
                contract.load_json(text)

    def test_refrel_structured_text(self):
        for variant, q in (("q4k", 4096), ("q16k", 16384)):
            bases = 1048576
            blocks = (bases + q - 1) // q
            text = (f"refrel3 v1 Q {q} flags 1 | reference ref.fa sha256 "
                    + "a" * 64 + f", {bases} bases | assembly {bases} bases, {blocks} blocks"
                    + " | FASTA XXH3 " + "b" * 16
                    + f" | meta 123 B (raw 456), block hashes {blocks * 8} B, payload 789 B")
            self.assertEqual(contract.check_refrel(text, variant)["Q"], q)
            for bad in (text + " extra", text.replace(f"Q {q}", f"Q {q}0"),
                        text.replace("flags 1", "flags 0")):
                with self.assertRaises(ValueError):
                    contract.check_refrel(bad, variant)

    def test_two_bit_semantics(self):
        data = {"status": "PASS", "codec": "2-bit-capacity", "synthetic_payload_bytes": 10}
        self.assertEqual(contract.check_two_bit(json.dumps(data))["synthetic_payload_bytes"], 10)
        data["status"] = "FAILED"
        with self.assertRaises(ValueError):
            contract.check_two_bit(json.dumps(data))

    def test_shell_blocks_heredoc_regression(self):
        lf = chr(10)
        good = lf.join(("steps:", "  - name: example", "    run: |", "      set -euo pipefail",
                        "      for x in one two; do", "        python3 - <<'PY'", "      print(1)",
                        "      PY", "      done", ""))
        bad = good.replace("      PY" + lf, "        PY" + lf)
        for text, expected in ((good, 0), (bad, 2)):
            blocks = list(syntax.run_blocks(text))
            self.assertEqual(len(blocks), 1)
            cp = subprocess.run(["bash", "-n"], input=blocks[0][1], text=True, capture_output=True)
            self.assertEqual(cp.returncode, expected)
        with self.assertRaises(ValueError):
            list(syntax.run_blocks("    run: echo bypass"))


if __name__ == "__main__":
    unittest.main()
