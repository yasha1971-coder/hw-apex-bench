#!/usr/bin/env python3
"""Freeze/verify a run contract. Does not launch codecs, corpora downloads or CI."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


def sha256(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for data in iter(lambda:f.read(1048576),b''):h.update(data)
    return h.hexdigest()


def file_ref(root,path):
    p=Path(path)
    if p.is_absolute() or '..' in p.parts or '\\' in str(path) or ':' in str(path):
        raise ValueError('only corpus-root-relative paths are allowed')
    resolved=(root/p).resolve(strict=True)
    if not resolved.is_relative_to(root.resolve()):raise ValueError('path escapes contract root')
    return dict(path=p.as_posix(),bytes=resolved.stat().st_size,sha256=sha256(resolved))


def freeze(root,inputs,output):
    root=Path(root).resolve()
    if set(inputs)!={'protocol','runbook','corpus_manifest','requests'}:
        raise ValueError('protocol, runbook, corpus manifest and request list are all required')
    lock={'schema':'run-contract-v1','files':{k:file_ref(root,p) for k,p in inputs.items()}}
    encoded=(json.dumps(lock,sort_keys=True,indent=2)+chr(10)).encode()
    output=Path(output)
    if output.exists():
        if output.read_bytes()!=encoded:raise ValueError('frozen contract differs; use a new protocol/run version')
        return lock
    with output.open('xb') as f:f.write(encoded)
    return lock


def verify(root,output):
    data=json.loads(Path(output).read_text())
    if data.get('schema')!='run-contract-v1':raise ValueError('wrong contract schema')
    if set(data['files'])!={'protocol','runbook','corpus_manifest','requests'}:
        raise ValueError('incomplete frozen run contract')
    for role,expected in data['files'].items():
        if file_ref(Path(root).resolve(),expected['path'])!=expected:
            raise ValueError('frozen contract changed: '+role)
    return data


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['freeze','verify'])
    p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    for arg in ('protocol','runbook','corpus-manifest','requests'):p.add_argument('--'+arg)
    a=p.parse_args()
    if a.operation=='freeze':
        inputs={k:getattr(a,k) for k in ('protocol','runbook','corpus_manifest','requests')}
        if any(v is None for v in inputs.values()):p.error('all four input roles are required')
        freeze(a.root,inputs,a.output)
    else:verify(a.root,a.output)
    print('CONTRACT_PASS sha256='+sha256(a.output))
if __name__=='__main__':main()
