"""Native reader/whole-decode connections for the verdict job (no subprocess fallback).

Creation/build commands stay outside this job. Every input archive, native library,
sidecar and build receipt is hash-locked before opening. Missing AGC geometry is
FAILED, never a guessed Q. This module does not run anything on import.
"""
from __future__ import annotations

import ctypes
from fractions import Fraction
from pathlib import Path

from review.axis3 import native_readers as native
from review.axis3.agc_adapter import AgcReader, PIN as AGC_PIN
from review.axis3.bgzf_adapter import BgzfReader, blocks, HTS_PIN
from review.axis3.verdict_data import FastaTruth, checked_file, load_json

REFREL_PIN = "5b6d5cec0f5962a561ac48822a1b5c48793a5b47"
OPENZL_PIN = "32246b48faee46807f84183dac4db479089f5445"
ZSTD_PIN = "f8745da6ff1ad1e7bab384bd1f9d742439278e99"
OZ_VARIANTS = {"l1_w64k": (1, 16, 65536), "l1_w1m": (1, 20, 1048576),
               "l3_w64k": (3, 16, 65536), "l3_w1m": (3, 20, 1048576)}
FAMILIES = {"refrel3", "bgzf", "zstd-seekable", "lz4-indexed", "ozseg", "agc"}
FOREIGN_FAMILIES = FAMILIES - {"refrel3"}


def positive_mean(sizes):
    if any(type(n) is not int or n < 0 for n in sizes):
        raise ValueError("invalid canonical granule sizes")
    positive = [n for n in sizes if n > 0]
    if not positive:
        raise ValueError("no positive canonical decode granules")
    return Fraction(sum(positive), len(positive))


def bgzf_canonical_sizes(archive, source, assembly):
    """ISIZE is raw FASTA bytes; count sequence positions in each emitted block."""
    truth = FastaTruth([(assembly, source)])
    try:
        def prefix(x):
            total = 0
            for row in truth.records.values():
                if not row["length"] or x <= row["offset"]:
                    continue
                lines, rest = divmod(x - row["offset"], row["line_bytes"])
                total += min(row["length"], lines * row["line_bases"] + min(rest, row["line_bases"]))
            return total
        raw = 0
        sizes = []
        for member in blocks(archive):
            end = raw + member["ulen"]
            sizes.append(prefix(end) - prefix(raw))
            raw = end
        if raw != Path(source).stat().st_size:
            raise ValueError("BGZF raw geometry differs from source FASTA")
        if sum(sizes) != sum(n for _, _, n in truth.contigs()):
            raise ValueError("BGZF canonical geometry mismatch")
        return sizes
    finally:
        truth.close()


def _expected_contigs(assembly):
    return [(c["contig_id"], c["length"]) for c in assembly["contigs"]]


def _check_map(reader, assembly):
    expected = [(assembly["assembly_id"], c, n) for c, n in _expected_contigs(assembly)]
    observed = [(a, c, n) for (a, c), (_, n) in reader.map.items()]
    if observed != expected:
        raise ValueError("canonical map differs from frozen assembly order/lengths")


class Single:
    scope = "cpu-in-process"
    decoder_threads = 1

    def __init__(self, assembly, reader, full, *, close=None):
        self.assembly = assembly
        self.reader = reader
        self.full = full
        self._close = close or getattr(reader, "close", lambda: None)

    def contig_length(self, a, c):
        if a != self.assembly["assembly_id"]:
            raise ValueError("unknown assembly for native handle")
        return self.reader.contig_length(a, c)

    def translated(self, request):
        if request.assembly != self.assembly["assembly_id"]:
            raise ValueError("unknown assembly for translation")
        return self.reader.translated(request)

    def fetch(self, a, c, s, e):
        if type(s) is not int or type(e) is not int or not 0 <= s < e <= self.contig_length(a, c):
            raise ValueError("window outside contig")
        return self.reader.fetch(a, c, s, e)

    def close(self):
        self._close()


class CohortReader:
    scope = "cpu-in-process"
    decoder_threads = 1

    def __init__(self, singles, q, geometry, build, boundary):
        self.singles = {s.assembly["assembly_id"]: s for s in singles}
        if len(self.singles) != len(singles):
            raise ValueError("duplicate native assembly handle")
        self.q = q
        self.geometry = geometry
        self.build = build
        self.full_timing_boundary = boundary

    def contig_length(self, a, c):
        return self.singles[a].contig_length(a, c)

    def translated(self, r):
        return self.singles[r.assembly].translated(r)

    def fetch(self, a, c, s, e):
        return self.singles[a].fetch(a, c, s, e)

    def decode_native(self):
        # Do not hash, strip FASTA or join assembly outputs inside this interval.
        return [(a, *s.full()) for a, s in self.singles.items()]

    def close(self):
        for s in self.singles.values():
            s.close()


