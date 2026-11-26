# Copyright 2026 yasha1971-coder
# SPDX-License-Identifier: Apache-2.0
"""Original, one-sequence standard .2bit writer and structural reference check.

No Kent/UCSC code or binaries, native libraries, subprocesses or clocks.
N blocks include N/n; soft-mask blocks independently include a/c/g/t/n.
Their overlap preserves lowercase n in the file, without changing lib2bit.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = ROOT / '.work/hw-region-2'
MAGIC = 0x1A412743
ALPHABET = b'ACGTNacgtn'
PACK_CODES = bytes({ord('T'): 0, ord('C'): 1, ord('A'): 2, ord('G'): 3,
                    ord('t'): 0, ord('c'): 1, ord('a'): 2, ord('g'): 3,
                    ord('N'): 0, ord('n'): 0}.get(i, 255) for i in range(256))


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def packed_json(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def parse_fasta(path):
    """Preserve every base byte and validate the single-record .fai geometry."""
    path = Path(path)
    sequence = bytearray()
    source_hash = hashlib.sha256()
    with path.open('rb') as stream:
        header = stream.readline()
        source_hash.update(header)
        require(header.startswith(b'>') and header.endswith(b'\n'), 'one FASTA header with a line terminator required')
        name_bytes = header[1:].rstrip(b'\r\n').split(None, 1)[0]
        require(0 < len(name_bytes) <= 255, '2bit sequence name must contain 1..255 bytes')
        name = name_bytes.decode('ascii')
        require(all(33 <= c <= 126 for c in name_bytes), 'sequence name must be printable non-whitespace ASCII')
        offset = len(header)
        line_bases = line_width = None
        previous = None
        for line in stream:
            source_hash.update(line)
            require(not line.startswith(b'>'), 'only one chromosome is supported')
            if previous is not None:
                require(previous == (line_bases, line_width), 'non-final FASTA lines must have identical .fai geometry')
            body = line[:-1] if line.endswith(b'\n') else line
            if line.endswith(b'\r\n'):
                body = body[:-1]
            require(body, 'empty FASTA sequence line')
            invalid = re.search(b'[^ACGTNacgtn]', body)
            require(invalid is None, 'unsupported base at coordinate ' + str(len(sequence) + (invalid.start() if invalid else 0)))
            if line_bases is None:
                line_bases, line_width = len(body), len(line)
            require(len(body) <= line_bases, 'FASTA line exceeds first line width')
            sequence.extend(body)
            previous = len(body), len(line)
    require(sequence and len(sequence) < 1 << 32, '2bit version0 needs a nonempty sequence shorter than 2^32 bases')
    fai = dict(name=name, length=len(sequence), offset=offset, line_bases=line_bases, line_width=line_width)
    return sequence, fai, dict(path=str(path.resolve()), bytes=path.stat().st_size, sha256=source_hash.hexdigest())


def fai_text(fai):
    return ('\t'.join(str(fai[key]) for key in ('name', 'length', 'offset', 'line_bases', 'line_width')) + '\n').encode('ascii')


def reference_fetch(path, fai, start, length):
    """FAI byte-span extraction, with only CR/LF removed and case unchanged."""
    require(type(start) is int and type(length) is int and 0 <= start <= fai['length'] and 0 <= length <= fai['length'] - start,
            'reference interval outside sequence')
    if length == 0:
        return b''
    def at(base):
        return fai['offset'] + (base // fai['line_bases']) * fai['line_width'] + base % fai['line_bases']
    begin, end = at(start), at(start + length - 1) + 1
    with Path(path).open('rb') as stream:
        stream.seek(begin)
        result = stream.read(end - begin).replace(b'\r', b'').replace(b'\n', b'')
    require(len(result) == length, 'FAI reference span returned the wrong number of bases')
    return result


def runs(sequence, pattern):
    return [(match.start(), match.end() - match.start()) for match in re.finditer(pattern, sequence)]


def u32_array(values, endian):
    require(all(type(v) is int and 0 <= v < 1 << 32 for v in values), '2bit uint32 overflow')
    return struct.pack(endian + str(len(values)) + 'I', *values) if values else b''


def pack_bases(sequence):
    """TCAG=0,1,2,3; four bases per byte, most significant pair first."""
    require(re.search(b'[^ACGTNacgtn]', sequence) is None, 'unsupported base; no normalization is permitted')
    result = bytearray()
    for begin in range(0, len(sequence), 1 << 22):
        codes = bytes(sequence[begin:begin + (1 << 22)]).translate(PACK_CODES)
        codes += b'\0' * (-len(codes) % 4)
        result.extend((a << 6) | (b << 4) | (c << 2) | d
                      for a, b, c, d in zip(codes[0::4], codes[1::4], codes[2::4], codes[3::4]))
    return bytes(result)


def encode_twobit(name, sequence, endian='<'):
    """Original format implementation; default little-endian fits pinned lib2bit."""
    name_bytes = name.encode('ascii')
    require(endian in ('<', '>') and 0 < len(name_bytes) <= 255 and 0 < len(sequence) < 1 << 32, 'invalid one-chromosome 2bit input')
    n_blocks = runs(sequence, b'[Nn]+')
    mask_blocks = runs(sequence, b'[acgtn]+')
    bases = pack_bases(sequence)
    record_offset = 16 + 1 + len(name_bytes) + 4
    header = struct.pack(endian + '4I', MAGIC, 0, 1, 0)
    index = bytes([len(name_bytes)]) + name_bytes + struct.pack(endian + 'I', record_offset)
    record = (struct.pack(endian + '2I', len(sequence), len(n_blocks))
              + u32_array([start for start, size in n_blocks], endian) + u32_array([size for start, size in n_blocks], endian)
              + struct.pack(endian + 'I', len(mask_blocks))
              + u32_array([start for start, size in mask_blocks], endian) + u32_array([size for start, size in mask_blocks], endian)
              + struct.pack(endian + 'I', 0))
    value = header + index + record + bases
    return value, dict(name=name, length=len(sequence), endianness='little' if endian == '<' else 'big', version=0,
                      record_offset=record_offset, packed_bases_offset=record_offset + len(record), packed_bases_bytes=len(bases),
                      packed_bases_sha256=digest(bases), n_blocks=[list(row) for row in n_blocks], mask_blocks=[list(row) for row in mask_blocks])


def decode_twobit(raw, store_masked=True):
    """Independent structural decoder: N first, then lowercase ALL mask bases.

    This follows .2bit information semantics, including N/mask overlap. It is
    deliberately not lib2bit and does not change the library's behavior.
    """
    require(len(raw) >= 16, 'truncated 2bit header')
    if struct.unpack_from('<I', raw)[0] == MAGIC:
        endian = '<'
    elif struct.unpack_from('>I', raw)[0] == MAGIC:
        endian = '>'
    else:
        raise ValueError('bad 2bit signature')
    magic, version, count, reserved = struct.unpack_from(endian + '4I', raw)
    require(version == 0 and count == 1 and reserved == 0, 'structural checker supports exactly one version0 chromosome')
    position = 16
    name_length = raw[position]
    position += 1
    require(name_length > 0 and position + name_length + 4 <= len(raw), 'truncated 2bit index')
    name = raw[position:position + name_length].decode('ascii')
    position += name_length
    record_offset = struct.unpack_from(endian + 'I', raw, position)[0]
    require(position + 4 <= record_offset <= len(raw) - 16, 'invalid sequence record offset')
    position = record_offset
    def read_values(number):
        nonlocal position
        require(type(number) is int and number >= 0 and number <= (len(raw) - position) // 4, 'truncated 2bit uint32 array')
        result = list(struct.unpack_from(endian + str(number) + 'I', raw, position)) if number else []
        position += 4 * number
        return result
    length, n_count = read_values(2)
    n_starts, n_sizes = read_values(n_count), read_values(n_count)
    mask_count = read_values(1)[0]
    mask_starts, mask_sizes = read_values(mask_count), read_values(mask_count)
    require(read_values(1) == [0] and length > 0 and len(raw) - position == (length + 3) // 4, '2bit reserved field or packed extent differs')
    for starts, sizes in ((n_starts, n_sizes), (mask_starts, mask_sizes)):
        end = 0
        for start, size in zip(starts, sizes):
            require(size > 0 and end <= start <= length and size <= length - start, 'unsorted/overlapping/out-of-bounds interval table')
            end = start + size
    payload = memoryview(raw)[position:]
    if length % 4:
        require((payload[-1] & ((1 << (2 * (4 - length % 4))) - 1)) == 0, 'nonzero padding base bits')
    alphabet = b'TCAG'
    # This byte expansion is independent of pack_bases and its translation map.
    expansion = [bytes(alphabet[(word >> shift) & 3] for shift in (6, 4, 2, 0)) for word in range(256)]
    output = bytearray()
    for begin in range(0, len(payload), 1 << 20):
        output.extend(b''.join(expansion[word] for word in payload[begin:begin + (1 << 20)]))
    del output[length:]
    for start, size in zip(n_starts, n_sizes):
        output[start:start + size] = b'N' * size
    if store_masked:
        for start, size in zip(mask_starts, mask_sizes):
            output[start:start + size] = output[start:start + size].lower()
    return bytes(output), dict(name=name, length=length, endianness='little' if endian == '<' else 'big',
                               n_blocks=[list(row) for row in zip(n_starts, n_sizes)], mask_blocks=[list(row) for row in zip(mask_starts, mask_sizes)])


def self_test():
    sequence = b'TCAGtcagNNnnACTG'
    data, table = encode_twobit('fixture', sequence)
    expected_packed = bytes.fromhex('1b1b0093')
    require(data[table['packed_bases_offset']:] == expected_packed and table['n_blocks'] == [[8, 4]]
            and table['mask_blocks'] == [[4, 4], [10, 2]], 'known packed/N/mask fixture failed')
    restored, parsed = decode_twobit(data)
    require(restored == sequence and parsed['n_blocks'] == table['n_blocks'] and parsed['mask_blocks'] == table['mask_blocks'], 'known case-preserving roundtrip failed')
    upper, ignored = decode_twobit(data, store_masked=False)
    require(upper == sequence.upper(), 'known case-folded structural reference failed')
    big, ignored = encode_twobit('fixture', sequence, endian='>')
    require(decode_twobit(big)[0] == sequence, 'independent big-endian structural reader failed')
    for short in (b'A', b'AC', b'ACG', b'n', b'NNnn', b'acgtnACGTN'):
        raw, ignored = encode_twobit('short', short)
        require(decode_twobit(raw)[0] == short, 'partial-byte/mask/N control failed')
    return dict(status='PASS', source='invented correctness fixture only, not benchmark evidence',
                sequence_ascii=sequence.decode('ascii'), packed_hex=expected_packed.hex(), n_blocks=[[8, 4]],
                mask_blocks=[[4, 4], [10, 2]], case_preserving_roundtrip=True, clocks=0, native_calls=0)


def immutable(path, raw):
    path = Path(path)
    if path.exists():
        require(path.read_bytes() == raw, 'refuse to overwrite differing writer artifact: ' + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def write_fasta(fasta, outputdir, expected_source_sha=None, expected_sequence_sha=None):
    outputdir = Path(outputdir).resolve()
    require(outputdir.is_relative_to(STATE.resolve()), 'writer artifacts must stay in owned .work/hw-region-2')
    fixture = self_test()
    sequence, fai, source = parse_fasta(fasta)
    sequence_sha = digest(sequence)
    if expected_source_sha is not None:
        require(source['sha256'] == expected_source_sha, 'original FASTA source SHA differs')
    if expected_sequence_sha is not None:
        require(sequence_sha == expected_sequence_sha, 'case-preserved sequence SHA differs')
    data, tables = encode_twobit(fai['name'], sequence, endian='<')
    restored, parsed = decode_twobit(data, store_masked=True)
    require(parsed['name'] == fai['name'] and parsed['length'] == fai['length'] and restored == sequence,
            'writer structural roundtrip differs from original sequence')
    alphabet = {chr(key): value for key, value in sorted(Counter(sequence).items())}
    first_n = sequence.find(b'n')
    sequence_record = dict(path=str(outputdir / 'seq.bin'), bytes=len(sequence), sha256=sequence_sha,
                           alphabet=alphabet, lowercase_n_count=alphabet.get('n', 0), first_lowercase_n=None if first_n < 0 else first_n)
    fai_bytes = fai_text(fai)
    index_record = dict(path=str(outputdir / 'source.fai'), bytes=len(fai_bytes), sha256=digest(fai_bytes), geometry=fai)
    archive_record = dict(path=str(outputdir / 'sequence.2bit'), bytes=len(data), sha256=digest(data), **tables)
    metadata = dict(schema='hw-region-2-original-writer-v1', status='PASS', implementation='original repository implementation; no Kent/UCSC code',
                    license='Apache-2.0', license_sha256=sha(ROOT / 'LICENSE'), source_sha256=sha(__file__),
                    clocks=0, measurements_of_time=False, native_calls=0, source_fasta=source, sequence=sequence_record,
                    fai=index_record, archive=archive_record, known_fixture=fixture,
                    structural_check=dict(status='PASS', case_preserved=True, sha256=digest(restored),
                        method='independent structural parser; base expansion, then N intervals, then all lowercase mask intervals including overlapping n',
                        lib2bit_invoked=False))
    # Finish all structural checks before publishing any output.
    immutable(outputdir / 'seq.bin', sequence)
    immutable(outputdir / 'source.fai', fai_bytes)
    immutable(outputdir / 'sequence.2bit', data)
    immutable(outputdir / 'metadata.json', packed_json(metadata))
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--self-test', action='store_true')
    mode.add_argument('--fasta', type=Path)
    parser.add_argument('--outputdir', type=Path)
    parser.add_argument('--expected-source-sha')
    parser.add_argument('--expected-sequence-sha')
    args = parser.parse_args()
    if args.self_test:
        result = self_test()
    else:
        require(args.outputdir is not None, '--outputdir is required for --fasta')
        result = write_fasta(args.fasta, args.outputdir, args.expected_source_sha, args.expected_sequence_sha)
    print(packed_json(result).decode(), end='')


if __name__ == '__main__':
    main()
