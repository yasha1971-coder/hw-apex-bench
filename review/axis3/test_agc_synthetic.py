#!/usr/bin/env python3
"""Native correctness only: one create per mode, library ranges and CLI oracle."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess
from agc_adapter import AgcReader, create


def bases(path):
    return b"".join(s for s in path.read_bytes().splitlines() if not s.startswith(b">"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", type=Path, required=True)
    ap.add_argument("--library", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20261003)
    common = bytearray(rng.choice(b"ACGT") for _ in range(1048576))
    samples = []
    lf = bytes([10])
    for number in range(3):
        seq = bytearray(common)
        for i in range(1000 + 137 * number):
            at = (i * 1009 + number * 7919) % len(seq)
            seq[at] = b"ACGT"[(b"ACGT".index(seq[at]) + number + 1) % 4]
        p = args.out / f"assembly{number}.fa"
        p.write_bytes(b">shared" + lf + lf.join(seq[i:i + 80] for i in range(0, len(seq), 80)) + lf)
        subprocess.run(["samtools", "faidx", str(p)], check=True)
        samples.append((f"assembly{number}", p))
    ref = args.out / "reference.fa"
    ref.write_bytes(b">shared" + lf + lf.join(common[i:i + 80] for i in range(0, len(common), 80)) + lf)
    for mode in ("t2t", "noref"):
        archive = args.out / (mode + ".agc")
        receipt = create(args.binary, samples, mode, archive, ref if mode == "t2t" else None, 1)
        checked = 0
        with AgcReader(args.library, archive, receipt["archive_sha256"]) as reader:
            for sample, source in samples:
                truth = bases(source)
                for start, length in ((0, 1), (1000, 4096), (65535, 8192), (len(truth) - 65536, 65536)):
                    got = reader.fetch(sample, "shared", start, length)
                    expected = truth[start:start + length]
                    # AGC CLI and API both use 0-based INCLUSIVE coordinates.
                    agc_query = f"shared@{sample}:{start}-{start + length - 1}"
                    cli = subprocess.run([str(args.binary), "getctg", str(archive), agc_query], capture_output=True, check=True).stdout
                    cli_bases = b"".join(x for x in cli.splitlines() if not x.startswith(b">"))
                    # samtools faidx uses 1-based inclusive coordinates.
                    faidx_query = f"shared:{start + 1}-{start + length}"
                    sam = subprocess.run(["samtools", "faidx", str(source), faidx_query], capture_output=True, check=True).stdout
                    sam_bases = b"".join(x for x in sam.splitlines() if not x.startswith(b">"))
                    if got != expected or cli_bases != expected or sam_bases != expected:
                        raise SystemExit(f"FAILED mode={mode} sample={sample} start0={start} len={length}")
                    checked += 1
                    print(json.dumps({"stage": "AGC_RANGE_PASS", "mode": mode, "sample": sample,
                                      "contig": "shared", "start0": start, "end0": start + length - 1,
                                      "length": length, "sha256": hashlib.sha256(got).hexdigest()}))
                for start, length in ((len(truth), 1), (0, len(truth) + 1)):
                    try: reader.fetch(sample, "shared", start, length)
                    except ValueError: pass
                    else: raise SystemExit("FAILED: out-of-range window was clipped or accepted")
        (args.out / (mode + ".receipt.json")).write_text(json.dumps(receipt, indent=2) + chr(10))
        print(f"PASS AGC mode={mode} create_calls=1 append_calls=0 ranges={checked} bit_perfect=true")


if __name__ == "__main__": main()
