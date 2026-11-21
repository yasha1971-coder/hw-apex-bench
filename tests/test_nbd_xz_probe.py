"""HWAB-NBD-1: harness/nbd_xz_probe.py on a synthetic image (8 MiB: data in granules 0, 2, 5, zeros elsewhere).

Checks: the data map finds exactly those granules; every answer of nbdkit-xz-filter equals the raw bytes (0
mismatches, exit 0); negative control: the same archive judged against a raw image with one changed byte in every
data granule gives mismatches and exit 1 (the judge can fail). Skipped when nbdkit, its xz filter or python3-libnbd
are missing.
"""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; PROBE = ROOT / "harness" / "nbd_xz_probe.py"
MIB = 1 << 20


def have_tools():
    if not shutil.which("nbdkit") or not shutil.which("xz") or not os.path.exists("/usr/bin/time"): return False
    try: import nbd  # noqa: F401
    except ImportError: return False
    return subprocess.run(["nbdkit", "--dump-plugin", "--filter=xz", "null"], capture_output=True).returncode == 0


@unittest.skipUnless(have_tools(), "nbdkit with the xz filter, python3-libnbd, xz and /usr/bin/time needed")
class NbdXzProbe(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp()); self.raw = self.d / "img.raw"
        img = bytearray(8 * MIB)
        for gi in (0, 2, 5): img[gi * MIB:(gi + 1) * MIB] = os.urandom(MIB // 2) + bytes(MIB // 2)
        self.raw.write_bytes(img)
        self.xz = self.d / "img-g1M.raw.xz"
        with open(self.xz, "wb") as f:
            subprocess.run(["xz", "-6", "--block-size=1MiB", "-c", str(self.raw)], stdout=f, check=True)

    def tearDown(self): shutil.rmtree(self.d)

    def run_probe(self, raw, out):
        return subprocess.run([sys.executable, str(PROBE), "--raw", str(raw), "--archive", f"1:{self.xz}", "--n", "40",
                               "--repeats", "1", "--out", str(out), "--overhead"], capture_output=True, text=True)

    def test_answers_equal_raw(self):
        r = self.run_probe(self.raw, self.d / "ok")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        dm = json.load(open(self.d / "ok" / "data_map.json")); s = json.load(open(self.d / "ok" / "summary.json"))
        self.assertEqual(dm["granules"], [0, 2, 5]); self.assertEqual(dm["data_blocks"]["1"], 3)
        self.assertEqual(s["mismatches"], 0)
        row = s["rows"]["g1M"][0]
        for k in ("A_p50_ms", "B_p50_ms", "C_p50_ms", "peak_rss_kib"): self.assertIsNotNone(row.get(k), k)
        self.assertIn("file", s["rows"])

    def test_last_block_shorter_than_g(self):
        # 8 MiB image at g = 3 MiB with data in the last granule: the last block (granules 6-7) holds 2 MiB of the
        # image and is a data block; every planned read must stay inside the image (HWAB-NBD-1c: 5 GiB at g = 24 MiB)
        raw = self.d / "img7.raw"; img = bytearray(self.raw.read_bytes()); img[7 * MIB:] = os.urandom(MIB); raw.write_bytes(img)
        x3 = self.d / "img-g3M.raw.xz"
        with open(x3, "wb") as f:
            subprocess.run(["xz", "-6", "--block-size=3MiB", "-c", str(raw)], stdout=f, check=True)
        r = subprocess.run([sys.executable, str(PROBE), "--raw", str(raw), "--archive", f"3:{x3}", "--n", "60",
                            "--repeats", "1", "--out", str(self.d / "g3")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.load(open(self.d / "g3" / "summary.json"))["mismatches"], 0)

    def test_negative_control_judge_fails(self):
        bad = self.d / "bad.raw"; img = bytearray(self.raw.read_bytes())
        for gi in (0, 2, 5):
            for o in range(0, MIB // 2, 4096): img[gi * MIB + o] ^= 0xFF   # one byte in every 4 KiB of the data
        bad.write_bytes(img)
        r = self.run_probe(bad, self.d / "bad")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertGreater(json.load(open(self.d / "bad" / "summary.json"))["mismatches"], 0)


if __name__ == "__main__":
    unittest.main()
