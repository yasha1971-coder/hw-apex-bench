#!/usr/bin/env python3
"""Freeze 10 chromosome-matched triplets before encoding; no codec is invoked."""
import argparse, collections, hashlib, json, random
from pathlib import Path
P=argparse.ArgumentParser();P.add_argument('--fasta',type=Path,required=True);P.add_argument('--report',type=Path,required=True);P.add_argument('--censat',type=Path,required=True);P.add_argument('--telomeres',type=Path,required=True);P.add_argument('--out',type=Path,required=True)
a=P.parse_args();a.out.mkdir(parents=True,exist_ok=False)
W=2097152;SEED=20260916;rng=random.Random(SEED)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def merge(xs):
 out=[]
 for l,h in sorted(xs):
  if out and l<=out[-1][1]:out[-1][1]=max(h,out[-1][1])
  else:out.append([l,h])
 return out
mapping={}
for line in a.report.read_text().splitlines():
 if not line.startswith('#'):
  r=line.split('\t');mapping[r[9]]={'accession':r[4],'length':int(r[8])}
hor=collections.defaultdict(list);excluded=collections.defaultdict(list);tel=collections.defaultdict(list)
for line in a.censat.read_text().splitlines():
 r=line.split('\t');interval=(int(r[1]),int(r[2]));assert 0<=interval[0]<interval[1]<=mapping[r[0]]['length']
 excluded[r[0]].append(interval)
 if r[3].startswith('hor_'):hor[r[0]].append(interval)
for line in a.telomeres.read_text().splitlines():
 r=line.split('\t');lo,hi=int(r[1]),int(r[2]);assert 0<=lo<hi<=mapping[r[0]]['length'];tel[r[0]].append((lo,hi))
 excluded[r[0]].append((max(0,lo-W),min(mapping[r[0]]['length'],hi+W)))
# One triplet per chromosome. Eligible autosomes have a >=2 MiB contiguous HOR array.
eligible=[c for c in sorted(hor,key=lambda x:int(x[3:]) if x[3:].isdigit() else 100) if c[3:].isdigit() and any(h-l>=W for l,h in merge(hor[c])) and tel[c]]
chosen=rng.sample(eligible,10);sides=['p']*5+['q']*5;rng.shuffle(sides);windows=[]
for c,side in zip(chosen,sides):
 arrays=[(l,h) for l,h in merge(hor[c]) if h-l>=W];lo,hi=rng.choice(arrays);start=rng.randint(lo,hi-W)
 windows.append({'chromosome':c,'group':'centromeric_HOR','start':start,'end':start+W,'stratum_bounds':[lo,hi]})
 lo,hi=(min(tel[c]) if side=='p' else max(tel[c]));start=0 if side=='p' else mapping[c]['length']-W
 assert start<=lo<hi<=start+W
 windows.append({'chromosome':c,'group':'telomere_context','start':start,'end':start+W,'telomere_interval':[lo,hi],'telomere_fraction':(hi-lo)/W,'arm':side})
 blocks=merge(excluded[c]);gaps=[];pos=0
 for lo,hi in blocks:
  if lo-pos>=W:gaps.append((pos,lo))
  pos=max(pos,hi)
 if mapping[c]['length']-pos>=W:gaps.append((pos,mapping[c]['length']))
 total=sum(hi-lo-W+1 for lo,hi in gaps);pick=rng.randrange(total)
 for lo,hi in gaps:
  n=hi-lo-W+1
  if pick<n:start=lo+pick;break
  pick-=n
 windows.append({'chromosome':c,'group':'annotation_complement','start':start,'end':start+W})
for w in windows:w['accession']=mapping[w['chromosome']]['accession'];w['file']=w['chromosome']+'-'+w['group']+'.seq'
# Record coordinates before sequence extraction or any compression.
manifest={'seed':SEED,'window_bytes':W,'selection':'10 eligible autosomes sampled without replacement; 5 p and 5 q ends; one triplet per chromosome; random valid control start','sequence_representation':'bases only; preserve case, remove FASTA headers and line breaks; no concatenation of distant intervals','source_md5_expected':'cd1e52ce400c027ed0b7ab4b9d613f5a','annotations':{str(p):sha(p) for p in [a.report,a.censat,a.telomeres]},'windows':windows}
(a.out/'selection.json').write_text(json.dumps(manifest,indent=2)+'\n')
md5=hashlib.md5();acc=None;parts=[]
def finish():
 if acc is None:return
 rows=[w for w in windows if w['accession']==acc]
 if not rows:return
 seq=b''.join(parts);assert len(seq)==mapping[rows[0]['chromosome']]['length']
 for w in rows:
  data=seq[w['start']:w['end']];assert len(data)==W and set(data)<=set(b'ACGTacgt')
  (a.out/w['file']).write_bytes(data);w['input_sha256']=hashlib.sha256(data).hexdigest();w['acgt_fraction']=1.0
with a.fasta.open('rb') as f:
 for line in f:
  md5.update(line)
  if line.startswith(b'>'):
   finish();acc=line[1:].split()[0].decode();parts=[]
  elif any(w['accession']==acc for w in windows):parts.append(line.rstrip(b'\r\n'))
finish();assert md5.hexdigest()==manifest['source_md5_expected'];assert all('input_sha256' in w for w in windows)
manifest['source_md5_verified']=md5.hexdigest();(a.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('Frozen and extracted',len(windows),'windows on',chosen,flush=True)
