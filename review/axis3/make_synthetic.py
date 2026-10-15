#!/usr/bin/env python3
import random,sys
from pathlib import Path
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True); rng=random.Random(20261003)
ref="".join(rng.choice("ACGT") for _ in range(1024*1024))
for j in range(3):
 s=list(ref)
 for i in range(1000+j*137):
  p=(i*1009+j*7919)%len(s);s[p]="ACGT"[("ACGT".index(s[p])+j+1)%4]
 seq="".join(s); p=out/f"asm{j+1}.fa"
 with p.open("w") as f:
  f.write(f">asm{j+1}\n"); f.write("\n".join(seq[i:i+80] for i in range(0,len(seq),80))+"\n")
