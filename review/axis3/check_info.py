#!/usr/bin/env python3
"""Strict parsers for Axis 3 CI output; no codec or format changes."""
import argparse
import json
import re
from pathlib import Path

OZSEG_VARIANTS = {
    "l1_w64k": (65536, 16, 1), "l1_w1m": (1048576, 20, 1),
    "l3_w64k": (65536, 16, 3), "l3_w1m": (1048576, 20, 3),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def integer(value, name, minimum=0):
    require(type(value) is int and value >= minimum,
            f"{name}: expected integer >= {minimum}, got {value!r}")
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(text):
    value = json.loads(text, object_pairs_hook=unique_object)
    require(type(value) is dict, "expected a JSON object")
    return value


def check_ozseg(text, variant, input_bases):
    q, window_log, level = OZSEG_VARIANTS[variant]
    integer(input_bases, "input_bases")
    data = load_json(text)
    for key, expected in (("Q", q), ("windowLog", window_log), ("level", level)):
        actual = integer(data[key], key)
        require(actual == expected, f"{key}: {actual} != {expected}")
    frames = data["frames"]
    require(type(frames) is list, "frames must be an array")
    expected_count = (input_bases + q - 1) // q
    require(len(frames) == expected_count,
            f"frame_count: {len(frames)} != {expected_count}")
    total = 0
    for i, frame in enumerate(frames):
        require(type(frame) is dict, f"frame {i}: expected object")
        length = integer(frame["ulen"], f"frames[{i}].ulen", 1)
        require(length == min(q, input_bases - total),
                f"frame {i}: unexpected uncompressed length {length}")
        require(integer(frame["uoff"], f"frames[{i}].uoff") == total,
                f"frame {i}: uncompressed offset is not contiguous")
        total += length
    require(total == input_bases, f"sum_ulen: {total} != {input_bases}")
    require(integer(data["uncompressed_bases"], "uncompressed_bases") == input_bases,
            "declared total does not equal independent FASTA truth")
    return {"variant": variant, "Q": q, "windowLog": window_log, "level": level,
            "frames": len(frames), "sum_ulen": total}


# Exact documented stdout grammar of cmd_info at the frozen upstream pin:
# aceapex/research/refrel/refrel3v1.cpp, commit 5b6d5cec, lines 157-162.
REFREL_INFO = re.compile(
    r"refrel3 v(?P<version>[0-9]+) Q (?P<Q>[0-9]+) flags (?P<flags>[0-9]+)"
    r" \| reference (?P<reference>.+) sha256 (?P<reference_sha256>[0-9a-f]{64}),"
    r" (?P<reference_bases>[0-9]+) bases \| assembly (?P<bases>[0-9]+) bases,"
    r" (?P<blocks>[0-9]+) blocks \| FASTA XXH3 (?P<fasta_xxh3>[0-9a-f]{16})"
    r" \| meta (?P<meta_bytes>[0-9]+) B \(raw (?P<meta_raw>[0-9]+)\),"
    r" block hashes (?P<hash_bytes>[0-9]+) B, payload (?P<payload_bytes>[0-9]+) B"
)


def check_refrel(text, variant):
    match = REFREL_INFO.fullmatch(text.strip())
    require(match is not None, "invalid refrel3 v1 info record")
    data = match.groupdict()
    for key in ("version", "Q", "flags", "reference_bases", "bases", "blocks",
                "meta_bytes", "meta_raw", "hash_bytes", "payload_bytes"):
        data[key] = int(data[key])
    q = {"q4k": 4096, "q16k": 16384}[variant]
    require(data["version"] == 1, "refrel3 version must be 1")
    require(data["Q"] == q, f"refrel3 Q: {data['Q']} != {q}")
    require(data["flags"] == 1, "synthetic archive must retain block checksums")
    require(data["blocks"] == (data["bases"] + q - 1) // q, "refrel3 block count")
    require(data["hash_bytes"] == data["blocks"] * 8, "refrel3 hash table size")
    return {"variant": variant, **data}


def check_two_bit(text):
    data = load_json(text)
    require(data["codec"] == "2-bit-capacity", "unexpected capacity codec")
    require(data["status"] == "PASS", "capacity correctness status is not PASS")
    integer(data["synthetic_payload_bytes"], "synthetic_payload_bytes")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="kind", required=True)
    oz = sub.add_parser("ozseg")
    oz.add_argument("path", type=Path)
    oz.add_argument("variant", choices=OZSEG_VARIANTS)
    oz.add_argument("input_bases", type=int)
    rr = sub.add_parser("refrel3")
    rr.add_argument("path", type=Path)
    rr.add_argument("variant", choices=("q4k", "q16k"))
    tb = sub.add_parser("two-bit")
    tb.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        text = args.path.read_text(encoding="utf-8")
        if args.kind == "ozseg":
            result = check_ozseg(text, args.variant, args.input_bases)
        elif args.kind == "refrel3":
            result = check_refrel(text, args.variant)
        else:
            result = check_two_bit(text)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.exit(1, f"INFO_CONTRACT_FAIL: {exc}" + chr(10))
    print("INFO_CONTRACT_PASS", json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
