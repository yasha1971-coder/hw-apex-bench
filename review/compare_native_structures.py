#!/usr/bin/env python3
"""Compare deterministic evidence to historical rows, without comparing clocks."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'harness'))
from native_comparison import FROZEN


def compare(historical,manifest):
    blob=Path(historical).read_bytes()
    if hashlib.sha256(blob).hexdigest()!=FROZEN:raise ValueError('historical data changed')
    old=[json.loads(line) for line in blob.splitlines()]
    current=json.loads(Path(manifest).read_text())
    if any(r['corpus']['md5']!=current['corpus_md5'] for r in old if r['metric']=='ratio'):
        raise ValueError('corpus differs from historical comparison scope')
    audits=[]
    for entry in current['adapters']:
        plan=entry['plan'];codec=plan['codec'];values={r['axis']:r['value'] for r in entry['measurements']}
        before={r['metric']:r for r in old if r['codec']==codec and r['metric'] in ('ratio','amplification')}
        if 'ratio' in before:
            r=before['ratio'];new=values['ratio'];archive=next(v for p,v in new['archive_artifacts'].items() if Path(p).name=='archive')
            audits.append({'codec':codec,'field':'archive_bytes','old':r['archive_bytes'],'new':archive['bytes'],'equal':r['archive_bytes']==archive['bytes']})
            audits.append({'codec':codec,'field':'archive_sha256','old':r['archive_sha256'],'new':archive['sha256'],'equal':r['archive_sha256']==archive['sha256']})
            audits.append({'codec':codec,'field':'ratio','old':r['value'],'new':new['ratio'],'equal':r['value']==new['ratio']})
        if 'amplification' in before:
            a=before['amplification']['value'];b=values['amplification']['value']
            audits.append({'codec':codec,'field':'amplification','old':a,'new':b,'equal':a==b})
        prior={(r['access_profile'],r['n']):r for r in old if r['codec']==codec and r['metric']=='batch_throughput' and r['method']=='loop'}
        for p in values['h_alpha']['profiles']:
            r=prior.get((p['profile'],p['count']))
            if r:
                # Float summation order can change last bits; trace hash remains exact.
                audits.append({'codec':codec,'field':'H_alpha','profile':p['profile'],'n':p['count'],
                    'old':r['H_alpha'],'new':p['H_alpha_bits'],'equal':r['H_alpha']==p['H_alpha_bits'],
                    'absolute_difference':abs(r['H_alpha']-p['H_alpha_bits']),
                    'trace_sha256_equal':r['query_trace_sha256']==p['trace_sha256']})
        if codec=='zstd-seekable':
            prior={r['g']:r for r in old if r['codec']=='zstd-seekable-cg' and r['metric']=='cg_curve_ratio_loss_percent'}
            curve=values['c_g']
            for p in curve['points']:
                r=prior[p['granularity']]
                audits.append({'codec':codec,'field':'c_g_percent','granularity':p['granularity'],
                    'old':r['value'],'new':p['c_g_percent'],'equal':r['value']==p['c_g_percent'],
                    'baseline_bytes_equal':r['baseline']['total_bytes']==curve['baseline']['archive_bytes'],
                    'point_bytes_equal':r['point']['total_bytes']==p['archive_bytes']})
    return {'historical_sha256':FROZEN,'fresh_manifest_sha256':hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
        'scope':'deterministic comparable archives, counters, shared traces and zstd c(g); no timing equality claim',
        'checks':audits,'exact_matches':sum(a['equal'] for a in audits),'differences':sum(not a['equal'] for a in audits)}

if __name__=='__main__':print(json.dumps(compare(sys.argv[1],sys.argv[2]),indent=2))
