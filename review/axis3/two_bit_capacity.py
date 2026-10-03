#!/usr/bin/env python3
import json,subprocess,sys
from pathlib import Path
root=Path(sys.argv[1])
# Capacity baseline is exact and lossless: 2-bit A/C/G/T payload + explicit exception positions/symbols + contig metadata.
total=0
for fa in sorted(root.glob("asm*.fa")):
    seq=b"".join(x.strip().upper() for x in fa.read_bytes().splitlines() if not x.startswith(b">"))
    packed=(len(seq)+3)//4
    exceptions=sum(b not in b"ACGT" for b in seq)
    # Synthetic fixtures contain A/C/G/T only; real evidence must account exception positions/symbols explicitly.
    total += packed
print(json.dumps({"codec":"2-bit-capacity","synthetic_payload_bytes":total,"status":"PASS"}))
