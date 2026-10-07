import hashlib
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROTOCOL_PATH = "review/axis3/PROTOCOL_AXIS3.md"


class ProtocolFreezeTest(unittest.TestCase):
    def setUp(self):
        self.freeze = json.loads((ROOT / "review/axis3/PROTOCOL_FREEZE.json").read_text())
        self.protocol = (ROOT / PROTOCOL_PATH).read_text(encoding="utf-8")

    def test_freeze_record_matches_the_canonical_protocol(self):
        self.assertEqual(self.freeze["protocol_path"], PROTOCOL_PATH)
        self.assertFalse((ROOT / "review/axis3/PROTOCOL_AXIS3.frozen.md").exists())
        digest = hashlib.sha256((ROOT / PROTOCOL_PATH).read_bytes()).hexdigest()
        self.assertEqual(digest, self.freeze["sha256"])

    def test_v11_coordinate_contract(self):
        self.assertEqual(self.freeze["protocol_version"], "1.1")
        self.assertEqual(self.freeze["coordinate_convention"], "0-based-half-open")
        for clause in ("frozen protocol v1.1", "(assembly_id, contig_id, start0, end0)",
                       "0 <= start0 < end0 <= contig_length", "end0-start0",
                       "A request never crosses a contig boundary", "[start0,end0-1]",
                       "[start0+1,end0]", "both the canonical request and the translated library"):
            self.assertIn(clause, self.protocol)
        self.assertNotIn("Common [start,end] is 1-based inclusive", self.protocol)

    def test_v11_same_domain_and_timing_boundary(self):
        self.assertEqual(self.freeze["byte_domain"], "uppercase-sequence-without-FASTA-framing")
        for clause in ("`D_Q` and `Q` use this same canonical sequence-byte domain",
                       "outside the timed decode boundary", "native output-byte count and canonical count",
                       "the window-law row is FAILED", "do not relabel raw ISIZE as canonical Q"):
            self.assertIn(clause, self.protocol)

    def test_model_b_and_independent_calibration_retained(self):
        for clause in ("t(W)=c0+(W+Q-1)/D_Q", "c0 = median(t(W=1)) - Q/D_Q",
                       "separate 10,000-request", "same format, thread and seed rule",
                       "excluded from the verdict set W={1024,8192,65536}",
                       "If c0<0, model B is FAIL", "<=20% inclusive",
                       "at least four non-ACEAPEX formats",
                       "printed beside B but never affects the verdict"):
            self.assertIn(clause, self.protocol)
        self.assertEqual(self.freeze["window_law_primary"], "B")
        self.assertEqual(self.freeze["window_law_secondary"], "A")

    def test_pins_and_correctness_thresholds_unchanged(self):
        for literal in ("32246b48faee46807f84183dac4db479089f5445",
                        "e67e3fc865a459779118d3d4e9fbdf42c70ba75e",
                        "5b6d5cec0f5962a561ac48822a1b5c48793a5b47",
                        "seed 20261003", "10,000 requests per W", "one decode thread",
                        "load <0.5", ">20,000,000,000 bytes"):
            self.assertIn(literal, self.protocol)

    def test_freeze_names_prior_version_and_rerun_rule(self):
        self.assertEqual(self.freeze["supersedes_sha256"],
                         "0510e0fceaaf6e6eba291e440606a504ff61342e79e652f765eab1d0d1622646")
        self.assertEqual(self.freeze["change_rule"],
                         "semantic change requires new protocol version and complete rerun")


if __name__ == "__main__":
    unittest.main()
