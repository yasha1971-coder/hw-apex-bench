#!/usr/bin/env python3
"""Untimed shell region operation using a native resident context."""
from pathlib import Path
import sys
from resident_probe import Context
library,archive,offset,length,output,sidecar=sys.argv[1:]
offset,length=int(offset),int(length)
if not (0<=offset<1<<64 and 0<=length<=1<<30):
    raise SystemExit('invalid range or shell operation buffer limit (1 GiB)')
ctx=Context(library,Path(archive).read_bytes(),sidecar=sidecar or None)
try:
    n,data=ctx.region(offset,length)
    if n!=length: raise SystemExit('native region failed')
    Path(output).write_bytes(data)
finally:
    ctx.close()
