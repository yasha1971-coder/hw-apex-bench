#!/usr/bin/env python3
"""Tiny real-native Axis 4 CLI acceptance. Output is synthetic, never a benchmark."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys

from review.axis3 import bgzf_adapter, agc_adapter
from review.axis3.verdict_data import file_ref, load_json, sha256_file, write_json
from review.axis3.verdict_readers import REFREL_PIN, ZSTD_PIN
from tools.axis4_evidence_verify import verify

REPO = Path(__file__).resolve().parents[1]


def command(argv, **kwargs):
    return subprocess.run([str(x) for x in argv], check=True, text=True, capture_output=True, **kwargs)


def acceptance(root, family, library, encoder, source_root, variant=None):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    library, source_root = Path(library).resolve(strict=True), Path(source_root).resolve(strict=True)
    commit = command(['git','-C',source_root,'rev-parse','HEAD']).stdout.strip()
    if command(['git','-C',source_root,'status','--porcelain']).stdout:
        raise ValueError('native source checkout is not clean')
    expected = {'refrel3':REFREL_PIN, 'zstd-seekable':ZSTD_PIN,
                'bgzf':bgzf_adapter.HTS_PIN, 'fasta-faidx':bgzf_adapter.HTS_PIN, 'agc':agc_adapter.PIN}[family]
    if commit != expected:
        raise ValueError('native source pin mismatch')
    lib = root / library.name
    shutil.copyfile(library, lib)
    rng = random.Random(20261003)
    base = bytes(rng.choice(b'ACGT') for _ in range(12288))
    assemblies, sequences = [], {}
    for i, aid in enumerate(('asm1','asm2')):
        seq = bytearray(base)
        for pos in range(i, len(seq), 127):
            seq[pos] = b'ACGT'[(b'ACGT'.index(seq[pos])+i+1)%4]
        sequences[aid] = bytes(seq)
        fasta = root / (aid+'.fa')
        with fasta.open('wb') as f:
            for name,start,end in (('chr',0,8192),('tail',8192,12288)):
                f.write(('>'+name+'\n').encode())
                for pos in range(start,end,79):
                    f.write(seq[pos:min(end,pos+79)]+b'\n')
        assemblies.append({'assembly_id':aid,'source_url':'synthetic:seed-20261003/'+aid,
                           'fasta':file_ref(root,fasta)})
    groups = []
    for i in range(20):
        contig = 'tail' if i % 3 == 0 else 'chr'
        start = i * 83
        groups.append({a:{'assembly_id':a,'contig_id':contig,'start0':start,'end0':start+1024}
                       for a in sequences})
    write_json(root/'groups.json', groups)
    write_json(root/'cohort.json', {'schema':'axis4-corpus-v1','evidence_kind':'synthetic','assemblies':assemblies})
    invocations = []

    def cli(*args):
        argv = [sys.executable,'-m','tools.axis4',*map(str,args)]
        got = command(argv, cwd=REPO)
        invocations.append({'argv':argv,'returncode':got.returncode,'stdout':got.stdout,'stderr':got.stderr})
        return json.loads(got.stdout)

    prepared = cli('prepare','--root',root,'--manifest','cohort.json','--groups','groups.json',
                   '--out','prepared')['prepared']
    L = ctypes.CDLL(str(lib))
    if family in ('refrel3','zstd-seekable'):
        L.ZSTD_versionString.restype=ctypes.c_char_p
        dependencies={'libzstd':L.ZSTD_versionString().decode()}
    elif family == 'agc':
        dependencies={'source_submodules':command(['git','-C',source_root,'submodule','status','--recursive']).stdout}
    else:
        L.hwa_bgzf_version.restype=ctypes.c_char_p
        dependencies={'htslib':L.hwa_bgzf_version().decode(),
                      'libdeflate_commit':bgzf_adapter.LIBDEFLATE_PIN}
    receipt = {
        'source_commit':commit,'codec_version':{'refrel3':'frozen-v1','zstd-seekable':'1.5.7',
                                               'bgzf':'1.24','fasta-faidx':'1.24','agc':'3.2.4'}[family],
        'compiler':command(['g++' if family=='refrel3' else 'gcc','--version']).stdout.splitlines()[0],
        'flags':['-O3','-fPIC','-shared'], 'dependencies':dependencies,
        'library_sha256':sha256_file(lib),'decoder_threads':1,
        'evidence_kind':'synthetic', 'provenance_scope':'clean source pin, loaded dependency versions, library SHA; build logs retained separately'}
    write_json(root/'build.json',receipt)
    variant = variant or {'refrel3':'q4k','zstd-seekable':'default','bgzf':'default','fasta-faidx':'plain','agc':'noref'}[family]
    spec={'family':family,'variant':variant,'library':file_ref(root,lib),
          'build_receipt':file_ref(root,root/'build.json'),'archives':[]}
    if family=='refrel3':
        spec['reference']=file_ref(root,root/'asm1.fa')
    if family == 'agc':
        archive=root/'cohort.agc'
        creation=agc_adapter.create(Path(encoder),[(a['assembly_id'],root/a['fasta']['path']) for a in assemblies],
                                    variant,archive,root/'asm1.fa' if variant=='t2t' else None)
        receipt.update(creation)
        (root/'build.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
        spec['build_receipt']=file_ref(root,root/'build.json')
        spec['archive']=file_ref(root,archive)
        del spec['archives']
        if variant=='t2t':spec['reference']=file_ref(root,root/'asm1.fa')
    for assembly in ([] if family=='agc' else assemblies):
        aid=assembly['assembly_id']; source=root/(aid+'.fa')
        entry={'assembly_id':aid}
        if family=='refrel3':
            archive=root/(aid+'.rr3')
            q={'q4k':4096,'q16k':16384}[variant]
            got=command([encoder,'encode',root/'asm1.fa',q,1,source,archive])
            invocations.append({'argv':[str(encoder),'encode',str(root/'asm1.fa'),str(q),'1',str(source),str(archive)],
                                'returncode':got.returncode,'stdout':got.stdout,'stderr':got.stderr})
        elif family=='zstd-seekable':
            raw=root/(aid+'.raw');raw.write_bytes(sequences[aid])
            got=command([encoder,raw,4096,3])
            archive=Path(str(raw)+'.zst')
            mapping=root/(aid+'.map.json')
            write_json(mapping,{'canonical_bytes':len(sequences[aid]),'contigs':[
                {'assembly_id':aid,'contig_id':'chr','prefix':0,'length':8192},
                {'assembly_id':aid,'contig_id':'tail','prefix':8192,'length':4096}]})
            entry['contig_map']=file_ref(root,mapping)
        elif family=='bgzf':
            archive=root/(aid+'.bgz')
            bgzf_adapter.create(encoder,lib,source,archive)
            entry['fai']=file_ref(root,Path(str(archive)+'.fai'))
            entry['gzi']=file_ref(root,Path(str(archive)+'.gzi'))
        else:
            archive=source
            loaded=bgzf_adapter.library(lib)
            if loaded.hwa_bgzf_index(str(source).encode()) != 0:
                raise ValueError('FASTA indexing failed')
            entry['fai']=file_ref(root,Path(str(source)+'.fai'))
        entry['archive']=file_ref(root,archive)
        spec['archives'].append(entry)
    write_json(root/'plan.json',{'schema':'axis4-plan-v1','prepared':prepared,'reader':spec})
    cli('run','--root',root,'--plan','plan.json','--out','evidence')
    result=cli('verify','--evidence',root/'evidence/evidence.json','--input-root',root,
               '--prepared-sha256',prepared['sha256'])
    if result['verified'] != 40 or result['sample_bytes_verified'] != 32 or result['evidence_kind'] != 'synthetic':
        raise ValueError('synthetic acceptance count/kind')
    # A non-sampled response must also be judged.
    evidence=root/'evidence/evidence.json'; data=load_json(evidence)
    rid=next(row['id'] for row in data['rows'] if row['id'] not in data['sample_ids'])
    data['rows'][rid]['observed_sha256']='0'*64
    bad=root/'evidence/tampered.json';write_json(bad,data)
    try:
        verify(bad,root,prepared['sha256'])
    except ValueError:
        tamper='REJECTED'
    else:
        raise AssertionError('non-sampled SHA tamper accepted')
    receipt={'status':'PASS','family':family,'variant':variant,'evidence_kind':'synthetic',
             'verified':40,'sample_bytes_verified':32,'unsampled_tamper':tamper,
             'library_sha256':sha256_file(lib),'prepared_sha256':prepared['sha256'],
             'invocations':invocations}
    write_json(root/'acceptance.json',receipt)
    return {k:v for k,v in receipt.items() if k!='invocations'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True)
    p.add_argument('--family',required=True,choices=['refrel3','zstd-seekable','bgzf','fasta-faidx','agc'])
    p.add_argument('--library',required=True)
    p.add_argument('--encoder',required=True)
    p.add_argument('--source-root',required=True)
    p.add_argument('--variant')
    a=p.parse_args()
    print(json.dumps(acceptance(a.root,a.family,a.library,a.encoder,a.source_root,a.variant),sort_keys=True))


if __name__=='__main__':
    main()
