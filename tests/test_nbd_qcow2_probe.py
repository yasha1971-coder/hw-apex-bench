"""HWAB-NBD-2: harness/nbd_qcow2_probe.py on a synthetic image (4 MiB: data in 64 KiB clusters 0, 3, 17, 40, zeros
elsewhere), compressed qcow2 with zstd and zlib (qemu-img convert -c).

Checks: the data map finds exactly those clusters; every answer of qemu-nbd equals the raw bytes (0 mismatches, exit 0)
for both images and for the NBD overhead row; negative control: the same images judged against a raw image with one
changed byte in every 4 KiB of the data give mismatches and exit 1 (the judge can fail). Skipped when qemu-img,
qemu-nbd, nbdkit or python3-libnbd are missing.
"""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; PROBE = ROOT / "harness" / "nbd_qcow2_probe.py"
CL = 65536; DATA = (0, 3, 17, 40)


def have_tools():
    if not all(shutil.which(t) for t in ("qemu-img", "qemu-nbd", "nbdkit")) or not os.path.exists("/usr/bin/time"): return False
    try: import nbd  # noqa: F401
    except ImportError: return False
    return True


@unittest.skipUnless(have_tools(), "qemu-img, qemu-nbd, nbdkit, python3-libnbd and /usr/bin/time needed")
class NbdQcow2Probe(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp()); self.raw = self.d / "img.raw"
        img = bytearray(64 * CL)
        for c in DATA: img[c * CL:(c + 1) * CL] = os.urandom(CL // 2) + bytes(CL // 2)
        self.raw.write_bytes(img); self.img = {}
        for z in ("zstd", "zlib"):
            p = self.d / f"img-{z}.qcow2"
            subprocess.run(["qemu-img", "convert", "-c", "-O", "qcow2", "-o", f"compression_type={z}", str(self.raw), str(p)], check=True)
            self.img[z] = p

    def tearDown(self): shutil.rmtree(self.d)

    def run_probe(self, raw, out):
        return subprocess.run([sys.executable, str(PROBE), "--raw", str(raw), "--image", f"qcow2-zstd:{self.img['zstd']}",
                               "--image", f"qcow2-zlib:{self.img['zlib']}", "--n", "40", "--repeats", "1", "--out", str(out),
                               "--overhead"], capture_output=True, text=True)

    def test_answers_equal_raw(self):
        r = self.run_probe(self.raw, self.d / "ok")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        dm = json.load(open(self.d / "ok" / "data_map.json")); s = json.load(open(self.d / "ok" / "summary.json"))
        self.assertEqual(dm["clusters"], list(DATA)); self.assertEqual(s["mismatches"], 0)
        for key in ("qcow2-zstd", "qcow2-zlib", "file"):
            row = s["rows"][key][0]
            for k in ("A_p50_ms", "C_p50_ms", "peak_rss_kib"): self.assertIsNotNone(row.get(k), (key, k))

    def test_negative_control_judge_fails(self):
        bad = self.d / "bad.raw"; img = bytearray(self.raw.read_bytes())
        for c in DATA:
            for o in range(0, CL // 2, 4096): img[c * CL + o] ^= 0xFF   # one byte in every 4 KiB of the data
        bad.write_bytes(img)
        r = self.run_probe(bad, self.d / "bad")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertGreater(json.load(open(self.d / "bad" / "summary.json"))["mismatches"], 0)


if __name__ == "__main__":
    unittest.main()
