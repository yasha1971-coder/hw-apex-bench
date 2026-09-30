#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
base=ROOT/"evidence/aceapex-v220-gpu-20260930"
d=json.loads((base/"results.json").read_text())
assert d["status"]=="measured"
assert d["external_runner"]=="Colab"
assert d["source_ace_commit"].startswith("27b61b1")
assert d["statistic"]=="median of 3"
assert "bit-perfect" in d["correctness"]
release=(base/"source/release-v2.2.0.md").read_text()
for r in d["rows"]:
    assert str(r["archive_bytes"]).replace(" ","") in release.replace(" ","")
    assert r["on_device_ms"]>0 and r["h2d_total_ms"]>0
    assert r["check"]=="bit-perfect"
assert d["raw_log"]["committed_in_upstream_snapshot"] is False
print("PASS: four measured external Blackwell rows; upstream raw-log absence disclosed")
