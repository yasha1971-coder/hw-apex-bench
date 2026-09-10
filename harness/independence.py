"""Same-corpus independence cost. Whole-file means one LZ access block for ACEAPEX."""
import filecmp, hashlib, json, os, pathlib, shlex, struct, subprocess
from configurations import CODECS, configuration, clean_environment

STRICT_REASONS = {
    'bgzip+htslib': 'n/a: gzip and bgzip use different encoder implementations; no same-encoder block-size-only baseline measured',
    'aceapex-interactive': 'n/a for this profile/SHA: the strict supplied pair uses the default configuration at 7216280, not --profile interactive at 1b13df3',
    'aceapex-dense': 'n/a for this profile/SHA: no block-size-only dense pair has been supplied',
}

ACE_CORE_STRICT = {
    'codec': 'aceapex-default-7216280',
    'sha': '7216280298baa976152f6978ea1ac9c7b65fc4ad',
    'block': 16384,
    'whole_block': 253935557,
    'input_bytes': 253935557,
    'blocked_archive_bytes': 80829622,
    'whole_archive_bytes': 79510864,
    'threads': 8,
    'machine': 'AMD EPYC 4344P (ace-core)',
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
        if codec == 'zstd-seekable':
            rows.append(dict(rows[-1],metric='independence_cost_strict_percent',value=loss,status='measured',
                reason='same zstd 1.5.7 encoder and level -3; one frame versus independent 16384-byte frames',
                baseline_contract='Only frame size changes; complete output files, including seek table, are counted'))
        else:
            rows.append(dict(rows[-1],metric='independence_cost_strict_percent',value=None,status='n/a',
                reason=STRICT_REASONS[codec],baseline_contract='Only independent block size may change; all other explicit settings remain fixed'))
        restored.unlink()
    c=ACE_CORE_STRICT
    ratio_g=c['input_bytes']/c['blocked_archive_bytes']
    ratio_whole=c['input_bytes']/c['whole_archive_bytes']
    loss=100*(1-ratio_g/ratio_whole)
    rows.append(dict(meta,codec=c['codec'],configuration={
            'implementation':'aceapex','profile':'default','block':c['block'],
            'baseline_block':c['whole_block'],'encoder_requested_threads':c['threads']},
        metric='independence_cost_strict_percent',value=loss,unit='percent',status='declared',
        measurement_source='user-supplied ace-core measurement; exact archive bytes and commands supplied, archive hashes and restore receipt not supplied',
        formula='100 * (1 - ratio_g / ratio_whole)',ratio_g=ratio_g,ratio_whole=ratio_whole,
        independent_archive_bytes=c['blocked_archive_bytes'],whole_archive_bytes=c['whole_archive_bytes'],
        input_bytes=c['input_bytes'],hardware={'machine':c['machine']},threads_requested=c['threads'],
        versions={'aceapex_sha':c['sha'],'compiler':'not supplied','libzstd':'not supplied'},
        correctness='declared; no archive hashes or byte-equal restore receipt supplied',
        commands=[
          'ACEAPEX_BS=16384 ./aceapex c --in chr1.fa --out /tmp/g16.aet --threads 8',
          'ACEAPEX_BS=253935557 ./aceapex c --in chr1.fa --out /tmp/gall.aet --threads 8',
          'stat -c%s /tmp/g16.aet /tmp/gall.aet'],
        note='Whole means one ACEAPEX block spanning the input; block logic remains active. Complete .aet file bytes are counted.'))
    (D/'independence-raw.json').write_text(json.dumps([r for r in rows if r['metric'] in ('configuration_ratio_loss_percent','independence_cost_strict_percent')],indent=2)+'\n')
    return rows

def render_independence(rows):
    # Historical numeric records retain their original metric name and bytes.
    rr=[r for r in rows if r['metric'] in ('independence_cost_percent','configuration_ratio_loss_percent')]
    if {r['codec'] for r in rr}!=set(CODECS) or len(rr)!=4:raise ValueError('Incomplete independence comparison')
    strict=[r for r in rows if r['metric']=='independence_cost_strict_percent']
    if any(r['metric']=='configuration_ratio_loss_percent' for r in rr):
        if len(strict)!=5 or {r['codec'] for r in strict}!=set(CODECS)|{ACE_CORE_STRICT['codec']}:
            raise ValueError('Missing strict baseline eligibility records')
    strict_by={r['codec']:r for r in strict}
    if strict_by['bgzip+htslib']['value'] is not None or strict_by['bgzip+htslib']['status']!='n/a':
        raise ValueError('bgzip must remain n/a without a same-encoder baseline')
    if strict_by['zstd-seekable']['status']!='measured':raise ValueError('zstd strict pair missing')
    if strict_by[ACE_CORE_STRICT['codec']]['status']!='declared':raise ValueError('external ACEAPEX provenance must remain declared')
    out=['## Independence cost c(g): strict baseline contract','','Only the independent block size may change. Corpus bytes, encoder revision, level, effective search/entropy parameters and threads must otherwise be fixed. Deterministic encoder behavior caused by the changed boundary is part of the treatment.',
         '`c(g) = 100 × (1 − ratio_g / ratio_whole)`. Every ratio uses input bytes divided by complete output-file bytes. Historical JSONL metric independence_cost_percent means the operational comparison; strict claims are explicit rows with their own provenance.','',
         '| Codec/profile | block bytes | ratio g | ratio whole | Operational loss % | Strict c(g) | Encoder threads requested |','|---|---:|---:|---:|---:|---|---:|']
    for r in rr:
        expected=100*(1-r['whole_archive_bytes']/r['independent_archive_bytes'])
        if abs(expected-r['value'])>1e-10 or not r['full_restore_byte_equal']:raise ValueError('Invalid c(g) evidence')
        sr=strict_by[r['codec']]
        sv=f"{sr['value']:.6f}" if sr['value'] is not None else 'n/a'
        out.append(f"| {r['codec']} | {r['configuration']['block']} | {r['ratio_g']:.6f} | {r['ratio_whole']:.6f} | {r['value']:.6f} | {sv} | 1 |")
    ext=strict_by[ACE_CORE_STRICT['codec']]
    out.append(f"| ACEAPEX default @ 7216280 (ace-core, declared) | {ACE_CORE_STRICT['block']} | {ext['ratio_g']:.6f} | {ext['ratio_whole']:.6f} | — | {ext['value']:.6f} | {ACE_CORE_STRICT['threads']} |")
    for codec in ('bgzip+htslib','aceapex-interactive','aceapex-dense'):
        out += ['', codec+': '+STRICT_REASONS[codec]+'.']
    out += ['', 'ACEAPEX default @ 7216280 is shown from supplied ace-core archive sizes: 80829622 bytes at 16 KiB and 79510864 bytes for one whole-input block. Status is declared because compiler/libzstd versions, archive hashes and a byte-equal restore receipt were not supplied. The GitHub runner reproduction remains a separate machine result.']
    out += ['', 'zstd bases are explicitly zstd 1.5.7 level -3, one continuous frame versus independent 16384-byte frames. The user-reported historical version is 1.4.8 with 6.68%; version change is a hypothesis for the difference, not an attribution established by a matched rerun.',
            'The historical 0.410% is payload-only: it excludes the AET header and 64-byte BlockOffsets entry per block. The cross-codec archive ratio includes both. Neither 0.410% nor 6.68% is an acceptance target.']
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