def _check_receipt(root, spec):
    family = spec["family"]
    if family not in FAMILIES:
        raise ValueError("unsupported verdict family")
    lib = checked_file(root, spec["library"])
    receipt = load_json(checked_file(root, spec["build_receipt"]))
    for key in ("source_commit", "codec_version", "compiler", "flags", "dependencies", "library_sha256"):
        if key not in receipt:
            raise ValueError("build receipt missing " + key)
    pin = {"refrel3": REFREL_PIN, "agc": AGC_PIN, "ozseg": OPENZL_PIN,
           "bgzf": HTS_PIN, "zstd-seekable": ZSTD_PIN}.get(family)
    if pin is not None and receipt["source_commit"] != pin:
        raise ValueError("codec pin differs from retained implementation")
    if (receipt["library_sha256"] != spec["library"]["sha256"]
            or receipt.get("decoder_threads") != 1 or not receipt["compiler"]
            or not isinstance(receipt["flags"], list) or not receipt["dependencies"]):
        raise ValueError("invalid library hash/thread/compiler provenance")
    if family == "lz4-indexed" and receipt["codec_version"] != "1.10.0":
        raise ValueError("LZ4 version differs from retained 1.10.0")
    if (not isinstance(receipt["source_commit"], str) or len(receipt["source_commit"]) != 40
            or any(c not in "0123456789abcdef" for c in receipt["source_commit"])):
        raise ValueError("full source commit is required")
    return lib, receipt


