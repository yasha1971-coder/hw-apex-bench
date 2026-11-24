"""Deterministically retain every repeat attempt without changing its bytes."""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def pack_attempts(source_dir, output_dir):
    source, output = Path(source_dir).resolve(), Path(output_dir).resolve()
    if not source.is_dir() or output.is_relative_to(source):
        raise ValueError('attempt artifact output must be outside the retained source directory')
    entries = sorted(source.rglob('*'), key=lambda p: p.relative_to(source).as_posix())
    if any(p.is_symlink() for p in entries):
        raise ValueError('attempt state contains a symlink')
    files = [p for p in entries if p.is_file()]
    if not files:
        raise ValueError('no retained attempt files')
    output.mkdir(parents=True, exist_ok=True)
    archive = output / 'attempts.tar.gz'
    pending = output / 'attempts.tar.gz.writing'
    records = []
    with pending.open('wb') as stream:
        with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w|') as tar:
                for path in files:
                    if not path.resolve().is_relative_to(source):
                        raise ValueError('retained path escaped its source')
                    data, name = path.read_bytes(), path.relative_to(source).as_posix()
                    records.append(dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
                    member = tarfile.TarInfo(name)
                    member.size, member.mode, member.mtime = len(data), 0o644, 0
                    tar.addfile(member, io.BytesIO(data))
        stream.flush()
        os.fsync(stream.fileno())
    pending.replace(archive)
    manifest = dict(schema='hw-gift-1b-attempts-v1', archive_file=archive.name,
                    archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), files=records)
    temporary = output / 'attempts.json.writing'
    with temporary.open('wb') as stream:
        stream.write(packed(manifest))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(output / 'attempts.json')
    return manifest
