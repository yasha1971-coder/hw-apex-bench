#!/usr/bin/env python3
"""Reordered native BGZF response experiment; no throughput claims.

Requires a SHA-pinned Axis4 plan. Requests execute synchronously; only the
htslib BGZF decoder owns worker threads. Independent FASTA verification runs
for every repetition, including every response SHA and selected response bytes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
from tools import axis4
from tools.axis4_evidence_verify import verify
from review.axis3.verdict_data import checked_file, file_ref, load_json


def experiment(root, plan_name, out_name, repeats=20, seed=20261009):
    root=Path(root).resolve(strict=True)
    if type(repeats) is not int or repeats < 20:
        raise ValueError('race experiment requires at least 20 repetitions')
    _,plan,prepared,_=axis4.load_plan(root,plan_name)
    if plan['reader']['family'] != 'bgzf' or prepared['evidence_kind'] != 'synthetic':
        raise ValueError('requires synthetic native BGZF plan')
    out=axis4.new_output(root,out_name)
    reference=None;records=[]
    for rep in range(repeats):
        shuffled=json.loads(json.dumps(prepared))
        random.Random(seed+rep).shuffle(shuffled['groups'])
        prefix=out/f'repetition-{rep:02d}'
        prefix.mkdir()
        axis4.write_json(prefix/'prepared.json',shuffled)
        p={**plan,'prepared':file_ref(root,prefix/'prepared.json')}
        axis4.write_json(prefix/'plan.json',p)
        for n in (1,2,8,16):
            run_name=(prefix/f'threads-{n}').relative_to(root).as_posix()
            d=axis4.run(root,(prefix/'plan.json').relative_to(root).as_posix(),run_name,decoder_threads=n)
            if d['status'] != 'PASS':raise ValueError(d['error'])
            receipt=verify(root/run_name/'evidence.json',root,p['prepared']['sha256'])
            identities=sorted([(r['assembly'],r['canonical']['contig_id'],r['canonical']['start0'],
                       r['canonical']['end0'],r['length'],r['observed_sha256']) for r in d['rows']])
            if reference is None:reference=identities
            if identities != reference:raise ValueError('responses differ by threads/order/repetition')
            records.append({'repetition':rep,'threads':n,'evidence':file_ref(root,root/run_name/'evidence.json'),
                            'verification':receipt})
    result={'schema':'axis4-thread-experiment-v1','status':'PASS','seed':seed,'repeats':repeats,
            'decoder_threads':[1,2,8,16],'runs':records,'responses_per_run':len(reference),
            'response_identity_sha256':hashlib.sha256(json.dumps(reference,separators=(',',':')).encode()).hexdigest()}
    axis4.write_json(out/'acceptance.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('root','plan','out'):p.add_argument('--'+k,required=True)
    p.add_argument('--repeats',type=int,default=20);p.add_argument('--seed',type=int,default=20261009)
    a=p.parse_args();r=experiment(a.root,a.plan,a.out,a.repeats,a.seed)
    print(json.dumps({k:v for k,v in r.items() if k!='runs'},sort_keys=True))


if __name__=='__main__':main()
