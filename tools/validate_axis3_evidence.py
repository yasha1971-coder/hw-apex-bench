#!/usr/bin/env python3
"""Validate evidence schema and content hashes; no downloads or measurements."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
from jsonschema import Draft202012Validator

SCHEMA = Path(__file__).resolve().parents[1]/'schemas/axis3-evidence-v1.schema.json'


def loads(text):
    def pairs(items):
        d={}
        for key,value in items:
            if key in d: raise ValueError('duplicate JSON key: '+key)
            d[key]=value
        return d
    def bad_constant(s):raise ValueError('non-finite JSON number: '+s)
    return json.loads(text,object_pairs_hook=pairs,parse_constant=bad_constant)


def digest_file(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def validate_record(data, root: Path):
    schema=loads(SCHEMA.read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(data)
    root=root.resolve()
    refs=[data[k] for k in ('protocol','runbook','corpus_manifest','requests')]+data['raw_logs']
    if data['silence_gate'] is not None: refs.append(data['silence_gate'])
    for ref in refs:
        text=ref['path'];p=PurePosixPath(text)
        if p.is_absolute() or '..' in p.parts or '\\' in text or ':' in text or chr(0) in text:
            raise ValueError('evidence path must be root-relative and traversal-free')
        path=(root/text).resolve(strict=True)
        if not path.is_relative_to(root):raise ValueError('symlink escapes evidence root')
        if not path.is_file() or path.stat().st_size!=ref['bytes']:
            raise ValueError('referenced file size mismatch: '+text)
        if digest_file(path)!=ref['sha256']:
            raise ValueError('referenced SHA-256 mismatch: '+text)
    metrics=data['metrics']
    if metrics:
        if any(isinstance(v,(int,float)) and not math.isfinite(v) for v in metrics.values()):
            raise ValueError('non-finite metric')
        if not metrics['p50_us']<=metrics['p95_us']<=metrics['p99_us']:
            raise ValueError('quantiles are not ordered')
        if not math.isclose(metrics['bytes_per_assembly'],metrics['stored_bytes']/data['n_assemblies'],rel_tol=1e-12):
            raise ValueError('storage accounting inconsistent')
    return data


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('evidence',type=Path);p.add_argument('--root',type=Path,required=True)
    a=p.parse_args()
    try:
        data=validate_record(loads(a.evidence.read_text()),a.root)
    except Exception as exc:
        p.exit(1,f'EVIDENCE_FAILED {type(exc).__name__}: {exc}\n')
    print('EVIDENCE_VALID',data['run_id'],data['status'])
if __name__=='__main__':main()
