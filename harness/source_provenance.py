#!/usr/bin/env python3
"""Validate that claim provenance names the source files actually compiled."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(trace_path: Path, specifications: list[dict]) -> dict:
    records = [json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()]
    compiled = {}
    for record in records:
        for source in record["sources"]:
            p = str(Path(source["path"]).resolve())
            # Configure probes may compile then delete a temporary TU. Its hash
            # remains trustworthy because the wrapper captured it before exec.
            # Persistent sources are re-hashed to detect post-compile mutation.
            persistent = Path(p).is_file()
            if persistent and sha256(Path(p)) != source["sha256"]:
                raise RuntimeError("compiled source changed after trace: " + p)
            compiled[p] = {"sha256": source["sha256"], "persistent": persistent}
    results = []
    for spec in specifications:
        if spec.get("status") == "n/a":
            if not spec.get("reason"):
                raise RuntimeError("n/a source provenance requires a reason")
            results.append(spec)
            continue
        root = Path(spec["repository_root"]).resolve()
        actual_commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        if actual_commit != spec["expected_commit"]:
            raise RuntimeError(f"{spec['codec']}: dependency commit mismatch")
        if subprocess.check_output(
                ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
                text=True).strip():
            raise RuntimeError(f"{spec['codec']}: compiled repository has tracked modifications")
        required = [(root / rel).resolve() for rel in spec["required_translation_units"]]
        missing = [str(p) for p in required if str(p) not in compiled or not p.is_file()]
        if missing:
            raise RuntimeError(
                f"{spec['codec']}: provenance source was not compiled: " + ", ".join(missing)
            )
        actual = [
            {"path": str(Path(p).relative_to(root)), **evidence}
            for p, evidence in sorted(compiled.items()) if Path(p).is_relative_to(root)
        ]
        if not actual:
            raise RuntimeError(f"{spec['codec']}: no compiled source under declared repository")
        results.append({**spec, "status": "verified", "actual_commit": actual_commit,
                        "compiled_translation_units": actual})
    return {
        "contract": "claim provenance must name a translation unit observed in the actual compiler trace",
        "trace_sha256": sha256(trace_path),
        "codecs": results,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True, type=Path)
    ap.add_argument("--spec", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ns = ap.parse_args()
    result = verify(ns.trace, json.loads(ns.spec.read_text())["codecs"])
    ns.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
