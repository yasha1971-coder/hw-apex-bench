"""Hash-bound run inputs and sequence-domain truth for the B verdict job.

This module never times codecs. Input references are relative to one explicit
root. Native inputs are prepared by the build session, not downloaded here.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import time

from tools.silence_contract import judge

HASH = re.compile(r"[0-9a-f]{64}")
DOMAIN = "uppercase-sequence-without-FASTA-framing"
PROTOCOL_PATH = "review/axis3/PROTOCOL_AXIS3.md"


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path):
    def unique(items):
        out = {}
        for k, v in items:
            if k in out:
                raise ValueError("duplicate JSON key: " + k)
            out[k] = v
        return out

    def bad_number(value):
        raise ValueError("nonfinite JSON number: " + value)

    return json.loads(Path(path).read_text(encoding="utf-8"),
                      object_pairs_hook=unique, parse_constant=bad_number)


def resolve(root, name):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise ValueError("nonempty root-relative POSIX path required")
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts or name != p.as_posix():
        raise ValueError("path must be normalized and root-relative")
    root = Path(root).resolve(strict=True)
    result = (root / p).resolve(strict=True)
    if not result.is_relative_to(root) or not result.is_file():
        raise ValueError("file reference escapes input root or is not a file")
    return result


def file_ref(root, path):
    root = Path(root).resolve(strict=True)
    p = Path(path).resolve(strict=True)
    if not p.is_relative_to(root) or not p.is_file():
        raise ValueError("file reference outside root")
    return {"path": p.relative_to(root).as_posix(), "bytes": p.stat().st_size,
            "sha256": sha256_file(p)}


def checked_file(root, ref):
    if not isinstance(ref, dict) or set(ref) != {"path", "bytes", "sha256"}:
        raise ValueError("file reference requires path, bytes, sha256")
    if type(ref["bytes"]) is not int or ref["bytes"] < 0 or not HASH.fullmatch(ref["sha256"]):
        raise ValueError("invalid file size/hash")
    p = resolve(root, ref["path"])
    if file_ref(root, p) != ref:
        raise ValueError("frozen file changed: " + ref["path"])
    return p


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as f:
        json.dump(value, f, sort_keys=True, indent=2, allow_nan=False)
        f.write(chr(10))


def write_jsonl(path, rows):
    with Path(path).open("x", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, allow_nan=False) + chr(10))


def verify_protocol(repo):
    repo = Path(repo)
    record = load_json(repo / "review/axis3/PROTOCOL_FREEZE.json")
    if (record.get("protocol_path") != PROTOCOL_PATH or record.get("protocol_version") != "1.1"
            or record.get("byte_domain") != DOMAIN
            or record.get("coordinate_convention") != "0-based-half-open"
            or record.get("verdict_windows_bytes") != [1024, 8192, 65536]
            or record.get("calibration_window_bytes") != 1):
        raise ValueError("B needs the v1.1 verdict-window clarification")
    if sha256_file(repo / PROTOCOL_PATH) != record.get("sha256"):
        raise ValueError("canonical protocol SHA differs from FREEZE")
    return record


class FastaTruth:
    """Small faidx-like index for truth preparation, not a measured format.

    Retains offsets/line widths rather than all HPRC bases. Variable wrapping
    within a contig is rejected, never guessed; LF and CRLF are both supported.
    Source bytes are never modified. Empty contigs are kept but cannot be read.
    """
    scope = "truth-only"
    decoder_threads = 1

    def __init__(self, sources):
        self.records, self.files, self.assemblies = {}, {}, []
        try:
            for assembly, path in sources:
                if not isinstance(assembly, str) or not assembly or assembly in self.files:
                    raise ValueError("distinct nonempty assembly IDs required")
                self.assemblies.append(assembly)
                fh = Path(path).open("rb")
                self.files[assembly] = fh
                current = None
                tail_seen = False
                while True:
                    offset = fh.tell()
                    line = fh.readline()
                    if not line:
                        break
                    if line.startswith(b">"):
                        words = line[1:].split()
                        if not words:
                            raise ValueError("empty FASTA contig ID")
                        name = words[0].decode("utf-8")
                        key = (assembly, name)
                        if key in self.records:
                            raise ValueError("duplicate FASTA contig")
                        current = {"assembly_id": assembly, "contig_id": name, "length": 0,
                                   "offset": fh.tell(), "line_bases": 0, "line_bytes": 0}
                        self.records[key] = current
                        tail_seen = False
                        continue
                    if current is None:
                        raise ValueError("FASTA sequence before header")
                    seq = line.rstrip(b"\r\n")
                    if not seq or any(c in seq for c in (b" ", b"\t", b">")):
                        raise ValueError("blank or malformed FASTA sequence line")
                    if tail_seen:
                        raise ValueError("nonuniform FASTA wrapping")
                    if not current["line_bases"]:
                        current.update(offset=offset, line_bases=len(seq), line_bytes=len(line))
                    else:
                        if len(seq) > current["line_bases"]:
                            raise ValueError("nonuniform FASTA line width")
                        # A shorter last line (or no final newline) is legal.
                        if len(seq) < current["line_bases"] or len(line) != current["line_bytes"]:
                            tail_seen = True
                    current["length"] += len(seq)
                if not any(k[0] == assembly for k in self.records):
                    raise ValueError("assembly has no FASTA records")
        except Exception:
            self.close()
            raise

    def contigs(self):
        return [(a, c, x["length"]) for (a, c), x in self.records.items()]

    def fetch(self, assembly, contig, start0, end0):
        row = self.records[assembly, contig]
        if type(start0) is not int or type(end0) is not int or not 0 <= start0 < end0 <= row["length"]:
            raise ValueError("invalid truth window")
        lb, lw, base = row["line_bases"], row["line_bytes"], row["offset"]
        s = base + start0 // lb * lw + start0 % lb
        e = base + (end0 - 1) // lb * lw + (end0 - 1) % lb + 1
        f = self.files[assembly]
        f.seek(s)
        result = f.read(e - s).replace(b"\r", b"").replace(b"\n", b"").upper()
        if len(result) != end0 - start0:
            raise ValueError("truth mapping produced wrong length")
        return result

    def full_identity(self, assembly):
        h = hashlib.sha256()
        total = 0
        for a, c, n in self.contigs():
            if a != assembly:
                continue
            for pos in range(0, n, 1048576):
                data = self.fetch(a, c, pos, min(n, pos + 1048576))
                h.update(data)
                total += len(data)
        return {"canonical_bytes": total, "canonical_sha256": h.hexdigest()}

    def close(self):
        for fh in self.files.values():
            fh.close()
        self.files.clear()


def normalize_full(domain, data, contigs):
    """Return canonical chunks, validating FASTA contig order/length if present."""
    if domain == "sequence":
        yield bytes(data).upper()
        return
    if domain != "fasta":
        raise ValueError("unknown native full-decode output domain")
    names, sizes = [], []
    current = None
    for line in bytes(data).splitlines():
        if line.startswith(b">"):
            words = line[1:].split()
            if not words:
                raise ValueError("decoded FASTA has empty name")
            names.append(words[0].decode("utf-8"))
            sizes.append(0)
            current = len(sizes) - 1
        else:
            if current is None or not line or any(c in line for c in (b" ", b"\t")):
                raise ValueError("malformed decoded FASTA")
            sizes[current] += len(line)
            yield line.upper()
    if list(zip(names, sizes)) != [(c["contig_id"], c["length"]) for c in contigs]:
        raise ValueError("decoded FASTA contig order/length differs from frozen corpus")


def _process_sample():
    rows = {}
    for p in Path("/proc").glob("[0-9]*/stat"):
        try:
            raw = p.read_text()
            fields = raw[raw.rfind(")") + 2:].split()
            # proc(5): utime/stime 14/15; starttime 22, after pid and comm.
            rows[int(p.parent.name)] = (int(fields[11]) + int(fields[12]), int(fields[19]))
        except FileNotFoundError:
            pass  # Process exited; a new process is identified by starttime.
    return rows


def capture_silence(output_disk):
    """Called only by the explicit ace-core run command, never by unit imports."""
    if socket.gethostname() != "ace-core":
        raise ValueError("official verdict job requires host ace-core")
    before = _process_sample()
    started = time.monotonic()
    time.sleep(1.01)
    after = _process_sample()
    seconds = time.monotonic() - started
    hz = os.sysconf("SC_CLK_TCK")
    processes = []
    for pid, (ticks, starttime) in after.items():
        old = before.get(pid)
        delta = ticks - old[0] if old and old[1] == starttime else ticks
        processes.append({"pid": pid, "starttime_ticks": starttime,
                          "before_ticks": old[0] if old else None, "after_ticks": ticks,
                          "cpu_percent": 100 * max(0, delta) / hz / seconds,
                          "own_process": pid == os.getpid()})
    policies = {}
    for p in Path("/sys/devices/system/cpu/cpufreq").glob("policy*/scaling_governor"):
        policies[p.parent.name] = {"governor": p.read_text().strip()}
        freq = p.with_name("scaling_cur_freq")
        policies[p.parent.name]["cur_khz"] = freq.read_text().strip() if freq.exists() else "unavailable"
    disk = os.statvfs(output_disk)
    cpuinfo = Path("/proc/cpuinfo").read_text()
    models = sorted({line.split(":", 1)[1].strip() for line in cpuinfo.splitlines()
                     if line.startswith("model name")})
    snapshot = {"host": socket.gethostname(), "uptime": Path("/proc/uptime").read_text().strip(),
                "load1": os.getloadavg()[0], "loadavg_raw": Path("/proc/loadavg").read_text().strip(),
                "disk_available_bytes": disk.f_bavail * disk.f_frsize,
                "sampling_seconds": seconds, "clock_ticks_per_second": hz, "processes": processes,
                "cpu_models": models, "frequency_policy": policies or {"status": "unavailable"}}
    return judge(snapshot)
