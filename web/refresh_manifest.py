"""Refresh existing publication file digests; never generate measurement data."""
import hashlib
import json
from pathlib import Path
import os
import tempfile

from validate_publication import reject_constant, unique_object

ROOT = Path(__file__).resolve().parents[1]


def refresh(root=ROOT):
    root = Path(root).resolve()
    target = root / "evidence/published-results.json"
    original = target.read_bytes()
    manifest = json.loads(original, object_pairs_hook=unique_object,
                          parse_constant=reject_constant)
    if manifest["schema"] != "cabench-publication-v1":
        raise ValueError("Unknown publication manifest schema")
    changed = False
    for name, entry in manifest["files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or path == target.resolve():
            raise ValueError(f"Invalid publication path: {name}")
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(chunk)
                digest.update(chunk)
        value = digest.hexdigest()
        changed |= entry["bytes"] != size or entry["sha256"] != value
        entry["bytes"], entry["sha256"] = size, value
    if not changed:
        return False
    # All inputs must be readable before replacing the manifest.
    fd, temporary = tempfile.mkstemp(prefix=".publication-", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        os.chmod(temporary, target.stat().st_mode & 0o777)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


if __name__ == "__main__":
    print("Publication digests refreshed" if refresh() else "Publication digests unchanged")
