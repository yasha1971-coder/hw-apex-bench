"""Export the instrument-style homepage from one verified JSONL run."""
import hashlib,json,pathlib,sys
R=pathlib.Path(__file__).resolve().parents[1]
rows=[json.loads(s) for s in (R/'results.jsonl').read_text().splitlines()]
assert len({r['run_id'] for r in rows})==1
cs=['bgzip+htslib','zstd-seekable','aceapex-interactive','aceapex-dense']
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
data=dict(configs=F,batch=[{k:r[k] for k in keys} for r in batch],speedups=[{k:r[k] for k in ['codec','access_profile','value']} for r in rows if r['metric']=='batch_speedup_over_loop' and r['n']==5000],
 run_id=rows[0]['run_id'],commit=rows[0]['benchmark_commit'],versions=rows[0]['versions'],hardware=rows[0]['hardware'],results_sha256=hashlib.sha256((R/'results.jsonl').read_bytes()).hexdigest())
text=(R/'web/index.template.html').read_text().replace('__BENCH_DATA__',json.dumps(data,separators=(',',':')).replace('</','<\\/'))
target=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else R/'web/index.html';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
print('Exported',target,'from',data['commit'])
