import ctypes
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import agc_adapter as agc


class Fn:
    def __init__(self, fn): self.fn = fn
    def __call__(self, *a): return self.fn(*a)


class FakeLibrary:
    def __init__(self):
        self.calls = []
        self.truth = (b"ACGTN" * 1000)
        self.hwa_agc_open = Fn(lambda path, prefetch: 17)
        self.hwa_agc_length = Fn(lambda ctx, sample, contig: len(self.truth) if (sample, contig) == (b"asm2", b"shared") else -1)
        self.hwa_agc_fetch = Fn(self.fetch)
        self.hwa_agc_close = Fn(lambda ctx: self.calls.append(("close", ctx)))
        self.hwa_agc_error = Fn(lambda: b"mock refusal")
        self.hwa_agc_version = Fn(lambda: ("libagc-3.2.4@" + agc.PIN).encode())
    def fetch(self, ctx, sample, contig, start, length, dst, capacity):
        self.calls.append(("fetch", sample, contig, start, length, capacity))
        data = self.truth[start:start + length]
        ctypes.memmove(dst, data, len(data))
        return len(data)


class AgcAdapterTest(unittest.TestCase):
    def test_single_create_modes(self):
        for mode in ("t2t", "noref"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                rows = []
                for sample in ("asm1", "asm2", "asm3"):
                    fasta = root / f"{sample}.source"
                    fasta.write_bytes(b">shared" + bytes([10]) + b"ACGT" + bytes([10]))
                    rows.append((sample, fasta))
                reference = root / "ref.fa"
                reference.write_bytes(rows[0][1].read_bytes())
                out = root / "cohort.agc"
                calls = []
                def run(argv, **kwargs):
                    calls.append(argv)
                    self.assertEqual(argv[1], "create")
                    self.assertNotIn("append", argv)
                    self.assertEqual(argv.count("asm1.fa"), 1)
                    self.assertTrue(all((Path(kwargs["cwd"]) / f"{n}.fa").is_file() for n, _ in rows))
                    Path(argv[argv.index("-o") + 1]).write_bytes(b"mockAGC")
                    return subprocess.CompletedProcess(argv, 0, b"", b"")
                with patch.object(agc.subprocess, "run", side_effect=run):
                    receipt = agc.create(root / "agc", rows, mode, out, reference if mode == "t2t" else None)
                self.assertEqual(len(calls), 1)
                self.assertEqual(receipt["create_calls"], 1)
                self.assertEqual(receipt["append_calls"], 0)
                self.assertEqual(receipt["reference_sample"], "__reference_t2t" if mode == "t2t" else "asm1")
                self.assertEqual(receipt["archive_sha256"], hashlib.sha256(b"mockAGC").hexdigest())

    def test_range_uses_explicit_ids_and_no_process(self):
        fake = FakeLibrary()
        with patch.object(agc.ctypes, "CDLL", return_value=fake), patch.object(agc.subprocess, "run", side_effect=AssertionError("read spawned process")):
            with agc.AgcReader(Path("fake.so"), Path("fake.agc")) as reader:
                for start, length in ((0, 1), (0, 1024), (1000, 4096 - 100), (4999, 1)):
                    self.assertEqual(reader.fetch("asm2", "shared", start, length), fake.truth[start:start + length])
                self.assertEqual(fake.calls[0], ("fetch", b"asm2", b"shared", 0, 1, 1))
            self.assertEqual(fake.calls[-1], ("close", 17))

    def test_bounds_do_not_clip(self):
        fake = FakeLibrary()
        with patch.object(agc.ctypes, "CDLL", return_value=fake):
            with agc.AgcReader(Path("fake.so"), Path("fake.agc")) as reader:
                for start, length in ((-1, 1), (0, 0), (4999, 2), (5000, 1), (0, 5001), (True, 1)):
                    with self.assertRaises(ValueError): reader.fetch("asm2", "shared", start, length)
                with self.assertRaises(ValueError): reader.fetch("wrong_sample", "shared", 0, 1)
        self.assertFalse(any(c[0] == "fetch" for c in fake.calls))

    def test_receipt_hash_before_native_open(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "data.agc"
            p.write_bytes(b"wrong")
            with patch.object(agc.ctypes, "CDLL", side_effect=AssertionError("must not enter native parser")):
                with self.assertRaises(ValueError): agc.AgcReader(Path("fake.so"), p, "0" * 64)

    def test_create_rejects_ambiguous_mode_and_duplicate_sample(self):
        with self.assertRaises(ValueError): agc.create(Path("agc"), [("x", Path("a")), ("x", Path("b"))], "noref", Path("out"))
        with self.assertRaises(ValueError): agc.create(Path("agc"), [("x", Path("a"))], "noref", Path("out"), Path("t2t"))
        with self.assertRaises(ValueError): agc.create(Path("agc"), [("x", Path("a"))], "t2t", Path("out"))


if __name__ == "__main__": unittest.main()
