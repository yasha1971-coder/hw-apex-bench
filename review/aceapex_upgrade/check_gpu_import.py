#!/usr/bin/env python3
import json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/"evidence/aceapex-gpu-open-20260929"
data=json.loads((BASE/"results.json").read_text())
assert data["schema"]=="aceapex-gpu-open-colab-v1"
assert data["status"]=="measured" and data["external_runner"]=="Colab"
assert data["axes"]["region_seek"].startswith("n/a")

for row in data["rows"]:
    p=BASE/row["source_log"]
    text=p.read_text()
    assert "bit-perfect" in text
    assert row["gpu"].replace("NVIDIA ","") in text or row["gpu"] in text
    assert str(row["archive_bytes"]) in text.replace(" ","")
    assert row["ace_commit"][:7] in text
    if row["corpus"]=="chr1":
        assert "9465e0f0df6e2c6eb39729c39cee5465" in text
    else:
        assert "cd1e52ce400c027ed0b7ab4b9d613f5a" in text or "t2t" in text.lower()
    assert row["check"]=="bit-perfect"
    assert row["on_device_ms"]>0 and row["on_device_gb_s"]>0

expected={"Tesla T4","NVIDIA L4","NVIDIA A100-SXM4-40GB","NVIDIA A100-SXM4-80GB",
          "NVIDIA RTX PRO 6000 Blackwell Server Edition"}
assert expected <= {r["gpu"] for r in data["rows"]}
assert {r["corpus"] for r in data["rows"]}=={"chr1","t2t"}
print(f'PASS: {len(data["rows"])} measured GPU rows backed by imported Colab logs')
