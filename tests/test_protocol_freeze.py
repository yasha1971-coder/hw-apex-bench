import hashlib
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ProtocolFreezeTest(unittest.TestCase):
    def test_freeze_record_matches_the_canonical_protocol(self):
        freeze = json.loads((ROOT / "review/axis3/PROTOCOL_FREEZE.json").read_text())
        self.assertEqual(freeze["protocol_path"], "review/axis3/PROTOCOL_AXIS3.md")
        self.assertFalse((ROOT / "review/axis3/PROTOCOL_AXIS3.frozen.md").exists())
        digest = hashlib.sha256((ROOT / freeze["protocol_path"]).read_bytes()).hexdigest()
        self.assertEqual(digest, freeze["sha256"])


if __name__ == "__main__":
    unittest.main()
