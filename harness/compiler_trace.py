#!/usr/bin/env python3
"""Transparent compiler wrapper that records the translation units actually built."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys


SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".cu"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] != "--real":
        raise SystemExit("usage: compiler_trace.py --real COMPILER [compiler arguments]")
    real, args = sys.argv[2], sys.argv[3:]
    trace = os.environ.get("CABENCH_COMPILE_TRACE")
    if trace:
        sources = []
        for arg in args:
            p = Path(arg)
            if p.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            p = (Path.cwd() / p).resolve() if not p.is_absolute() else p.resolve()
            if p.is_file():
                sources.append({"path": str(p), "sha256": sha256(p)})
        if sources:
            record = json.dumps({
                "compiler": real,
                "cwd": str(Path.cwd().resolve()),
                "argv": [real, *args],
                "sources": sources,
            }, sort_keys=True) + "\n"
            fd = os.open(trace, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            try:
                os.write(fd, record.encode())
            finally:
                os.close(fd)
    os.execvp(real, [real, *args])


if __name__ == "__main__":
    raise SystemExit(main())
