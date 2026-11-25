"""Generate the report and unsent issue from saved HW-GIFT-1c evidence only."""
from decimal import Decimal,localcontext
import csv
import gzip
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PIN='f8745da6ff1ad1e7bab384bd1f9d742439278e99'
UP='https://github.com/facebook/zstd/blob/'+PIN+'/'


def check(ok,message):
    if not ok:raise ValueError(message)


def load(path):return json.loads(Path(path).read_bytes())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def percent(num,den):
    with localcontext() as c:
        c.prec=40
        return f'{Decimal(num)*100/Decimal(den):.6f}'


def ratio(num,den):
    with localcontext() as c:
        c.prec=40
        return f'{Decimal(num)/Decimal(den):.6f}'


def ms(ns):return f'{ns//1000000}.{ns%1000000:06d}'


def evidence():
    method=load(HERE/'method-check.json');proof=load(HERE/'minimal-proof.json');study=load(HERE/'case-study.json')
    env=load(HERE/'environment.json');audit=load(HERE/'audit/independent-audit.json')
    check(method['status']==proof['status']==audit['status']=='PASS','method/proof/audit failed')
    check(method['environment_sha256']==sha(HERE/'environment.json'),'environment changed')
    for name,digest in env['source_sha256'].items():check(sha(HERE/name)==digest,'instrument source changed: '+name)
    check(proof['controls_sha256']==sha(HERE/'method-check.json') and proof['case_study_sha256']==sha(HERE/'case-study.json'),'proof provenance changed')
    check(audit['source_sha256']==sha(HERE/'audit/verify_independent.py'),'independent audit source changed')
    for name in ('original','pyzstd'):
        p=proof[name];check(sha(HERE/p['path'])==p['sha256'],'minimal frame changed')
    cases=sorted((load(p) for p in (HERE/'cases').glob('*.json')),key=lambda r:r['case_index'])
    check(len(cases)==8 and [r['case_index'] for r in cases]==list(range(8)),'complete eight-case matrix required')
    for r in cases:
        check(r['environment_sha256']==sha(HERE/'environment.json') and r['method_check_sha256']==sha(HERE/'method-check.json')
              and r['minimal_proof_sha256']==sha(HERE/'minimal-proof.json'),'matrix identity changed')
        path=HERE/'cases'/r['frame_records_file'];check(sha(path)==r['frame_records_sha256'],'raw frame record hash changed')
        rows=[json.loads(x) for x in gzip.decompress(path.read_bytes()).splitlines()]
        check(len(rows)==r['frame_count'] and [v['index'] for v in rows]==list(range(r['frame_count'])),'frame record grid changed')
        check(sum(v['decompressed_bytes'] for v in rows)==r['input_bytes'],'frame source size accounting failed')
        for v in ('original','patched','pyzstd'):
            a=r['archives'][v];total=sum(x['variants'][v]['compressed_bytes'] for x in rows)
            check(total==a['data_bytes'] and total+a['seek_table_bytes']==a['bytes'],'archive size accounting failed')
            check(a['seek_table_bytes']==17+r['frame_count']*(12 if a['checksum_flag'] else 8),'seek table accounting failed')
            check(a['restored_sha256']==r['input_sha256'],'source oracle changed')
        check(all(x['variants']['patched']['sha256']==x['variants']['pyzstd']['sha256'] for x in rows),'patched frame does not equal pyzstd')
        check(r['archives']['patched']['bytes']-r['archives']['pyzstd']['bytes']==4*r['frame_count']==r['residual_bytes'],'residual bytes unexplained')
        review=next(a for a in audit['cases'] if (a['chunk'],a['g'])==(r['chunk'],r['g']))
        check(all(review['archive_sha256'][v]==a['sha256'] for v,a in r['archives'].items()),'independent audit does not bind actual archives')
    observation=load(HERE/'timing/observation.json');check(observation['status']=='CLEAN','optional pair is not CLEAN')
    base=HERE/'timing';selected=(base/observation['selected_result']).resolve()
    check(selected.is_relative_to(base.resolve()),'timing result path escaped evidence')
    for item in observation['attempts']:
        check(sha(base/item['receipt_path'])==item['receipt_sha256'],'timed receipt changed')
        if item['result_path']:check(sha(base/item['result_path'])==item['result_sha256'],'timed raw result changed')
    item=next(x for x in observation['attempts'] if x['result_path']==observation['selected_result'])
    receipt=load(base/item['receipt_path']);timed=load(selected)
    check(receipt['status']=='CLEAN' and receipt['returncode']==0 and receipt['command_started'],'invalid CLEAN receipt')
    check(receipt['flock_command'][:2]==['flock','/run/lock/ovh-bench.lock'] and receipt['load1_threshold']=='2.0','wrong lock/load policy')
    check(all(Decimal(receipt[k]['loadavg_raw'].split()[0])<=Decimal('2.0') for k in ('start','end')),'LOADED pair accepted')
    check(timed['observations_per_operation']==1 and timed['clock_calls']==8 and timed['cpu_affinity']==[0],'wrong paired observation scope')
    target=next(r for r in cases if r['chunk']=='enwik8-L3' and r['g']==262144)
    for variant,v in timed['variants'].items():
        check(v['archive']=={k:target['archives'][variant][k] for k in ('bytes','sha256')},'timed archive differs from matrix')
        check(v['bit_perfect'] and v['restored_sha256']==target['input_sha256'],'timed source restoration failed')
        check(all(type(v[k]) is int and v[k]>0 for k in ('compression_elapsed_ns','decompression_elapsed_ns')),'invalid elapsed value')
    return method,proof,study,cases,audit,observation,timed,receipt


