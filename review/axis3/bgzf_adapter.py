#!/usr/bin/env python3
"""Stock BGZF and matched-g variants with identical pinned htslib read path."""
import ctypes
import hashlib
from pathlib import Path
import struct
import subprocess

HTS_PIN = "4b705e4fada8ee2b6b15746f725ee8ac51631803"
LIBDEFLATE_PIN = "dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f"
MAX_UNCOMPRESSED_BLOCK = 65280


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for data in iter(lambda: f.read(1024 * 1024), b""): h.update(data)
    return h.hexdigest()


def blocks(path):
    """Read actual BGZF members, not a nominal Q. Ignore the empty EOF member."""
    result = []
    with Path(path).open("rb") as f:
        size = f.seek(0, 2)
        position = 0
        while position < size:
            f.seek(position)
            header = f.read(12)
            if len(header) != 12 or header[:3] != bytes.fromhex("1f8b08") or header[3] != 4:
                raise ValueError("not a complete BGZF header")
            extra = f.read(struct.unpack_from("<H", header, 10)[0])
            offset, block_size = 0, None
            while offset < len(extra):
                if offset + 4 > len(extra): raise ValueError("short BGZF extra field")
                tag, n = extra[offset:offset + 2], struct.unpack_from("<H", extra, offset + 2)[0]
                offset += 4
                if offset + n > len(extra): raise ValueError("short BGZF extra value")
                if tag == b"BC":
                    if n != 2 or block_size is not None: raise ValueError("invalid or duplicate BC field")
                    block_size = struct.unpack_from("<H", extra, offset)[0] + 1
                offset += n
            if block_size is None or block_size < len(header) + len(extra) + 8 or position + block_size > size:
                raise ValueError("BGZF block extends outside archive")
            f.seek(position + block_size - 4)
            ulen = struct.unpack("<I", f.read(4))[0]
            if ulen > 65536: raise ValueError("BGZF ISIZE exceeds format limit")
            if ulen:
                result.append({"coff": position, "clen": block_size, "ulen": ulen})
            position += block_size
    if position != size: raise ValueError("BGZF trailing bytes")
    return result


def library(path):
    lib = ctypes.CDLL(str(Path(path).resolve()))
    lib.hwa_bgzf_matched.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
    lib.hwa_bgzf_matched.restype = ctypes.c_int
    lib.hwa_bgzf_index.argtypes = [ctypes.c_char_p]
    lib.hwa_bgzf_index.restype = ctypes.c_int
    lib.hwa_bgzf_open.argtypes = [ctypes.c_char_p]
    lib.hwa_bgzf_open.restype = ctypes.c_void_p
    lib.hwa_bgzf_length.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.hwa_bgzf_length.restype = ctypes.c_int64
    lib.hwa_bgzf_fetch.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint64,
                                    ctypes.c_uint64, ctypes.c_void_p, ctypes.c_size_t]
    lib.hwa_bgzf_fetch.restype = ctypes.c_int64
    lib.hwa_bgzf_close.argtypes = [ctypes.c_void_p]
    lib.hwa_bgzf_close.restype = None
    lib.hwa_bgzf_version.restype = ctypes.c_char_p
    if lib.hwa_bgzf_version().decode() != "1.24":
        raise ValueError("htslib runtime version differs from repository pin")
    return lib


def create(binary, libpath, source, output, mode="default", granule=None):
    source, output = Path(source), Path(output)
    if mode not in ("default", "matched-g"): raise ValueError("unknown BGZF mode")
    if mode == "default" and granule is not None: raise ValueError("stock default cannot override g")
    if mode == "matched-g" and (type(granule) is not int or not 1 <= granule <= MAX_UNCOMPRESSED_BLOCK):
        raise ValueError("matched-g requires a legal BGZF target in 1..65280")
    if output.exists(): raise FileExistsError(output)
    lib = library(libpath)
    if mode == "default":
        # No binary-mode or newline policy override: stock author's defaults.
        with output.open("xb") as f:
            subprocess.run([str(binary), "-@", "1", "-c", str(source)], stdout=f, check=True)
    else:
        rc = lib.hwa_bgzf_matched(str(source).encode(), str(output).encode(), granule)
        if rc != 0: raise RuntimeError(f"bgzf_write/flush failed: {rc}")
    if lib.hwa_bgzf_index(str(output).encode()) != 0: raise RuntimeError("fai_build3 failed")
    artifacts = [output, Path(str(output) + ".fai"), Path(str(output) + ".gzi")]
    for path in artifacts:
        if not path.is_file(): raise ValueError(f"missing required sidecar {path.name}")
    geometry = blocks(output)
    total = sum(b["ulen"] for b in geometry)
    if total != source.stat().st_size: raise ValueError("BGZF block total differs from FASTA bytes")
    if mode == "matched-g":
        expected = [granule] * (total // granule)
        if total % granule: expected.append(total % granule)
        if [b["ulen"] for b in geometry] != expected:
            raise ValueError("matched-g archive does not have the requested flush boundaries")
    return {"codec": "BGZF", "mode": mode, "htslib_version": "1.24", "htslib_commit": HTS_PIN,
            "libdeflate_commit": LIBDEFLATE_PIN, "build_threads": 1, "decode_threads": 1,
            "scope": "cpu-in-process", "granule_target": granule, "blocks": len(geometry),
            "Q_mean_uncompressed_bytes": total / len(geometry) if geometry else None,
            "uncompressed_fasta_bytes": total, "storage_bytes": sum(p.stat().st_size for p in artifacts),
            "artifacts": [{"path": p.name, "bytes": p.stat().st_size, "sha256": digest(p)} for p in artifacts]}


class BgzfReader:
    def __init__(self, libpath, archive):
        self.lib = library(libpath)
        self.handle = self.lib.hwa_bgzf_open(str(Path(archive).resolve()).encode())
        if not self.handle: raise ValueError("htslib failed to load existing FASTA indexes")

    def contig_length(self, contig):
        if not self.handle or not isinstance(contig, str) or not contig or chr(0) in contig:
            raise ValueError("explicit valid contig required")
        n = self.lib.hwa_bgzf_length(self.handle, contig.encode())
        if n < 0: raise ValueError("contig not found")
        return n

    def fetch(self, contig, start0, length):
        if type(start0) is not int or type(length) is not int or start0 < 0 or length <= 0:
            raise ValueError("nonempty integer window required")
        n = self.contig_length(contig)
        if start0 > n or length > n - start0: raise ValueError("window exceeds contig; no clipping")
        out = ctypes.create_string_buffer(length)
        got = self.lib.hwa_bgzf_fetch(self.handle, contig.encode(), start0, length, out, length)
        if got != length: raise ValueError("htslib fetch error or short output")
        return out.raw

    def close(self):
        if self.handle: self.lib.hwa_bgzf_close(self.handle); self.handle = None
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
