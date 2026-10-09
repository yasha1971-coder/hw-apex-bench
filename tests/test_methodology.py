"""A5: documentation/protocol regression checks, never a measurement or native run.

The checks protect explicit contract clauses and exercise the existing pure
window-law function on synthetic arithmetic. They do not claim to prove every
possible English statement consistent. Production algorithms are not patched.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import inspect
import json
from pathlib import Path
import re
import unittest

from tools import verdict_refrel3 as job
from tools import window_law as law

ROOT = Path(__file__).resolve().parents[1]
METHOD = ROOT / "METHODOLOGY.md"
PROTOCOL = ROOT / "review/axis3/PROTOCOL_AXIS3.md"
FREEZE = ROOT / "review/axis3/PROTOCOL_FREEZE.json"


def normalized(text):
    return " ".join(text.replace("`", "").split())


def contract_errors(method, protocol, freeze):
    """Finite regression guard for the approved clauses, not a semantic oracle."""
    m, p = normalized(method), normalized(protocol)
    errors = []
    required = {
        "coordinates": "(assembly_id, contig_id, start0, end0)",
        "half-open bounds": "0 <= start0 < end0 <= contig_length",
        "htslib/AGC translation": "[start0,end0-1]",
        "one-based translation": "[start0+1,end0]",
        "independent c0": "c0 = median(t(W=1)) - Q/D_Q",
        "negative c0": "If c0<0, model B is FAIL",
        "calibration": "CALIBRATION_ONLY",
        "diagnostic": "DIAGNOSTIC_ONLY",
        "threshold": "<=20% inclusive",
    }
    for key, clause in required.items():
        if clause not in m or clause not in p:
            errors.append(key)
    for key, clause in {
        "primary B": "t_B(W) = c0 + (W+Q-1)/D_Q",
        "secondary A": "t_A(W) = (W+Q-1)/D_Q",
        "no acceptance fallback": "Model A never affects the verdict.",
        "same domain": "D_Q and Q use the same canonical sequence-byte domain as W",
        "outside timer": "outside the timed decode boundary",
    }.items():
        if clause not in m:
            errors.append(key)
    stale = ("Common coordinates are 1-based inclusive",
             "Use only R = D_Q/(W + Q - 1)",
             "without fitted multipliers or overhead subtraction")
    for clause in stale:
        if clause in m:
            errors.append("stale rule: " + clause)
    roles = re.findall(r"^\| (\d+) \| (CALIBRATION_ONLY|VERDICT) \| (Yes|No) \|$", method, re.M)
    expected = [("1", "CALIBRATION_ONLY", "No")] + [
        (str(w), "VERDICT", "Yes") for w in freeze["verdict_windows_bytes"]]
    if roles != expected:
        errors.append("window roles")
    if freeze.get("protocol_version") != "1.1" or "frozen protocol v1.1" not in p:
        errors.append("protocol version")
    return errors


class MethodologyTest(unittest.TestCase):
    def setUp(self):
        self.method = METHOD.read_text(encoding="utf-8")
        self.protocol = PROTOCOL.read_text(encoding="utf-8")
        self.freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
        self.text = normalized(self.method)

    def test_frozen_authority_and_digest_are_consistent(self):
        self.assertEqual(self.freeze["protocol_path"], str(PROTOCOL.relative_to(ROOT)))
        self.assertEqual(hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(), self.freeze["sha256"])
        self.assertEqual(contract_errors(self.method, self.protocol, self.freeze), [])
        self.assertIn("it does not replace or amend it", self.text)

    def test_all_supporting_document_links_exist(self):
        links = re.findall(r"\]\(([^)]+)\)", self.method)
        self.assertGreaterEqual(len(links), 4)
        for link in links:
            with self.subTest(link=link):
                self.assertFalse(Path(link).is_absolute())
                self.assertTrue((ROOT / link).is_file())
        self.assertIn("review/axis3/PROTOCOL_AXIS3.md", links)
        runbook = (ROOT / "review/axis3/RUN.md").read_text(encoding="utf-8")
        self.assertIn("[METHODOLOGY.md](../../METHODOLOGY.md) is aligned with the frozen v1.1 contract.", runbook)
        self.assertNotIn("their reconciliation is A5, not part of this patch", runbook)

    def test_coordinates_and_library_translations_match_protocol(self):
        self.assertEqual(self.freeze["coordinate_convention"], "0-based-half-open")
        for clause in ("[start0,end0)", "end0-start0", "A request never crosses a contig boundary"):
            self.assertIn(clause, self.text)
            self.assertIn(clause, normalized(self.protocol))
        for api in ("htslib faidx_fetch_seq64", "AGC range API"):
            self.assertIn(f"| {api} | `[start0,end0-1]` | 0-based inclusive |", self.method)
        self.assertIn("both canonical and translated coordinates", self.text)

    def test_canonical_domain_and_bgzf_q_not_raw_isize(self):
        self.assertEqual(self.freeze["byte_domain"], "uppercase-sequence-without-FASTA-framing")
        for clause in ("Truth is uppercase sequence bytes without FASTA headers or line separators",
                       "do not relabel raw ISIZE as canonical Q", "Q is not the LZ lookback window",
                       "raw FASTA offsets are never substituted for canonical coordinates"):
            self.assertIn(clause, self.text)

    def test_w_and_seed_come_from_protocol_and_production(self):
        self.assertEqual(set(self.freeze["verdict_windows_bytes"]), law.VERDICT_WINDOWS)
        self.assertEqual(self.freeze["calibration_window_bytes"], 1)
        for clause in (f"{job.REQUESTS:,} requests per W", f"seed {job.SEED}"):
            self.assertIn(clause, self.text)
            self.assertIn(clause, self.protocol)
        self.assertIn("uniformly over valid starts", self.text)

    def test_one_thread_and_execution_scopes_not_mixed(self):
        self.assertIn("one persistent library handle and one decode thread", self.text)
        self.assertIn("CPU in-process, GPU in-process and process-per-request CLI are separate scopes", self.text)
        self.assertIn("Do not silently substitute a helper process", self.text)
        self.assertIn("one decode thread", self.protocol)

    def test_formula_b_and_formula_a_match_pure_implementation(self):
        self.assertIn("t_B(W) = c0 + (W+Q-1)/D_Q", self.text)
        self.assertIn("t_A(W) = (W+Q-1)/D_Q", self.text)
        self.assertEqual(self.freeze["window_law_primary"], "B")
        self.assertEqual(self.freeze["window_law_secondary"], "A")
        row = law.diagnose(1000000, 1024, 4096, 6119, 5096)
        self.assertEqual(row["c0_us"], 1000)
        self.assertEqual(row["primary_predicted_p50_us"], 6119)
        self.assertEqual(row["secondary_predicted_p50_us"], 5119)

    def test_probe_is_independent_and_outside_verdict(self):
        self.assertIn("separate 10,000-request W=1 random-position experiment", self.text)
        self.assertIn("same format, thread, corpus and seed rule", self.text)
        self.assertIn("W=1 is excluded from the verdict set", self.text)
        self.assertIn("No coefficients are fitted", self.text)
        row = law.diagnose(1000000, 1, 4096, 900000, 5096)
        self.assertEqual(row["window_role"], "CALIBRATION_ONLY")
        self.assertFalse(row["verdict_eligible"])

    def test_diagnostic_windows_never_rescue_or_fail_error_verdict(self):
        self.assertIn("its prediction error does not change the aggregate verdict", self.text)
        self.assertIn("Freeze that W list before execution", self.text)
        for w in (2, 256, 4096, 32768):
            with self.subTest(w=w):
                row = law.diagnose(1000000, w, 4096, 900000, 5096)
                self.assertEqual(row["verdict"], "DIAGNOSTIC_ONLY")
                self.assertFalse(row["verdict_eligible"])

    def test_negative_c0_retains_b_fail_even_if_a_is_exact(self):
        self.assertIn("If c0<0, model B is FAIL", self.text)
        self.assertIn("c0 is reported unchanged", self.text)
        self.assertIn("use secondary model A as the diagnostic reference only", self.text)
        self.assertIn("cannot turn a model-B FAIL into PASS", self.text)
        for w in self.freeze["verdict_windows_bytes"]:
            a_us = w + 4096 - 1
            row = law.diagnose(1000000, w, 4096, a_us, 4000)
            self.assertEqual(row["c0_us"], -96)
            self.assertEqual(row["secondary_predicted_p50_us"], a_us)
            self.assertEqual(row["model_status"], "FAIL")
            self.assertEqual(row["verdict"], "FAIL")

    def test_zero_c0_is_in_domain_and_models_coincide(self):
        self.assertIn("For c0=0, B remains applicable", self.text)
        row = law.diagnose(1000000, 1024, 4096, 5119, 4096)
        self.assertEqual(row["c0_us"], 0)
        self.assertEqual(row["primary_predicted_p50_us"], row["secondary_predicted_p50_us"])
        self.assertEqual(row["verdict"], "PASS")

    def test_twenty_percent_is_inclusive_with_predicted_denominator(self):
        self.assertIn("|error_B_percent| <=20% inclusive", self.text)
        self.assertEqual(law.TOLERANCE_PERCENT, 20)
        self.assertIn("100 * (measured_p50 - predicted_B_p50) / predicted_B_p50", self.text)
        for factor, want in ((Fraction(4, 5), "PASS"), (Fraction(6, 5), "PASS"),
                             (Fraction(799, 1000), "FAIL"), (Fraction(1201, 1000), "FAIL")):
            row = law.diagnose(1000000, 1024, 4096, Fraction(6119) * factor, 5096)
            self.assertEqual(row["verdict"], want)

    def test_dq_repeats_match_b_job_without_executing_it(self):
        self.assertIn("three warmups and nine measured full decodes", self.text)
        signature = inspect.signature(job.run_dq_series)
        self.assertEqual(signature.parameters["warmups"].default, 3)
        self.assertEqual(signature.parameters["repeats"].default, 9)
        self.assertIn("including warmups", self.text)
        self.assertIn("median measured full-decode time", self.text)
        self.assertIn("same corpus", self.text)

    def test_framing_and_hash_are_outside_full_decode_timer(self):
        self.assertIn("framing removal, canonicalization and SHA validation occur outside the timed decode boundary", self.text)
        self.assertIn("D_Q and Q use the same canonical sequence-byte domain as W", self.text)
        self.assertIn("both native and canonical output-byte counts", self.text)
        self.assertIn("If neither implements the required boundary, the row is FAILED", self.text)
        self.assertIn("outside the timed decode boundary", normalized(self.protocol))

    def test_foreign_family_coverage_does_not_double_count_bgzf(self):
        self.assertIn("at least four non-ACEAPEX format families", self.text)
        self.assertIn("two required configurations but one family", self.text)
        entries = [{"family": "refrel3", "variant": q, "data_status": "PASS", "verdict": "PASS"}
                   for q in ("q4k", "q16k")]
        for family, variant in (("bgzf", "default"), ("bgzf", "matched-g"),
                                ("zstd-seekable", "one"), ("lz4-indexed", "one")):
            entries.append(dict(family=family, variant=variant, data_status="PASS", verdict="PASS"))
        self.assertEqual(job.aggregate(entries)["foreign_format_count"], 3)
        self.assertFalse(job.aggregate(entries)["coverage_complete"])
        entries.append(dict(family="ozseg", variant="l1_w64k", data_status="PASS", verdict="PASS"))
        self.assertEqual(job.aggregate(entries)["foreign_format_count"], 4)
        self.assertTrue(job.aggregate(entries)["coverage_complete"])
        self.assertIn("q4k and q16k", self.text)

    def test_host_gate_thresholds_remain_protocol_values(self):
        for clause in ("load <0.5", ">20,000,000,000 bytes", "10% or more of one CPU"):
            self.assertIn(clause, self.text)
            self.assertIn(clause, normalized(self.protocol))
        self.assertIn("official host must be ace-core", self.text)
        self.assertIn("not proof of continuous quiescence", self.text)

    def test_correctness_is_not_waived_on_diagnostics_or_model_failure(self):
        self.assertIn("Distinguish model FAIL from data FAILED", self.text)
        self.assertIn("no correctness failure is waived as diagnostic", self.text)
        self.assertIn("A negative c0 is a model failure, not by itself evidence of a decoding error", self.text)
        self.assertIn("evidence-integrity verification is not a model-B PASS", self.text)

    def test_stock_configuration_reference_accounting_and_other_axes(self):
        for clause in ("one create", "not a chain of append", "A shared reference is counted once, never omitted",
                       "Axis 4 maps each query group explicitly to every selected assembly",
                       "bit flips, byte replacement, truncation", "10-second watchdog",
                       "Pre-decode refusal requires an explicit validation stage",
                       "A worker's successful process exit does not prove"):
            self.assertIn(clause, self.text)
        self.assertIn("supports synthetic evidence only", self.text)
        self.assertIn("regenerated mutations", self.text)
        self.assertIn("Harness verification PASS does not imply integrity PASS", self.text)

    def test_guard_rejects_regression_to_one_based_common_coordinates(self):
        changed = self.method.replace("using zero-based half-open coordinates", "Common coordinates are 1-based inclusive")
        self.assertTrue(contract_errors(changed, self.protocol, self.freeze))

    def test_guard_rejects_primary_a_or_acceptance_fallback(self):
        for old, new in (("t_B(W) = c0 + (W+Q-1)/D_Q", "t_B(W) = (W+Q-1)/D_Q"),
                         ("Model A never affects the verdict.", "Model A replaces the verdict when c0<0."),
                         ("If c0<0, model B is FAIL", "If c0<0, model B is PASS")):
            with self.subTest(old=old):
                self.assertTrue(contract_errors(self.method.replace(old, new), self.protocol, self.freeze))

    def test_guard_rejects_diagnostic_or_calibration_in_verdict(self):
        for old, new in (("| 1 | CALIBRATION_ONLY | No |", "| 1 | VERDICT | Yes |"),
                         ("| 8192 | VERDICT | Yes |", "| 4096 | VERDICT | Yes |")):
            with self.subTest(old=old):
                self.assertTrue(contract_errors(self.method.replace(old, new), self.protocol, self.freeze))

    def test_guard_rejects_threshold_and_protocol_drift(self):
        self.assertTrue(contract_errors(self.method.replace("<=20% inclusive", "<20% exclusive"), self.protocol, self.freeze))
        self.assertTrue(contract_errors(self.method, self.protocol.replace("If c0<0, model B is FAIL", "If c0<0, model B is PASS"), self.freeze))


if __name__ == "__main__":
    unittest.main()
