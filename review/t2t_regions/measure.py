#!/usr/bin/env python3
"""Measure stored archive bytes on already frozen windows; no timing claims."""
import argparse,hashlib,json,os,platform,re,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser()
for name in ['windows','out','ace','bgzip','seekable','zstd']:p.add_argument('--'+name,required=True,type=Path)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((a.windows/'manifest.json').read_text());env=os.environ.copy()
for k in list(env):
 if k.startswith(('ACEAPEX_','LIT_','FSE_')) or k=='MIN_MATCH':del env[k]
env['ACEAPEX_BS']='16384'
bins={k:str(getattr(a,k).resolve()) for k in ['ace','bgzip','seekable','zstd']}
meta={'schema':'hw-apex-t2t-regional-ratio-v1','date_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'platform':platform.platform(),'binaries':{k:{'path':v,'sha256':sha(Path(v))} for k,v in bins.items()},'window_manifest_sha256':sha(a.windows/'manifest.json'),'ace_environment':{'ACEAPEX_BS':'16384','LIT_CHUNK':None,'FSE_CHUNK':None,'MIN_MATCH':None},'ace_sha':'4915321bf118e564ef3883e58927992c7f9d8dc3','ace_threads':8,'ace_level':2,'bgzip_threads':8,'bgzip_level':6,'bgzip_htslib':'1.19','bgzip_libdeflate':'1.19','zstd':'1.5.7','zstd_level':3,'zstd_frame_bytes':16384,'zstd_threads':1,'timings_published':False}
(a.out/'provenance.json').write_text(json.dumps(meta,indent=2)+'\n')
with (a.out/'results.jsonl').open('x') as results:
 for w in manifest['windows']:
  inp=(a.windows/w['file']).resolve();source=inp.read_bytes();assert sha(inp)==w['input_sha256'] and len(source)==manifest['window_bytes']
  for codec in ['aceapex','bgzip','zstd-seekable']:
   stem=w['file']+'.'+codec;arc=(a.out/(stem+'.archive')).resolve();restored=(a.out/(stem+'.restored')).resolve();log=a.out/(stem+'.log');artifacts=[arc]
   if codec=='aceapex':
    enc=[bins['ace'],'c','--in',str(inp),'--out',str(arc),'--threads','8'];dec=[bins['ace'],'d','--in',str(arc),'--out',str(restored),'--threads','8']
   elif codec=='bgzip':
    idx=Path(str(arc)+'.gzi');artifacts.append(idx);enc=[bins['bgzip'],'-l','6','-@','8','-i','-I',str(idx),'-c',str(inp)];dec=[bins['bgzip'],'-d','-c',str(arc)]
   else:
    produced=Path(str(inp)+'.zst');assert not produced.exists();enc=[bins['seekable'],str(inp),'16384','3'];dec=[bins['zstd'],'-d','-c',str(arc)]
   with log.open('wb') as lf:
    if codec=='bgzip':
     with arc.open('xb') as f:subprocess.run(enc,check=True,env=env,stdout=f,stderr=lf,timeout=600)
    else:subprocess.run(enc,check=True,env=env,stdout=lf,stderr=lf,timeout=600)
    if codec=='zstd-seekable':produced.rename(arc)
    if codec=='aceapex':subprocess.run(dec,check=True,env=env,stdout=lf,stderr=lf,timeout=600)
    else:
     with restored.open('xb') as f:subprocess.run(dec,check=True,env=env,stdout=f,stderr=lf,timeout=600)
   assert restored.read_bytes()==source,'restore mismatch';restored.unlink()
   stored=sum(p.stat().st_size for p in artifacts)
   row={**w,'codec':codec,'input_bytes':len(source),'stored_bytes':stored,'ratio':len(source)/stored,'archive_artifacts':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in artifacts},'encode_command':enc,'decode_command':dec,'verified':'byte-exact','log_sha256':sha(log)}
   if codec=='aceapex':
    # CLI reports only stream payload; complete archive is the primary metric.
    m=re.search(r'Compressed:\s+(\d+) bytes',log.read_text());assert m
    row['cli_stream_bytes']=int(m.group(1));row['cli_stream_ratio']=len(source)/int(m.group(1));row['header_and_block_table_bytes']=stored-int(m.group(1))
   results.write(json.dumps(row,sort_keys=True)+'\n');results.flush()
  print('Verified 3 codecs:',w['chromosome'],w['group'],flush=True)
print('Complete: 90 archives restored byte-exactly',flush=True)
