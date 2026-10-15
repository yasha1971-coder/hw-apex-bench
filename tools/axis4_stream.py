"""Bounded FASTA framing and prepare-only window hashing; never writes FASTA."""
from contextlib import contextmanager
import gzip
import hashlib
from pathlib import Path
import zlib

CHUNK = 65536
HEADER_LIMIT = 4096


@contextmanager
def source_stream(path):
    """gzip accepts concatenated members and BGZF; consume EOF to check trailers."""
    path = Path(path)
    with path.open('rb') as raw:
        magic = raw.read(2)
        raw.seek(0)
        compressed = path.suffix.lower() in ('.gz', '.bgz', '.bgzf') or magic == b'\x1f\x8b'
        stream = gzip.GzipFile(fileobj=raw, mode='rb') if compressed else raw
        try:
            yield stream, 'gzip' if compressed else 'plain'
        except (OSError, EOFError, zlib.error) as exc:
            raise ValueError('invalid or truncated gzip/FASTA stream: '+str(exc)) from exc
        finally:
            if compressed:
                stream.close()


def segments(stream, raw_hash, counter):
    """Yield bounded sequence pieces, even for a chromosome on one huge line.

    Only headers are accumulated, with a declared strict 4096-byte maximum.
    Header fragments, CRLF across chunk boundaries and final missing LF work.
    Hash every original decompressed byte before FASTA normalization.
    """
    start = True
    pending_cr = b''
    while True:
        raw = stream.readline(CHUNK)
        if not raw:
            break
        raw_hash.update(raw)
        counter[0] += len(raw)
        if start and raw.startswith(b'>'):
            header = raw
            while not header.endswith(b'\n'):
                if len(header) > HEADER_LIMIT:
                    raise ValueError('FASTA header exceeds 4096 bytes')
                part = stream.readline(CHUNK)
                if not part:
                    break
                raw_hash.update(part)
                counter[0] += len(part)
                header += part
            if len(header) > HEADER_LIMIT:
                raise ValueError('FASTA header exceeds 4096 bytes')
            words = header[1:].split()
            if not words:
                raise ValueError('empty FASTA contig')
            yield 'header', words[0].decode('utf-8')
            start = True
            continue
        ended = raw.endswith(b'\n')
        data = pending_cr+raw
        pending_cr = b''
        if ended:
            data = data[:-1]
            if data.endswith(b'\r'):
                data = data[:-1]
        elif data.endswith(b'\r'):
            data, pending_cr = data[:-1], b'\r'
        if (start and not data) or any(c in data for c in (b' ', b'\t', b'>', b'\r', b'\n')):
            raise ValueError('malformed FASTA sequence')
        if data:
            yield 'sequence', data.upper()
        start = ended


def prepare_truth(path, queries):
    """Sweep sorted windows. Retain hashes, lengths and contig metadata only."""
    pending = {}
    hashes, lengths = {}, {}
    for rid, q in queries:
        if type(q['start0']) is not int or type(q['end0']) is not int or not 0 <= q['start0'] < q['end0']:
            raise ValueError('invalid truth window')
        if rid in hashes:
            raise ValueError('duplicate truth request id')
        pending.setdefault(q['contig_id'], []).append((q['start0'], q['end0'], rid))
        hashes[rid], lengths[rid] = hashlib.sha256(), 0
    for rows in pending.values():
        rows.sort()
    raw_hash, canonical = hashlib.sha256(), hashlib.sha256()
    raw_bytes, total, contigs, seen = [0], 0, [], set()
    current, offset, cursor, todo, active = None, 0, 0, [], []
    with source_stream(path) as (stream, encoding):
        for kind, value in segments(stream, raw_hash, raw_bytes):
            if kind == 'header':
                if value in seen:
                    raise ValueError('duplicate FASTA contig')
                seen.add(value)
                contigs.append({'contig_id': value, 'length': 0})
                current, offset, cursor, todo, active = value, 0, 0, pending.get(value, []), []
                continue
            if current is None:
                raise ValueError('FASTA sequence before header')
            canonical.update(value)
            total += len(value)
            contigs[-1]['length'] += len(value)
            end = offset+len(value)
            while cursor < len(todo) and todo[cursor][0] < end:
                active.append(todo[cursor])
                cursor += 1
            remaining = []
            for start, stop, rid in active:
                piece = value[max(start, offset)-offset:min(stop, end)-offset]
                hashes[rid].update(piece)
                lengths[rid] += len(piece)
                if stop > end:
                    remaining.append((start, stop, rid))
            active, offset = remaining, end
    if not contigs:
        raise ValueError('assembly has no FASTA records')
    for rid, q in queries:
        if lengths[rid] != q['end0']-q['start0']:
            raise ValueError('truth request outside FASTA')
    return {'contigs': contigs, 'canonical_bytes': total, 'canonical_sha256': canonical.hexdigest(),
            'truth': {'encoding': encoding, 'uncompressed_bytes': raw_bytes[0],
                      'uncompressed_sha256': raw_hash.hexdigest(), 'chunk_bytes': CHUNK}}, {
            rid: digest.hexdigest() for rid, digest in hashes.items()}
