"""Same-corpus independence cost. Whole-file means one LZ access block for ACEAPEX."""
import filecmp, hashlib, json, os, pathlib, shlex, struct, subprocess
from configurations import CODECS, configuration, clean_environment

def add_independence(rows, meta, D):
    fa=D/'chr1.fa'; size=fa.stat().st_size
    def sha(p):
        h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(1048576),b''):h.update(b)
        return h.hexdigest()
    for codec in CODECS:
        cfg=configuration(codec); original=next(r for r in rows if r['codec']==codec and r['metric']=='ratio')
        arc=D/('whole-'+codec.replace('+','-')+'.archive'); restored=D/'whole-restored.fa'
        env=clean_environment(os.environ); overrides={}; commands=[]
        if codec=='bgzip+htslib':
            encode=['gzip','-n','-6','-c',str(fa)]; decode=['gzip','-d','-c',str(arc)]
            baseline={'format':'gzip, one member','level':6,'threads_requested':1,'version':subprocess.check_output(['gzip','--version'],text=True).splitlines()[0],
                'caveat':'Operational bgzip/gzip comparison: implementations and match search differ; not a pure block-reset ablation.'}
        elif codec=='zstd-seekable':
            encode=[str(D/'zstd/programs/zstd'),'-3','-T1','--no-check','-f',str(fa),'-o',str(arc)]
            decode=[str(D/'zstd/programs/zstd'),'-d','-c',str(arc)]
            baseline={'format':'zstd, one frame','level':3,'threads_requested':1,'checksum':False,
                'caveat':'Same pinned zstd and level; whole-file frame permits its normal level-3 window, while seekable frames restart. Frame and seek-table overhead included.'}
        else:
            overrides={'ACEAPEX_BS':str(size)};env.update(overrides)
            encode=[str(D/'aceapex-cli'),'c','--in',str(fa),'--out',str(arc),'--threads','1','--level','2','--profile',cfg['profile']]
            decode=[str(D/'aceapex-cli'),'d','--in',str(arc),'--out',str(restored),'--profile',cfg['profile']]
            baseline={'format':'ACEPX2','block':size,'num_blocks':1,'profile':cfg['profile'],'level':2,'threads_requested':1,
                'environment_overrides':overrides,'literal_chunk_bytes':int(cfg['effective_environment']['LIT_CHUNK']),
                'fse_chunk_bytes':int(cfg['effective_environment']['FSE_CHUNK']),
                'caveat':'Only ACEAPEX_BS is overridden. Entropy chunking and source search limits remain fixed; upstream skips chain flattening above 1 MiB, so this is a whole-block configuration comparison, not a pure dependency-reset ablation.'}
        for args in (encode,decode):
            prefix='env '+shlex.join(k+'='+v for k,v in overrides.items())+' ' if overrides else ''
            command=prefix+shlex.join(args)
            if args is encode and codec=='bgzip+htslib':
                command+=' > '+shlex.quote(str(arc))
                with arc.open('wb') as f:subprocess.run(args,stdout=f,env=env,check=True,timeout=900)
            elif args is decode and not codec.startswith('aceapex'):
                command+=' > '+shlex.quote(str(restored))
                with restored.open('wb') as f:subprocess.run(args,stdout=f,env=env,check=True,timeout=900)
            else:subprocess.run(args,env=env,check=True,timeout=900)
            commands.append(command)
        if not filecmp.cmp(fa,restored,shallow=False):raise RuntimeError(codec+' whole-file baseline restore mismatch')
        if codec.startswith('aceapex'):
            with arc.open('rb') as f:h=f.read(28)
            if struct.unpack_from('<II',h,20)!=(size,1):raise RuntimeError('Whole-file ACEAPEX block configuration not honored')
        archived=arc.stat().st_size; independent=original['archive_bytes']+original['index_bytes']
        whole_ratio=size/archived; retained=original['value']/whole_ratio; loss=100*(1-retained)
        rows.append(dict(meta,codec=codec,configuration=cfg,metric='independence_cost_percent',value=loss,unit='percent',status='measured',
            formula='100 * (1 - ratio_g / ratio_whole)',ratio_g=original['value'],ratio_whole=whole_ratio,
            independent_archive_bytes=independent,whole_archive_bytes=archived,input_bytes=size,retained_ratio_fraction=retained,
            baseline_configuration=baseline,whole_archive_sha256=sha(arc),archive_sha256=original['archive_sha256'],
            correctness='pass',full_restore_byte_equal=True,commands=original['commands']+commands,
            note='Negative cost is retained if measured. No threshold is fitted to expected 0.41% or 6.68%.' ))
        restored.unlink()
    (D/'independence-raw.json').write_text(json.dumps([r for r in rows if r['metric']=='independence_cost_percent'],indent=2)+'\n')
    return rows

def render_independence(rows):
    rr=[r for r in rows if r['metric']=='independence_cost_percent']
    if {r['codec'] for r in rr}!=set(CODECS) or len(rr)!=4:raise ValueError('Incomplete independence comparison')
    out=['## Independence cost c(g)','','`c(g) = 100 × (1 − ratio_g / ratio_whole)`; signed loss of compression ratio. All archive headers and required indexes count.','',
         '| Codec/profile | block bytes | ratio g | ratio whole | c(g) loss % | Encoder threads requested |','|---|---:|---:|---:|---:|---:|']
    for r in rr:
        expected=100*(1-r['whole_archive_bytes']/r['independent_archive_bytes'])
        if abs(expected-r['value'])>1e-10 or not r['full_restore_byte_equal']:raise ValueError('Invalid c(g) evidence')
        out.append(f"| {r['codec']} | {r['configuration']['block']} | {r['ratio_g']:.6f} | {r['ratio_whole']:.6f} | {r['value']:.6f} | 1 |")
    out+=['','Whole-file baseline: one gzip member, one zstd frame, or one ACEAPEX output block covering the complete file.','ACEAPEX retains the corresponding profile’s entropy chunk sizes; only ACEAPEX_BS changes. The pinned encoder skips chain flattening above 1 MiB, so the baseline also crosses that implementation branch.','bgzip/gzip use different implementations. These are documented operational configuration comparisons; the differences are not attributed solely to independence.','Complete commands, baseline settings, sizes, archive hashes and restore checks accompany every JSONL point. Expected historical percentages are not acceptance thresholds.','','Stop for review before plateau throughput and the three-machine experiment.','']
    return '\n'.join(out)
