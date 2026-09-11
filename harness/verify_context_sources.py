#!/usr/bin/env python3
"""Reject a different ACE source tree before compiling the context proof."""
import hashlib
import json
from pathlib import Path
import sys

manifest=json.loads(Path(__file__).with_name('context-ace-sources.json').read_text())
root=Path(sys.argv[1])
for name,expected in manifest['files'].items():
    if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:
        raise SystemExit('ACE source does not match '+manifest['commit']+': '+name)
