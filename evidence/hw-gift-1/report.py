"""Usage: python3 report.py samples.jsonl. Refuse incomplete/duplicate evidence."""
import json, sys
from statistics import median
from itertools import product
from pathlib import Path

rows={}
for line in Path(sys.argv[1]).read_text().splitlines():
    r=json.loads(line); k=tuple(r[t] for t in ('src','level','g','n','rep'))
    assert k not in rows
    rows[k]=r
gs=[65536,262144,1048576,4194304,16777216,67108864]
keys=list(product(['enwik8','silesia.tar'],[3,19],gs,[4096,65536]))
assert set(rows)=={(*k,r) for k in keys for r in range(-1,5)}
out={}
for k in keys:
    neg=rows[*k,-1]; assert neg['negative']=='native error'
    size=neg['archive_bytes']; src,level,g,n=k
    base=rows[src,level,gs[-1],n,-1]['archive_bytes']
    per=[]
    for rep in range(5):
        row=rows[*k,rep]; s=row['samples']; assert len(s)==1000
        a,b=[sorted(p[i] for p in s) for i in (1,2)]
        per.append([a[499]/1e6,a[989]/1e6,b[499]/1e6,b[989]/1e6,row['peak_kib']])
    out[k]=[100*(size/base-1),*map(median,zip(*per))]
for src in ['enwik8','silesia.tar']:
    print('\n##',src,'\n\n|level|frame B|read B|size delta %|first p50 ms|first p99 ms|repeat p50 ms|repeat p99 ms|peak RSS KiB|\n|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
    for k,v in out.items():
        if k[0]==src:print('|',' | '.join(map(str,k[1:])), '|',' | '.join(f'{x:.6g}' for x in v),'|')
small=out['enwik8',3,gs[0],4096]; big=out['enwik8',3,gs[-1],4096]
print('\nPrediction:', 'HIT' if big[1]/small[1]>=10 and small[0]<=15 else 'MISS', 'p50 ratio',big[1]/small[1],'size delta %',small[0])
