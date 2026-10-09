#!/usr/bin/env python3
"""Exercise both native BGZF configurations against samtools and FASTA bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess
from bgzf_adapter import BgzfReader, create


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bgzip", type=Path, required=True)
    p.add_argument("--library", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20261003)
    truth = {"c1": bytes(rng.choice(b"ACGTN") for _ in range(1048576)), "c2": b"GATTACA" * 12000}
    source = a.out / "truth.fa"; lf = bytes([10])
    with source.open("wb") as f:
        for name, seq in truth.items():
            f.write(b">" + name.encode() + lf)
            for i in range(0, len(seq), 80): f.write(seq[i:i+80] + lf)
    subprocess.run(["samtools", "faidx", str(source)], check=True)
    for mode, q in (("default", None), ("matched-g", 4096), ("matched-g", 16384), ("matched-g", 65280)):
        label = mode if q is None else f"matched-g{q}"
        archive = a.out / (label + ".bgz")
        receipt = create(a.bgzip, a.library, source, archive, mode, q)
        checked = 0
        with BgzfReader(a.library, archive) as reader:
            for name, seq in truth.items():
                if reader.contig_length(name) != len(seq): raise SystemExit("length mismatch")
                for start, length in ((0, 1), (4095, 2), (65535, 8192), (len(seq)-65536, 65536), (len(seq)-1, 1)):
                    got = reader.fetch(name, start, length)
                    query = f"{name}:{start+1}-{start+length}"
                    output = subprocess.run(["samtools", "faidx", str(source), query], capture_output=True, check=True).stdout
                    oracle = b"".join(x for x in output.splitlines() if not x.startswith(b">"))
                    if got != oracle or got != seq[start:start+length]: raise SystemExit(f"FAILED {label} {query}")
                    print(json.dumps({"stage": "BGZF_RANGE_PASS", "mode": label, "query": query, "length": length,
                                      "sha256": hashlib.sha256(got).hexdigest()}))
                    checked += 1
        (a.out / (label + ".json")).write_text(json.dumps(receipt, indent=2) + chr(10))
        print(f"PASS BGZF mode={label} ranges={checked} bit_perfect=true")


if __name__ == "__main__": main()
