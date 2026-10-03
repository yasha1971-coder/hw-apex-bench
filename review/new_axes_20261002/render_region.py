#!/usr/bin/env python3
import json,sys
from pathlib import Path
rows=[json.loads(p.read_text()) for p in sorted(Path(sys.argv[1]).glob("*.json"))]
print("# Single-region latency — common 10,000-request lists\n")
print("| corpus | codec | device | mode | p50 us | p95 us | p99 us | verified |")
print("|---|---|---|---|---:|---:|---:|---|")
for r in rows:
    print(f'| {r["corpus"]} | {r["codec"]} | {r["device"]} | {r["mode"]} | {r["p50_us"]:.3f} | {r["p95_us"]:.3f} | {r["p99_us"]:.3f} | {r["bit_perfect"]} |')
print("\nRows with different modes are separate scopes and are not ranked together. zstd and lz4: no random-access index, therefore no latency row.")
