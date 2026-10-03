#!/usr/bin/env python3
import json,sys
from pathlib import Path
root=Path(sys.argv[1]); rows=[json.loads(p.read_text()) for p in sorted(root.glob("*/summary.json"))]
print("# Corruption robustness — common harness\n")
print("| codec | version | checksum | refused | caught | harmless | SILENT | hang | crash |")
print("|---|---|---|---:|---:|---:|---:|---:|---:|")
for r in rows:
    o=r["outcomes"]
    print(f'| {r["codec"]} | {r["version"]} | {r["checksum_mode"]} | {o.get("refused",0)} | {o.get("caught",0)} | {o.get("harmless",0)} | {o.get("SILENT",0)} | {o.get("hang",0)} | {o.get("crash",0)} |')
print("\nEach row: 10,000 deterministic mutations; watchdog 10 s; memory limit recorded in summary.json.")
