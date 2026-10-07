#!/usr/bin/env python3
"""Axis 5 worker: one decoder invocation, machine-readable outcome boundary."""
import argparse,json
from pathlib import Path
from tools.application_corruption import decode_once,sha256

def main():
 p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--truth',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--timeout',type=float,default=10);p.add_argument('decoder',nargs='+');a=p.parse_args()
 r=decode_once(a.decoder,a.archive,a.output,truth_sha256=sha256(a.truth),truth_bytes=a.truth.stat().st_size,timeout=a.timeout)
 print(json.dumps(r,sort_keys=True))
if __name__=='__main__':main()
