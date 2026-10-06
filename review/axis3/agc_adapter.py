#!/usr/bin/env python3
"""Pinned AGC cohort adapter. Creation is one CLI call; reads are libagc in-process.

AGC receives explicit sample AND contig identifiers, and zero-based inclusive
start/end. The adapter API uses start0 and length; end0 = start0 + length - 1.
'noref' means no EXTERNAL reference, not disabling AGC's reference algorithm:
the first ordered cohort member is used once as the required AGC reference.
"""
from __future__ import annotations
import ctypes
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Iterable

PIN = "e67e3fc865a459779118d3d4e9fbdf42c70ba75e"
SAMPLE_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def create(binary: Path, assemblies: Iterable[tuple[str, Path]], mode: str,
           output: Path, reference: Path | None = None, threads: int = 1) -> dict:
    """Use author-supported single create with defaults, never append."""
    rows = [(sample, Path(path).resolve()) for sample, path in assemblies]
    if not rows or type(threads) is not int or threads < 1:
        raise ValueError("nonempty cohort and positive build thread count required")
    names = [sample for sample, _ in rows]
    if len(set(names)) != len(names) or any(SAMPLE_ID.fullmatch(n) is None for n in names):
        raise ValueError("unique shell/AGC-safe sample identifiers required")
    if "__reference_t2t" in names:
        raise ValueError("reserved reference sample name")
    if mode not in ("t2t", "noref"):
        raise ValueError("AGC mode must be t2t or noref")
    if mode == "t2t" and reference is None:
        raise ValueError("t2t requires a separately pinned reference FASTA")
    if mode == "noref" and reference is not None:
        raise ValueError("noref must not silently use an external reference")
    output = output.resolve()
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    for _, path in rows:
        if not path.is_file():
            raise FileNotFoundError(path)
    with tempfile.TemporaryDirectory(prefix="agc-stage-", dir=output.parent) as directory:
        stage = Path(directory)
        for sample, path in rows:
            (stage / f"{sample}.fa").symlink_to(path)
        if mode == "t2t":
            ref = Path(reference).resolve(strict=True)
            (stage / "__reference_t2t.fa").symlink_to(ref)
            ordered = ["__reference_t2t.fa"] + [f"{n}.fa" for n in names]
        else:
            ordered = [f"{n}.fa" for n in names]
        # AGC embeds reference once. N counts only queried cohort assemblies.
        argv = [str(binary.resolve()), "create", "-t", str(threads),
                "-o", str(output), *ordered]
        cp = subprocess.run(argv, cwd=stage, capture_output=True, check=False)
        if cp.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"AGC create failed rc={cp.returncode}: "
                               + cp.stderr.decode("utf-8", "replace")[-3000:])
    receipt = {
        "schema": "axis3-agc-build-v1", "codec": "AGC", "version": "3.2.4",
        "upstream_commit": PIN, "mode": mode, "cohort_order": names,
        "reference_sample": "__reference_t2t" if mode == "t2t" else names[0],
        "external_reference": mode == "t2t", "create_calls": 1, "append_calls": 0,
        "build_threads": threads, "archive_file": output.name,
        "archive_bytes": output.stat().st_size, "archive_sha256": sha256_file(output),
        "argv_template": ["${AGC_BIN}", "create", "-t", str(threads), "-o", output.name, *ordered],
        "query_api": "CAGCFile::GetCtgSeq", "agc_coordinates": "0-based-inclusive",
        "adapter_coordinates": "0-based-start-plus-length", "prefetch": True,
    }
    return receipt


class AgcReader:
    """One persistent native context; no command execution on the read path."""
    def __init__(self, library: Path, archive: Path, expected_sha256: str | None = None):
        if expected_sha256 is not None and sha256_file(archive) != expected_sha256:
            raise ValueError("AGC archive SHA-256 differs from the build receipt")
        self.lib = ctypes.CDLL(str(library.resolve()))
        self.lib.hwa_agc_open.argtypes = [ctypes.c_char_p, ctypes.c_int]
        self.lib.hwa_agc_open.restype = ctypes.c_void_p
        self.lib.hwa_agc_length.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        self.lib.hwa_agc_length.restype = ctypes.c_int64
        self.lib.hwa_agc_fetch.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p,
                                         ctypes.c_uint64, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_size_t]
        self.lib.hwa_agc_fetch.restype = ctypes.c_int64
        self.lib.hwa_agc_close.argtypes = [ctypes.c_void_p]
        self.lib.hwa_agc_close.restype = None
        self.lib.hwa_agc_error.restype = ctypes.c_char_p
        self.lib.hwa_agc_version.restype = ctypes.c_char_p
        self.handle = self.lib.hwa_agc_open(str(archive.resolve()).encode(), 1)
        if not self.handle:
            raise RuntimeError(self.error())
        self.version = self.lib.hwa_agc_version().decode("ascii")
        if PIN not in self.version:
            self.close()
            raise ValueError("AGC shim provenance differs from the pinned version")

    def error(self) -> str:
        return (self.lib.hwa_agc_error() or b"AGC error").decode("utf-8", "replace")

    def contig_length(self, assembly_id: str, contig: str) -> int:
        if not self.handle:
            raise ValueError("reader is closed")
        n = self.lib.hwa_agc_length(self.handle, assembly_id.encode(), contig.encode())
        if n < 0:
            raise ValueError(self.error())
        return n

    def fetch(self, assembly_id: str, contig: str, start0: int, length: int) -> bytes:
        if not self.handle or type(start0) is not int or type(length) is not int or start0 < 0 or length <= 0:
            raise ValueError("invalid or empty window")
        total = self.contig_length(assembly_id, contig)
        if start0 > total or length > total - start0:
            raise ValueError("window exceeds contig; clipping is forbidden")
        destination = ctypes.create_string_buffer(length)
        n = self.lib.hwa_agc_fetch(self.handle, assembly_id.encode(), contig.encode(),
                                  start0, length, destination, length)
        if n != length:
            raise ValueError(self.error())
        return destination.raw

    def close(self) -> None:
        if self.handle:
            self.lib.hwa_agc_close(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