def size_table(cases):
    rows=['|corpus/level|frame KiB|N frames|original contrib B|hint=0 contrib B|pyzstd B|change B|change %|remaining B|',
          '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in cases:
        a=r['archives'];old=a['original']['bytes'];new=a['patched']['bytes']
        rows.append(f"|[{r['chunk']}](cases/{r['chunk']}-{r['g']}.json)|{r['g']//1024}|{r['frame_count']}|{old}|{new}|{a['pyzstd']['bytes']}|{new-old}|{percent(new-old,old)}|{r['residual_bytes']}|")
    return rows


def build_report(values):
    method,proof,study,cases,audit,obs,timed,receipt=values
    original,patched=timed['variants']['original'],timed['variants']['patched']
    cp,pp=proof['original'],proof['pyzstd'];modelc=cp['result']['cparams_from_policy'];modelp=pp['result']['cparams_from_policy']
    source_link=UP+'contrib/seekable_format/zstdseek_compress.c#L234'
    out=['# HW-GIFT-1c: source-size hint changes the writer policy','',
         '**STATUS: COMPLETE.** The exact cause is contrib’s unconditional '
         f'[`ZSTD_c_srcSizeHint = maxFrameSize`, zstdseek_compress.c:234]({source_link}). '
         'pyzstd’s writer leaves that hint unset. The hint selects small-source compression parameters and a smaller window while pledged size remains unknown. '
         'Disabling the hint in a private copy makes every tested data frame byte-identical to pyzstd. '
         'Full archives retain an exactly explained optional seek-table checksum difference.','',
         '[Original preregistration](CALIBRATION.md) · [Pinned source paths](SOURCE_PATHS.md) · [One-line patch](zstdseek_compress.patch) · '
         '[Minimal C program](frame_probe.c) · [Independent audit](audit/independent-audit.json)','',
         '## Preregistered calibration','',
         '|hypothesis|forecast / observed fact|verdict|','|---|---|---|',
         '|H1|The source-size-tier/window part is supported, but the stated single-END/pledged-size mechanism is false: both actual writers stream with unknown pledged size; contrib supplies a hint. FCS is absent in both. At 512 KiB the size gap vanishes, but a window-descriptor byte still differs.|Literal **MISS**; corrected hint mechanism recorded separately.|',
         '|H2|Holding hint and final empty END fixed, replacing two 128 KiB CONTINUE feeds with one whole-frame CONTINUE changes neither writer’s frame SHA.|**Rejected / MISS**: declared kill-H2 condition met.|','',
         'The declared kill-H1 predicate (identical headers and effective parameters) is not met: windows differ and the source-derived parameter policies differ. '
         'That does not convert the incorrect pledge premise into a HIT. No hypothesis or criterion was rewritten after inspection. '
         'The result establishes the pinned code cause on these inputs; it does not claim a general speed law or novelty.','',
         '## Method controls and references','',
         f"All three required controls passed before comparison: identical 256 KiB input/call produced identical bytes twice; level 3 vs 4 differed and the comparator reported byte {method['negative_first_difference']}; a separate first-call END frame decoded to known FCS {method['known_fcs']}. "
         'Corrupted frame magic also raised a native error. [Raw method checks](method-check.json).','',
         'The old C runner deleted its temporary archives. This investigation reconstructed C references with the unchanged encoder and required exact HW-GIFT-1b SHA/size equality for the six existing points. '
         'Existing pyzstd archives were read directly and likewise checked. The two new 128/512 KiB points use the same writer paths. '
         'No historical timing series was rerun.','',
         '## Main anomaly: enwik8 L3, 256 KiB','',
         f"[Per-frame CSV](frame-comparison.csv): {study['frames']} frames, including {study['full_frames']} full frames; all {study['full_frames_with_size_gap']} full frames have different compressed lengths. "
         'pyzstd is smaller in 381 of 382 total frames; full frame 272 is one byte larger (75675 → 75676 B). This local loss remains in the CSV.','',
         'Both header descriptors are `0x00`: no FCS, no frame-content checksum, no dictionary ID. The window byte differs:','',
         '|writer|frame-0 header hex|window descriptor|window B|FCS|','|---|---|---|---:|---|']
    for kind,label in [('original','contrib'),('pyzstd','pyzstd')]:
        h=study[kind+'_header'];out.append(f"|{label}|`{h['header_hex']}`|`0x{h['window_descriptor']:02x}`|{h['window_size']}|absent|")
    out+=['','Parameter policy returned by pinned `ZSTD_getCParams(level, hint-or-UNKNOWN, 0)`:',
          '|policy|windowLog|chainLog|hashLog|searchLog|minMatch|targetLength|strategy|','|---|---:|---:|---:|---:|---:|---:|---|']
    for label,m in [('hint=262144',modelc),('hint=0 / UNKNOWN',modelp)]:
        out.append('|'+label+'|'+'|'.join(str(m[k]) for k in ('windowLog','chainLog','hashLog','searchLog','minMatch','targetLength','strategy'))+' (dfast)|')
    out+=['','These are source-derived policy values, not requested-zero CCtx getters presented as internal-state measurements. '
          f"The source fallback using the hint is [zstd_compress.c:1641–1645]({UP}lib/compress/zstd_compress.c#L1641); size-tier selection is [line 7762]({UP}lib/compress/zstd_compress.c#L7762). "
          'The applied window is checked independently in actual headers. The experiment changes the hint as a whole and does not isolate the contribution of each internal parameter.','',
          '## Exact minimal reproduction','',
          'Take bytes `[0,262144)` of the hash-verified enwik8 input. Use a fresh CCtx, no pledged-size call, CONTINUE input and a final empty END. The only policy difference is hint 262144 versus zero.','',
          '```sh','cc -std=c11 -O2 -Wall -Wextra -Werror -I"$ZSTD/lib" frame_probe.c "$ZSTD/lib/libzstd.a" -pthread -o frame_probe',
          'head -c 262144 enwik8 > slice.bin','./frame_probe slice.bin contrib.zst 3 262144 131072 empty',
          './frame_probe slice.bin pyzstd.zst 3 0 262144 empty','sha256sum contrib.zst pyzstd.zst','```','',
          '|frame|bytes|SHA-256, exactly equal to frame 0 in the complete reference archive|','|---|---:|---|',
          f"|contrib|{cp['result']['frame_bytes']}|`{cp['sha256']}`|",f"|pyzstd policy|{pp['result']['frame_bytes']}|`{pp['sha256']}`|",'',
          'Both outputs restore the original slice exactly. The independent controller rebuilt the C probe and reproduced both hashes again. '
          '[Minimal proof and H2 controls](minimal-proof.json). The first-call END used for known-FCS validation is kept separate from this real streaming path.','',
          '## One-line private-copy change','',
          '```diff','- ZSTD_CCtx_setParameter(zcs->cstream, ZSTD_c_srcSizeHint, (int)zcs->maxFrameSize);',
          '+ ZSTD_CCtx_setParameter(zcs->cstream, ZSTD_c_srcSizeHint, 0);','```','',
          'The original pinned source stays clean. No other writer policy is changed. Patched contrib keeps seek-table checksums enabled.','',
          '## Complete size effect','',*size_table(cases),'',
          'All numbers include complete seek tables. Change compares contrib with checksums enabled on both sides. All 11667 patched data frames match pyzstd byte for byte. '
          'Every archive was restored bit for bit and every present seek-table XXH64 field was checked. [Independent size CSV](audit/independent-cases.csv).','',
          'At 512 KiB, all 191 original data frames have the same lengths and payload bytes as pyzstd except byte offset 5: `0x48` (524288-byte window) becomes `0x58` (2097152-byte window). '
          'The independent audit checked every byte, including the tail. Thus the observed extra size effect disappears at that boundary; frame-byte equality still requires the hint change.','',
          '## Every remaining byte','',
          'Contrib’s example enables optional seek-table checksums; pyzstd omits them. Each enabled entry stores compressed size (4 B), decompressed size (4 B), '
          'and the low 32 bits of XXH64 of the uncompressed frame with seed zero (4 B). Without checksum it stores only the two sizes. '
          'The skippable header is 8 B; the common footer is 9 B. Hence table sizes are `17 + 12*N` and `17 + 8*N`.','',
          'Removing each four-byte checksum, adjusting the little-endian skippable payload-length field and clearing footer descriptor bit 7 yields the exact pyzstd archive. '
          'Adding the independently calculated checksums, updating length and setting that bit reconstructs the exact patched contrib archive. '
          'All data-frame bytes stay untouched in both transformations; both directions were checked for all eight cases.','',
          'For the main anomaly: **608998 B of frame data + 1528 B of table fields = 610526 B**. '
          'The patch removes the frame-data difference and retains the checksum option. All multi-byte table fields are little-endian. '
          'For N=382 the table payload lengths are 4593 and 3065 B; including the 8-byte skippable header, tables are 4601 and 3073 B.','',
          '|main-case table|8-byte skippable header hex|9-byte footer hex|','|---|---|---|',
          f"|patched contrib|`{cases[2]['archives']['patched']['table_header_hex']}`|`{cases[2]['archives']['patched']['footer_hex']}`|",
          f"|pyzstd|`{cases[2]['archives']['pyzstd']['table_header_hex']}`|`{cases[2]['archives']['pyzstd']['footer_hex']}`|",'',
          '## One paired speed observation','',
          '[Preregistered timing scope](TIMING_PROTOCOL.md) · [Raw pair](timing/attempt-001/pair.json) · [Lock/load receipt](timing/attempt-001/ovh-bench.json) · [Untimed native selfcheck](timing/selfcheck.json)','',
          'Complete enwik8, L3, 256 KiB frames; same native writer/decoder paths, table checksums enabled in both. Buffers reside in RAM; fresh context initialization, prefault, hashing and byte comparisons are outside inner timers. '
          'Internal first-use codec allocations remain inside. Order was original encode, patched encode, original decode, patched decode. One observation each, no warmups.','',
          '|variant|compression ns|compression ms|full decode ns|full decode ms|archive B|','|---|---:|---:|---:|---:|---:|']
    for label,v in [('original',original),('hint=0',patched)]:
        out.append(f"|{label}|{v['compression_elapsed_ns']}|{ms(v['compression_elapsed_ns'])}|{v['decompression_elapsed_ns']}|{ms(v['decompression_elapsed_ns'])}|{v['archive']['bytes']}|")
    out+=['',f"On this pair, compression elapsed changed {percent(patched['compression_elapsed_ns']-original['compression_elapsed_ns'],original['compression_elapsed_ns'])}% and full decode elapsed changed {percent(patched['decompression_elapsed_ns']-original['decompression_elapsed_ns'],original['decompression_elapsed_ns'])}%. "
          'No speed penalty was observed in this pair. Fixed order and one pair do not establish a general ranking, distribution or throughput plateau.','',
          f"Host: {receipt['start']['cpu']}, ace-core / CPU 0, {receipt['start']['kernel']}, {receipt['start']['governor']}. "
          f"Boundary load1: {receipt['start']['loadavg_raw'].split()[0]} → {receipt['end']['loadavg_raw'].split()[0]}; shared blocking OVH lock, threshold 2.0. "
          f"{obs['retaken_pairs']} of {obs['logical_pairs']} paired observations retaken; {obs['loaded_attempts']} LOADED attempts. "
          'All attempts, UTC date/loadavg/nproc, raw /proc/stat and observational other-core deltas are retained. Absolute times apply to this host and RAM-resident workload.','',
          '## Which output to choose','',
          '- For storage density on these small-frame cases, pyzstd’s no-hint policy is smaller overall. Patched contrib achieves the same data bytes while retaining its optional table checksums. '
          'Users wanting byte-identical complete pyzstd archives must also choose the no-checksum table representation; that is a separate format option, not another compression fix.',
          '- For constrained encoder/window memory, the original hint remains a useful choice. In the minimal L3/256 KiB probe, `ZSTD_sizeof_CCtx` after encoding was '
          f"{cp['result']['context_bytes']} B with the hint and {pp['result']['context_bytes']} B without it ({ratio(pp['result']['context_bytes'],cp['result']['context_bytes'])}×). "
          'This is CCtx accounting, not process RSS. The declared window grows from 256 KiB to 2 MiB. At 512 KiB the change buys no stored-byte saving.',
          '- The one speed pair supports only its recorded observation. Choose a hint policy explicitly for the storage/memory budget; broader speed or default-policy recommendations require more evidence.','',
          '## Audit and scope','',
          f"Independent controller: {audit['archives_verified']} actual archives, {audit['frame_decodes_verified']} native frame decodes, two rebuilt minimal correctness encodings, zero clocks. "
          f"[Audit output](audit/independent-audit.json), SHA-256 `{sha(HERE/'audit/independent-audit.json')}`; [separate parser/verifier source](audit/verify_independent.py). "
          'The controller imports neither primary run.py nor seekable.py.','',
          f"[Additional read-only timing audit](audit/timing-audit.json), SHA-256 `{sha(HERE/'audit/timing-audit.json')}`, independently checked the selected result, raw stdout, lock/load receipts, per-core deltas and archive/build identities without rerunning a timed operation.",'',
          'Preregistration 65baf466 was the first branch commit before encoding. Each verified chunk was committed/pushed before advancing. The separate method document is PR #91. '
          'Existing HW-GIFT-1/1b evidence remains unchanged. [Draft upstream issue](ZSTD_ISSUE_DRAFT.md) is a local unsent artifact; pyzstd issue #75 was not changed. '
          'PR #92 stays draft; no merge or external contact was performed.','']
    return '\n'.join(out)


def issue_draft(cases):
    return '\n'.join(['# LOCAL DRAFT — not submitted','',
      '## Title','', 'Small seekable frames: unconditional srcSizeHint selects a different ratio/window policy','',
      f'Pinned zstd 1.5.7 `{PIN}`; pyzstd 0.20.0 / backports.zstd 1.8.0 linked to zstd 1.5.7. '
      'Both writer paths were source-traced and their exact frame-0 SHA values reproduced with a small C program.','',
      f'In [zstdseek_compress.c:234]({UP}contrib/seekable_format/zstdseek_compress.c#L234), the seekable writer supplies maxFrameSize as ZSTD_c_srcSizeHint. '
      'The source-size fallback selects different small-source compression parameters and windows. pyzstd does not set the hint on this path. '
      'Both stream with unknown pledged size and absent FCS. Feeding a whole frame in one CONTINUE call does not remove the difference.','',
      'The following one-line change on a private copy makes all tested data frames byte-identical to pyzstd:','',
      '```diff','- ZSTD_CCtx_setParameter(zcs->cstream, ZSTD_c_srcSizeHint, (int)zcs->maxFrameSize);',
      '+ ZSTD_CCtx_setParameter(zcs->cstream, ZSTD_c_srcSizeHint, 0);','```','',*size_table(cases),'',
      'Remaining bytes are exactly four optional seek-table checksum bytes per frame, with matching payload-length/descriptor changes. '
      'Complete native restore and table XXH64 checks passed for every archive. At 512 KiB there is no size saving; every data frame changes only the window-descriptor byte.','',
      'This is a storage/memory policy tradeoff rather than evidence for universally removing the hint. The L3/256 KiB minimal probe reports CCtx size '
      '1566233 → 3663385 B and declared window 256 KiB → 2 MiB. One preregistered resident pair observed encode 340959823 → 312972138 ns and full decode '
      '81793021 → 70095693 ns; one fixed-order pair is not a general speed comparison.','',
      'Would an explicit policy option or documentation of the small-frame ratio/window tradeoff be appropriate? '
      'The exact minimal C program, per-frame CSV, source pins, complete byte accounting and raw pair are retained with the HW-GIFT-1c evidence.','',
      'This file is a draft for owner review only. It has not been sent to facebook/zstd or any other external party.',''])


def main():
    values=evidence()
    (HERE/'RESULTS.md').write_text(build_report(values),encoding='utf-8',newline='')
    (HERE/'ZSTD_ISSUE_DRAFT.md').write_text(issue_draft(values[3]),encoding='utf-8',newline='')
    print('REPORT_SAVED_DATA_VERIFIED',sha(HERE/'RESULTS.md'))


if __name__=='__main__':main()
