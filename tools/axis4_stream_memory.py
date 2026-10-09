#!/usr/bin/env python3
"""Synthetic truth-only memory probe. Offline, gzip-only, never a codec timing."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import time
import tracemalloc

from tools.axis4_stream import prepare_truth
from tools.axis4_evidence_verify import independent_truth
from review.axis3.verdict_data import sha256_file, write_json


def worker(path,size):
    queries=[(i,{'contig_id':'c','start0':p,'end0':p+1024}) for i,p in
             enumerate((0,2048,size//2,size-1024))]
    tracemalloc.start()
    start=time.perf_counter_ns()
    identity, hashes=prepare_truth(path,queries)
    elapsed=time.perf_counter_ns()-start
    _, prepare_peak=tracemalloc.get_traced_memory()
    tracemalloc.stop()
    tracemalloc.start()
    start=time.perf_counter_ns()
    observed,buffers=independent_truth(path,queries,{0,1,2,3},identity)
    verify_elapsed=time.perf_counter_ns()-start
    _, verify_peak=tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if hashes!=observed or sum(len(v) for v in buffers.values())!=4096:
        raise ValueError('memory probe correctness failed')
    return {'sequence_bytes':size,'compressed_bytes':path.stat().st_size,
            'compressed_sha256':sha256_file(path), 'truth':identity['truth'],
            'canonical_sha256':identity['canonical_sha256'],
            'prepare_traced_peak_bytes':prepare_peak,'verify_traced_peak_bytes':verify_peak,
            'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),
            'prepare_elapsed_ns':elapsed,'verify_elapsed_ns':verify_elapsed,
            'queries':4,'sample_bytes':4096,'status':'PASS'}


def benchmark(out,sizes=(1048576,8388608,67108864)):
    out=Path(out).resolve()
    out.mkdir(parents=True,exist_ok=False)
    rows=[]
    for size in sizes:
        p=out/(str(size)+'.fa.gz')
        # Compress only bounded generated pieces; never store a plain FASTA.
        with p.open('xb') as file:
            with gzip.GzipFile(fileobj=file,mode='wb',mtime=0,filename='') as stream:
                stream.write(b'>c synthetic-fixed-pattern\n')
                chunk=(b'acgtNRYC'*8192)
                for offset in range(0,size,len(chunk)):
                    stream.write(chunk[:min(len(chunk),size-offset)])
                stream.write(b'\n')
        result=subprocess.run([sys.executable,'-m','tools.axis4_stream_memory','--worker',str(p),
                               '--size',str(size)],capture_output=True,text=True,check=True,timeout=120)
        rows.append(json.loads(result.stdout))
    # A bounded-reader regression criterion, recorded before interpreting timing.
    for field in ('prepare_traced_peak_bytes','verify_traced_peak_bytes'):
        if max(r[field] for r in rows)>2097152:
            raise ValueError('truth probe exceeded fixed 2 MiB Python-allocation budget')
    receipt={'status':'PASS','scope':'synthetic-truth-only, excludes native decoder workspace',
             'pattern':'acgtNRYC repeated; no random sampling; four fixed 1024-byte windows',
             'criterion':'each traced peak <= 2097152 bytes; input size increases with fixed queries',
             'uncompressed_FASTA_files':0,'chunk_bytes':65536,'header_limit_bytes':4096,
             'platform':sys.platform,'python':sys.version,
             'implementation_sha256':{name:sha256_file(Path(__file__).parent/name) for name in (
                 'axis4_stream.py','axis4_evidence_verify.py','axis4_stream_memory.py')},
             'rows':rows,'performance_valid':False}
    write_json(out/'memory.json',receipt)
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path)
    p.add_argument('--worker',type=Path)
    p.add_argument('--size',type=int)
    a=p.parse_args()
    if a.worker:
        result=worker(a.worker,a.size)
    elif a.out:
        result=benchmark(a.out)
    else:
        p.error('--out or --worker required')
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    main()
