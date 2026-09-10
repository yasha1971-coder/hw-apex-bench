#!/usr/bin/env python3
"""Reproduce the ACEAPEX block-size-only c(g) pair at one pinned revision."""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import struct
import subprocess
import sys
import urllib.request


ACEAPEX_SHA = "ee5a37eda18b81c1300a1ee44a7e06b6be925bd2"
ACEAPEX_MAIN_BLOB = "ac345a5849dd53d696cd31bfc9bbcbeb6cfe37b0"
CORPUS_SIZE = 253_935_557
BLOCKED_BS = 16_384
THREADS = 8
CLEARED_ENV = (
    "ACEAPEX_BS", "LIT_CHUNK", "FSE_CHUNK", "MIN_MATCH", "HASH_LOG",
    "LIT_LEVEL", "LIT_LANES", "NO_REP", "DIRECT8", "FORCED_BIN",
    "ACEAPEX_DUMP", "LD_PRELOAD",
)
HEADER = struct.Struct("<8sIQII8sQQQQ")
BLOCK_OFFSETS_BYTES = 64


def run(args: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None,
        stdout=None, log: Path | None = None) -> subprocess.CompletedProcess[str]:
    p = subprocess.run(args, cwd=cwd, env=env, stdout=stdout or subprocess.PIPE,
                       stderr=subprocess.PIPE, text=stdout is None, check=False)
    if log is not None:
        text = "" if stdout is not None else (p.stdout or "")
        text += p.stderr or ""
        log.write_text(text)
    p.check_returncode()
    return p


