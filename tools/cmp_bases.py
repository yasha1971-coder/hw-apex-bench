#!/usr/bin/env python3
import argparse,hashlib
from pathlib import Path
def bases(path):
    lines=Path(path).read_bytes().splitlines()
    return b"".join(x for x in lines if not x.startswith(b">")).upper()
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--got",required=True);ap.add_argument("--want",required=True);ap.add_argument("--variant",required=True);ap.add_argument("--expected-len",type=int,required=True)
    a=ap.parse_args();got,want=bases(a.got),bases(a.want)
    if got != want:
        n=min(len(got),len(want));off=next((i for i in range(n) if got[i]!=want[i]),n);lo=max(0,off-40);hi=min(max(len(got),len(want)),off+40)
        print(f"variant={a.variant} base_offset={off} got_len={len(got)} want_len={len(want)}")
        print(f"got_sha256={hashlib.sha256(got).hexdigest()} want_sha256={hashlib.sha256(want).hexdigest()}")
        print("got_context="+got[lo:min(hi,len(got))].decode("ascii","replace"))
        print("want_context="+want[lo:min(hi,len(want))].decode("ascii","replace"))
        raise SystemExit(1)
    if len(got)!=a.expected_len: print(f"variant={a.variant} length_error got_len={len(got)} expected_len={a.expected_len}");raise SystemExit(2)
    print(f"PASS variant={a.variant} len={len(got)} sha256={hashlib.sha256(got).hexdigest()}")
if __name__=="__main__": main()
