#!/usr/bin/env python3
"""Recreate the small all-four context proof corpus; no download or timings."""
from pathlib import Path
import random
import sys
r=random.Random(8472)
Path(sys.argv[1]).write_bytes(bytes(r.randrange(256) for _ in range(32771))+
                            b'ACGT'*60000+bytes(range(256))*300)
