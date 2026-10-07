"""A2: executable documentation checks; never run a benchmark or load a codec."""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest
from unittest import mock

from review.axis3 import check_verdict_native, native_d6_worker, verdict_data
from tools import verdict_refrel3 as job

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "review/axis3/RUN.md"
TEXT = BOOK.read_text(encoding="utf-8")
PATTERN = re.compile(
    r"<!-- runbook-(command|recipe):([a-z0-9-]+) -->\s*"
    r"```(sh|python)\n(.*?)\n```", re.S)
BLOCKS = {ident: (kind, lang, source) for kind, ident, lang, source in PATTERN.findall(TEXT)}


def recipe(name):
    return compile(BLOCKS[name][2], f"RUN.md:{name}", "exec")


def module_command(name):
    """Inspect the actual example argv; never launch the command."""
    text = BLOCKS[name][2].replace("\\\n", " ")
    line = next(line for line in text.splitlines() if '"$PYTHON" -m ' in line)
    tokens = shlex.split(line)
    if ">" in tokens:
        tokens = tokens[:tokens.index(">")]
    tokens = ["16384" if t == "$GRANULE_RAW_BYTES" else t for t in tokens]
    return tokens[2], tokens[3:]


class _ParserCaptured(BaseException):
    def __init__(self, parser):
        self.parser = parser


def parser_for(main):
    # Stop main at parsing, before any file/codec/timing operation.
    def capture(parser, *args, **kwargs):
        raise _ParserCaptured(parser)
    with mock.patch.object(argparse.ArgumentParser, "parse_args", capture):
        try:
            main()
        except _ParserCaptured as caught:
            return caught.parser
    raise AssertionError("entrypoint did not build an ArgumentParser")


class RunbookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="a2-doc-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {"INPUT_ROOT": str(self.root)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def execute_recipe(self, name):
        output = io.StringIO()
        with mock.patch.object(Path, "cwd", return_value=ROOT), redirect_stdout(output):
            exec(recipe(name), {"__name__": "__runbook_example__"})
        return output.getvalue()

    def test_block_inventory_is_closed_and_unique(self):
        found = PATTERN.findall(TEXT)
        self.assertEqual(len(found), len(BLOCKS))
        self.assertEqual(set(BLOCKS), {
            "environment", "check-refrel3", "check-bgzf-default", "check-bgzf-matched",
            "freeze-runbook", "prepare", "file-references", "validate-inputs",
            "verdict-run", "verify", "axis4-tests", "axis5-case"})
        self.assertEqual(TEXT.count("```sh"), sum(x[1] == "sh" for x in BLOCKS.values()))
        self.assertEqual(TEXT.count("```python"), sum(x[1] == "python" for x in BLOCKS.values()))

    def test_every_shell_example_passes_bash_n_without_execution(self):
        for name, (_, lang, source) in BLOCKS.items():
            if lang != "sh":
                continue
            with self.subTest(command=name):
                result = subprocess.run(["bash", "-n"], input=source, text=True,
                                        capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(source.startswith("set -euo pipefail"))

    def test_every_python_recipe_compiles(self):
        for name, (_, lang, source) in BLOCKS.items():
            if lang == "python":
                with self.subTest(recipe=name):
                    compile(source, name, "exec")

    def test_b_command_argv_matches_production_parser(self):
        parser = parser_for(job.main)
        for name, operation in (("prepare", "prepare"), ("verdict-run", "run"), ("verify", "verify")):
            module, argv = module_command(name)
            with self.subTest(command=name):
                self.assertEqual(module, "tools.verdict_refrel3")
                parsed = parser.parse_args(argv)
                self.assertEqual(parsed.operation, operation)
                if operation == "prepare":
                    self.assertEqual(job.checked_windows([int(x) for x in parsed.windows.split(",")]),
                                     [1, 1024, 8192, 65536])
                    self.assertEqual(parsed.out, "prepared")
                if operation == "run":
                    self.assertEqual(parsed.plan, "plan.json")

    def test_native_check_argv_matches_production_parser(self):
        parser = parser_for(check_verdict_native.main)
        for name in ("check-refrel3", "check-bgzf-default", "check-bgzf-matched"):
            module, argv = module_command(name)
            with self.subTest(command=name):
                self.assertEqual(module, "review.axis3.check_verdict_native")
                parsed = parser.parse_args(argv)
                if name == "check-refrel3":
                    self.assertEqual(parsed.family, "refrel3")
                    self.assertIsNotNone(parsed.reference)
                else:
                    self.assertEqual(parsed.family, "bgzf")
                    self.assertEqual(parsed.variant, "matched-g" if name.endswith("matched") else "default")
                if name.endswith("matched"):
                    self.assertEqual(parsed.granule, 16384)

    def test_d6_argv_keeps_decoder_placeholders_and_case_scope(self):
        module, argv = module_command("axis5-case")
        self.assertEqual(module, "review.axis3.native_d6_worker")
        parsed = parser_for(native_d6_worker.main).parse_args(argv)
        self.assertEqual(parsed.timeout, 10)
        self.assertEqual(parsed.decoder, ["bash", "$REPO/review/axis3/openzl_adapter.sh",
                                          "decode", "{archive}", "{output}"])
        self.assertIn("SINGLE_CASE_ONLY", TEXT)
        self.assertIn("The worker's process exit 0 is not a correctness verdict", TEXT)
        self.assertIn("without normalization", TEXT)

    def test_runbook_is_bound_to_unchanged_protocol(self):
        freeze = verdict_data.verify_protocol(ROOT)
        self.assertIn(freeze["sha256"], TEXT)
        for term in ("zero-based", "half-open", "CALIBRATION_ONLY", "DIAGNOSTIC_ONLY",
                     "1024, 8192, 65536", "<=20% inclusive", "c0<0", "outside the timer",
                     "c0=median(t(W=1))-Q/D_Q"):
            self.assertIn(term, TEXT)
        self.assertEqual(freeze["protocol_version"], "1.1")
        self.assertEqual(freeze["verdict_windows_bytes"], [1024, 8192, 65536])

    def test_freeze_recipe_copies_exact_tracked_bytes_and_reports_hash(self):
        with mock.patch.object(job, "run", side_effect=AssertionError("no benchmark")), \
                mock.patch.object(verdict_data, "capture_silence", side_effect=AssertionError("no telemetry")):
            info = json.loads(self.execute_recipe("freeze-runbook"))
        self.assertEqual((self.root / "RUN.md").read_bytes(), BOOK.read_bytes())
        self.assertEqual(info["runbook"], verdict_data.file_ref(self.root, self.root / "RUN.md"))
        self.assertEqual(info["protocol_sha256"], verdict_data.verify_protocol(ROOT)["sha256"])

    def test_freeze_recipe_identical_copy_is_not_rewritten(self):
        self.execute_recipe("freeze-runbook")
        before = (self.root / "RUN.md").stat().st_mtime_ns
        self.execute_recipe("freeze-runbook")
        self.assertEqual((self.root / "RUN.md").stat().st_mtime_ns, before)

    def test_freeze_recipe_refuses_changed_copy(self):
        destination = self.root / "RUN.md"
        destination.write_bytes(b"different retained runbook")
        with self.assertRaisesRegex(SystemExit, "RUN.md changed"):
            self.execute_recipe("freeze-runbook")
        self.assertEqual(destination.read_bytes(), b"different retained runbook")

    def test_freeze_recipe_refuses_symlink(self):
        destination = self.root / "RUN.md"
        destination.symlink_to(BOOK)
        with self.assertRaisesRegex(SystemExit, "must not be a symlink"):
            self.execute_recipe("freeze-runbook")

    def test_reference_recipe_round_trips_relative_hashes(self):
        self.execute_recipe("freeze-runbook")
        (self.root / "prepared").mkdir()
        (self.root / "prepared/prepared.json").write_bytes(b"{}")
        refs = json.loads(self.execute_recipe("file-references"))
        self.assertEqual([r["path"] for r in refs], ["RUN.md", "prepared/prepared.json"])
        for ref in refs:
            checked = verdict_data.checked_file(self.root, ref)
            self.assertEqual(hashlib.sha256(checked.read_bytes()).hexdigest(), ref["sha256"])

    def test_reference_recipe_rejects_symlink_escape(self):
        (self.root / "RUN.md").symlink_to(BOOK)
        with self.assertRaisesRegex(ValueError, "escapes input root"):
            self.execute_recipe("file-references")

    def readiness(self, *, wrong_head=False, wrong_book=False):
        # The production load_plan implementation has its own B tests. Here test
        # only this documentation recipe's added boundary checks, with real refs.
        (self.root / "RUN.md").write_bytes(b"wrong" if wrong_book else BOOK.read_bytes())
        plan = {"harness_commit": "a" * 40,
                "runbook": verdict_data.file_ref(self.root, self.root / "RUN.md")}
        with mock.patch.object(job, "load_plan", return_value=(plan, {}, {}, {}, {})), \
                mock.patch.object(job, "harness_identity", return_value={"commit": ("b" if wrong_head else "a") * 40}), \
                mock.patch.object(job, "open_reader", side_effect=AssertionError("must not load codecs")), \
                mock.patch.object(job, "run", side_effect=AssertionError("must not run")), \
                mock.patch.object(job, "capture_silence", side_effect=AssertionError("must not sample")):
            return self.execute_recipe("validate-inputs")

    def test_readiness_recipe_is_preparation_only(self):
        self.assertIn("INPUT_HASHES_PASS", self.readiness())

    def test_readiness_recipe_rejects_wrong_applied_head(self):
        with self.assertRaisesRegex(SystemExit, "actual applied HEAD"):
            self.readiness(wrong_head=True)

    def test_readiness_recipe_rejects_untracked_runbook_variant(self):
        with self.assertRaisesRegex(SystemExit, "tracked RUN.md"):
            self.readiness(wrong_book=True)

    def test_axis4_command_is_unit_test_not_a_fake_measurement_cli(self):
        module, argv = module_command("axis4-tests")
        self.assertEqual(module, "unittest")
        self.assertEqual(argv, ["discover", "-s", "tests", "-p", "test_cohort_region_engine.py", "-v"])
        self.assertIn("NO_OFFICIAL_CLI", TEXT)
        self.assertIn("PREPARED_ONLY", TEXT)
        self.assertNotIn('"$PYTHON" -m tools.cohort_region_engine', TEXT)
        self.assertIn("does not write a locked input/output", TEXT)

    def test_every_documented_relative_target_exists(self):
        links = re.findall(r"\]\(([^)]+)\)", TEXT)
        for link in links:
            with self.subTest(link=link):
                self.assertFalse(Path(link).is_absolute())
                self.assertTrue((BOOK.parent / link).is_file())
        scripts = set(re.findall(r"`((?:review/axis3|codecs)/[a-z0-9_/.+-]+\.sh)`", TEXT))
        self.assertGreater(len(scripts), 5)
        for script in scripts:
            with self.subTest(script=script):
                self.assertTrue((ROOT / script).is_file())

    def test_time_space_and_evidence_claims_are_bounded(self):
        self.assertIn("needs measurement on", TEXT)
        self.assertIn("not proof of continuous quiescence", TEXT)
        self.assertIn("not a capacity estimate", " ".join(TEXT.replace("**", "").split()))
        self.assertIn("does not currently report a complete peak-RSS", TEXT)
        self.assertIn("preserve", TEXT.lower())
        for name in ("results.json", "dq.jsonl", "table.md", "SHA256SUMS", "silence-initial.json"):
            self.assertIn(name, TEXT)
        self.assertIn("not that model B passed", TEXT)
        self.assertIn("not require the patch author's commit object", TEXT)


if __name__ == "__main__":
    unittest.main()
