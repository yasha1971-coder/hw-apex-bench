#!/usr/bin/env python3
"""Syntax-check literal run: | shell blocks without executing them or using YAML packages.

This checker is deliberately limited to literal block scalars. Non-literal run
values cause a failure rather than being silently omitted. It is used on the
Axis 3 workflow; it does not interpret GitHub expressions or execute commands.
"""
import argparse
import re
import subprocess
from pathlib import Path


def run_blocks(text):
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        match = re.match(r"^( *)run:\s*(.*?)\s*$", lines[i])
        if match is None:
            i += 1
            continue
        marker = i + 1
        indent = len(match.group(1))
        if match.group(2) not in ("|", "|-", "|+"):
            raise ValueError(f"line {marker}: only literal run blocks are supported")
        i += 1
        body = []
        while i < len(lines):
            line = lines[i]
            if line.strip() and len(line) - len(line.lstrip(" ")) <= indent:
                break
            body.append(line)
            i += 1
        nonempty = [len(s) - len(s.lstrip(" ")) for s in body if s.strip()]
        if not nonempty:
            raise ValueError(f"line {marker}: empty run block")
        trim = min(nonempty)
        yield marker, "".join(s[trim:] if s.strip() else chr(10) for s in body)


def check(path):
    count = 0
    for line, script in run_blocks(path.read_text(encoding="utf-8")):
        result = subprocess.run(["bash", "-n"], input=script, text=True,
                                capture_output=True, check=False)
        if result.returncode:
            raise ValueError(f"{path}:{line}: bash -n exit {result.returncode}: "
                             + result.stderr)
        count += 1
    if count == 0:
        raise ValueError(f"{path}: no shell run blocks found")
    print(f"PASS workflow_shell_syntax file={path} blocks={count}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", type=Path, nargs="+")
    args = parser.parse_args()
    try:
        for path in args.paths:
            check(path)
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + chr(10))


if __name__ == "__main__":
    main()
