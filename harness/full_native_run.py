#!/usr/bin/env python3
"""Authorized full native comparison, isolated from the published results file."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'.work/native-full'


def main():
    from native_comparison import FROZEN
    if hashlib.sha256((ROOT/'results.jsonl').read_bytes()).hexdigest()!=FROZEN:
        raise ValueError('historical publication differs before full run')
    WORK.mkdir(parents=True,exist_ok=False)
    spec=json.loads((ROOT/'corpora.json').read_text())['chr1_hg38'];corpus=WORK/'chr1.fa'
    with urllib.request.urlopen(spec['url'],timeout=120) as response, gzip.GzipFile(fileobj=response) as src, corpus.open('wb') as out:
        shutil.copyfileobj(src,out,1024*1024)
    h=hashlib.md5()
    with corpus.open('rb') as src:
        for b in iter(lambda:src.read(1024*1024),b''):h.update(b)
    if h.hexdigest()!=spec['md5']:raise ValueError('corpus MD5 mismatch')
    codecs=['bgzip_1_19','zstd_seekable','aceapex','aceapex_dense']
    for codec in codecs:
        print('Qualify '+codec,flush=True)
        with (WORK/(codec+'-check.log')).open('w') as log:
            subprocess.run(['./run.sh','--check','codecs/'+codec+'.sh'],cwd=ROOT,stdout=log,stderr=log,check=True)
    command=['./run.sh','--measure','--input',str(corpus),'--output-dir',str(WORK/'run'),
             '--plateau','--baseline','bgzip_1_19']
    for codec in codecs:command+=['--codec',codec]
    for axis in ('ratio','encode','decode','region','amplification','batch','h_alpha','c_g','break_even'):
        command+=['--axis',axis]
    print('Run all nine axes; full logs remain in the artifact',flush=True)
    with (WORK/'measure.log').open('w') as log:
        subprocess.run(command,cwd=ROOT,stdout=log,stderr=log,check=True)
    subprocess.run(['python3','review/verify_nine_axes.py',str(WORK/'run/manifest.json')],cwd=ROOT,check=True)
    subprocess.run(['python3','harness/native_comparison.py','results.jsonl',str(WORK/'run/manifest.json')],cwd=ROOT,check=True)
    print('Full candidate artifact complete; publication unchanged',flush=True)

if __name__=='__main__':main()
