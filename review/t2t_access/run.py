#!/usr/bin/env python3
"""Measure only retained archives, using the unchanged native resident worker."""
import argparse, ctypes as C, hashlib, json, math, os, platform, random, statistics, subprocess, sys, time, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'harness'))
from resident_probe import Context
sha=lambda b:hashlib.sha256(b).hexdigest()
def rows(p):return [json.loads(s) for s in p.read_text().splitlines()]
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--libraries',type=Path,required=True);ap.add_argument('--sweep-bundle',type=Path,required=True);ap.add_argument('--pilot-bundle',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();o=a.out.resolve();o.mkdir(exist_ok=False);(o/'inputs').mkdir();(o/'archives').mkdir();(o/'raw').mkdir();libs=a.libraries.resolve()
 start=time.time();allowed=sorted(os.sched_getaffinity(0));cpu=allowed[0];os.sched_setaffinity(0,{cpu})
 env={k:v for k,v in os.environ.items() if not k.startswith(('ACEAPEX_','HB_','LIT_','FSE_')) and k not in {'MIN_MATCH','HASH_LOG','OMP_NUM_THREADS','XZ_OPT','XZ_DEFAULTS'}}
 manifest=json.loads((ROOT/'evidence/t2t-regions-20260916/manifest.json').read_text());sweep=rows(ROOT/'evidence/t2t-granularity-20260916/results.jsonl');pilot=rows(ROOT/'evidence/t2t-regions-20260916/results.jsonl');configs=[]
 receipt=json.loads((ROOT/'evidence/t2t-granularity-20260916/archive-bundle.json').read_text());assert sha(a.sweep_bundle.read_bytes())==receipt['sha256']
 with zipfile.ZipFile(a.sweep_bundle) as z:
  for w in manifest['windows']:
   b=z.read('windows/'+w['file']);assert len(b)==2097152 and sha(b)==w['input_sha256'];(o/'inputs'/w['file']).write_bytes(b)
  for r in sweep:
   b=z.read('measurement/'+r['archive']);assert sha(b)==r['archive_sha256'] and len(b)==r['stored_bytes'];(o/'archives'/r['archive']).write_bytes(b);configs.append(dict(r,sidecar='',library_codec='aceapex' if r['codec']=='aceapex' else 'zstd_seekable'))
 with zipfile.ZipFile(a.pilot_bundle) as z:
  for r in pilot:
   if r['codec']!='bgzip':continue
   for name,info in r['archive_artifacts'].items():
    b=z.read('measurement/'+name);assert sha(b)==info['sha256'] and len(b)==info['bytes'];(o/'archives'/name).write_bytes(b)
   name=next(n for n in r['archive_artifacts'] if not n.endswith('.gzi'))
   configs.append(dict(r,archive=name,archive_sha256=r['archive_artifacts'][name]['sha256'],granularity=65280,sidecar=str(o/'archives'/(name+'.gzi')),library_codec='bgzip'))
 assert len(configs)==330
 hardware={'platform':platform.platform(),'cpuinfo':Path('/proc/cpuinfo').read_text(),'meminfo':Path('/proc/meminfo').read_text(),'affinity_available':allowed,'timed_cpu':cpu,'lscpu':subprocess.check_output(['lscpu'],text=True),'cgroup_memory_max':Path('/sys/fs/cgroup/memory.max').read_text() if Path('/sys/fs/cgroup/memory.max').exists() else 'unavailable'}
 dump(o/'host.json',hardware)
 prov={'schema':'hwb-t2t-access-v1','benchmark_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'protocol_sha256':sha((Path(__file__).with_name('PROTOCOL.md')).read_bytes()),'script_sha256':sha(Path(__file__).read_bytes()),'build':json.loads((libs/'build-receipt.json').read_text()),'worker_sha256':sha((libs/'native_measure').read_bytes()),'n_configs':330,'n_timing_passes':3,'n_samples_per_pass':200,'query_length':16384,'warmups':12,'timings_level':'declared','amplification_scope':'native entropy/block decoder output, not memory traffic or LZ reference reach','environment_removed':sorted(set(os.environ)-set(env)),'host_file':'host.json','full_source_gzip_checked':False,'toolchain':{c:subprocess.check_output([c,'--version'],text=True).splitlines()[0] for c in ['gcc','g++','ld']}}
 dump(o/'provenance.json',prov)
 # Gate all archives before any timing: ordinary and counter readers, full bytes and boundaries.
 for i,r in enumerate(configs):
  raw=(o/'inputs'/r['file']).read_bytes();arc=(o/'archives'/r['archive']).read_bytes();g=r['granularity']
  probes={(0,16384),(len(raw)-16384,16384),(0,len(raw)),(0,1),(g//2,1)}
  for b in [g,2*g,len(raw)//2]:
   if b<len(raw):probes.add((max(0,b-8192),min(16384,len(raw)-max(0,b-8192))))
  for variant in ['context.so','counter-context.so']:
   ctx=Context(libs/r['library_codec']/variant,arc,len(raw),r['sidecar'] or None)
   try:
    if variant=='context.so':
     buf=C.create_string_buffer(len(raw));assert ctx.lib.hc_decode(ctx.ptr,buf,len(raw))==len(raw) and buf.raw==raw
    for off,n in probes:
     got,data=ctx.region(off,n);assert got==n and data==raw[off:off+n],(i,variant,off,n)
   finally:ctx.close()
  if (i+1)%60==0:print('Qualified',i+1,'archives',flush=True)
 dump(o/'qualification.json',{'archives':330,'ordinary_full_restores':330,'ordinary_and_counter_boundary_checks':'byte-exact','before_timing':True})
 results=[]
 for pass_id in range(3):
  order=list(range(330));random.Random(20260918+pass_id).shuffle(order)
  for j,i in enumerate(order):
   r=configs[i];base=f'{i:03d}.pass{pass_id}';cmd=[str(libs/'native_measure'),str(libs/r['library_codec']/'context.so'),str(o/'archives'/r['archive']),str(o/'inputs'/r['file']),'region',r['sidecar']]
   p=o/'raw'/(base+'.jsonl');log=o/'raw'/(base+'.log')
   with p.open('x') as out,log.open('x') as err:subprocess.run(cmd,stdout=out,stderr=err,env=env,check=True,timeout=180)
   samples=rows(p);assert len(samples)==200 and all(s['verified'] and s['requested_bytes']==16384 and math.isfinite(s['latency_ms']) and s['latency_ms']>=0 for s in samples)
   results.append({'config':i,'pass':pass_id,'raw':str(p.relative_to(o)),'sha256':sha(p.read_bytes()),'command':cmd})
   if (j+1)%100==0:print('Timing pass',pass_id+1,j+1,'/330',flush=True)
 counts=[]
 for i,r in enumerate(configs):
  p=o/'raw'/f'{i:03d}.counts.jsonl';log=o/'raw'/f'{i:03d}.counts.log';cmd=[str(libs/'native_measure'),str(libs/r['library_codec']/'counter-context.so'),str(o/'archives'/r['archive']),str(o/'inputs'/r['file']),'amplification',r['sidecar']]
  with p.open('x') as out,log.open('x') as err:subprocess.run(cmd,stdout=out,stderr=err,env=env,check=True,timeout=180)
  ss=rows(p);assert len(ss)==200 and all(s['verified'] and s['decoded_bytes']>=0 for s in ss)
  timed=rows(o/'raw'/f'{i:03d}.pass0.jsonl');assert [s['byte_offset'] for s in ss]==[s['byte_offset'] for s in timed]
  counts.append({'config':i,'raw':str(p.relative_to(o)),'sha256':sha(p.read_bytes()),'command':cmd})
  if (i+1)%100==0:print('Counting',i+1,'/330',flush=True)
 dump(o/'configurations.json',configs);dump(o/'timing-index.json',results);dump(o/'counter-index.json',counts)
 dump(o/'completion.json',{'completed':True,'archives':330,'timed_queries':198000,'counted_queries':66000,'elapsed_seconds':round(time.time()-start,3),'all_byte_exact':True,'historical_results_sha256':sha((ROOT/'results.jsonl').read_bytes())})
 print('PASS: complete retained-archive access sweep',flush=True)
if __name__=='__main__':main()
