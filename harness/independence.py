"""Same-corpus independence cost. Whole-file means one LZ access block for ACEAPEX."""
import filecmp, hashlib, json, os, pathlib, shlex, struct, subprocess
from configurations import CODECS, configuration, clean_environment

STRICT_REASONS = {
    'bgzip+htslib': 'n/a: gzip and bgzip use different encoder implementations; no same-encoder block-size-only baseline measured',
    'zstd-seekable': 'n/a: level -3 is matched, but equal effective compression parameters beyond frame size have not been verified',
    'aceapex-interactive': 'n/a: per-block first-MiB flattening eligibility changes; its separate effect has not been isolated',
    'aceapex-dense': 'n/a: per-block first-MiB flattening eligibility changes; its separate effect has not been isolated',
}

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
                'caveat':'Only ACEAPEX_BS is overridden. MIN_MATCH is unset and defaults to 0. LIT/FSE profile chunks remain fixed. Flattening is eligible only where local_pos < 1 MiB in each block; the whole-file block loses eligibility after its first MiB. This is not an isolated block-reset ablation.'}
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
        rows.append(dict(meta,codec=codec,configuration=cfg,metric='configuration_ratio_loss_percent',value=loss,unit='percent',status='measured',
            formula='100 * (1 - ratio_g / ratio_whole)',ratio_g=original['value'],ratio_whole=whole_ratio,
            independent_archive_bytes=independent,whole_archive_bytes=archived,input_bytes=size,retained_ratio_fraction=retained,
            baseline_configuration=baseline,whole_archive_sha256=sha(arc),archive_sha256=original['archive_sha256'],
            correctness='pass',full_restore_byte_equal=True,commands=original['commands']+commands,
            note='Negative cost is retained if measured. No threshold is fitted to expected 0.41% or 6.68%.' ))
        rows.append(dict(rows[-1],metric='independence_cost_strict_percent',value=None,status='n/a',
            reason=STRICT_REASONS[codec],baseline_contract='Only independent block size may change; effective encoder parameters and algorithmic modes must otherwise be fixed'))
        restored.unlink()
    (D/'independence-raw.json').write_text(json.dumps([r for r in rows if r['metric'] in ('configuration_ratio_loss_percent','independence_cost_strict_percent')],indent=2)+'\n')
    return rows

def render_independence(rows):
    # Historical numeric records retain their original metric name and bytes.
    rr=[r for r in rows if r['metric'] in ('independence_cost_percent','configuration_ratio_loss_percent')]
    if {r['codec'] for r in rr}!=set(CODECS) or len(rr)!=4:raise ValueError('Incomplete independence comparison')
    strict=[r for r in rows if r['metric']=='independence_cost_strict_percent']
    if any(r['metric']=='configuration_ratio_loss_percent' for r in rr):
        if len(strict)!=4 or {r['codec'] for r in strict}!=set(CODECS):
            raise ValueError('Missing strict baseline eligibility records')
    for r in strict:
        if r['value'] is not None or r['status']!='n/a' or r.get('reason')!=STRICT_REASONS[r['codec']]:
            raise ValueError('No audited block-size-only baseline is implemented for this codec')
    out=['## Independence cost c(g): strict baseline contract','','Only the independent block size may change. Corpus bytes, encoder revision, level, effective search/entropy parameters, threads and algorithmic modes must otherwise be fixed. A CLI flag match alone is insufficient if another algorithmic mode changes with block size.',
         '`c(g) = 100 × (1 − ratio_g / ratio_whole)`. Below, the two ratios and their operational loss are measured; strict c(g) is n/a until the one-parameter contract is demonstrated. Historical JSONL metric independence_cost_percent means the operational comparison, not a retrospectively certified strict c(g).','',
         '| Codec/profile | block bytes | ratio g | ratio whole | Operational loss % | Strict c(g) | Encoder threads requested |','|---|---:|---:|---:|---:|---|---:|']
    for r in rr:
        expected=100*(1-r['whole_archive_bytes']/r['independent_archive_bytes'])
        if abs(expected-r['value'])>1e-10 or not r['full_restore_byte_equal']:raise ValueError('Invalid c(g) evidence')
        out.append(f"| {r['codec']} | {r['configuration']['block']} | {r['ratio_g']:.6f} | {r['ratio_whole']:.6f} | {r['value']:.6f} | n/a | 1 |")
    for codec in CODECS:
        out += ['', codec+': '+STRICT_REASONS[codec]+'.']
    out += ['', 'zstd bases are explicitly zstd 1.5.7 level -3, one continuous frame versus independent 16384-byte frames. The user-reported historical version is 1.4.8 with 6.68%; version change is a hypothesis for the difference, not an attribution established by a matched rerun.',
            'Neither 0.41% nor 6.68% is a target. Any new strict c(g) must come from its own verified pair and keep that pair’s ratios and commands; a historical value cannot replace a different pair’s measured loss.']
    out+=['','Whole-file means one continuous member/frame/output block, not an unlimited match window. gzip retains its 32 KiB backward-distance limit; this does not make its blocks independent. bgzip adds independent member boundaries, index/headers and implementation differences.',
          'ACEAPEX uses the same pinned binary on both sides. ACEAPEX_BS changes from 16384 or 262144 to 253935557. MIN_MATCH was cleared and defaults to 0. LIT_CHUNK/FSE_CHUNK remain 65536/4096 (interactive) or 1048576/32768 (dense).',
          'Important correction: flattening is not disabled for the entire large block. The actual guard is local_pos < (1u<<20), with c_off <= local_pos. Eligible non-rep matches in its first MiB may be flattened; later matches are not. Each small block resets local_pos. The separate size impact of this difference is unmeasured; isolated c(g) is n/a for these ACEAPEX pairs.',
          'The old JSONL baseline caveat used the inaccurate shorthand “skips chain flattening above 1 MiB”. Raw historical evidence is preserved; this report and INDEPENDENCE_AUDIT.md correct that interpretation. No observed archive size or ratio has changed.',
          '', '### Both compression commands for every row', '',
          'Commands below are the recorded commands, with the runner checkout prefix replaced by `.` for local replay. Each compression command is paired with its own ratio and archive size. Codec wrappers are part of the pinned benchmark source. Before replay, clear overrides exactly as run.sh does:', '', '```bash',
          'unset ACEAPEX_BS LIT_CHUNK FSE_CHUNK MIN_MATCH LIT_LEVEL LIT_LANES NO_REP DIRECT8 FORCED_BIN ACEAPEX_DUMP LD_PRELOAD', '```']
    for r in rr:
        commands=r['commands']; prefix='/home/runner/work/hw-apex-bench/hw-apex-bench/'
        out += ['', '#### '+r['codec'], '', f"Blocked: ratio **{r['ratio_g']:.12f}**, archive + required index **{r['independent_archive_bytes']} bytes**.", '', '```bash', commands[0].replace(prefix,'./'), '```', '', f"Continuous baseline: ratio **{r['ratio_whole']:.12f}**, archive **{r['whole_archive_bytes']} bytes**.", '', '```bash', commands[-2].replace(prefix,'./'), '```']
    out+=['','[Expanded CLI commands, environment and flattening audit](INDEPENDENCE_AUDIT.md). Expected historical percentages are not acceptance thresholds.','','Stop for review before plateau throughput and the three-machine experiment.','']
    return '\n'.join(out)
