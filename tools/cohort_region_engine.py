"""Axis 4: each frozen query group must cover every requested assembly.

The API accepts explicit per-assembly coordinate mappings; it does not pretend
that contig identifiers across HPRC assemblies are automatically homologous.
"""
from __future__ import annotations
import hashlib
import time
from pathlib import Path


def storage_bytes(paths: list[Path]) -> int:
    canonical = [p.resolve(strict=True) for p in paths]
    if len(set(canonical)) != len(canonical):
        raise ValueError('duplicate archive/index/reference storage path')
    if any(not p.is_file() for p in canonical): raise ValueError('storage entry is not a file')
    return sum(p.stat().st_size for p in canonical)


def run_cohort(reader, groups, assemblies, storage_paths, *, clock=time.perf_counter_ns):
    if reader.scope != 'cpu-in-process' or reader.decoder_threads != 1:
        raise ValueError('Axis 4 CPU scope requires one persistent in-process reader')
    if not groups or not assemblies or len(set(assemblies)) != len(assemblies):
        raise ValueError('nonempty distinct cohort and query groups required')
    for group in groups:
        if set(group) != set(assemblies): raise ValueError('query does not cover the full cohort')
        for a, window in group.items():
            if window.assembly != a or window.start < 1 or window.end < window.start:
                raise ValueError('bad explicit assembly/contig coordinate mapping')
    stored=storage_bytes(storage_paths);raw=[]
    for group_id, group in enumerate(groups):
        start=clock()
        for assembly in assemblies:
            w=group[assembly]
            try:
                result=reader.fetch(assembly,w.contig,w.start,w.end)
                actual=hashlib.sha256(result.upper()).hexdigest()
                if len(result)!=w.length or actual!=w.sha256:
                    raise ValueError('cohort answer differs from frozen FASTA truth')
                raw.append(dict(group_id=group_id,assembly=assembly,sha256=actual,
                                requested_bytes=w.length,status='PASS'))
            except Exception as exc:
                raw.append(dict(group_id=group_id,assembly=assembly,status='FAILED',error=str(exc)))
                return dict(axis=4,status='FAILED',seconds=None,stored_bytes=stored,
                            query_groups=len(groups),assemblies=len(assemblies)),raw
        stop=clock()
        if stop<=start: raise ValueError('nonpositive cohort interval')
        raw[-1]['group_wall_ns']=stop-start
    total=sum(r.get('group_wall_ns',0) for r in raw)
    return dict(axis=4,status='PASS',seconds=total/1e9,stored_bytes=stored,
                query_groups=len(groups),assemblies=len(assemblies),
                verified=len(groups)*len(assemblies),
                timing_scope='persistent-reader cohort loop including SHA judge'),raw
