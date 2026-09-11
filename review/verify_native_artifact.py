#!/usr/bin/env python3
"""Verify a downloaded native smoke ZIP and its raw-sample/receipt links."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import tempfile
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'harness'))
from native_execution import samples


def verify(path,expected):
    actual=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    def require(test,message):
        if not test: raise ValueError(message)
    require(actual==expected.removeprefix('sha256:'),'ZIP SHA-256 mismatch')
    with zipfile.ZipFile(path) as z:
        def one(suffix):
            names=[n for n in z.namelist() if n.endswith(suffix)]
            require(len(names)==1,'expected exactly one '+suffix)
            return names[0]
        receipt_bytes=z.read(one('/check.json'));receipt=json.loads(receipt_bytes)
        manifest_name=one('/manifest.json');m=json.loads(z.read(manifest_name))
        require(m['schema']=='cabench-native-samples-v1' and m['status']=='pass' and m['published'] is False,'invalid manifest')
        require(receipt['status']=='pass' and len(m['adapters'])==1,'invalid correctness evidence')
        adapter=m['adapters'][0];plan=adapter['plan']
        require(plan['receipt_sha256']==hashlib.sha256(receipt_bytes).hexdigest(),'receipt hash mismatch')
        require(plan['qualification_sha256']==receipt['qualification_sha256'],'qualification mismatch')
        require(plan['codec']==receipt['codec'] and plan['version']==receipt['version'],'codec/version mismatch')
        values={row['axis']:row['value'] for row in adapter['measurements']}
        require(set(values)=={'ratio','region','decode','break_even'},'incomplete smoke axes')
        for phase in ('region','decode'):
            row=values[phase]
            blob=z.read(str(Path(manifest_name).parent/row['raw_samples']))
            require(hashlib.sha256(blob).hexdigest()==row['raw_sha256'],'raw samples hash mismatch')
            with tempfile.TemporaryDirectory() as tmp:
                raw=Path(tmp)/'samples.jsonl';raw.write_bytes(blob)
                points=samples(raw,phase,m['corpus_bytes'])
            require(row['n_samples']==len(points) and row['verified']=='byte-exact','sample metadata mismatch')
            if phase=='region':
                ordered=sorted(p['latency_ms'] for p in points)
                require(row['region_p50_ms']==ordered[99] and row['region_p99_ms']==ordered[197],'percentile mismatch')
            else:
                require(row['full_decode_median_ms']==statistics.median(p['wall_ms'] for p in points),'decode median mismatch')
                require(row['plateau_status']=='data_edge','single-size smoke is not plateau evidence')
        b=values['break_even']
        require(b['region']==values['region'] and b['decode']==values['decode'],'break-even did not reuse samples')
        require(b['break_even_N']==math.floor(values['decode']['full_decode_median_ms']/values['region']['region_p50_ms'])+1,'break-even mismatch')
        ratio=values['ratio'];stored=sum(x['bytes'] for x in ratio['archive_artifacts'].values())
        require(ratio['archive_bytes']==stored and ratio['ratio']==m['corpus_bytes']/stored,'archive accounting mismatch')
        return {'zip_sha256':actual,'codec':plan['codec'],'version':plan['version'],
                'manifest_sha256':hashlib.sha256(z.read(manifest_name)).hexdigest(),
                'receipt_sha256':plan['receipt_sha256'],'qualification_sha256':plan['qualification_sha256'],
                'corpus_sha256':m['corpus_sha256'],'corpus_bytes':m['corpus_bytes'],
                'region_samples':200,'decode_samples':5,'required_archive_files':len(ratio['archive_artifacts']),
                'break_even_reuses_samples':True,'publication':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('zip',type=Path);p.add_argument('sha256')
    args=p.parse_args();print(json.dumps(verify(args.zip,args.sha256),indent=2))
