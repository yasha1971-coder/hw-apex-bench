"""Export the instrument-style homepage from one verified JSONL run."""
import hashlib,json,pathlib,sys
from validate_publication import validate
R=pathlib.Path(__file__).resolve().parents[1]
rows=validate(R)
cs=['bgzip+htslib','zstd-seekable','aceapex-interactive','aceapex-dense']
core_rows=[r for r in rows if r['codec'] in cs]
assert len({r['run_id'] for r in core_rows})==1
def one(c,m,**kw):
 a=[r for r in rows if r['codec']==c and r['metric']==m and all(r.get(k)==v for k,v in kw.items())]
 assert len(a)==1,(c,m,kw)
 return a[0]
F=[]
for c in cs:
 core={m:one(c,m)['value'] for m in ['ratio','region_p50','region_p99','amplification','break_even_n']}
 core.update(codec=c,configuration=one(c,'ratio')['configuration'])
 F.append(core)
batch=[r for r in rows if r['metric']=='batch_throughput' and r['n']==5000]
assert len(batch)==30 and all(r['threads_requested']==1 and r['comparison_contract']=='loop1-vs-batch1' for r in batch)
keys=['codec','method','access_profile','n','threads_requested','H_alpha','value','commands']
zfront=[]
for frame in [16384,65536,262144,2097152]:
 def z(metric): return one('zstd-seekable-frontier',metric,frame_bytes=frame)
 zfront.append(dict(frame_bytes=frame,ratio=z('zstd_frame_ratio')['value'],p50=z('zstd_frame_region_p50_ms')['value'],
   p99=z('zstd_frame_region_p99_ms')['value'],amplification=z('zstd_frame_amplification')['value'],
   full_decode=z('zstd_frame_full_decode_mb_s')['value'],full_status=z('zstd_frame_full_decode_mb_s')['status']))
gpu=[r for r in rows if r.get('evidence_group')=='gpu-declared']
data=dict(configs=F,batch=[{k:r[k] for k in keys} for r in batch],speedups=[{k:r[k] for k in ['codec','access_profile','value']} for r in rows if r['metric']=='batch_speedup_over_loop' and r['n']==5000],
 zstd_frontier=zfront,gpu=gpu,
 run_id=rows[0]['run_id'],commit=rows[0]['benchmark_commit'],versions=rows[0]['versions'],hardware=rows[0]['hardware'],results_sha256=hashlib.sha256((R/'results.jsonl').read_bytes()).hexdigest())
text=(R/'web/index.template.html').read_text().replace('__BENCH_DATA__',json.dumps(data,separators=(',',':')).replace('</','<\\/'))
target=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else R/'web/index.html';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
print('Exported',target,'from',data['commit'])
