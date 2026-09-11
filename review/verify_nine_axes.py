#!/usr/bin/env python3
"""Audit a complete new-path run without changing published results."""
import hashlib
import json
import math
from pathlib import Path
import sys


def verify(path):
    path=Path(path);m=json.loads(path.read_text());root=path.parent
    def require(ok,message):
        if not ok:raise ValueError(message)
    require(m['status']=='pass' and m['published'] is False,'not a completed candidate run')
    payload=(root/'results.jsonl').read_bytes()
    require(hashlib.sha256(payload).hexdigest()==m['results_sha256'],'result hash mismatch')
    serialized=[json.loads(line) for line in payload.splitlines()]
    require(len(serialized)==m['results_records'],'result count mismatch')
    for r in serialized:
        require(r['command'] and r['run_id']==m['run_id'] and r['corpus_md5']==m['corpus_md5'],'incomplete provenance')
        require(r['value'] is not None or bool(r.get('reason')),'unexplained n/a')
        require(r['baseline_ratio']['value'] is not None or bool(r['baseline_ratio']['reason']),'unexplained baseline n/a')
    axes={'ratio','encode','decode','region','amplification','batch','h_alpha','c_g','break_even'}
    summary=[]
    for adapter in m['adapters']:
        plan=adapter['plan'];items={x['axis']:x for x in adapter['measurements']}
        require(set(items)==axes,'incomplete axis selection')
        for item in items.values():
            if item['value'] is None:
                require(item['reason'] and not any(s in item['reason'] for s in ('not ported','not connected','not implemented')),'migration gap disguised as n/a')
        values={k:v['value'] for k,v in items.items()}
        for axis in ('region','amplification'):
            r=values[axis];blob=(root/r['raw_samples']).read_bytes()
            require(hashlib.sha256(blob).hexdigest()==r['raw_sha256'],'raw hash mismatch')
            samples=[json.loads(line) for line in blob.splitlines()]
            require(len(samples)==200 and all(p['verified'] for p in samples),'incomplete region verification')
            if axis=='amplification':require(r['value']==sum(p['decoded_bytes'] for p in samples)/(200*16384),'counter ratio mismatch')
        for axis in ('encode','decode'):
            r=values[axis]
            require('points' in r and (r['value'] is not None)==r['plateau_reached'],'missing or inconsistent plateau')
            tail=r['points'][-3:]
            flat=len(tail)==3 and max(p['value'] for p in tail)/min(p['value'] for p in tail)-1<=.05 and all(p['sample_cv']<=.05 for p in tail)
            require(flat==r['plateau_reached'],'plateau decision differs from evidence')
        if values['c_g']:
            c=values['c_g'];require(c['baseline']['geometry']['nonempty_units']==1,'not a whole-file baseline')
            require([p['granularity'] for p in c['points']]==[4096,16384,65536,262144,1048576],'incomplete c(g) grid')
            for p in c['points']:
                require(p['c_g_percent']==100*(1-c['baseline']['archive_bytes']/p['archive_bytes']),'c(g) formula differs')
                a=dict(p['configuration']);b=dict(c['baseline']['configuration']);a.pop('granularity');b.pop('granularity')
                require(a==b,'c(g) changed another parameter')
        h=values['h_alpha']['profiles'];counts={p['count'] for p in h}
        require(len(h)==5*len(counts) and {p['profile'] for p in h}=={'uniform','sorted','clustered','hot-set','zipf1.2'},'incomplete access profiles')
        if values['batch']:
            require(len(values['batch']['profiles'])==len(h),'incomplete batch profiles')
            require(all(p['threads']==1 and p['verified']=='byte-exact' for p in values['batch']['profiles']),'batch verification or workers differ')
        summary.append({'codec':plan['codec'],'version':plan['version'],'axes':9,'supported':sum(v is not None for v in values.values()),
                        'encode_status':values['encode']['status'],'decode_status':values['decode']['status'],'profile_counts':sorted(counts)})
    return {'status':'pass','records':len(serialized),'corpus_md5':m['corpus_md5'],'adapters':summary}

if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),indent=2))
