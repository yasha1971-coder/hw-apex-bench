"""Verify retained HW-GIFT-1b checkpoints and reduce them without codec execution.

`python -B report.py verify [CHUNK]` only reads evidence.
`python -B report.py report` prints a complete report; --output saves it.
Archive identities and geometry below are retained encoder receipts. Compressed
archives remain in the runner's durable state rather than in these checkpoints.
"""
import argparse
from decimal import Decimal, localcontext
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parent / "hw-gift-1"
REPO = HERE.parents[1]
C_FILES = [f"samples-{g}.jsonl.gz" for g in (65536, 262144, 1048576, 4194304, 16777216, 67108864)] + ["archives.json", "controls.json", "run.json"]
C_SOURCE_PATHS = ("evidence/hw-gift-1/reproduce.sh", "evidence/hw-gift-1/sweep.py",
                  "evidence/hw-gift-1/pair.c", "evidence/hw-gift-1/report.py", "codecs/native/zstd_seekable.c")
C_SOURCE_COMMIT = "85603dc8f52f20ae5fa09c50820bc30000be726f"
GS = (65536, 262144, 1048576, 4194304, 16777216, 67108864, None)
NS = (4096, 65536)
CHUNKS = {f"{name}-L{level}": (src, level) for name, src in
          (("enwik8", "enwik8"), ("silesia", "silesia.tar")) for level in (3, 19)}
INPUT = {
    "enwik8": (100000000, "2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8"),
    "silesia.tar": (211947520, "a667bac80089b3d04d5496772149e632f0758974b0579d743cd8d6e5e0d63eb2"),
}
CAL = "c4809624beb0ad7a243163455d9c05545bc52d99"
AMENDMENT = "0bd4ab29794f610884e66fdb3ca6c6c93495a4e4"
ORIGINAL_PROTOCOL_SHA256 = "f8a32188585e70d68fcc3a845565a03f4b8bf5e271f9bafb586dc17eeee96164"
AMENDED_PROTOCOL_SHA256 = "37b0d137cccaed3cef5ab1ebb1a05d07c55616b4b0d11c819135c7be4e591649"
ZSTD_COMMIT = "f8745da6ff1ad1e7bab384bd1f9d742439278e99"
C_WORKER_SHA256 = "d2fd5a7b30fca6d56d51d56db983633d7bfa00aab4ccb831468669dd2b50c351"
C_PAIR_SHA256 = "620f3193f65e6a5b67dcd973ea161fe2f3c9566053e586102042b78f3e50a959"
C_ADAPTER_SHA256 = "e077315773eade4fa8417845ce2caa4d669a01d94721153d596fe953d83638d3"
PYZSTD_VERSION = "0.20.0"
WHEEL_FILENAME = "pyzstd-0.20.0-py3-none-any.whl"
WHEEL_SHA256 = "9c6aff5aa9b12bb14d51f724915f176db9b187214d66d93d990c75ff054483c6"
HASH = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")


def check(ok, why):
    if not ok:
        raise ValueError(why)


def frame_name(g):
    return "default" if g is None else str(g)


FILES = [f"samples-{frame_name(g)}.jsonl.gz" for g in GS] + ["archives.json", "controls.json", "run.json"]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical_source_sha(source_root, name):
    """Hash the pinned Git blob, unaffected by checkout newline conversion.

    Nongit roots support standalone synthetic fixtures with explicitly supplied
    bytes. In a repository, an absent pinned object or path is an error.
    """
    source_root = Path(source_root)
    if (source_root / ".git").exists():
        data = subprocess.check_output(["git", "-C", str(source_root), "show", f"{C_SOURCE_COMMIT}:{name}"])
        return hashlib.sha256(data).hexdigest()
    return sha(source_root / name)


def is_int(x, minimum=0):
    return type(x) is int and x >= minimum


def is_hash(x):
    return isinstance(x, str) and HASH.fullmatch(x) is not None


def load(path):
    def unique(pairs):
        ret = {}
        for key, value in pairs:
            check(key not in ret, f"duplicate JSON key: {key}")
            ret[key] = value
        return ret
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


