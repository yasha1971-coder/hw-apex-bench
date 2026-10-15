#!/usr/bin/env python3
"""Deterministic streaming Q3 input generator; never runs on import."""
import argparse
from pathlib import Path
BASES=1_718_000_000
CHUNK=b'ACGT'*(1024*1024//4)
def generate(path, bases=BASES):
    if bases<=0 or bases%4: raise ValueError('bases must be a positive multiple of four')
    path=Path(path)
    if path.exists(): raise FileExistsError(path)
    with path.open('xb') as f:
        f.write(b'>q3_synthetic\n')
        remaining=bases
        while remaining:
            n=min(len(CHUNK),remaining)
            f.write(CHUNK[:n]);f.write(b'\n');remaining-=n
    return path.stat().st_size
if __name__=='__main__':
    p=argparse.ArgumentParser();sp=p.add_subparsers(dest='cmd',required=True)
    g=sp.add_parser('generate');g.add_argument('--output',required=True)
    a=p.parse_args()
    if a.cmd=='generate':print(generate(a.output))
