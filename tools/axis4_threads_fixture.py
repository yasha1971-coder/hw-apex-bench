#!/usr/bin/env python3
"""Generate multi-block matched-g BGZF and run genuine native worker acceptance."""
import argparse
from pathlib import Path
import random
import shutil
from review.axis3.bgzf_adapter import create
from review.axis3.verdict_data import file_ref, load_json, sha256_file, write_json
from tools import axis4
from tools.axis4_threads_synthetic import experiment


def fixture(out, library, receipt):
    library,receipt=Path(library).resolve(strict=True),Path(receipt).resolve(strict=True)
    provenance=load_json(receipt)
    if provenance['library_sha256']!=sha256_file(library):raise ValueError('build receipt/library SHA mismatch')
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(library,out/'libhwa_bgzf.so');shutil.copyfile(receipt,out/'build.json')
    assemblies=[];archives=[]
    for i in (1,2):
        aid=f'asm{i}';seq=bytes(random.Random(20261009+i).choices(b'ACGTN',k=262144))
        fasta=out/f'{aid}.fa'
        with fasta.open('wb') as f:
            for name,part in (('chr',seq[:131072]),('tail',seq[131072:])):
                f.write(b'>'+name.encode()+b'\n')
                for start in range(0,len(part),70):f.write(part[start:start+70]+b'\n')
        archive=out/f'{aid}.bgz'
        create(None,out/'libhwa_bgzf.so',fasta,archive,'matched-g',4096)
        assemblies.append({'assembly_id':aid,'source_url':'synthetic:A12-multiblock', 'fasta':file_ref(out,fasta)})
        archives.append({'assembly_id':aid,'archive':file_ref(out,archive),'fai':file_ref(out,Path(str(archive)+'.fai')),
                         'gzi':file_ref(out,Path(str(archive)+'.gzi'))})
    groups=[]
    for i in range(40):
        start=(i*4096+3550)%(131072-2048)
        groups.append({a['assembly_id']:{'assembly_id':a['assembly_id'],'contig_id':'chr' if i%2==0 else 'tail',
                        'start0':start,'end0':start+2048} for a in assemblies})
    write_json(out/'cohort.json',{'schema':'axis4-corpus-v1','evidence_kind':'synthetic','assemblies':assemblies})
    write_json(out/'groups.json',groups)
    prepared=axis4.prepare(out,'cohort.json','groups.json','prepared')
    write_json(out/'plan.json',{'schema':'axis4-plan-v1','prepared':prepared,'reader':{
        'family':'bgzf','variant':'matched-g','granule_raw_bytes':4096,'library':file_ref(out,out/'libhwa_bgzf.so'),
        'build_receipt':file_ref(out,out/'build.json'),'archives':archives}})
    return experiment(out,'plan.json','thread-experiment')


if __name__=='__main__':
    import json
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('out','library','receipt'):p.add_argument('--'+key,required=True)
    a=p.parse_args();r=fixture(a.out,a.library,a.receipt)
    print(json.dumps({k:v for k,v in r.items() if k!='runs'},sort_keys=True))
