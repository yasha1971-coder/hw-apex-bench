"""Independent archive-geometry check of the four ACEAPEX stream counters."""
import struct

def check_ace_counts(path, samples, config):
    data = path.read_bytes()
    block, count = struct.unpack_from("<II", data, 20)
    sizes = struct.unpack_from("<4Q", data, 36)
    p = 68 + count * 64
    totals = []
    literal_chunk = None
    for i, size in enumerate(sizes):
        h = struct.unpack_from("<Q", data, p)[0]
        if i == 0:
            assert h & (1 << 61), "This check requires chunked literals"
            literal_chunk = struct.unpack_from("<Q", data, p + 8)[0]
            totals.append(h & ~((1 << 60) | (1 << 61) | (1 << 62)))
        else:
            totals.append(h & ~(1 << 63))
        p += size
    chunks = [literal_chunk] + [int(config["reader_environment"]["FSE_CHUNK"])] * 3
    for s in samples:
        lo = s["byte_offset"] // block
        hi = (s["byte_offset"] + s["requested_bytes"] - 1) // block
        first = struct.unpack_from("<8Q", data, 68 + lo * 64)
        last = struct.unpack_from("<8Q", data, 68 + hi * 64)
        expected = []
        for i, chunk in enumerate(chunks):
            start, end = first[i], last[i] + last[i + 4]
            value = 0 if (i > 0 and end <= start) else max(0, min(totals[i], ((end - 1) // chunk + 1) * chunk) - (start // chunk) * chunk)
            expected.append(value)
        assert s["stream_decoded_bytes"] == expected, (s["query"], s["stream_decoded_bytes"], expected)
        assert s["decoded_bytes"] == sum(expected)
