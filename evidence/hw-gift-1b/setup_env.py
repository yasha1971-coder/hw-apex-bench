"""Prepare a hash-pinned HW-GIFT-1b venv; this does not run any measurement."""
import argparse
from datetime import datetime, timezone
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import sys
import urllib.request
import venv
import zipfile


ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.20.0"
WHEEL = "pyzstd-0.20.0-py3-none-any.whl"
WHEEL_SHA256 = "9c6aff5aa9b12bb14d51f724915f176db9b187214d66d93d990c75ff054483c6"
PYPI = "https://pypi.org/pypi/pyzstd/json"


def check(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def normalized(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def packed(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def read_json_url(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        raw = response.read()
    return raw, json.loads(raw)


def probe(python):
    program = """import importlib.metadata as m, json, platform, sys, sysconfig, pyzstd
print(json.dumps(dict(python=platform.python_version(), executable=sys.executable,
    site_packages=sysconfig.get_paths()['purelib'], pyzstd_version=pyzstd.__version__,
    zstd_version=pyzstd.zstd_version,
    distributions={d.metadata['Name']: d.version for d in m.distributions()})))"""
    return json.loads(subprocess.check_output([str(python), "-I", "-B", "-c", program]))


def verify_receipt(receipt_path):
    receipt = json.loads(receipt_path.read_bytes())
    check(receipt["pyzstd_version"] == VERSION and receipt["pypi_version"] == VERSION
          and receipt["wheel_filename"] == WHEEL and receipt["wheel_sha256"] == WHEEL_SHA256,
          "receipt does not match the preregistered setup pin")
    for wheel in receipt["wheels"]:
        check(file_sha(wheel["wheel_path"]) == wheel["wheel_sha256"], "saved wheel hash changed")
    base = Path(receipt["installed_files_base"])
    for relative, expected in receipt["installed_files_sha256"].items():
        check(file_sha(base / relative) == expected, "installed payload changed: " + relative)
    actual = probe(receipt["installed_python"])
    check(actual == receipt["runtime"], "installed versions, executable or backend changed")
    print("PINNED_ENVIRONMENT_VERIFIED", receipt_path)


def prepare(state):
    check(sys.version_info >= (3, 11), "CPython >= 3.11 is required")
    check(platform.python_implementation() == "CPython", "CPython is required")
    state = state.resolve()
    check(state.is_relative_to((ROOT / ".work").resolve()), "state must stay in this repo's .work/")
    receipt_path = state / "install-receipt.json"
    if receipt_path.exists():
        verify_receipt(receipt_path)
        return
    environment = state / "venv"
    check(not environment.exists(), "venv exists without final receipt; inspect partial setup before continuing")
    state.mkdir(parents=True, exist_ok=True)
    metadata_dir = state / "pypi"
    metadata_dir.mkdir(exist_ok=True)
    raw, latest = read_json_url(PYPI)
    check(latest["info"]["version"] == VERSION,
          "PyPI latest changed; stop and review the version pin before any measurement")
    check(any(f["filename"] == WHEEL and f["digests"]["sha256"] == WHEEL_SHA256
              for f in latest["urls"]), "PyPI latest wheel differs from the recorded pin")
    (metadata_dir / "pyzstd-latest.json").write_bytes(raw)
    fetched_at = datetime.now(timezone.utc).isoformat()
    wheels_dir = state / "wheels"
    wheels_dir.mkdir(exist_ok=True)
    check(not any(wheels_dir.iterdir()), "partial wheel download exists; inspect it before preparing again")
    run(sys.executable, "-m", "pip", "download", "--isolated", "--only-binary=:all:",
        "--index-url", "https://pypi.org/simple", "--dest", wheels_dir, "pyzstd==" + VERSION)
    records, payload = [], {}
    for path in sorted(wheels_dir.iterdir()):
        check(path.suffix == ".whl", "non-wheel download")
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            metadata = [name for name in names if name.endswith(".dist-info/METADATA")]
            check(len(metadata) == 1, "ambiguous wheel metadata")
            message = BytesParser().parsebytes(archive.read(metadata[0]))
            name, version = normalized(message["Name"]), message["Version"]
            url = f"https://pypi.org/pypi/{name}/{version}/json"
            source_raw, source = read_json_url(url)
            matches = [f for f in source["urls"] if f["filename"] == path.name]
            check(len(matches) == 1, "wheel not present in exact-version PyPI metadata")
            sha = file_sha(path)
            check(sha == matches[0]["digests"]["sha256"], "downloaded wheel SHA-256 mismatch")
            if name == "pyzstd":
                check(path.name == WHEEL and sha == WHEEL_SHA256, "pyzstd wheel pin mismatch")
            (metadata_dir / f"{name}-{version}.json").write_bytes(source_raw)
            records.append(dict(name=name, version=version, wheel_filename=path.name,
                                wheel_path=str(path), wheel_sha256=sha, pypi_url=url,
                                pypi_json_sha256=digest(source_raw)))
            for member in names:
                if member.endswith("/") or ".dist-info/" in member:
                    continue
                relative = PurePosixPath(member)
                check(not relative.is_absolute() and ".." not in relative.parts
                      and not any(part.endswith(".data") for part in relative.parts),
                      "unsupported wheel payload path")
                expected = digest(archive.read(member))
                check(member not in payload or payload[member] == expected, "wheel payload collision")
                payload[member] = expected
    check(len({record["name"] for record in records}) == len(records), "duplicate distributions")
    pyzstd_pin = next(record for record in records if record["name"] == "pyzstd")
    requirements = state / "requirements.lock"
    requirements.write_text("".join(f"{r['name']}=={r['version']} --hash=sha256:{r['wheel_sha256']}\n"
                                    for r in records), encoding="utf-8")
    (state / "wheel-manifest.json").write_bytes(packed(records))
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    run(python, "-m", "pip", "install", "--isolated", "--no-index", "--no-deps", "--require-hashes",
        "--find-links", wheels_dir, "--requirement", requirements)
    run(python, "-m", "pip", "check")
    actual = probe(python)
    check(actual["pyzstd_version"] == VERSION, "imported pyzstd version differs")
    installed = {normalized(name): version for name, version in actual["distributions"].items()}
    check(all(installed.get(r["name"]) == r["version"] for r in records), "installed dependency differs")
    base = Path(actual["site_packages"])
    for relative, expected in payload.items():
        check(file_sha(base / relative) == expected, "installed payload differs from wheel: " + relative)
    receipt = dict(pyzstd_version=VERSION, wheel_filename=WHEEL, wheel_sha256=WHEEL_SHA256,
                   wheel_path=pyzstd_pin["wheel_path"], pypi_json_sha256=digest(raw),
                   pypi_url=PYPI, pypi_version=latest["info"]["version"], fetched_at_utc=fetched_at,
                   installed_files_base=str(base), installed_files_sha256=payload,
                   installed_python=str(python), runtime=actual, wheels=records,
                   setup_script_sha256=file_sha(__file__))
    receipt_path.write_bytes(packed(receipt))
    verify_receipt(receipt_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=ROOT / ".work" / "hw-gift-1b")
    args = parser.parse_args()
    prepare(args.state)
