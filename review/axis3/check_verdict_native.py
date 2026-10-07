#!/usr/bin/env python3
"""CI correctness check for the real B refrel3/BGZF full-decode connections.

Uses retained synthetic archives produced by existing CI. No clocks, no rates,
no new corpus download. Run via python3 -m review.axis3.check_verdict_native.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from review.axis3.verdict_data import FastaTruth, file_ref, write_json
from review.axis3.verdict_readers import HTS_PIN, REFREL_PIN, open_reader
from tools.axis3_window_engine import Window
from tools.verdict_refrel3 import full_check


def check(family, variant, library, archive, source, reference=None, granule=None):
    # Stage concrete inputs under one root so the same hash/path contract as the
    # official job is exercised. The compiler string is for this CI build only.
    with tempfile.TemporaryDirectory(prefix="verdict-native-correctness-") as td:
        root = Path(td)
        for name, src in (("reader.so", library), ("archive.bin", archive), ("source.fa", source)):
            shutil.copyfile(src, root / name)
        aid = "synthetic-assembly"
        truth = FastaTruth([(aid, root / "source.fa")])
        reader = None
        try:
            assembly = {"assembly_id": aid, "fasta": file_ref(root, root / "source.fa"),
                        "contigs": [{"contig_id": c, "length": n} for a, c, n in truth.contigs()],
                        **truth.full_identity(aid)}
            corpus = {"assemblies": [assembly]}
            libref = file_ref(root, root / "reader.so")
            compiler = subprocess.run(["g++" if family == "refrel3" else "gcc", "--version"],
                                      check=True, capture_output=True, text=True).stdout.splitlines()[0]
            receipt = {"source_commit": REFREL_PIN if family == "refrel3" else HTS_PIN,
                       "codec_version": "refrel3-v1" if family == "refrel3" else "1.24",
                       "compiler": compiler, "flags": ["see pinned CI build script"],
                       "dependencies": {"provenance": "CI build log; no performance receipt"},
                       "library_sha256": libref["sha256"], "decoder_threads": 1}
            write_json(root / "build.json", receipt)
            arc = {"assembly_id": aid, "archive": file_ref(root, root / "archive.bin")}
            spec = {"id": "native-check", "family": family, "variant": variant,
                    "library": libref, "build_receipt": file_ref(root, root / "build.json"), "archives": [arc]}
            if family == "refrel3":
                if reference is None:
                    raise ValueError("refrel3 check requires reference")
                shutil.copyfile(reference, root / "ref.fa")
                spec["reference"] = file_ref(root, root / "ref.fa")
            else:
                for suffix, key in ((".fai", "fai"), (".gzi", "gzi")):
                    shutil.copyfile(str(archive) + suffix, root / ("archive.bin" + suffix))
                    arc[key] = file_ref(root, root / ("archive.bin" + suffix))
                if variant == "matched-g":
                    spec["granule_raw_bytes"] = granule
            reader = open_reader(root, spec, corpus)
            full = full_check(reader.decode_native(), corpus)
            checked = 0
            for a, c, length in truth.contigs():
                for w in (1, 1024, 8192, 65536):
                    if w > length:
                        continue
                    for start in sorted({0, length - w, min(4095, length - w)}):
                        want = truth.fetch(a, c, start, start + w)
                        got = reader.fetch(a, c, start, start + w)
                        if got != want:
                            raise AssertionError("native verdict connection differs from FASTA")
                        r = Window(checked, a, c, start, start + w, hashlib.sha256(want).hexdigest())
                        translated = reader.translated(r)
                        if family == "refrel3" and translated["convention"] != "0-based-half-open":
                            raise AssertionError("refrel3 shim ABI translation differs")
                        print(json.dumps({"stage": "B_NATIVE_RANGE_PASS", "family": family, "variant": variant,
                                          "canonical": r.canonical(), "translated": translated,
                                          "sha256": hashlib.sha256(got).hexdigest()}, sort_keys=True))
                        checked += 1
            print(json.dumps({"stage": "B_NATIVE_FULL_PASS", "family": family, "variant": variant,
                              "checks": full, "windows_checked": checked,
                              "correctness_only": True, "timings_recorded": False}, sort_keys=True))
        finally:
            if reader is not None:
                reader.close()
            truth.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--family", choices=("refrel3", "bgzf"), required=True)
    p.add_argument("--variant", required=True)
    for name in ("library", "archive", "source"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--reference", type=Path)
    p.add_argument("--granule", type=int)
    a = p.parse_args()
    check(a.family, a.variant, a.library, a.archive, a.source, a.reference, a.granule)


if __name__ == "__main__":
    main()
