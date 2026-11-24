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
import tarfile
import io
import unittest
from unittest import mock

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


def clean_benchmark_entry(row,host):
    def boundary(second):
        return dict(timestamp_utc=f"2026-11-24T00:00:{second:02d}+00:00",
                    date_u="Tue Nov 24 00:00:03 UTC 2026\n",loadavg_raw="0.50 0.40 0.30 1/100 123\n",nproc=16,
                    hostname=host["hostname"],cpu=host["cpu"],kernel=host["kernel"],
                    governor=host["governor"],pinned_core=0,other_processes=[])
    start,end=boundary(3),boundary(4)
    start.update(proc_stat_raw="cpu0 100 0 10 200 5 0 0 0\ncpu1 100 0 10 200 5 0 0 0 20 0\n",proc_stat_error=None)
    end.update(proc_stat_raw="cpu0 110 0 20 220 10 0 0 0\ncpu1 110 0 20 220 10 0 0 0 30 0\n",proc_stat_error=None)
    delta=dict(status="ok",pinned_core=0,cpus={"cpu1":dict(total_jiffies=45,busy_jiffies=20,idle_jiffies=20,iowait_jiffies=5,busy_percent=100.0*20/45)})
    start["other_cpu_delta"],end["other_cpu_delta"]=copy.deepcopy(delta),copy.deepcopy(delta)
    receipt=dict(schema="ovh-bench-v2",policy_commit=report.POLICY,status="CLEAN",helper_sha256="f"*64,
                 threshold_amendment_commit=report.THRESHOLD_AMENDMENT,load1_threshold="2.0",
                 lock_path=report.BENCH_LOCK,flock_command=["flock",report.BENCH_LOCK,"python","-B","synthetic-helper.py","_inside"],
                 command=["python","-B","synthetic-measure.py"],returncode=0,command_started=True,
                 waiting_since_utc="2026-11-24T00:00:02+00:00",start=start,end=end)
    return dict(g=row["g"],n=row["n"],rep=row["rep"],receipt=receipt,
                row_sha256=report.hashlib.sha256(packed(row)).hexdigest())


def pack_payload(folder,payload):
    raw=io.BytesIO()
    with tarfile.open(fileobj=raw,mode="w") as archive:
        for name,data in sorted(payload.items()):
            info=tarfile.TarInfo(name)
            info.size=len(data)
            archive.addfile(info,io.BytesIO(data))
    (folder/"attempts.tar.gz").write_bytes(gzip.compress(raw.getvalue(),mtime=0))
    save(folder/"attempts.json",dict(schema="hw-gift-1b-attempts-v1",archive_file="attempts.tar.gz",
                                   archive_sha256=report.sha(folder/"attempts.tar.gz"),
                                   files=[dict(path=name,bytes=len(data),sha256=report.hashlib.sha256(data).hexdigest())
                                          for name,data in sorted(payload.items())]))


def fixture_attempts(folder,run,rows,reader):
    payload={}
    logical=[*run["benchmark_runs"],*([run["blocked_repeat"]] if "blocked_repeat" in run else [])]
    for repeat in logical:
        key=repeat["g"],repeat["n"],repeat["rep"]
        row=rows[key]
        if "attempts" not in repeat:
            repeat["attempts"]=[dict(attempt=1,status="CLEAN",receipt=copy.deepcopy(repeat["receipt"]),row_sha256=repeat["row_sha256"])]
        if "receipt" in repeat:
            repeat["attempts"][-1].update(receipt=copy.deepcopy(repeat["receipt"]),row_sha256=repeat["row_sha256"])
        for attempt in repeat["attempts"]:
            receipt=attempt["receipt"]
            name=f"{report.frame_name(key[0])}-{key[1]}-{key[2]}/attempt-{attempt['attempt']}/ovh-bench.json"
            attempt["receipt_path"]=name
            native={k:v for k,v in row.items() if k not in ("src","level","g","n","rep")}
            output=packed(native) if reader=="c" and receipt["command_started"] else b""
            receipt.update(stdout_sha256=report.hashlib.sha256(output).hexdigest(),stderr_sha256=report.hashlib.sha256(b"").hexdigest())
            payload[name+".stdout"],payload[name+".stderr"]=output,b""
            if receipt["command_started"]:
                if reader=="pyzstd":
                    raw_name=str(Path(name).with_name("row.json")).replace("\\","/")
                    attempt["raw_row_path"]=raw_name
                    payload[raw_name]=packed(row)
                else:
                    attempt["raw_stdout_path"]=name+".stdout"
                    attempt["raw_stdout_sha256"]=report.hashlib.sha256(output).hexdigest()
            else:
                attempt["raw_row_path"]=None
            payload[name]=packed(receipt)
        if "receipt" in repeat:
            repeat["receipt"]=copy.deepcopy(repeat["attempts"][-1]["receipt"])
    run.update(load_amendment_commit=report.LOAD_AMENDMENT,planned_repeats=70 if reader=="pyzstd" else 60,
               threshold_amendment_commit=report.THRESHOLD_AMENDMENT,load1_threshold="2.0",
               started_repeats=len(logical),retaken_repeats=sum(len(r["attempts"])>1 for r in logical),
               loaded_attempts=sum(a["status"]=="LOADED" for r in logical for a in r["attempts"]))
    pack_payload(folder,payload)


