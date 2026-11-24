"""Synthetic offline-contract tests. No codec is imported or executed.

All sample timings, hashes, archive geometries and offsets constructed here are
invented test inputs in a TemporaryDirectory; none is experimental evidence.
"""
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("gift1b_report", Path(__file__).with_name("report.py"))
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


def packed(value):
    return (json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n").encode()


def save(path, value):
    path.write_bytes(packed(value))


def sums(folder):
    (folder / "SHA256SUMS").write_bytes("".join(
        f"{report.sha(folder / name)}  {name}\n" for name in sorted(report.FILES)).encode())


class OfflineContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="hw-gift-1b-synthetic-tests-")
        cls.root = Path(cls.tmp.name)
        cls.evidence = cls.root / "hw-gift-1b"
        cls.baseline = cls.root / "hw-gift-1"
        cls.evidence.mkdir()
        cls.baseline.mkdir()
        cls.calibration = cls.evidence / "CALIBRATION.md"
        cls.calibration.write_bytes(Path(__file__).with_name("CALIBRATION.md").read_bytes())
        for chunk, (src, level) in report.CHUNKS.items():
            folder, baseline = cls.evidence / chunk, cls.baseline / chunk
            folder.mkdir()
            baseline.mkdir()
            original_rows = [dict(n=n, rep=rep, samples=[[rep * 10000 + i * 97, 0, 0] for i in range(1000)])
                             for n in report.NS for rep in range(5)]
            raw = b"".join(packed(r) for r in original_rows)
            source_hashes = {}
            for g in report.GS[:-1]:
                name = f"samples-{g}.jsonl.gz"
                (baseline / name).write_bytes(gzip.compress(raw, mtime=0))
                source_hashes[name] = report.sha(baseline / name)
            host = dict(cpu="AMD EPYC 9V74 synthetic test host", cpu_affinity=[0], kernel="test", os="synthetic",
                        python="3.12.14", python_implementation="CPython", pyzstd_version=report.PYZSTD_VERSION,
                        zstd_version="synthetic", host_boot_sha256="a" * 64,
                        installation_receipt=dict(pyzstd_version=report.PYZSTD_VERSION, pypi_version=report.PYZSTD_VERSION,
                                                  wheel_filename=report.WHEEL_FILENAME, wheel_sha256=report.WHEEL_SHA256))
            receipt = host["installation_receipt"]
            receipt["wheels"] = [dict(name=name, version=version, wheel_filename=filename,
                                     wheel_sha256=digest, pypi_json_sha256="f"*64,
                                     pypi_url=f"https://pypi.org/pypi/{name}/{version}/json")
                                 for name, version, filename, digest in (
                                     ("pyzstd", report.PYZSTD_VERSION, report.WHEEL_FILENAME, report.WHEEL_SHA256),
                                     ("backports-zstd", "1.0.0", "backports_zstd-1.0.0-synthetic.whl", "e"*64))]
            receipt["runtime"] = dict(python=host["python"], pyzstd_version=host["pyzstd_version"],
                                      zstd_version=host["zstd_version"], distributions={"pyzstd":report.PYZSTD_VERSION,"backports.zstd":"1.0.0"})
            receipt["installed_files_sha256"] = {"pyzstd/__init__.py":"a"*64,"backports/zstd/_zstd.so":"b"*64}
            run = dict(corpus=src, level=level, input_bytes=report.INPUT[src][0], input_sha256=report.INPUT[src][1],
                       protocol_commit=report.CAL, protocol_sha256=report.sha(cls.calibration), runner_commit="b" * 40,
                       runner_sha256="c" * 64, verifier_sha256="d" * 64, host=host, offset_source_sha256=source_hashes)
            save(folder / "run.json", run)
            archives, controls, old_archives = [], [], []
            for grid_index, g in enumerate(report.GS):
                name = report.frame_name(g)
                input_bytes = report.INPUT[src][0]
                frame_sizes = [input_bytes] if g is None else [min(g, input_bytes-offset) for offset in range(0, input_bytes, g)]
                seek_bytes = 17 + 8 * len(frame_sizes)
                archive_bytes = 10000000 - grid_index * 100000
                compressed = archive_bytes - seek_bytes
                q, r = divmod(compressed, len(frame_sizes))
                frames = [dict(compressed_bytes=q + (i < r), decompressed_bytes=size) for i, size in enumerate(frame_sizes)]
                digest = f"{grid_index+1:064x}"
                archives.append(dict(g=g, frame=name, bytes=archive_bytes, sha256=digest, frames=frames,
                                     frame_count=len(frames), decompressed_bytes=input_bytes, seek_table_bytes=seek_bytes,
                                     checksum_flag=False))
                if g is not None:
                    old_archives.append(dict(g=g, bytes=archive_bytes, sha256=digest))
                rows = []
                for n in report.NS:
                    controls.append(dict(g=g, frame=name, n=n, offset=0, exception="ZstdError",
                                         negative="pyzstd exception", archive_sha256=digest))
                    for rep in range(5):
                        base = 40000 if g is None else 1000
                        rows.append(dict(src=src, level=level, g=g, frame=name, n=n, rep=rep,
                                         archive_bytes=archive_bytes, archive_sha256=digest, peak_kib=100,
                                         samples=[[rep*10000 + i*97, i+10, base+rep*100+i, i+20] for i in range(1000)]))
                (folder / f"samples-{name}.jsonl.gz").write_bytes(gzip.compress(b"".join(packed(row) for row in rows), mtime=0))
            save(folder / "archives.json", archives)
            save(folder / "controls.json", controls)
            save(baseline / "archives.json", old_archives)
            sums(folder)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.saved = {}
        self.folder = self.evidence / "enwik8-L3"

    def tearDown(self):
        for path, content in self.saved.items():
            path.write_bytes(content)

    def change(self, name, mutate, *, gzip_rows=False, repair_sums=True):
        path = self.folder / name
        self.saved.setdefault(path, path.read_bytes())
        if gzip_rows:
            data = [json.loads(line) for line in gzip.decompress(path.read_bytes()).splitlines()]
            mutate(data)
            path.write_bytes(gzip.compress(b"".join(packed(r) for r in data), mtime=0))
        else:
            data = json.loads(path.read_bytes())
            mutate(data)
            save(path, data)
        if repair_sums:
            checksum = self.folder / "SHA256SUMS"
            self.saved.setdefault(checksum, checksum.read_bytes())
            sums(self.folder)

    def verify(self):
        return report.verify_chunk(self.folder, "enwik8-L3", baseline_root=self.baseline)

    def test_complete_grid_and_deterministic_report(self):
        chunks = report.verify_all(self.evidence, baseline_root=self.baseline)
        result = report.build_report(chunks, baseline_root=self.baseline)
        self.assertEqual(result, report.build_report(chunks, baseline_root=self.baseline))
        self.assertIn("**HIT**", result)
        self.assertIn("|1073741824|yes|", result)
        self.assertEqual(len(report.predictions(chunks, baseline_root=self.baseline)["deviations"]), 24)

    def test_exact_integer_nearest_rank_reduction(self):
        chunk = self.verify()
        result = report.metrics([chunk["rows"][1048576, 4096, r] for r in range(5)])
        self.assertEqual(result, (509, 1699, 2189, 519, 1009))
        self.assertEqual(report.ms(101840392), "101.840392")

    def test_tamper_without_repaired_sums_is_rejected(self):
        self.change("run.json", lambda r: r.update(level=19), repair_sums=False)
        with self.assertRaisesRegex(ValueError, "SHA256SUMS"):
            self.verify()

    def test_changed_offset_with_repaired_sums_is_rejected(self):
        self.change("samples-65536.jsonl.gz", lambda rows: rows[0]["samples"][0].__setitem__(0, 1), gzip_rows=True)
        with self.assertRaisesRegex(ValueError, "offset sequence"):
            self.verify()

    def test_bool_is_not_a_timing(self):
        self.change("samples-65536.jsonl.gz", lambda rows: rows[0]["samples"][0].__setitem__(2, True), gzip_rows=True)
        with self.assertRaisesRegex(ValueError, "raw sample"):
            self.verify()

    def test_duplicate_row_is_rejected(self):
        self.change("samples-65536.jsonl.gz", lambda rows: rows.__setitem__(1, copy.deepcopy(rows[0])), gzip_rows=True)
        with self.assertRaisesRegex(ValueError, "duplicate sample"):
            self.verify()

    def test_archive_accounting_is_rejected(self):
        self.change("archives.json", lambda a: a[0].update(bytes=a[0]["bytes"]+1))
        with self.assertRaisesRegex(ValueError, "byte accounting"):
            self.verify()

    def test_default_must_be_one_frame(self):
        def mutate(archives):
            a = archives[-1]
            a["frames"] = [dict(compressed_bytes=100, decompressed_bytes=1),
                           dict(compressed_bytes=a["bytes"]-100-33, decompressed_bytes=a["decompressed_bytes"]-1)]
            a.update(frame_count=2, seek_table_bytes=33)
        self.change("archives.json", mutate)
        with self.assertRaisesRegex(ValueError, "one corpus frame"):
            self.verify()

    def test_negative_control_requires_exception(self):
        self.change("controls.json", lambda c: c[0].update(negative="byte mismatch"))
        with self.assertRaisesRegex(ValueError, "did not raise"):
            self.verify()

    def test_wrong_wheel_is_rejected(self):
        self.change("run.json", lambda r: r["host"]["installation_receipt"].update(wheel_sha256="0"*64))
        with self.assertRaisesRegex(ValueError, "wheel differs"):
            self.verify()

    def test_unpinned_native_dependency_is_rejected(self):
        self.change("run.json", lambda r: r["host"]["installation_receipt"].update(
            wheels=r["host"]["installation_receipt"]["wheels"][:1]))
        with self.assertRaisesRegex(ValueError, "pinned native"):
            self.verify()

    def test_mixed_host_is_rejected(self):
        self.change("run.json", lambda r: r["host"].update(host_boot_sha256="f"*64))
        with self.assertRaisesRegex(ValueError, "host boundary"):
            report.verify_all(self.evidence, baseline_root=self.baseline)

    def test_partial_report_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "all four"):
            report.build_report({"enwik8-L3": self.verify()}, baseline_root=self.baseline)

    def test_size_gate_exactly_one_percent_and_one_byte_over(self):
        chunks = report.verify_all(self.evidence, baseline_root=self.baseline)
        row = chunks["enwik8-L3"]["archives"][0]
        row["bytes"] = 10100000
        self.assertTrue(report.predictions(chunks, baseline_root=self.baseline)["size_pass"])
        row["bytes"] += 1
        gates = report.predictions(chunks, baseline_root=self.baseline)
        self.assertFalse(gates["size_pass"])
        self.assertEqual(sum(not d["passed"] for d in gates["deviations"]), 1)

    def test_latency_gate_exactly_twenty_and_one_ns_below(self):
        chunks = report.verify_all(self.evidence, baseline_root=self.baseline)
        anchor = chunks["enwik8-L3"]["rows"]
        for rep in range(5):
            for sample in anchor[None, 4096, rep]["samples"]:
                sample[2] = 20 * 1699
        self.assertTrue(report.predictions(chunks, baseline_root=self.baseline)["latency_pass"])
        for rep in range(5):
            for sample in anchor[None, 4096, rep]["samples"]:
                sample[2] -= 1
        self.assertFalse(report.predictions(chunks, baseline_root=self.baseline)["latency_pass"])


if __name__ == "__main__":
    unittest.main()