def open_reader(root, spec, corpus):
    """Open only the explicitly named persistent native implementation.

    A missing symbol is a hard failure with a rebuild instruction; no CLI or
    pre-decoded-memory substitute is selected. Called outside measured windows.
    """
    libpath, build = _check_receipt(root, spec)
    family = spec["family"]
    assemblies = corpus["assemblies"]
    if family == "agc":
        return _open_agc(root, spec, corpus, libpath, build)
    if [a["assembly_id"] for a in spec["archives"]] != [a["assembly_id"] for a in assemblies]:
        raise ValueError("archive order does not cover the frozen cohort")
    singles, geometries, all_sizes = [], [], []
    header_q = None
    try:
        for assembly, arc in zip(assemblies, spec["archives"]):
            aid = assembly["assembly_id"]
            path = checked_file(root, arc["archive"])
            n = assembly["canonical_bytes"]
            if family == "refrel3":
                ref = checked_file(root, spec["reference"])
                r = native.Refrel3Reader(libpath, ref, path, aid)
                expected = {"q4k": 4096, "q16k": 16384}.get(spec["variant"])
                if expected is None or r.q() != expected:
                    r.close()
                    raise ValueError("refrel3 RR_BS differs from variant")
                header_q = expected
                L = r.lib
                try:
                    L.hwa_rr3_size.argtypes = [ctypes.c_void_p]
                    L.hwa_rr3_size.restype = ctypes.c_uint64
                    L.hwa_rr3_decode.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
                    L.hwa_rr3_decode.restype = ctypes.c_int64
                except AttributeError:
                    r.close()
                    raise ValueError("rebuild refrel3 native library with B full-decode exports") from None
                if L.hwa_rr3_size(r.h) != n:
                    r.close()
                    raise ValueError("refrel3 canonical total differs from corpus")
                buf = ctypes.create_string_buffer(n + 64)

                def full(r=r, buf=buf, n=n):
                    got = r.lib.hwa_rr3_decode(r.h, buf, n)
                    if got != n:
                        raise ValueError("refrel3 native full decode failed")
                    return "sequence", memoryview(buf).cast("B")[:n]
                singles.append(Single(assembly, r, full))
                geometries.append({"assembly_id": aid, "canonical_bytes": n, "Q": expected,
                                   "method": "header-RR_BS", "units": (n + expected - 1) // expected})
            elif family == "bgzf":
                if spec["variant"] not in ("default", "matched-g"):
                    raise ValueError("BGZF must be default or matched-g")
                source = checked_file(root, assembly["fasta"])
                for suffix in (".fai", ".gzi"):
                    side = checked_file(root, arc["fai" if suffix == ".fai" else "gzi"])
                    if side != Path(str(path) + suffix):
                        raise ValueError("BGZF sidecar is not the one loaded by faidx")
                inner = BgzfReader(libpath, path)
                r = native.BgzfReaderAdapter(inner, aid)
                L = inner.lib
                try:
                    L.hwa_bgzf_dq_open.argtypes = [ctypes.c_char_p]
                    L.hwa_bgzf_dq_open.restype = ctypes.c_void_p
                    L.hwa_bgzf_dq_decode.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
                    L.hwa_bgzf_dq_decode.restype = ctypes.c_int64
                    L.hwa_bgzf_dq_close.argtypes = [ctypes.c_void_p]
                    L.hwa_bgzf_dq_close.restype = None
                except AttributeError:
                    inner.close()
                    raise ValueError("rebuild BGZF native library with B full-decode exports") from None
                handle = L.hwa_bgzf_dq_open(str(path).encode())
                if not handle:
                    inner.close()
                    raise ValueError("BGZF full-decode cursor refused archive")
                raw_size = source.stat().st_size
                buf = ctypes.create_string_buffer(raw_size + 1)

                def full(L=L, handle=handle, buf=buf, raw_size=raw_size):
                    got = L.hwa_bgzf_dq_decode(handle, buf, raw_size)
                    if got != raw_size:
                        raise ValueError("BGZF full output differs from source byte count")
                    return "fasta", memoryview(buf).cast("B")[:got]

                def close(inner=inner, L=L, handle=handle):
                    inner.close()
                    L.hwa_bgzf_dq_close(handle)
                singles.append(Single(assembly, r, full, close=close))
                sizes = bgzf_canonical_sizes(path, source, aid)
                all_sizes.extend(sizes)
                geometries.append({"assembly_id": aid, "canonical_sizes": sizes,
                                   "method": "FASTA-index-intersection-with-emitted-BGZF-blocks"})
                if spec["variant"] == "matched-g":
                    g = spec.get("granule_raw_bytes")
                    if type(g) is not int or not 1 <= g <= 65280:
                        raise ValueError("matched-g requires its predeclared legal raw-byte target")
                    if [x["ulen"] for x in blocks(path)] != [g] * (raw_size // g) + ([raw_size % g] if raw_size % g else []):
                        raise ValueError("matched-g emitted raw blocks differ from build declaration")
            elif family == "zstd-seekable":
                r = native.ResidentOffsetReader(libpath, path, checked_file(root, arc["contig_map"]))
                singles.append(Single(assembly, r, lambda r=r: ("sequence", r.decode_sequence())))
                _check_map(r, assembly)
                L = r.lib
                L.hc_version.restype = ctypes.c_char_p
                if L.hc_version().decode() != "1.5.7":
                    raise ValueError("zstd runtime differs from retained 1.5.7")
                L.hc_geometry.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_uint64)] * 4
                L.hc_geometry.restype = ctypes.c_int
                u, empty, raw, largest = [ctypes.c_uint64() for _ in range(4)]
                if L.hc_geometry(r.h, ctypes.byref(u), ctypes.byref(empty), ctypes.byref(raw), ctypes.byref(largest)) != 0:
                    raise ValueError("zstd seek-table geometry refused")
                if raw.value != n or u.value <= empty.value:
                    raise ValueError("zstd canonical geometry mismatch")
                geometries.append({"assembly_id": aid, "canonical_bytes": n,
                                   "units": u.value - empty.value, "empty_units": empty.value,
                                   "largest": largest.value, "method": "native-seek-table"})
            elif family == "lz4-indexed":
                index = checked_file(root, arc["index"])
                data = load_json(index)
                uoff = coff = 0
                sizes = []
                for f in data["frames"]:
                    if (any(type(f.get(k)) is not int for k in ("uoff", "coff", "ulen", "clen"))
                            or f["uoff"] != uoff or f["coff"] != coff
                            or not 0 < f["ulen"] <= 2147483647 or not 0 < f["clen"] <= 2147483647):
                        raise ValueError("invalid independent LZ4 frame directory")
                    uoff += f["ulen"]
                    coff += f["clen"]
                    sizes.append(f["ulen"])
                if uoff != n or coff != path.stat().st_size:
                    raise ValueError("LZ4 frame lengths differ from archive/corpus")
                r = native.IndexedLz4Reader(libpath, path, index)
                singles.append(Single(assembly, r, lambda r=r: ("sequence", r.decode_sequence())))
                _check_map(r, assembly)
                all_sizes.extend(sizes)
                geometries.append({"assembly_id": aid, "canonical_sizes": sizes, "method": "independent-LZ4-index"})
            elif family == "ozseg":
                r = native.OzsegReader(libpath, path)
                singles.append(Single(assembly, r, lambda r=r: ("sequence", r.decode_sequence())))
                expected = OZ_VARIANTS.get(spec["variant"])
                if expected is None or (r.meta["level"], r.meta["windowLog"], r.meta["Q"]) != expected:
                    raise ValueError("OpenZL paired variant differs from archive")
                if ([(x["name"], x["length"]) for x in r.meta["contigs"]] != _expected_contigs(assembly)
                        or len(r.contigs) != len(r.meta["contigs"])):
                    raise ValueError("OZSEG contigs differ from source or have duplicate IDs")
                prefix = 0
                for c in r.meta["contigs"]:
                    if c["start"] != prefix:
                        raise ValueError("invalid OZSEG contig prefix")
                    prefix += c["length"]
                if prefix != n or r.meta["uncompressed_bases"] != n:
                    raise ValueError("OZSEG canonical size mismatch")
                header_q = expected[2]
                geometries.append({"assembly_id": aid, "canonical_bytes": n, "Q": header_q,
                                   "method": "independent-frame-target", "lz_window_bytes": 1 << expected[1],
                                   "canonical_sizes": [f["ulen"] for f in r.meta["frames"]]})
        for s in singles:
            for c, n in _expected_contigs(s.assembly):
                if s.contig_length(s.assembly["assembly_id"], c) != n:
                    raise ValueError("native contig length differs from frozen corpus")
        if family == "zstd-seekable":
            q = Fraction(sum(g["canonical_bytes"] for g in geometries), sum(g["units"] for g in geometries))
        else:
            q = Fraction(header_q) if header_q else positive_mean(all_sizes)
        return CohortReader(singles, q, geometries, build,
                            "one-thread persistent full sequential native calls and adapter materialization; "
                            "FASTA normalization and all SHA work outside timer")
    except Exception:
        for s in singles:
            s.close()
        raise


def _open_agc(root, spec, corpus, libpath, build):
    if spec["variant"] not in ("t2t", "noref"):
        raise ValueError("AGC mode must be t2t or noref")
    archive = checked_file(root, spec["archive"])
    if spec["variant"] == "t2t":
        checked_file(root, spec["reference"])
    elif "reference" in spec:
        raise ValueError("noref must not add an external reference")
    # The public API does not expose independent-unit geometry. Require retained
    # instrumented source evidence rather than substituting segment_size or W.
    geom = load_json(checked_file(root, spec["geometry"]))
    checked_file(root, geom["source_log"])
    if (geom.get("schema") != "agc-canonical-geometry-v1" or geom.get("source_commit") != AGC_PIN
            or geom.get("archive_sha256") != spec["archive"]["sha256"]
            or not geom.get("independent_unit_definition") or geom.get("domain") != "canonical-sequence"):
        raise ValueError("AGC canonical granule evidence is missing or not archive-bound")
    q = positive_mean(geom["canonical_unit_sizes"])
    if build.get("create_calls") != 1 or build.get("append_calls") != 0 or build.get("mode") != spec["variant"]:
        raise ValueError("AGC receipt must show the selected mode, one stock create and no append chain")
    if build.get("cohort_order") != [a["assembly_id"] for a in corpus["assemblies"]]:
        raise ValueError("AGC sample names/order differ from corpus")
    inner = AgcReader(libpath, archive)
    adapter = native.AgcReaderAdapter(inner)
    singles = []
    try:
        for assembly in corpus["assemblies"]:
            aid = assembly["assembly_id"]
            for c, n in _expected_contigs(assembly):
                if inner.contig_length(aid, c) != n:
                    raise ValueError("AGC contig differs from frozen source")

            def full(assembly=assembly):
                chunks = [inner.fetch(assembly["assembly_id"], c["contig_id"], 0, c["length"])
                          for c in assembly["contigs"] if c["length"]]
                return "sequence", b"".join(chunks)
            singles.append(Single(assembly, adapter, full, close=lambda: None))
        result = CohortReader(singles, q, [geom], build,
                              "one-thread ordered complete-contig libagc calls including ctypes materialization; SHA outside")
        result.close = inner.close
        return result
    except Exception:
        inner.close()
        raise
