#!/usr/bin/env python3
import os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BIN=ROOT/".work/axes-20261002/ace"
def main():
    if len(sys.argv)!=5: raise SystemExit("usage: ace_cpu_adapter.py compress|decompress xxh3|no-xxh3 INPUT OUTPUT")
    op,mode,inp,out=sys.argv[1:]
    exe=BIN/("aceapex-xxh3" if mode=="xxh3" else "aceapex-no-xxh3")
    env=os.environ.copy(); env["AX_PROFILE"]="open"
    if op=="compress":
        subprocess.run([exe,"c","--in",inp,"--out",out,"--threads","1","--level","2"],env=env,check=True)
        if mode=="no-xxh3":
            p=Path(out); b=bytearray(p.read_bytes())
            if len(b)<36: raise SystemExit("ACE archive too short")
            b[28:36]=bytes(8); p.write_bytes(b)
    elif op=="decompress":
        subprocess.run([exe,"d","--in",inp,"--out",out],env=env,check=True)
    else: raise SystemExit("unknown operation")
if __name__=="__main__": main()
