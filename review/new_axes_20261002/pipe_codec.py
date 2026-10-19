#!/usr/bin/env python3
import subprocess,sys
def main():
    if len(sys.argv)<4: raise SystemExit("usage: pipe_codec.py OUTPUT COMMAND...")
    out=sys.argv[1]; cmd=sys.argv[2:]
    with open(out,"wb") as fh:
        subprocess.run(cmd,stdout=fh,check=True)
if __name__=="__main__": main()
