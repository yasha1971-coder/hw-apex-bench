#!/usr/bin/env python3
"""Compare fresh matched CPU metrics; retain excluded historical scopes explicitly."""
import collections
import hashlib
import json
from pathlib import Path
import sys
FROZEN='cb52b8cb9fac484a6474d976681ea85ae2c052d80d820422b7f57c25ec938100'
METRICS={'ratio':'ratio','region_p50':'region:p50','region_p99':'region:p99',
         'amplification':'amplification','break_even_n':'break_even',
         'encode_throughput_mb_s':'encode','full_decode_throughput_mb_s':'decode'}


def compare(historical,manifest_path):
    raw=Path(historical).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=FROZEN:raise ValueError('published 435 bytes changed')
    old=[json.loads(s) for s in raw.splitlines()]
    m=json.loads(Path(manifest_path).read_text());p=Path(manifest_path).parent
    payload=(p/'results.jsonl').read_bytes()
    if hashlib.sha256(payload).hexdigest()!=m['results_sha256']:raise ValueError('new result hash mismatch')
    new=[json.loads(s) for s in payload.splitlines()]
    index={(r['codec'],r['axis']):r for r in new if r['axis'] in METRICS.values()}
    comparisons=[]
    for row in old:
        if row['metric'] not in METRICS:continue
        r=index.get((row['codec'],METRICS[row['metric']]))
        if not r:continue
        versions=row.get('versions',{})
        expected=versions.get('htslib') if row['codec']=='bgzip+htslib' else versions.get('aceapex_sha') if row['codec'].startswith('aceapex-') else '1.5.7'
        version_matches=expected is not None and str(r['version']).removeprefix('aceapex@')==expected
        cfg=row.get('configuration',{});current=r['configuration']
        old_env=cfg.get('reader_environment',{})
        config_matches=all(current.get('reader_environment',{}).get(k)==v for k,v in old_env.items()) and current.get('level')==cfg.get('level')
        corpus_matches=r['corpus_md5']==row['corpus']['md5']
        comparisons.append({'codec':row['codec'],'metric':row['metric'],'old':row['value'],'new':r['value'],
            'same_codec_version':version_matches,'same_declared_parameters':config_matches,'same_corpus':corpus_matches,
            'new_over_old':r['value']/row['value'] if row['value'] and r['value'] is not None else None,
            'limitation':'new native callback boundary/build; absolute timings are host-specific'})
    result={'historical_records':len(old),'historical_sha256':FROZEN,'historical_bytes_preserved':True,
        'new_records':len(new),'new_sha256':m['results_sha256'],'new_run_id':m['run_id'],
        'fresh_bytes_equal_historical':payload==raw,'comparisons':comparisons,
        'historical_scopes':dict(collections.Counter(r.get('run_id') for r in old)),
        'excluded_from_equality_claim':['owner-declared GPU rows are not remeasured CPU results',
            'historical default c(g) at ee5 differs from new checked profile curves at 1b13',
            'historical zstd frontier configurations and auxiliary loop/relative rows have a different output layout',
            'new timings cannot be expected to reproduce old wall-clock bytes'],
        'conclusion':'native nine-axis execution checked; no claim of byte-identical fresh measurements or complete historical row replay'}
    (p/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    r=compare(sys.argv[1],sys.argv[2]);print(json.dumps({k:r[k] for k in ('historical_records','historical_bytes_preserved','new_records','fresh_bytes_equal_historical','conclusion')},indent=2))
