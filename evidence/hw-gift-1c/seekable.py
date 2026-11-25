"""Read seekable-zstd tables and frame headers without invoking a codec.

The parser checks byte accounting, entry bounds, magic values and header
structure. Native decoding and seek-table checksum verification are separate
checks performed by the experiment runner.
"""

import hashlib
import struct

FRAME_MAGIC = b'\x28\xb5\x2f\xfd'
SEEK_TABLE_MAGIC = 0x184D2A5E
SEEKABLE_MAGIC = 0x8F92EAB1


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _bytes(data):
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError('expected bytes-like data')
    return bytes(data)


def parse_header(frame: bytes) -> dict:
    """Decode a standard zstd frame header, including an unknown/zero FCS."""
    frame = _bytes(frame)
    _require(len(frame) >= 5 and frame[:4] == FRAME_MAGIC, 'invalid zstd data-frame magic')
    descriptor = frame[4]
    # Bit 3 is reserved. Bit 4 is unused and is intentionally not interpreted.
    _require(not descriptor & 0x08, 'reserved frame-header descriptor bit is set')
    single_segment = bool(descriptor & 0x20)
    checksum_flag = bool(descriptor & 0x04)
    dict_size = (0, 1, 2, 4)[descriptor & 0x03]
    fcs_flag = descriptor >> 6
    fcs_size = (1 if single_segment else 0) if fcs_flag == 0 else (0, 2, 4, 8)[fcs_flag]
    pos = 5
    window_descriptor = None
    window_size = None
    if not single_segment:
        _require(pos < len(frame), 'truncated window descriptor')
        window_descriptor = frame[pos]
        pos += 1
        window_base = 1 << (10 + (window_descriptor >> 3))
        window_size = window_base + (window_base >> 3) * (window_descriptor & 7)
    _require(pos + dict_size + fcs_size <= len(frame), 'truncated dictionary ID or frame content size')
    dict_id = int.from_bytes(frame[pos:pos + dict_size], 'little') if dict_size else 0
    pos += dict_size
    content_size = None
    if fcs_size:
        content_size = int.from_bytes(frame[pos:pos + fcs_size], 'little')
        if fcs_size == 2:
            content_size += 256
        pos += fcs_size
    if single_segment:
        window_size = content_size
    return dict(descriptor=descriptor, window_descriptor=window_descriptor,
                window_size=window_size, content_size=content_size,
                header_size=pos, checksum_flag=checksum_flag, dict_id=dict_id,
                header_hex=frame[:pos].hex())


def parse_archive(data: bytes) -> dict:
    """Parse one seekable archive; preserve original per-frame byte identities."""
    data = _bytes(data)
    _require(len(data) >= 17, 'archive shorter than an empty seek table')
    frame_count, descriptor, magic = struct.unpack_from('<IBI', data, len(data) - 9)
    _require(magic == SEEKABLE_MAGIC, 'invalid seekable footer magic')
    _require(not descriptor & 0x7C, 'reserved seek-table descriptor bits are set')
    checksum_flag = bool(descriptor & 0x80)
    entry_width = 12 if checksum_flag else 8
    seek_table_bytes = 17 + frame_count * entry_width
    _require(seek_table_bytes <= len(data), 'seek table exceeds archive length')
    data_bytes = len(data) - seek_table_bytes
    table_magic, table_size = struct.unpack_from('<II', data, data_bytes)
    _require(table_magic == SEEK_TABLE_MAGIC, 'invalid seek-table skippable-frame magic')
    _require(table_size == seek_table_bytes - 8, 'seek-table size field disagrees with footer')
    frames = []
    offset = 0
    for index in range(frame_count):
        entry = data_bytes + 8 + index * entry_width
        compressed, decompressed = struct.unpack_from('<II', data, entry)
        _require(compressed > 0 and decompressed > 0, 'seek table contains a nonpositive frame size')
        _require(offset + compressed <= data_bytes, 'data frame extends into seek table')
        raw_frame = data[offset:offset + compressed]
        header = parse_header(raw_frame)
        checksum = struct.unpack_from('<I', data, entry + 8)[0] if checksum_flag else None
        frames.append(dict(index=index, offset=offset, compressed_bytes=compressed,
                           decompressed_bytes=decompressed, checksum=checksum,
                           sha256=hashlib.sha256(raw_frame).hexdigest(), header=header))
        offset += compressed
    _require(offset == data_bytes, 'compressed frame sizes do not account for all data bytes')
    return dict(frame_count=frame_count, checksum_flag=checksum_flag,
                seek_table_bytes=seek_table_bytes, data_bytes=data_bytes, frames=frames,
                table_header_hex=data[data_bytes:data_bytes + 8].hex(),
                footer_hex=data[-9:].hex())


def rewrite_table(data: bytes, checksum_flag: bool, checksums=None) -> bytes:
    """Rebuild only the seek table; every original data-frame byte is retained.

    Enabling checksums on a table that lacks them requires one externally
    computed uint32 checksum per frame. Existing checksums may be reused when
    the input table already carries them; this function does not compute XXH64.
    """
    data = _bytes(data)
    if type(checksum_flag) is not bool:
        raise TypeError('checksum_flag must be bool')
    parsed = parse_archive(data)
    if checksum_flag:
        if checksums is None:
            _require(parsed['checksum_flag'], 'computed checksums required when enabling seek-table checksums')
            checksums = [frame['checksum'] for frame in parsed['frames']]
        else:
            checksums = list(checksums)
        _require(len(checksums) == parsed['frame_count'] and
                 all(type(value) is int and 0 <= value <= 0xFFFFFFFF for value in checksums),
                 'expected one uint32 checksum per frame')
    entries = []
    for index, frame in enumerate(parsed['frames']):
        entry = struct.pack('<II', frame['compressed_bytes'], frame['decompressed_bytes'])
        if checksum_flag:
            entry += struct.pack('<I', checksums[index])
        entries.append(entry)
    # Preserve the original unused descriptor bits 1..0 when changing only the
    # optional checksum field. Reserved bits were already rejected by parsing.
    descriptor = (data[-5] & 0x03) | (0x80 if checksum_flag else 0)
    footer = struct.pack('<IBI', parsed['frame_count'], descriptor, SEEKABLE_MAGIC)
    table_body = b''.join(entries) + footer
    table = struct.pack('<II', SEEK_TABLE_MAGIC, len(table_body)) + table_body
    return data[:parsed['data_bytes']] + table
