#!/usr/bin/env python3
"""Tables/optional plots from validated evidence only; never hard-code results."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from validate_axis3_evidence import loads, validate_record


def recompute(record, root):
    values=[]
    if record['status']!='PASS':return record
    identifiers=set()
    for ref in record['raw_logs']:
        with (root/ref['path']).open(encoding='utf-8') as f:
            for line in f:
                if not line.strip():continue
                row=loads(line)
                key=row['request_id']
                if key in identifiers:raise ValueError('duplicate raw request ID')
                identifiers.add(key)
                if row['status']!='PASS' or row['expected_sha256']!=row['observed_sha256']:
                    raise ValueError('raw correctness disagrees with PASS summary')
                if row['returned_bytes']!=record['window_bytes']:
                    raise ValueError('raw window length differs')
                n=row['elapsed_ns']
                if type(n) is not int or n<=0:raise ValueError('invalid raw latency')
                values.append(n)
    if len(values)!=record['samples']:raise ValueError('raw sample count differs')
    ordered=sorted(values);metrics=dict(record['metrics'])
    for percent in (50,95,99):
        got=ordered[(percent*len(values)+99)//100-1]/1000
        if abs(got-metrics[f'p{percent}_us'])>0.000000001:
            raise ValueError('summary quantile differs from raw log')
        metrics[f'p{percent}_us']=got
    rate=len(values)*1e9/sum(values)
    if abs(rate-metrics['windows_per_second'])>max(1e-9,rate*1e-12):
        raise ValueError('summary throughput differs from raw log')
    metrics['windows_per_second']=rate
    return dict(record,metrics=metrics)


def comparison_group(r):
    return (r['kind'],r['scope'],r['hardware']['machine_id'],r['protocol']['sha256'],
            r['runbook']['sha256'],r['corpus_manifest']['sha256'],r['requests']['sha256'],
            r['window_bytes'],r['n_assemblies'])


def escape(s):return str(s).replace('|','/').replace(chr(10),' ')


def render(records, baseline):
    lines=['# Axis 3 — evidence-derived report','',
           'Every figure below is read from hashed evidence. Synthetic and measured data are separate scopes.','']
    groups={}
    for r in records:groups.setdefault(comparison_group(r),[]).append(r)
    losses=[]
    for key,group in sorted(groups.items(),key=lambda item:str(item[0])):
        kind,scope,machine,*_=key
        lines += [f'## {escape(kind)} / {escape(scope)} / {escape(machine)} / W={key[-2]} / N={key[-1]}','',
                  '| Format | Variant | Status | Bytes/assembly | p50 us | p95 us | Windows/s |',
                  '|---|---|---|---:|---:|---:|---:|']
        baselines=[r for r in group if r['format']==baseline and r['status']=='PASS']
        if len(baselines)>1:raise ValueError('ambiguous baseline within comparison scope')
        for r in sorted(group,key=lambda r:(r['format'],r['variant'])):
            m=r['metrics']
            vals=([f'{m["bytes_per_assembly"]:.3f}',f'{m["p50_us"]:.3f}',f'{m["p95_us"]:.3f}',f'{m["windows_per_second"]:.3f}'] if m else ['n/a']*4)
            lines.append('| '+' | '.join(map(escape,[r['format'],r['variant'],r['status'],*vals]))+' |')
            for ref in r['raw_logs']:
                lines.append(f'<!-- raw-log {escape(ref["path"])} sha256={ref["sha256"]} -->')
            if baselines and m and r is not baselines[0]:
                base=baselines[0]['metrics'];worse=[]
                if m['p50_us']>base['p50_us']:worse.append('higher p50')
                if m['bytes_per_assembly']>base['bytes_per_assembly']:worse.append('larger storage')
                if worse:losses.append(f'{r["format"]}/{r["variant"]}: '+', '.join(worse))
        lines.append('')
    lines += ['## Where we lose','']
    lines += losses if losses else ['No supported loss comparison in the supplied evidence; this is not a claim of superiority.']
    lines += ['', '## Raw-log provenance','']
    for r in records:
        for ref in r['raw_logs']:lines.append(f'{escape(ref["path"])} — SHA-256 `{ref["sha256"]}`')
    return chr(10).join(lines)+chr(10)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('records',nargs='+',type=Path);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--baseline',required=True)
    p.add_argument('--plot-dir',type=Path)
    a=p.parse_args();root=a.root.resolve()
    rows=[recompute(validate_record(loads(f.read_text()),root),root) for f in a.records]
    a.output.write_text(render(rows,a.baseline))
    if a.plot_dir:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        a.plot_dir.mkdir(parents=True,exist_ok=True)
        groups={}
        for row in rows:
            if row['status']=='PASS':groups.setdefault(comparison_group(row),[]).append(row)
        for index,(key,group) in enumerate(groups.items()):
            fig,ax=plt.subplots(figsize=(9,5))
            ax.bar([r['format']+'/'+r['variant'] for r in group],[r['metrics']['p50_us'] for r in group])
            ax.set_ylabel('p50, microseconds');ax.set_title(f'{key[0]} / {key[1]} / W={key[-2]} / N={key[-1]}')
            ax.tick_params(axis='x',rotation=30)
            caption=chr(10).join(ref['path']+' sha256='+ref['sha256'] for r in group for ref in r['raw_logs'])
            fig.text(.01,.01,caption,fontsize=5);fig.tight_layout(rect=(0,.18,1,1))
            fig.savefig(a.plot_dir/f'p50-{index}.svg');plt.close(fig)
if __name__=='__main__':main()