def loaded_attempt(receipt,index):
    receipt=copy.deepcopy(receipt)
    receipt.update(status="LOADED",command_started=False,returncode=None,
                   ps_command="ps -eo pid,user,pcpu,comm --sort=-pcpu | head -8",
                   ps_top8="    PID USER     %CPU COMMAND\n    123 other    9.9 synthetic\n",
                   ps_captured_utc=f"2026-11-24T00:00:{index*3+2:02d}+00:00",
                   waiting_since_utc=f"2026-11-24T00:00:{index*3-1:02d}+00:00")
    for name,second in (("start",index*3),("end",index*3+1)):
        receipt[name].update(loadavg_raw="2.10 0.40 0.30 1/100 123\n",
                             timestamp_utc=f"2026-11-24T00:00:{second:02d}+00:00")
    return dict(attempt=index,status="LOADED",receipt=receipt,row_sha256=None,raw_row_path=None)


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
        cls.calibration.write_text(Path(__file__).with_name("CALIBRATION.md").read_text(encoding="utf-8"),
                                   encoding="utf-8", newline="\n")
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
            host = dict(cpu="AMD EPYC 4344P synthetic test host", hostname="ace-core", governor="performance",
                        cpu_affinity=[0], kernel="test", os="synthetic",
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
                       amendment_commit=report.AMENDMENT, original_protocol_sha256=report.ORIGINAL_PROTOCOL_SHA256,
                       runner_sha256="c" * 64, verifier_sha256="d" * 64, guard_sha256="e"*64, attempt=1,
                       host=host, offset_source_sha256=source_hashes)
            def snapshot(start, end):
                return dict(sample_start_utc=f"2026-11-24T00:00:{start:02d}+00:00",
                            sample_end_utc=f"2026-11-24T00:00:{end:02d}+00:00", interval_ns=1000000000,
                            hostname=host["hostname"], cpu=host["cpu"], kernel=host["kernel"],
                            governor=host["governor"], pinned_core=0, loadavg=[0.0,0.0,0.0],
                            other_load=dict(busy=False, active_processes=[], inspection_errors=[]))
            run.update(load_start=snapshot(0,1), load_end=snapshot(10,11), load_accepted=True, load_resume_starts=[])
            run.update(ovh_policy_commit=report.POLICY,ovh_bench_sha256="f"*64,benchmark_runs=[])
            save(folder / "run.json", run)
            archives, controls, old_archives = [], [], []
            all_py_rows={}
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
                run["benchmark_runs"].extend(clean_benchmark_entry(row,host) for row in rows)
                all_py_rows.update({(row["g"],row["n"],row["rep"]):row for row in rows})
            fixture_attempts(folder,run,all_py_rows,"pyzstd")
            save(folder / "run.json",run)
            save(folder / "archives.json", archives)
            save(folder / "controls.json", controls)
            save(baseline / "archives.json", old_archives)
            sums(folder)
            c_folder = cls.evidence / "c-baseline" / chunk
            c_folder.mkdir(parents=True)
            c_controls = []
            c_benchmark_runs=[]
            all_c_rows={}
            for archive in old_archives:
                g = archive["g"]
                py_rows = [json.loads(line) for line in gzip.decompress((folder/f"samples-{g}.jsonl.gz").read_bytes()).splitlines()]
                c_rows = []
                for n in report.NS:
                    negative = dict(src=src, level=level, g=g, n=n, rep=-1, negative="native error",
                                    archive_bytes=archive["bytes"], archive_sha256=archive["sha256"])
                    c_rows.append(negative)
                    c_controls.append({key:negative[key] for key in ("g","n","archive_sha256","negative")})
                    for rep in range(5):
                        py_row = next(r for r in py_rows if r["n"]==n and r["rep"]==rep)
                        c_rows.append(dict(src=src,level=level,g=g,n=n,rep=rep,peak_kib=100,
                                           samples=[[p[0],p[2],p[3]] for p in py_row["samples"]]))
                (c_folder/f"samples-{g}.jsonl.gz").write_bytes(gzip.compress(b"".join(packed(r) for r in c_rows),mtime=0))
                c_benchmark_runs.extend(clean_benchmark_entry(row,host) for row in c_rows if row["rep"]>=0)
                all_c_rows.update({(row["g"],row["n"],row["rep"]):row for row in c_rows if row["rep"]>=0})
            c_host = {k:host[k] for k in ("cpu","cpu_affinity","kernel","os","host_boot_sha256")}
            c_host.update(zstd_commit=report.ZSTD_COMMIT,zstd_linked="1.5.7",worker_sha256=report.C_WORKER_SHA256,
                          pair_sha256=report.C_PAIR_SHA256,adapter_sha256=report.C_ADAPTER_SHA256,
                          encoder_sha256="c"*64,reader_sha256="d"*64)
            save(c_folder/"run.json",dict(corpus=src,level=level,input_bytes=report.INPUT[src][0],input_sha256=report.INPUT[src][1],host=c_host))
            save(c_folder/"archives.json",old_archives)
            save(c_folder/"controls.json",c_controls)
            (c_folder/"SHA256SUMS").write_bytes("".join(f"{report.sha(c_folder/name)}  {name}\n" for name in sorted(report.C_FILES)).encode())
            acecore = dict(amendment_commit=report.AMENDMENT,protocol_sha256=report.sha(cls.calibration),
                           original_sha256sums_sha256=report.sha(c_folder/"SHA256SUMS"),
                           host={k:host[k] for k in ("hostname","cpu","cpu_affinity","kernel","os","host_boot_sha256","governor")},
                           load_start=snapshot(0,1),load_end=snapshot(10,11),load_accepted=True,
                           ovh_policy_commit=report.POLICY,ovh_bench_sha256="f"*64,benchmark_runs=c_benchmark_runs,
                           source_sha256={name:report.canonical_source_sha(report.REPO,name) for name in report.C_SOURCE_PATHS})
            fixture_attempts(c_folder,acecore,all_c_rows,"c")
            save(c_folder/"acecore.json",acecore)
        # Construct a wholly invented immutable 45-repeat v1 cohort for the
        # retention contract. Only this explicit fixture replaces Git lookup.
        c_folder=cls.evidence/"c-baseline"/"enwik8-L3"
        active=json.loads((c_folder/"acecore.json").read_bytes())
        c_rows={}
        for g in report.GS[:-1]:
            for row in [json.loads(line) for line in gzip.decompress((c_folder/f"samples-{g}.jsonl.gz").read_bytes()).splitlines()]:
                if row["rep"]>=0:c_rows[row["g"],row["n"],row["rep"]]=row
        old_runs=copy.deepcopy(active["benchmark_runs"][:45])
        for repeat in old_runs:
            receipt=repeat["receipt"]
            receipt.update(schema="ovh-bench-v1",helper_sha256=report.OLD_HELPER_SHA256)
            for field in ("threshold_amendment_commit","load1_threshold"):receipt.pop(field,None)
            for boundary in (receipt["start"],receipt["end"]):
                for field in ("proc_stat_raw","proc_stat_error","other_cpu_delta"):boundary.pop(field,None)
            repeat["attempts"][0]["receipt"]=copy.deepcopy(receipt)
        old_blocked=dict(g=16777216,n=65536,rep=0,attempts=[loaded_attempt(old_runs[0]["receipt"],i) for i in range(1,4)])
        old_record=dict(ovh_bench_sha256=report.OLD_HELPER_SHA256,benchmark_runs=old_runs,
                        blocked_repeat=old_blocked,host=active["host"])
        old_folder=cls.root/"invented-approved-snapshot";old_folder.mkdir()
        fixture_attempts(old_folder,old_record,c_rows,"c")
        old_payload=report.verify_attempt_artifact(old_folder)
        snapshot=dict(record=old_record,payload=old_payload,snapshot_sha256=report.hashlib.sha256(packed(old_record)).hexdigest(),
                      snapshot_attempts_sha256=report.sha(old_folder/"attempts.tar.gz"))
        cls.snapshot_patch=mock.patch.object(report,"immutable_retention_snapshot",return_value=snapshot)
        cls.snapshot_patch.start()
        active["benchmark_runs"][:45]=copy.deepcopy(old_record["benchmark_runs"])
        fixture_attempts(c_folder,active,c_rows,"c")
        payload=report.verify_attempt_artifact(c_folder)
        prefix=str(Path(old_blocked["attempts"][0]["receipt_path"]).parent.parent).replace("\\","/")+"/"
        payload.update({"pre-threshold/c8de6772/"+name:data for name,data in old_payload.items() if name.startswith(prefix)})
        pack_payload(c_folder,payload)
        retention=dict(schema="hw-gift-1b-approved-retention-v1",threshold_amendment_commit=report.THRESHOLD_AMENDMENT,
                       snapshot_commit=report.OLD_SNAPSHOT_COMMIT,snapshot_path=report.OLD_SNAPSHOT_PATH,
                       snapshot_sha256=snapshot["snapshot_sha256"],snapshot_attempts_sha256=snapshot["snapshot_attempts_sha256"],
                       retained_count=45,retained_runs_sha256=report.row_digest(old_record["benchmark_runs"]),
                       pre_threshold_blocked_repeat=old_record["blocked_repeat"],old_helper_sha256=report.OLD_HELPER_SHA256,
                       new_helper_sha256=active["ovh_bench_sha256"],reset_key=dict(g=16777216,n=65536,rep=0),reset_once=True,
                       history_prefix="pre-threshold/c8de6772",
                       retained_receipt_paths=sorted(a["receipt_path"] for r in old_record["benchmark_runs"] for a in r["attempts"]))
        active.update(approved_retention=retention,retaken_repeats=1,historical_loaded_attempts=3)
        save(c_folder/"acecore.json",active)

    @classmethod
    def tearDownClass(cls):
        cls.snapshot_patch.stop()
        cls.tmp.cleanup()

    def setUp(self):
        self.saved = {}
        self.folder = self.evidence / "enwik8-L3"

    def tearDown(self):
        for path, content in self.saved.items():
            path.write_bytes(content)

    def change(self, name, mutate, *, gzip_rows=False, repair_sums=True, sync_artifact=True):
        path = self.folder / name
        self.saved.setdefault(path, path.read_bytes())
        if gzip_rows:
            data = [json.loads(line) for line in gzip.decompress(path.read_bytes()).splitlines()]
            mutate(data)
            path.write_bytes(gzip.compress(b"".join(packed(r) for r in data), mtime=0))
        else:
            data = json.loads(path.read_bytes())
            mutate(data)
            if name=="run.json" and sync_artifact:
                for artifact in ("attempts.tar.gz","attempts.json"):
                    artifact_path=self.folder/artifact
                    self.saved.setdefault(artifact_path,artifact_path.read_bytes())
                rows={}
                for g in report.GS:
                    for row in [json.loads(line) for line in gzip.decompress((self.folder/f"samples-{report.frame_name(g)}.jsonl.gz").read_bytes()).splitlines()]:
                        rows[row["g"],row["n"],row["rep"]]=row
                fixture_attempts(self.folder,data,rows,"pyzstd")
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

    def test_foreign_workload_is_observational_below_load_threshold(self):
        def mutate(run):
            process=dict(pid=123,comm="synthetic-other-job",cpu_ticks_delta=10)
            run["load_end"]["other_load"].update(busy=True,active_processes=[process])
            run["benchmark_runs"][0]["receipt"]["start"]["other_processes"].append(process)
        self.change("run.json",mutate)
        self.verify()

    def test_resume_load_inspection_errors_are_observational(self):
        def mutate(run):
            snapshot=copy.deepcopy(run["load_start"])
            snapshot.update(sample_start_utc="2026-11-24T00:00:05+00:00",sample_end_utc="2026-11-24T00:00:06+00:00")
            snapshot["other_load"]["inspection_errors"].append("synthetic /proc inspection error")
            run["load_resume_starts"].append(snapshot)
        self.change("run.json",mutate)
        self.verify()

    def test_governor_change_is_rejected(self):
        self.change("run.json",lambda r:r["load_end"].update(governor="powersave"))
        with self.assertRaisesRegex(ValueError,"governor"):
            self.verify()

    def test_c_manifest_binding_is_rejected(self):
        path=self.evidence/"c-baseline"/"enwik8-L3"/"acecore.json"
        self.saved[path]=path.read_bytes()
        value=json.loads(path.read_bytes())
        value["original_sha256sums_sha256"]="0"*64
        save(path,value)
        with self.assertRaisesRegex(ValueError,"bind original"):
            report.verify_c_chunk(path.parent,"enwik8-L3",baseline_root=self.baseline)

    def test_c_timed_source_mismatch_is_rejected(self):
        path=self.evidence/"c-baseline"/"enwik8-L3"/"acecore.json"
        self.saved[path]=path.read_bytes()
        value=json.loads(path.read_bytes())
        value["source_sha256"]["evidence/hw-gift-1/sweep.py"]="0"*64
        save(path,value)
        with self.assertRaisesRegex(ValueError,"source changed"):
            report.verify_c_chunk(path.parent,"enwik8-L3",baseline_root=self.baseline)

    def test_c_repeat_percentiles_and_same_host_report(self):
        chunks=report.verify_all(self.evidence,baseline_root=self.baseline)
        c=chunks["_c_baseline"]["enwik8-L3"]["rows"]
        self.assertEqual(report.c_metrics([c[65536,4096,r] for r in range(5)]),(1699,2189,519,1009))
        self.assertIn("Matched-host C-reader comparison",report.build_report(chunks,baseline_root=self.baseline))

    def test_c_source_hash_uses_pinned_git_blob(self):
        with mock.patch.object(report.subprocess,"check_output",return_value=b"canonical LF\n") as command:
            actual=report.canonical_source_sha(report.REPO,"evidence/hw-gift-1/sweep.py")
        self.assertEqual(actual,report.hashlib.sha256(b"canonical LF\n").hexdigest())
        command.assert_called_once_with(["git","-C",str(report.REPO),"show",
                                         report.C_SOURCE_COMMIT+":evidence/hw-gift-1/sweep.py"])

    def test_c_source_hash_nongit_fixture_uses_fixture_bytes(self):
        with tempfile.TemporaryDirectory(prefix="hw-gift-1b-nongit-fixture-") as directory:
            path=Path(directory)/"synthetic.py"
            path.write_bytes(b"invented CRLF\r\n")
            with mock.patch.object(report.subprocess,"check_output") as command:
                self.assertEqual(report.canonical_source_sha(directory,path.name),report.sha(path))
            command.assert_not_called()

    def test_load_boundary_two_point_zero_is_accepted(self):
        def mutate(run):
            receipt=run["benchmark_runs"][0]["receipt"]
            receipt["start"]["loadavg_raw"]="2.0 5.00 8.00 1/100 123\n"
            receipt["end"]["loadavg_raw"]="2.00000000000000000000 5.00 8.00 1/100 123\n"
        self.change("run.json",mutate)
        self.verify()

    def test_loaded_two_point_zero_one_is_rejected(self):
        self.change("run.json",lambda r:r["benchmark_runs"][0]["receipt"]["end"].update(
            loadavg_raw="2.01 0.40 0.30 1/100 123\n"))
        with self.assertRaisesRegex(ValueError,"LOADED"):
            self.verify()

    def test_load_threshold_compares_exact_decimals(self):
        self.change("run.json",lambda r:r["benchmark_runs"][0]["receipt"]["start"].update(
            loadavg_raw="2.00000000000000000001 0.40 0.30 1/100 123\n"))
        with self.assertRaisesRegex(ValueError,"LOADED"):
            self.verify()

    def test_loaded_status_is_never_accepted(self):
        self.change("run.json",lambda r:r["benchmark_runs"][0]["receipt"].update(status="LOADED"))
        with self.assertRaisesRegex(ValueError,"not CLEAN"):
            self.verify()

    def test_nonblocking_lock_command_is_rejected(self):
        self.change("run.json",lambda r:r["benchmark_runs"][0]["receipt"]["flock_command"].insert(1,"-n"))
        with self.assertRaisesRegex(ValueError,"blocking shared flock"):
            self.verify()

    def test_missing_timed_repeat_receipt_is_rejected(self):
        self.change("run.json",lambda r:r["benchmark_runs"].pop())
        with self.assertRaisesRegex(ValueError,"timed-repeat receipts"):
            self.verify()

    def test_timed_receipt_row_binding_is_rejected(self):
        self.change("run.json",lambda r:r["benchmark_runs"][0].update(row_sha256="0"*64))
        with self.assertRaisesRegex(ValueError,"row binding"):
            self.verify()

    def test_new_cpu_deltas_are_recomputed_from_first_eight_counters(self):
        def mutate(run):
            receipt=run["benchmark_runs"][0]["receipt"]
            for boundary in (receipt["start"],receipt["end"]):
                boundary["other_cpu_delta"]["cpus"]["cpu1"]["busy_jiffies"]+=1
        self.change("run.json",mutate)
        with self.assertRaisesRegex(ValueError,"does not match raw"):
            self.verify()

    def test_new_cpu_monitor_unavailable_is_observational(self):
        def mutate(run):
            receipt=run["benchmark_runs"][0]["receipt"]
            for boundary in (receipt["start"],receipt["end"]):
                boundary.update(proc_stat_raw=None,proc_stat_error="synthetic capture error",
                                other_cpu_delta=dict(status="unavailable",pinned_core=0,cpus={},error="capture unavailable"))
        self.change("run.json",mutate)
        self.verify()

    def test_guest_counters_do_not_change_cpu_utilization(self):
        self.change("run.json",lambda run:run["benchmark_runs"][0]["receipt"]["end"].update(
            proc_stat_raw="cpu0 110 0 20 220 10 0 0 0 99999 99999\ncpu1 110 0 20 220 10 0 0 0 99999 99999\n"))
        self.verify()

    def test_new_python_cohort_cannot_use_legacy_receipts(self):
        self.change("run.json",lambda run:run["benchmark_runs"][0]["receipt"].update(schema="ovh-bench-v1"))
        with self.assertRaisesRegex(ValueError,"unapproved legacy"):
            self.verify()

    def test_c_enwik8_requires_the_authorized_retention(self):
        path=self.evidence/"c-baseline"/"enwik8-L3"/"acecore.json"
        self.saved[path]=path.read_bytes();record=json.loads(path.read_bytes());record.pop("approved_retention")
        save(path,record)
        with self.assertRaisesRegex(ValueError,"must retain"):
            report.verify_c_chunk(path.parent,"enwik8-L3",baseline_root=self.baseline)

    def test_retained_45_dictionaries_cannot_be_backfilled(self):
        path=self.evidence/"c-baseline"/"enwik8-L3"/"acecore.json"
        self.saved[path]=path.read_bytes();record=json.loads(path.read_bytes())
        record["benchmark_runs"][0]["receipt"]["start"]["proc_stat_raw"]="invented backfill"
        save(path,record)
        with self.assertRaisesRegex(ValueError,"45 approved CLEAN"):
            report.verify_c_chunk(path.parent,"enwik8-L3",baseline_root=self.baseline)

    def test_authorized_reset_is_counted_and_historical_loads_are_separate(self):
        result=report.verify_c_chunk(self.evidence/"c-baseline"/"enwik8-L3","enwik8-L3",baseline_root=self.baseline)
        self.assertEqual(result["retry_counts"]["retaken_repeats"],1)
        self.assertEqual(result["retry_counts"]["loaded_attempts"],0)
        self.assertEqual(result["retry_counts"]["historical_loaded_attempts"],3)
        old=result["acecore"]["benchmark_runs"][:45]
        self.assertTrue(all("proc_stat_raw" not in r["receipt"]["start"] for r in old))

    def test_legacy_receipt_keeps_the_stricter_one_point_zero_threshold(self):
        old=copy.deepcopy(report.immutable_retention_snapshot()["record"]["benchmark_runs"][0]["receipt"])
        old["start"]["loadavg_raw"]="1.01 0.00 0.00 1/100 123\n"
        host=json.loads((self.folder/"run.json").read_bytes())["host"]
        with self.assertRaisesRegex(ValueError,"LOADED status"):
            report.verify_benchmark_receipt(old,host,report.OLD_HELPER_SHA256,"CLEAN")

    def test_retention_snapshot_anchor_tamper_is_rejected(self):
        path=self.evidence/"c-baseline"/"enwik8-L3"/"acecore.json"
        self.saved[path]=path.read_bytes();record=json.loads(path.read_bytes())
        record["approved_retention"]["snapshot_sha256"]="0"*64
        save(path,record)
        with self.assertRaisesRegex(ValueError,"snapshot_sha256"):
            report.verify_c_chunk(path.parent,"enwik8-L3",baseline_root=self.baseline)

    def test_loaded_twice_then_first_clean_is_accepted(self):
        def mutate(run):
            repeat=run["benchmark_runs"][0]
            first=loaded_attempt(repeat["receipt"],1)
            second=loaded_attempt(repeat["receipt"],2)
            third=copy.deepcopy(repeat["attempts"][-1])
            third["attempt"]=3
            third["receipt"]["waiting_since_utc"]="2026-11-24T00:00:08+00:00"
            third["receipt"]["start"]["timestamp_utc"]="2026-11-24T00:00:09+00:00"
            third["receipt"]["end"]["timestamp_utc"]="2026-11-24T00:00:10+00:00"
            repeat.update(attempts=[first,second,third],receipt=third["receipt"])
        self.change("run.json",mutate)
        result=self.verify()
        self.assertEqual(result["retry_counts"]["retaken_repeats"],1)
        self.assertEqual(result["retry_counts"]["loaded_attempts"],2)
        self.assertEqual(result["retry_counts"]["started_repeats"],70)

    def test_clean_repeat_must_not_be_retimed(self):
        def mutate(run):
            repeat=run["benchmark_runs"][0]
            extra=copy.deepcopy(repeat["attempts"][0])
            extra["attempt"]=2
            repeat["attempts"].append(extra)
        self.change("run.json",mutate)
        with self.assertRaisesRegex(ValueError,"first CLEAN wins"):
            self.verify()

    def test_four_attempts_are_prohibited(self):
        def mutate(run):
            repeat=run["benchmark_runs"][0]
            repeat["attempts"]=[loaded_attempt(repeat["receipt"],i) for i in range(1,4)]+[copy.deepcopy(repeat["attempts"][0])]
            repeat["attempts"][-1]["attempt"]=4
        self.change("run.json",mutate)
        with self.assertRaisesRegex(ValueError,"one to three total"):
            self.verify()

    def test_nonzero_child_is_fatal_even_when_loaded(self):
        def mutate(run):
            repeat=run["benchmark_runs"][0]
            first=loaded_attempt(repeat["receipt"],1)
            first["receipt"].update(command_started=True,returncode=5)
            final=copy.deepcopy(repeat["attempts"][0])
            final["attempt"]=2
            repeat["attempts"]=[first,final]
        self.change("run.json",mutate)
        with self.assertRaisesRegex(ValueError,"ERROR/nonzero"):
            self.verify()

    def test_retry_counter_tamper_is_rejected(self):
        self.change("run.json",lambda run:run.update(retaken_repeats=99),sync_artifact=False)
        with self.assertRaisesRegex(ValueError,"retry counter"):
            self.verify()

    def test_missing_loaded_ps_is_rejected(self):
        def mutate(run):
            repeat=run["benchmark_runs"][0]
            first=loaded_attempt(repeat["receipt"],1)
            first["receipt"].pop("ps_top8")
            final=copy.deepcopy(repeat["attempts"][0]);final["attempt"]=2
            repeat["attempts"]=[first,final]
        self.change("run.json",mutate)
        with self.assertRaisesRegex(ValueError,"ps_top8"):
            self.verify()

    def test_attempt_tar_path_escape_is_rejected_without_extraction(self):
        with tempfile.TemporaryDirectory(prefix="hw-gift-1b-unsafe-tar-") as directory:
            folder=Path(directory)
            pack_payload(folder,{"../escape":b"invented"})
            with self.assertRaisesRegex(ValueError,"unsafe attempt artifact path"):
                report.verify_attempt_artifact(folder)

    def test_attempt_tar_symlink_is_rejected_without_extraction(self):
        with tempfile.TemporaryDirectory(prefix="hw-gift-1b-link-tar-") as directory:
            folder=Path(directory)
            raw=io.BytesIO()
            with tarfile.open(fileobj=raw,mode="w") as archive:
                member=tarfile.TarInfo("link");member.type=tarfile.SYMTYPE;member.linkname="../escape"
                archive.addfile(member)
            (folder/"attempts.tar.gz").write_bytes(gzip.compress(raw.getvalue(),mtime=0))
            save(folder/"attempts.json",dict(schema="hw-gift-1b-attempts-v1",archive_sha256=report.sha(folder/"attempts.tar.gz"),
                                           files=[dict(path="link",bytes=0,sha256=report.hashlib.sha256(b"").hexdigest())]))
            with self.assertRaisesRegex(ValueError,"nonregular member"):
                report.verify_attempt_artifact(folder)

    def test_attempt_tar_duplicate_member_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="hw-gift-1b-duplicate-tar-") as directory:
            folder=Path(directory);raw=io.BytesIO()
            with tarfile.open(fileobj=raw,mode="w") as archive:
                for _ in range(2):
                    archive.addfile(tarfile.TarInfo("duplicate"),io.BytesIO(b""))
            (folder/"attempts.tar.gz").write_bytes(gzip.compress(raw.getvalue(),mtime=0))
            save(folder/"attempts.json",dict(schema="hw-gift-1b-attempts-v1",archive_sha256=report.sha(folder/"attempts.tar.gz"),
                                           files=[dict(path="duplicate",bytes=0,sha256=report.hashlib.sha256(b"").hexdigest())]))
            with self.assertRaisesRegex(ValueError,"duplicate attempt archive"):
                report.verify_attempt_artifact(folder)

    def test_three_loaded_attempts_produce_blocked_report_without_statistics(self):
        original=json.loads((self.folder/"run.json").read_bytes())
        key=(65536,4096,0)
        rows=[json.loads(line) for line in gzip.decompress((self.folder/"samples-65536.jsonl.gz").read_bytes()).splitlines()]
        row=next(r for r in rows if (r["g"],r["n"],r["rep"])==key)
        repeat=original["benchmark_runs"][0]
        attempts=[loaded_attempt(repeat["receipt"],index) for index in range(1,4)]
        blocked=dict(g=key[0],n=key[1],rep=key[2],attempts=attempts)
        record=copy.deepcopy(original)
        record.update(reader="pyzstd",status="BLOCKED: load",chunk="enwik8-L3",benchmark_runs=[],
                      blocked_repeat=blocked,ps_top8=attempts[-1]["receipt"]["ps_top8"],load_accepted=False)
        with tempfile.TemporaryDirectory(prefix="hw-gift-1b-blocked-fixture-") as directory:
            evidence=Path(directory);folder=evidence/"blocked"/"pyzstd-enwik8-L3";folder.mkdir(parents=True)
            fixture_attempts(folder,record,{key:row},"pyzstd")
            save(folder/"BLOCKED.json",record)
            verified=report.verify_blocked(folder,baseline_root=self.baseline)
            self.assertEqual(verified["retry_counts"],dict(planned_repeats=70,started_repeats=1,retaken_repeats=1,loaded_attempts=3))
            result=report.build_blocked_report(evidence,baseline_root=self.baseline)
            self.assertIn("1 of 1 started logical repeats were retaken",result)
            self.assertNotIn("**HIT**",result)
            self.assertNotIn("first p50 ms",result)
            self.assertIn("synthetic",result)
            record["retaken_repeats"]=0
            save(folder/"BLOCKED.json",record)
            with self.assertRaisesRegex(ValueError,"retry counter"):
                report.verify_blocked(folder,baseline_root=self.baseline)
            record["retaken_repeats"]=1
            record["blocked_repeat"]["attempts"].pop()
            save(folder/"BLOCKED.json",record)
            with self.assertRaisesRegex(ValueError,"exactly three"):
                report.verify_blocked(folder,baseline_root=self.baseline)


if __name__ == "__main__":
    unittest.main()