def digest(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def command_text(args: list[str], bs: int, cwd: Path) -> str:
    clears = " ".join("-u " + shlex.quote(k) for k in CLEARED_ENV)
    return f"cd {shlex.quote(str(cwd))} && env {clears} ACEAPEX_BS={bs} " + shlex.join(args)


def archive_record(path: Path) -> dict:
    with path.open("rb") as f:
        raw = f.read(HEADER.size)
    if len(raw) != HEADER.size:
        raise RuntimeError(f"short ACEAPEX header: {path}")
    magic, version, orig_size, block_size, num_blocks, _xxh, *streams = HEADER.unpack(raw)
    if magic != b"ACEPX2\0\0" or version != 2 or orig_size != CORPUS_SIZE:
        raise RuntimeError(f"unexpected ACEAPEX header: {path}")
    payload_bytes = sum(streams)
    expected_bytes = HEADER.size + num_blocks * BLOCK_OFFSETS_BYTES + payload_bytes
    archive_bytes = path.stat().st_size
    if archive_bytes != expected_bytes:
        raise RuntimeError(
            f"archive accounting mismatch for {path}: stat={archive_bytes}, header={expected_bytes}"
        )
    return {
        "archive_bytes": archive_bytes,
        "payload_bytes": payload_bytes,
        "container_overhead_bytes": archive_bytes - payload_bytes,
        "header_bytes": HEADER.size,
        "block_offsets_bytes": num_blocks * BLOCK_OFFSETS_BYTES,
        "block_size": block_size,
        "num_blocks": num_blocks,
        "archive_sha256": digest(path, "sha256"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", type=Path, default=Path(".work/strict-ace-cg"))
    ns = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    work = (root / ns.work).resolve() if not ns.work.is_absolute() else ns.work.resolve()
    work.mkdir(parents=True, exist_ok=True)

    corpus = json.loads((root / "corpora.json").read_text())["chr1_hg38"]
    gz = work / "chr1.fa.gz"
    fa = work / "chr1.fa"
    if not fa.exists() or fa.stat().st_size != CORPUS_SIZE or digest(fa, "md5") != corpus["md5"]:
        urllib.request.urlretrieve(corpus["url"], gz)
        with gzip.open(gz, "rb") as src, fa.open("wb") as dst:
            shutil.copyfileobj(src, dst)
    if fa.stat().st_size != CORPUS_SIZE or digest(fa, "md5") != corpus["md5"]:
        raise RuntimeError("chr1 corpus size or MD5 mismatch")

    source = work / "aceapex"
    if not source.exists():
        run(["git", "clone", "--no-checkout", "https://github.com/yasha1971-coder/aceapex.git", str(source)])
    run(["git", "fetch", "--depth=1", "origin", ACEAPEX_SHA], cwd=source)
    run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=source)
    actual_sha = run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip()
    if actual_sha != ACEAPEX_SHA:
        raise RuntimeError(f"ACEAPEX SHA mismatch: {actual_sha}")
    run(["make", "clean"], cwd=source)
    trace = work / "compile-trace.jsonl"
    trace.unlink(missing_ok=True)
    traced_cxx = f"{shlex.quote(sys.executable)} {shlex.quote(str(root / 'harness/compiler_trace.py'))} --real g++"
    build_env = os.environ.copy()
    build_env["CABENCH_COMPILE_TRACE"] = str(trace)
    build = run(["make", "-j2", f"CXX={traced_cxx}"], cwd=source, env=build_env,
                log=work / "build.log")
    spec = work / "source-spec.json"
    spec.write_text(json.dumps({"codecs": [{
        "codec": "aceapex",
        "repository_root": str(source),
        "expected_commit": ACEAPEX_SHA,
        "required_translation_units": ["src/aceapex_main.cpp"],
    }]}, indent=2) + "\n")
    provenance = work / "source-provenance.json"
    run([sys.executable, str(root / "harness/source_provenance.py"),
         "--trace", str(trace), "--spec", str(spec), "--out", str(provenance)])
    binary = source / "aceapex"

    base_env = os.environ.copy()
    for key in CLEARED_ENV:
        base_env.pop(key, None)
    configurations = []
    command_lines = []
    for label, bs in (("g16", BLOCKED_BS), ("gall", CORPUS_SIZE)):
        archive = work / f"{label}.aet"
        restored = work / f"{label}.fa"
        env = base_env.copy()
        env["ACEAPEX_BS"] = str(bs)
        enc = [str(binary), "c", "--in", str(fa), "--out", str(archive), "--threads", str(THREADS)]
        dec = [str(binary), "d", "--in", str(archive), "--out", str(restored), "--threads", str(THREADS)]
        try:
            run(enc, cwd=source, env=env, log=work / f"{label}-compress.log")
        except subprocess.CalledProcessError as exc:
            failure = {
                "claim": "aceapex_independence_cost_block_size_only",
                "status": "failed",
                "reason": "compression command did not complete; no strict c(g) can be reported",
                "failed_label": label,
                "failed_returncode": exc.returncode,
                "failed_signal": -exc.returncode if exc.returncode < 0 else None,
                "failed_command": command_text(enc, bs, source),
                "aceapex_sha": ACEAPEX_SHA,
                "corpus": {**corpus, "bytes": CORPUS_SIZE, "md5_verified": True},
                "completed_configurations": configurations,
                "only_changed_environment": "ACEAPEX_BS",
                "cleared_environment": list(CLEARED_ENV),
            }
            (work / "failure.json").write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n")
            print("STRICT_CG_EVIDENCE_BEGIN failure.json")
            print(json.dumps(failure, indent=2, sort_keys=True))
            print("STRICT_CG_EVIDENCE_END failure.json")
            raise
        rec = archive_record(archive)
        expected_blocks = (CORPUS_SIZE + bs - 1) // bs
        if rec["block_size"] != bs or rec["num_blocks"] != expected_blocks:
            raise RuntimeError(f"block configuration not honored for {label}: {rec}")
        run(dec, cwd=source, env=env, log=work / f"{label}-decompress.log")
        if digest(restored, "md5") != corpus["md5"] or not __import__("filecmp").cmp(fa, restored, shallow=False):
            raise RuntimeError(f"restore mismatch for {label}")
        rec.update({
            "label": label,
            "ratio_archive": CORPUS_SIZE / rec["archive_bytes"],
            "ratio_payload_only": CORPUS_SIZE / rec["payload_bytes"],
            "correctness": "pass",
            "restore_md5": digest(restored, "md5"),
            "compression_command": command_text(enc, bs, source),
            "decompression_command": command_text(dec, bs, source),
        })
        configurations.append(rec)
        command_lines += [rec["compression_command"], rec["decompression_command"]]

    blocked, whole = configurations
    strict_archive_percent = 100 * (1 - blocked["ratio_archive"] / whole["ratio_archive"])
    payload_only_percent = 100 * (1 - blocked["ratio_payload_only"] / whole["ratio_payload_only"])
    compiler = run(["g++", "--version"]).stdout.splitlines()[0]
    try:
        libzstd = run(["pkg-config", "--modversion", "libzstd"]).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        libzstd = "unknown"
    try:
        cpu = run(["lscpu", "-J"]).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        cpu = "unavailable"

    claim = {
        "claim": "aceapex_independence_cost_block_size_only",
        "status": "measured",
        "measured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "formula_archive": "100 * (1 - ratio_archive_g / ratio_archive_whole)",
        "formula_equivalent_bytes": "100 * (1 - archive_bytes_whole / archive_bytes_g)",
        "independence_cost_strict_percent": strict_archive_percent,
        "payload_only_loss_percent": payload_only_percent,
        "payload_only_is_not_archive_ratio": True,
        "corpus": {**corpus, "bytes": CORPUS_SIZE, "md5_verified": True},
        "codec": {
            "name": "aceapex",
            "sha": ACEAPEX_SHA,
            "source_blob_src_aceapex_main_cpp": ACEAPEX_MAIN_BLOB,
            "threads": THREADS,
            "cli_level": "default (2)",
            "profile": "n/a: this revision has no --profile flag",
            "explicit_environment_common": {},
            "only_changed_environment": "ACEAPEX_BS",
            "cleared_environment": list(CLEARED_ENV),
            "default_environment_note": "LIT_CHUNK, FSE_CHUNK, HASH_LOG, MIN_MATCH and all listed overrides are absent in both runs",
            "whole_meaning": "one independent ACEAPEX block spanning the input; block logic remains active",
            "reported_cli_compressed_scope": "entropy payload streams only; excludes AetHeader and BlockOffsets table",
        },
        "configurations": configurations,
        "commands": command_lines,
        "correctness": "pass",
        "machine": {"platform": platform.platform(), "machine": platform.machine(), "lscpu_json": json.loads(cpu) if cpu.startswith("{") else cpu},
        "versions": {"compiler": compiler, "libzstd": libzstd},
        "build": {"command": f"git checkout {ACEAPEX_SHA} && make -j2", "log": "build.log", "stdout_tail": (build.stdout or "")[-1000:]},
        "source_provenance": json.loads(provenance.read_text()),
    }
    (work / "claim.json").write_text(json.dumps(claim, indent=2, sort_keys=True) + "\n")
    (work / "commands.txt").write_text("\n".join(command_lines) + "\n")
    print("STRICT_CG_EVIDENCE_BEGIN claim.json")
    print(json.dumps(claim, indent=2, sort_keys=True))
    print("STRICT_CG_EVIDENCE_END claim.json")
    print(f"STRICT_CG_ARCHIVE_PERCENT={strict_archive_percent:.9f}")
    print(f"STRICT_CG_PAYLOAD_ONLY_PERCENT={payload_only_percent:.9f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
