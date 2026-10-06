import ctypes
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zlib
import bgzf_adapter as bg


def member(data):
    c = zlib.compressobj(wbits=-15)
    raw = c.compress(data) + c.flush()
    n = 18 + len(raw) + 8
    return bytes.fromhex("1f8b08040000000000ff060042430200") + struct.pack("<H", n - 1) + raw + struct.pack("<II", zlib.crc32(data), len(data))


class Fn:
    def __init__(self, call): self.call = call
    def __call__(self, *args): return self.call(*args)


class Fake:
    def __init__(self):
        self.truth = b"ACGTN" * 20000
        self.calls = []
        self.hwa_bgzf_version = Fn(lambda: b"1.24")
        self.hwa_bgzf_matched = Fn(self.matched)
        self.hwa_bgzf_index = Fn(self.index)
        self.hwa_bgzf_open = Fn(lambda p: 13)
        self.hwa_bgzf_close = Fn(lambda h: self.calls.append(("close", h)))
        self.hwa_bgzf_length = Fn(lambda h, name: len(self.truth) if name == b"chr" else -1)
        self.hwa_bgzf_fetch = Fn(self.fetch)
    def matched(self, source, output, q):
        self.calls.append(("matched", q))
        data = Path(source.decode()).read_bytes()
        Path(output.decode()).write_bytes(b"".join(member(data[i:i+q]) for i in range(0, len(data), q)) + member(b""))
        return 0
    def index(self, archive):
        for suffix in (".fai", ".gzi"): Path(archive.decode() + suffix).write_bytes(b"index")
        return 0
    def fetch(self, handle, contig, start, length, output, capacity):
        self.calls.append(("fetch", contig, start, length))
        ctypes.memmove(output, self.truth[start:start+length], length)
        return length


class TestBGZF(unittest.TestCase):
    def test_geometry_and_truncated_header(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "input.bgz"
            data = member(b"A" * 4096) + member(b"BC" * 11) + member(b"")
            path.write_bytes(data)
            info = bg.blocks(path)
            self.assertEqual([b["ulen"] for b in info], [4096, 22])
            for bad in (data[:-1], data[:10], b"wrongmagic", data + b"x"):
                path.write_bytes(bad)
                with self.assertRaises(ValueError): bg.blocks(path)

    def test_stock_and_matched_build_production_paths(self):
        for mode, q in (("default", None), ("matched-g", 4096), ("matched-g", 65280)):
            with self.subTest(mode=mode, q=q), tempfile.TemporaryDirectory() as d:
                root = Path(d); source = root / "truth.fa"; output = root / "arc.bgz"
                source.write_bytes(b">chr" + bytes([10]) + b"ACGT" * 50000 + bytes([10]))
                fake = Fake(); calls = []
                def cli(argv, **kwargs):
                    calls.append(argv)
                    self.assertEqual(argv, ["bgzip", "-@", "1", "-c", str(source)])
                    data = source.read_bytes(); g = 65280
                    kwargs["stdout"].write(b"".join(member(data[i:i+g]) for i in range(0, len(data), g)) + member(b""))
                    return subprocess.CompletedProcess(argv, 0)
                with patch.object(bg.ctypes, "CDLL", return_value=fake), patch.object(bg.subprocess, "run", side_effect=cli):
                    receipt = bg.create("bgzip", "fake.so", source, output, mode, q)
                self.assertEqual(len(calls), 1 if mode == "default" else 0)
                self.assertEqual(receipt["uncompressed_fasta_bytes"], source.stat().st_size)
                self.assertEqual(receipt["storage_bytes"], output.stat().st_size + 10)
                self.assertEqual(len(receipt["artifacts"]), 3)

    def test_inprocess_boundaries_and_no_subprocess(self):
        fake = Fake()
        with patch.object(bg.ctypes, "CDLL", return_value=fake), patch.object(bg.subprocess, "run", side_effect=AssertionError("unexpected process")):
            with bg.BgzfReader("fake.so", "arc.bgz") as reader:
                for start, length in ((0, 1), (4095, 2), (65535, 8192), (99999, 1)):
                    self.assertEqual(reader.fetch("chr", start, length), fake.truth[start:start+length])
                for start, length in ((100000, 1), (0, 100001), (-1, 1), (0, 0), (True, 4)):
                    with self.assertRaises(ValueError): reader.fetch("chr", start, length)
                with self.assertRaises(ValueError): reader.fetch("unknown", 0, 1)
                with self.assertRaises(ValueError): reader.fetch("chr" + chr(0) + "other", 0, 1)
        self.assertEqual(fake.calls[-1], ("close", 13))

    def test_illegal_geometry_is_not_relabelled(self):
        for q in (0, 65536, 1048576, True, "16384"):
            with self.assertRaises(ValueError): bg.create("x", "lib", "source", "out", "matched-g", q)
        with self.assertRaises(ValueError): bg.create("x", "lib", "source", "out", "default", 4096)


if __name__ == "__main__": unittest.main()
