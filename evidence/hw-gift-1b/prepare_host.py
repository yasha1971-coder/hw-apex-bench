"""Download verified ace-core prerequisites; OVH-BENCH permits parallel setup."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

from load_guard import snapshot


ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / ".work" / "hw-gift-1b"
INPUTS = ROOT / ".work" / "inputs"
PYTHON_FILE = "cpython-3.12.16+20261123-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
PYTHON_URL = ("https://github.com/astral-sh/python-build-standalone/releases/download/20261123/"
              "cpython-3.12.16%2B20261123-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz")
PYTHON_SHA = "c85811d35971d06612585a057db3b71806378df6ea8476275fb16aa5c9fe56a0"
ZSTD_SHA = "f8745da6ff1ad1e7bab384bd1f9d742439278e99"


def check(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            result.update(block)
    return result.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".writing")
    pending.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    pending.replace(path)


def download(url, target, expected):
    if target.exists():
        check(sha(target) == expected, "cached download hash differs: " + str(target))
        return
    pending = target.with_name(target.name + ".download")
    with urllib.request.urlopen(url, timeout=90) as response, pending.open("wb") as output:
        shutil.copyfileobj(response, output, 1 << 20)
    check(sha(pending) == expected, "download SHA-256 mismatch: " + url)
    pending.replace(target)


def safe_tar(archive, destination):
    """Extract regular payload first and links last into a fresh workspace tree."""
    destination = destination.resolve()
    check(destination.is_relative_to((ROOT / ".work").resolve()), "extraction escaped workspace")
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        paths, links = {}, []
        for member in members:
            name = PurePosixPath(member.name)
            check(not name.is_absolute() and ".." not in name.parts and "\\" not in member.name,
                  "unsafe tar path")
            check(str(name) not in paths, "duplicate tar path")
            check(member.isdir() or member.isfile() or member.issym() or member.islnk(),
                  "unsupported tar entry type")
            paths[str(name)] = member
            if member.issym() or member.islnk():
                links.append(member)
        link_names = {str(PurePosixPath(member.name)) for member in links}
        for name, member in paths.items():
            check(not any(str(parent) in link_names for parent in PurePosixPath(name).parents),
                  "tar payload descends through a link")
            target = destination / name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as input_file, target.open("xb") as output:
                    shutil.copyfileobj(input_file, output, 1 << 20)
                target.chmod(member.mode & 0o777)
        for member in links:
            target = destination / member.name
            link = PurePosixPath(member.linkname)
            check(not link.is_absolute() and "\\" not in member.linkname, "absolute tar link")
            relative = (PurePosixPath(member.name).parent / link) if member.issym() else link
            normalized = posixpath.normpath(str(relative))
            check(normalized != ".." and not normalized.startswith("../"), "tar link escapes extraction")
            target.parent.mkdir(parents=True, exist_ok=True)
            if member.issym():
                target.symlink_to(member.linkname)
            else:
                original = (destination / normalized).resolve()
                check(original.is_relative_to(destination) and original.is_file(), "invalid tar hardlink")
                os.link(original, target)
        for member in links:
            check((destination / member.name).resolve().is_relative_to(destination),
                  "resolved tar link escapes extraction")


def prepare_python(downloads):
    archive = downloads / PYTHON_FILE
    download(PYTHON_URL, archive, PYTHON_SHA)
    target = STATE / "python"
    receipt_path = STATE / "python-receipt.json"
    if not target.exists():
        with tempfile.TemporaryDirectory(prefix="python-extract-", dir=STATE) as temporary:
            extracted = Path(temporary)
            safe_tar(archive, extracted)
            check({path.name for path in extracted.iterdir()} == {"python"}, "unexpected Python archive root")
            (extracted / "python").replace(target)
    interpreter = target / "bin" / "python3.12"
    check(interpreter.is_file(), "missing prepared CPython")
    record = dict(version="3.12.16", release="20261123", url=PYTHON_URL,
                  archive_sha256=PYTHON_SHA, interpreter=str(interpreter), interpreter_sha256=sha(interpreter))
    if receipt_path.exists():
        check(json.loads(receipt_path.read_bytes()) == record, "prepared CPython changed")
    else:
        check(subprocess.check_output([str(interpreter), "-I", "-B", "-c", "import platform; print(platform.python_version())"],
                                      text=True).strip() == "3.12.16", "wrong prepared CPython version")
        write_json(receipt_path, record)
    return record


def prepare_corpora(downloads):
    corpora = json.loads((ROOT / "corpora.json").read_bytes())
    INPUTS.mkdir(parents=True, exist_ok=True)
    records = []
    for key, filename in (("enwik8", "enwik8"), ("silesia_tar", "silesia.tar")):
        info, target = corpora[key], INPUTS / filename
        expected, size = info["sha256"], info.get("uncompressed_bytes", info.get("bytes"))
        if not target.exists():
            pending = target.with_name(target.name + ".writing")
            retained = Path("/home/ubuntu/enwik8")
            if key == "enwik8" and retained.is_file() and sha(retained) == expected:
                shutil.copyfile(retained, pending)
            else:
                archive = downloads / ("enwik8.zip" if key == "enwik8" else "silesia.tar.gz")
                download(info["url"], archive, info["download_sha256"])
                if key == "enwik8":
                    with zipfile.ZipFile(archive) as source:
                        check(source.namelist() == ["enwik8"], "unexpected enwik8 ZIP contents")
                        with source.open("enwik8") as data, pending.open("wb") as output:
                            shutil.copyfileobj(data, output, 1 << 20)
                else:
                    with gzip.open(archive, "rb") as data, pending.open("wb") as output:
                        shutil.copyfileobj(data, output, 1 << 20)
            check(pending.stat().st_size == size and sha(pending) == expected, "prepared corpus differs")
            pending.replace(target)
        check(target.stat().st_size == size and sha(target) == expected, "existing corpus differs")
        records.append(dict(name=filename, bytes=size, sha256=expected, source_url=info["url"]))
    return records


def prepare_zstd():
    target = STATE / "zstd"
    if not target.exists():
        subprocess.run(["git", "init", str(target)], check=True)
        subprocess.run(["git", "-C", str(target), "remote", "add", "origin", "https://github.com/facebook/zstd.git"], check=True)
        subprocess.run(["git", "-C", str(target), "fetch", "--depth", "1", "origin", ZSTD_SHA], check=True)
        subprocess.run(["git", "-C", str(target), "checkout", "--detach", ZSTD_SHA], check=True)
    actual = subprocess.check_output(["git", "-C", str(target), "rev-parse", "HEAD"], text=True).strip()
    check(actual == ZSTD_SHA, "zstd source pin differs")
    check(not subprocess.check_output(["git", "-C", str(target), "status", "--porcelain"]), "zstd source is dirty")
    return dict(source="https://github.com/facebook/zstd.git", commit=ZSTD_SHA, path=str(target), compiled=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    start = snapshot(cpu=0, interval=2.0)
    write_json(STATE / "prepare-load-start.json", start)
    check(start.get('hostname') == 'ace-core' and 'AMD EPYC 4344P' in start.get('cpu', ''), 'wrong preparation host')
    downloads = STATE / "downloads"
    downloads.mkdir(exist_ok=True)
    python = prepare_python(downloads)
    corpora = prepare_corpora(downloads)
    zstd = prepare_zstd()
    end = snapshot(cpu=0, interval=2.0)
    write_json(STATE / "prepare-load-end.json", end)
    write_json(STATE / "prepare-receipt.json", dict(
        prepared_at_utc=datetime.now(timezone.utc).isoformat(), python=python,
        corpora=corpora, zstd=zstd, load_start=start, load_end=end,
        ovh_policy_commit='3e7201a0933030de8d3011eb658270e577e6eced',
        measurements_started=False))
    print("PREREQUISITES_VERIFIED_NO_BUILDS_OR_MEASUREMENTS")


if __name__ == "__main__":
    main()