def baseline_offsets(folder, n, rep):
    """Read the retained offsets, never generate a replacement sequence."""
    data = gzip.decompress((folder / "samples-65536.jsonl.gz").read_bytes())
    rows = [json.loads(line) for line in data.splitlines()]
    matches = [r for r in rows if r["n"] == n and r["rep"] == rep]
    check(len(matches) == 1, "missing/duplicate HW-GIFT-1 offset source row")
    offsets = [p[0] for p in matches[0]["samples"]]
    check(len(offsets) == 1000 and all(is_int(p) for p in offsets), "invalid saved offset list")
    return offsets


def verify_load_snapshot(snapshot, host):
    check(isinstance(snapshot, dict), "missing load snapshot")
    for key in ("hostname", "cpu", "kernel", "governor"):
        check(snapshot.get(key) == host.get(key), f"load snapshot differs from host {key}")
    check(type(snapshot.get("pinned_core")) is int and snapshot["pinned_core"] == 0
          and host.get("cpu_affinity") == [0], "load snapshot pinned core mismatch")
    check(is_int(snapshot.get("interval_ns"), 1000000000), "load observation interval is too short")
    times = []
    for key in ("sample_start_utc", "sample_end_utc"):
        check(isinstance(snapshot.get(key), str), "missing load sample UTC timestamp")
        try:
            value = datetime.fromisoformat(snapshot[key].replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("invalid load sample UTC timestamp") from None
        check(value.utcoffset() is not None and value.utcoffset().total_seconds() == 0, "load sample timestamp is not UTC")
        times.append(value)
    check(times[1] >= times[0], "load observation timestamps are reversed")
    other = snapshot.get("other_load")
    check(isinstance(other, dict) and other.get("busy") is False
          and other.get("active_processes") == [] and other.get("inspection_errors") == [], "other workload present or load inspection failed")
    averages = snapshot.get("loadavg")
    check(isinstance(averages, list) and len(averages) == 3
          and all(type(v) in (float, int) and v >= 0 for v in averages), "missing kernel load averages")
    return times


def verify_load_receipt(run, host):
    check(run.get("load_accepted") is True, "load guard did not accept this attempt")
    start = verify_load_snapshot(run.get("load_start"), host)
    end = verify_load_snapshot(run.get("load_end"), host)
    check(end[0] >= start[1], "end load observation predates start")
    resumes = run.get("load_resume_starts", [])
    check(isinstance(resumes, list), "invalid resume load receipts")
    previous_end = start[1]
    for resume in resumes:
        current = verify_load_snapshot(resume, host)
        check(previous_end <= current[0] and current[1] <= end[0], "resume load observations are out of order")
        previous_end = current[1]


def verify_installation_receipt(receipt, host):
    """Validate retained pins; actual installed bytes are checked by preflight."""
    check(isinstance(receipt, dict) and receipt, "missing wheel pin receipt")
    check(receipt.get("pyzstd_version") == host["pyzstd_version"]
          and receipt.get("pypi_version") == host["pyzstd_version"], "wheel does not match pinned latest PyPI version")
    check((host["pyzstd_version"], receipt.get("wheel_filename"), receipt.get("wheel_sha256"))
          == (PYZSTD_VERSION, WHEEL_FILENAME, WHEEL_SHA256), "wheel differs from preregistered environment pin")
    wheels = receipt.get("wheels")
    check(isinstance(wheels, list) and wheels, "missing dependency wheel pins")
    names = set()
    runtime = receipt.get("runtime")
    check(isinstance(runtime, dict) and runtime.get("python") == host["python"]
          and runtime.get("pyzstd_version") == host["pyzstd_version"]
          and str(runtime.get("zstd_version")) == host["zstd_version"], "installation runtime receipt mismatch")
    distributions = runtime.get("distributions")
    check(isinstance(distributions, dict), "missing installed distribution versions")
    normalized = {re.sub(r"[-_.]+", "-", name).lower(): version for name, version in distributions.items()}
    for wheel in wheels:
        name = wheel.get("name")
        check(isinstance(name, str) and name and name not in names, "duplicate/invalid dependency wheel")
        names.add(name)
        check(isinstance(wheel.get("version"), str) and normalized.get(name) == wheel["version"], "dependency installed version differs from wheel pin")
        check(is_hash(wheel.get("wheel_sha256")) and is_hash(wheel.get("pypi_json_sha256"))
              and isinstance(wheel.get("wheel_filename"), str) and wheel["wheel_filename"].endswith(".whl"), "incomplete dependency wheel identity")
        check(wheel.get("pypi_url") == f"https://pypi.org/pypi/{name}/{wheel['version']}/json", "dependency metadata source mismatch")
        if name == "pyzstd":
            check((wheel["version"], wheel["wheel_filename"], wheel["wheel_sha256"])
                  == (PYZSTD_VERSION, WHEEL_FILENAME, WHEEL_SHA256), "dependency pyzstd pin mismatch")
    check("pyzstd" in names, "pyzstd missing from installed wheel pins")
    payload = receipt.get("installed_files_sha256")
    check(isinstance(payload, dict) and payload, "missing installed payload hashes")
    for name, digest in payload.items():
        check(isinstance(name, str) and name, "invalid installed payload path")
        path = PurePosixPath(name)
        check(not path.is_absolute() and ".." not in path.parts and is_hash(digest), "invalid installed payload identity")
    try:
        python_version = tuple(int(v) for v in host["python"].split(".")[:2])
    except ValueError:
        raise ValueError("invalid Python version in host receipt") from None
    if python_version < (3, 14):
        check("backports-zstd" in names and any(name.endswith((".so", ".pyd")) for name in payload), "missing pinned native backports-zstd payload")


def verify_archive(a, g, input_bytes):
    check(a.get("g") == g and a.get("frame") == frame_name(g), "archive grid identity")
    check(is_int(a.get("bytes"), 1) and is_hash(a.get("sha256")), "invalid archive identity")
    frames = a.get("frames")
    check(isinstance(frames, list) and len(frames) > 0, "missing seek-table frames")
    check(is_int(a.get("frame_count"), 1) and a["frame_count"] == len(frames), "frame count mismatch")
    flag = a.get("checksum_flag")
    check(type(flag) is bool, "invalid seek-table checksum flag")
    check(a.get("seek_table_bytes") == 17 + (12 if flag else 8) * len(frames), "seek-table size mismatch")
    check(all(is_int(f.get("compressed_bytes"), 1) and is_int(f.get("decompressed_bytes"), 1)
              for f in frames), "invalid seek-table frame sizes")
    check(sum(f["compressed_bytes"] for f in frames) + a["seek_table_bytes"] == a["bytes"], "archive byte accounting mismatch")
    check(is_int(a.get("decompressed_bytes"), 1) and a["decompressed_bytes"] == input_bytes
          and sum(f["decompressed_bytes"] for f in frames) == input_bytes, "decompressed byte accounting mismatch")
    if g is None:
        check(len(frames) == 1 and input_bytes <= 1073741824, "default is not one corpus frame")
    else:
        check(all(f["decompressed_bytes"] == g for f in frames[:-1])
              and frames[-1]["decompressed_bytes"] <= g, "observed frame geometry differs from grid")


def verify_chunk(folder, chunk, *, baseline_root=BASELINE, calibration_path=None):
    """Independently validate one completed checkpoint; no native code or writes."""
    folder, baseline_root = Path(folder), Path(baseline_root)
    check(chunk in CHUNKS, "unknown checkpoint")
    check(folder.is_dir(), f"missing checkpoint: {chunk}")
    check({p.name for p in folder.iterdir()} == set(FILES + ["SHA256SUMS"]), "unexpected or missing checkpoint files")
    check(all((folder / f).is_file() and not (folder / f).is_symlink() for f in FILES + ["SHA256SUMS"]), "checkpoint contains nonregular file")
    expected_sums = "".join(f"{sha(folder / f)}  {f}\n" for f in sorted(FILES)).encode()
    check((folder / "SHA256SUMS").read_bytes() == expected_sums, "bad SHA256SUMS")
    src, level = CHUNKS[chunk]
    run = load(folder / "run.json")
    check(run.get("corpus") == src and run.get("level") == level, "run identity mismatch")
    check((run.get("input_bytes"), run.get("input_sha256")) == INPUT[src], "input identity mismatch")
    check(run.get("protocol_commit") == CAL, "protocol was not the preregistered first commit")
    check(run.get("amendment_commit") == AMENDMENT, "host amendment is not anchored")
    check(run.get("original_protocol_sha256") == ORIGINAL_PROTOCOL_SHA256, "original prediction bytes mismatch")
    calibration_path = Path(calibration_path) if calibration_path else folder.parent / "CALIBRATION.md"
    check(run.get("protocol_sha256") == sha(calibration_path) == AMENDED_PROTOCOL_SHA256, "protocol bytes mismatch")
    check(isinstance(run.get("runner_commit"), str) and COMMIT.fullmatch(run["runner_commit"]), "invalid runner commit")
    check(is_hash(run.get("runner_sha256")), "invalid runner SHA-256")
    check(is_hash(run.get("verifier_sha256")), "invalid verifier SHA-256")
    check(is_hash(run.get("guard_sha256")), "invalid load guard SHA-256")
    check(is_int(run.get("attempt"), 1), "invalid attempt identity")
    host = run.get("host")
    check(isinstance(host, dict), "missing host receipt")
    check("AMD EPYC 4344P" in host.get("cpu", "") and host.get("hostname") == "ace-core", "wrong amended host")
    affinity = host.get("cpu_affinity")
    check(affinity == [0], "the same pinned CPU 0 is required")
    check(isinstance(host.get("governor"), str) and host["governor"], "missing CPU governor")
    check(host.get("python_implementation") == "CPython", "CPython required")
    check(all(isinstance(host.get(k), str) and host[k] for k in
              ("kernel", "os", "python", "pyzstd_version", "zstd_version")), "incomplete host/build receipt")
    check(is_hash(host.get("host_boot_sha256")), "missing host/boot identity")
    verify_installation_receipt(host.get("installation_receipt"), host)
    verify_load_receipt(run, host)
    baseline = baseline_root / chunk
    source_hashes = run.get("offset_source_sha256")
    check(isinstance(source_hashes, dict) and source_hashes, "missing offset source hashes")
    check(set(source_hashes).issubset({f"samples-{g}.jsonl.gz" for g in GS if g is not None}), "unexpected offset source filename")
    check("samples-65536.jsonl.gz" in source_hashes, "canonical saved offsets are not hash-bound")
    for name, digest in source_hashes.items():
        check(is_hash(digest) and sha(baseline / name) == digest, "offset source hash mismatch")
    offsets = {(n, rep): baseline_offsets(baseline, n, rep) for n in NS for rep in range(5)}
    archives, controls = load(folder / "archives.json"), load(folder / "controls.json")
    check(isinstance(archives, list) and len(archives) == len(GS), "wrong archive grid size")
    check(isinstance(controls, list) and len(controls) == len(GS) * len(NS), "wrong negative control grid size")
    rows, control_keys = {}, set()
    for a, g in zip(archives, GS):
        verify_archive(a, g, INPUT[src][0])
        raw_rows = [json.loads(line) for line in gzip.decompress((folder / f"samples-{frame_name(g)}.jsonl.gz").read_bytes()).splitlines()]
        check(len(raw_rows) == 10, "incomplete frame sample grid")
        for row in raw_rows:
            check((row.get("src"), row.get("level"), row.get("g"), row.get("frame"))
                  == (src, level, g, frame_name(g)), "sample identity mismatch")
            n, rep = row.get("n"), row.get("rep")
            check(type(n) is int and n in NS and type(rep) is int and rep in range(5), "invalid repeat identity")
            key = g, n, rep
            check(key not in rows, "duplicate sample row")
            check((row.get("archive_bytes"), row.get("archive_sha256")) == (a["bytes"], a["sha256"]), "sample archive identity mismatch")
            check(is_int(row.get("peak_kib"), 1), "invalid peak RSS receipt")
            samples = row.get("samples")
            check(isinstance(samples, list) and len(samples) == 1000, "incomplete repeat samples")
            check(all(isinstance(p, list) and len(p) == 4 and all(is_int(v) for v in p) for p in samples), "invalid raw sample")
            check([p[0] for p in samples] == offsets[n, rep], "offset sequence differs from HW-GIFT-1")
            check(all(p[0] + n <= INPUT[src][0] for p in samples), "request outside corpus")
            rows[key] = row
    for control in controls:
        g, n = control.get("g"), control.get("n")
        check(g in GS and (g is None or type(g) is int) and n in NS and type(n) is int, "invalid negative control grid")
        key = g, n
        check(key not in control_keys, "duplicate negative control")
        control_keys.add(key)
        a = archives[GS.index(g)]
        check(control.get("frame") == frame_name(g) and control.get("archive_sha256") == a["sha256"], "control archive identity mismatch")
        check(type(control.get("offset")) is int and control["offset"] == 0, "negative control must read the damaged first frame")
        check(control.get("negative") == "pyzstd exception" and isinstance(control.get("exception"), str)
              and control["exception"], "corrupted frame did not raise")
    check(set(rows) == {(g, n, rep) for g in GS for n in NS for rep in range(5)}, "incomplete sample grid")
    return dict(run=run, archives=archives, controls=controls, rows=rows)


def verify_c_chunk(folder, chunk, *, baseline_root=BASELINE, source_root=REPO, calibration_path=None):
    """Verify the newly measured C baseline; do not re-audit historical timings."""
    folder, baseline_root, source_root = Path(folder), Path(baseline_root), Path(source_root)
    check(chunk in CHUNKS and folder.is_dir(), f"missing C baseline checkpoint: {chunk}")
    check({p.name for p in folder.iterdir()} == set(C_FILES + ["SHA256SUMS", "acecore.json"]), "unexpected or missing C checkpoint files")
    check(all((folder / name).is_file() and not (folder / name).is_symlink()
              for name in C_FILES + ["SHA256SUMS", "acecore.json"]), "C checkpoint contains nonregular file")
    expected_sums = "".join(f"{sha(folder / name)}  {name}\n" for name in sorted(C_FILES)).encode()
    check((folder / "SHA256SUMS").read_bytes() == expected_sums, "bad C SHA256SUMS")
    receipt = load(folder / "acecore.json")
    check(receipt.get("original_sha256sums_sha256") == sha(folder / "SHA256SUMS"), "C wrapper does not bind original checksum manifest")
    check(receipt.get("amendment_commit") == AMENDMENT, "C host amendment is not anchored")
    calibration_path = Path(calibration_path) if calibration_path else folder.parent.parent / "CALIBRATION.md"
    check(receipt.get("protocol_sha256") == sha(calibration_path) == AMENDED_PROTOCOL_SHA256, "C amended protocol bytes mismatch")
    sources = receipt.get("source_sha256")
    check(isinstance(sources, dict) and set(C_SOURCE_PATHS).issubset(sources), "missing unchanged C source hashes")
    for name in C_SOURCE_PATHS:
        check(sources[name] == canonical_source_sha(source_root, name), "C timed/original source changed: " + name)
    run = load(folder / "run.json")
    src, level = CHUNKS[chunk]
    check(run.get("corpus") == src and run.get("level") == level, "C run identity mismatch")
    check((run.get("input_bytes"), run.get("input_sha256")) == INPUT[src], "C input identity mismatch")
    host, wrapper_host = run.get("host"), receipt.get("host")
    check(isinstance(host, dict) and isinstance(wrapper_host, dict), "missing C host receipt")
    check("AMD EPYC 4344P" in host.get("cpu", "") and wrapper_host.get("hostname") == "ace-core"
          and host.get("cpu_affinity") == [0], "wrong C amended host/core")
    for key in ("cpu", "cpu_affinity", "kernel", "os", "host_boot_sha256"):
        check(host.get(key) == wrapper_host.get(key), f"C wrapper differs from measured host {key}")
    check(host.get("zstd_commit") == ZSTD_COMMIT and host.get("zstd_linked") == "1.5.7", "wrong C zstd revision")
    check((host.get("worker_sha256"), host.get("pair_sha256"), host.get("adapter_sha256"))
          == (C_WORKER_SHA256, C_PAIR_SHA256, C_ADAPTER_SHA256), "C timed source differs from HW-GIFT-1")
    for key in ("encoder_sha256", "reader_sha256", "worker_sha256", "pair_sha256", "adapter_sha256", "host_boot_sha256"):
        check(is_hash(host.get(key)), "missing C build/host fingerprint")
    verify_load_receipt(receipt, wrapper_host)
    archives, controls = load(folder / "archives.json"), load(folder / "controls.json")
    check(isinstance(archives, list) and len(archives) == 6, "wrong C archive grid")
    check(isinstance(controls, list) and len(controls) == 12, "wrong C control grid")
    rows, expected_controls = {}, []
    offsets = {(n, rep): baseline_offsets(baseline_root / chunk, n, rep) for n in NS for rep in range(5)}
    for archive, g in zip(archives, GS[:-1]):
        check(archive.get("g") == g and is_int(archive.get("bytes"), 1) and is_hash(archive.get("sha256")), "invalid C archive identity")
        data = gzip.decompress((folder / f"samples-{g}.jsonl.gz").read_bytes())
        records = [json.loads(line) for line in data.splitlines()]
        check(len(records) == 12, "incomplete C sample grid")
        for row, (n, rep) in zip(records, ((n, rep) for n in NS for rep in range(-1, 5))):
            check((row.get("src"), row.get("level"), row.get("g"), row.get("n"), row.get("rep"))
                  == (src, level, g, n, rep), "C sample identity/order mismatch")
            if rep == -1:
                check(row.get("negative") == "native error" and
                      (row.get("archive_bytes"), row.get("archive_sha256")) == (archive["bytes"], archive["sha256"]), "C negative control or archive binding failed")
                expected_controls.append({key: row[key] for key in ("g", "n", "archive_sha256", "negative")})
            else:
                samples = row.get("samples")
                check(isinstance(samples, list) and len(samples) == 1000 and
                      all(isinstance(p, list) and len(p) == 3 and all(is_int(v) for v in p) for p in samples), "invalid C raw samples")
                check([p[0] for p in samples] == offsets[n, rep], "C offsets differ from retained HW-GIFT-1")
                check(is_int(row.get("peak_kib"), 1), "invalid C RSS receipt")
                rows[g, n, rep] = row
    check(controls == expected_controls, "C corruption inventory differs from raw controls")
    return dict(run=run, acecore=receipt, archives=archives, controls=controls, rows=rows)


def verify_all(evidence_root=HERE, *, baseline_root=BASELINE, source_root=REPO):
    evidence_root = Path(evidence_root)
    chunks = {c: verify_chunk(evidence_root / c, c, baseline_root=baseline_root) for c in CHUNKS}
    runs = [chunks[c]["run"] for c in CHUNKS]
    for key in ("host", "runner_commit", "runner_sha256", "verifier_sha256", "guard_sha256", "protocol_commit", "protocol_sha256", "amendment_commit", "original_protocol_sha256"):
        check(all(run[key] == runs[0][key] for run in runs), f"checkpoints cross {key} boundary")
    c_chunks = {c: verify_c_chunk(evidence_root / "c-baseline" / c, c, baseline_root=baseline_root,
                                source_root=source_root) for c in CHUNKS}
    c_runs = [c_chunks[c]["run"] for c in CHUNKS]
    check(all(run["host"] == c_runs[0]["host"] for run in c_runs), "C checkpoints cross host/build boundary")
    for c in CHUNKS:
        c_host = c_chunks[c]["acecore"]["host"]
        for key in ("cpu", "hostname", "cpu_affinity", "kernel", "os", "host_boot_sha256", "governor"):
            check(c_host.get(key) == runs[0]["host"].get(key), f"readers do not share the same host/core: {key}")
    chunks["_c_baseline"] = c_chunks
    return chunks


def metrics(rows):
    """Median of five integer per-repeat nearest-rank percentiles."""
    check(len(rows) == 5, "five repeats required for reduction")
    per = []
    for row in rows:
        values = [sorted(p[col] for p in row["samples"]) for col in (1, 2, 3)]
        per.append((values[0][499], values[1][499], values[1][989], values[2][499], values[2][989]))
    return tuple(sorted(p[col] for p in per)[2] for col in range(5))


def c_metrics(rows):
    check(len(rows) == 5, "five C repeats required for reduction")
    per = []
    for row in rows:
        first = sorted(p[1] for p in row["samples"])
        repeat = sorted(p[2] for p in row["samples"])
        per.append((first[499], first[989], repeat[499], repeat[989]))
    return tuple(sorted(p[col] for p in per)[2] for col in range(4))


def ms(ns):
    check(is_int(ns), "latency must be integer ns")
    return f"{ns // 1000000}.{ns % 1000000:06d}"


def percent(numerator, denominator):
    with localcontext() as context:
        context.prec = 40
        return f"{Decimal(numerator) * 100 / Decimal(denominator):.6f}"


def ratio(numerator, denominator):
    if denominator == 0:
        return "n/a (zero baseline)"
    with localcontext() as context:
        context.prec = 40
        return f"{Decimal(numerator) / Decimal(denominator):.6f}"


def predictions(chunks, *, baseline_root=BASELINE):
    anchor = chunks["enwik8-L3"]["rows"]
    small = metrics([anchor[1048576, 4096, r] for r in range(5)])[1]
    default = metrics([anchor[None, 4096, r] for r in range(5)])[1]
    deviations = []
    for chunk in CHUNKS:
        old = {a["g"]: a["bytes"] for a in load(Path(baseline_root) / chunk / "archives.json")}
        for archive in chunks[chunk]["archives"]:
            g = archive["g"]
            if g is not None:
                base, actual = old[g], archive["bytes"]
                deviations.append(dict(chunk=chunk, g=g, old_bytes=base, new_bytes=actual,
                                       difference_bytes=actual-base, passed=abs(actual-base)*100 <= base))
    check(len(deviations) == 24, "prediction requires all 24 shared archive comparisons")
    return dict(first_p50_1mib_ns=small, first_p50_default_ns=default,
                latency_pass=default >= 20 * small, size_pass=all(d["passed"] for d in deviations),
                deviations=deviations)


def build_report(chunks, *, baseline_root=BASELINE):
    check(set(chunks) == set(CHUNKS) | {"_c_baseline"} and set(chunks["_c_baseline"]) == set(CHUNKS),
          "report requires all four pyzstd and all four matched-host C checkpoints")
    host = chunks["enwik8-L3"]["run"]["host"]
    out = ["# pyzstd SeekableZstdFile: frame size and first-read cost", "",
           "[Preregistered protocol and pre-measurement host amendment](CALIBRATION.md) · "
           "[Host and wheel receipt](enwik8-L3/run.json) · [Matched-host C receipt](c-baseline/enwik8-L3/acecore.json)", "",
           "Archives are resident in RAM; each pair uses a new io.BytesIO and SeekableZstdFile. "
           "Open is timed separately and excluded from first-read seek+read. Repeat is the immediate same seek+read. "
           "Both returned byte strings and lengths were checked against the source outside timing.", "",
           "Each percentile is the median of five per-repeat nearest-rank statistics (1000 requests each). "
           "Latencies retain integer-nanosecond precision. Archive bytes include the complete seek table; "
           "size delta is relative to the 64 MiB archive at the same corpus and level. "
           "Default means max_frame_content_size was omitted (1 GiB; one corpus frame).", "",
           f"Measured host: {host['cpu']}; affinity {host['cpu_affinity']}; {host['os']}; "
           f"CPython {host['python']}; pyzstd {host['pyzstd_version']}; linked zstd {host['zstd_version']}; "
           f"governor {host['governor']}. Absolute times apply to ace-core and this resident-archive workload. "
           "Start, resume and end load observations passed the retained idle-host guard; "
           "the same pinned core was used for the new C baseline. Historical HW-GIFT-1 host timings remain separate.", ""]
    for src in ("enwik8", "silesia.tar"):
        out.extend([f"## {src}", "", "|level|frame B|default|read B|archive B|size delta %|first p50 ms|first p99 ms|repeat p50 ms|repeat p99 ms|open p50 ms|",
                    "|---:|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
        for chunk, (corpus, level) in CHUNKS.items():
            if corpus != src:
                continue
            data = chunks[chunk]
            base = next(a["bytes"] for a in data["archives"] if a["g"] == 67108864)
            for a in data["archives"]:
                g = a["g"]
                for n in NS:
                    open50, first50, first99, repeat50, repeat99 = metrics([data["rows"][g, n, r] for r in range(5)])
                    out.append(f"|{level}|{1073741824 if g is None else g}|{'yes' if g is None else 'no'}|{n}|{a['bytes']}|"
                               f"{percent(a['bytes']-base,base)}|{ms(first50)}|{ms(first99)}|{ms(repeat50)}|{ms(repeat99)}|{ms(open50)}|")
        out.extend(["", "Raw samples, archive identities, geometry and controls: " + " · ".join(
            f"[{c}]({c}/)" for c, (corpus, _) in CHUNKS.items() if corpus == src), ""])
    gates = predictions(chunks, baseline_root=baseline_root)
    hit = gates["latency_pass"] and gates["size_pass"]
    out.extend(["## Preregistered prediction", "", f"**{'HIT' if hit else 'MISS'}**. Both gates must pass.", "",
                f"(a) {'PASS' if gates['latency_pass'] else 'FAIL'}: enwik8 L3, 4 KiB first-read p50: "
                f"default {gates['first_p50_default_ns']} ns; 1 MiB {gates['first_p50_1mib_ns']} ns. "
                "The exact gate is default_ns ≥ 20 × one_MiB_ns.", "",
                f"(b) {'PASS' if gates['size_pass'] else 'FAIL'}: all 24 shared-grid archive sizes must satisfy "
                "100 × abs(new_bytes − HW-GIFT-1_bytes) ≤ HW-GIFT-1_bytes. Gate decisions use integer bytes before rounding.", "",
                "|checkpoint|frame B|HW-GIFT-1 B|pyzstd B|difference B|difference %|within 1%|",
                "|---|---:|---:|---:|---:|---:|:---:|"])
    for d in gates["deviations"]:
        out.append(f"|[{d['chunk']}]({d['chunk']}/archives.json)|{d['g']}|{d['old_bytes']}|{d['new_bytes']}|"
                   f"{d['difference_bytes']}|{percent(d['difference_bytes'],d['old_bytes'])}|{'PASS' if d['passed'] else 'FAIL'}|")
    out.extend(["", "## Matched-host C-reader comparison", "",
                "The following measurements rerun the HW-GIFT-1 C timed reader on ace-core/core 0. "
                "The shared grid has no C default-1-GiB row. These comparisons are informational; "
                "predictions (a) and (b) above are unchanged and (b) uses the original HW-GIFT-1 archive sizes. "
                "C times its native region operation; pyzstd times seek+read. Reader and linked-library versions "
                "are recorded separately, so these are observations of the complete paths rather than an isolated API effect.", "",
                "|corpus|level|frame B|read B|C archive B|pyzstd archive B|C first p50 ms|pyzstd first p50 ms|C first p99 ms|pyzstd first p99 ms|pyzstd/C first p50|C repeat p50 ms|pyzstd repeat p50 ms|",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for chunk, (src, level) in CHUNKS.items():
        c_data, py_data = chunks["_c_baseline"][chunk], chunks[chunk]
        c_sizes = {a["g"]: a["bytes"] for a in c_data["archives"]}
        py_sizes = {a["g"]: a["bytes"] for a in py_data["archives"]}
        for g in GS[:-1]:
            for n in NS:
                c50, c99, cr50, _ = c_metrics([c_data["rows"][g, n, rep] for rep in range(5)])
                _, p50, p99, pr50, _ = metrics([py_data["rows"][g, n, rep] for rep in range(5)])
                out.append(f"|{src}|{level}|{g}|{n}|{c_sizes[g]}|{py_sizes[g]}|{ms(c50)}|{ms(p50)}|{ms(c99)}|{ms(p99)}|{ratio(p50,c50)}|{ms(cr50)}|{ms(pr50)}|")
    out.extend(["", "Matched-host C raw samples and load receipts: " + " · ".join(
        f"[{c}](c-baseline/{c}/)" for c in CHUNKS), "",
                "HW-GIFT-1 measured the zstd contrib C reader; this experiment measures pyzstd SeekableZstdFile. "
                "The retained archive-size comparison with original main data does not establish a cross-host timing ratio. "
                "Compressed archive SHA-256 and geometry are retained encoder receipts; checkpoint SHA256SUMS "
                "binds the committed samples and receipts.", ""])
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify", "verify-c", "report"))
    parser.add_argument("chunk", nargs="?", choices=CHUNKS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.action in ("verify", "verify-c"):
        check(args.output is None, "verify does not write")
        if args.action == "verify-c":
            if args.chunk:
                verify_c_chunk(HERE / "c-baseline" / args.chunk, args.chunk)
            else:
                for chunk in CHUNKS:
                    verify_c_chunk(HERE / "c-baseline" / chunk, chunk)
        elif args.chunk:
            verify_chunk(HERE / args.chunk, args.chunk)
        else:
            verify_all()
        print("VERIFIED", args.chunk or "all four checkpoints")
    else:
        check(args.chunk is None, "partial report is prohibited")
        result = build_report(verify_all())
        if args.output:
            args.output.write_text(result, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(result)


if __name__ == "__main__":
    main()
