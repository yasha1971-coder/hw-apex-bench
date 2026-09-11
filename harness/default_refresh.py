#!/usr/bin/env python3
"""Remeasure adaptive default beside explicit profiles on one runner."""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import filecmp
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shlex
import shutil
import struct
import subprocess
import sys
import urllib.request

from aceapex_strict_cg import ACEAPEX_SHA, CORPUS_SIZE, CLEARED_ENV, archive_record
from source_provenance import verify as verify_sources
from configurations import PROFILES

from cg_curve import digest, clean_env, seek_geometry, bgzf_geometry, CLEAR, ZSTD_SHA
ROOT = Path(__file__).resolve().parents[1]
ACEAPEX_SHA = "a194893b676a089e5916063d62c45e77483d2c10"
GROUP = "default-a194893-v1"

def build(work):
    work = work.resolve(); work.mkdir(parents=True, exist_ok=True)
    env = clean_env(os.environ)
    commands = []
    def run(args, *, target=None, overrides=None, cwd=ROOT):
        args = list(map(str, args)); e = dict(env, **(overrides or {}))
        cmd = 'cd ' + shlex.quote(str(cwd)) + ' && env ' + ' '.join('-u '+k for k in CLEAR)
        if overrides: cmd += ' ' + shlex.join(k+'='+str(v) for k,v in sorted(overrides.items()))
        cmd += ' ' + shlex.join(args)
        if target: cmd += ' > ' + shlex.quote(str(target))
        commands.append(cmd); print('+ '+cmd, file=sys.stderr, flush=True)
        (work/'commands.json').write_text(json.dumps(commands, indent=2)+'\n')
        log = work/f'command-{len(commands):04d}.log'
        if target:
            with target.open('wb') as f, log.open('wb') as err:
                subprocess.run(args, cwd=cwd, env=e, stdout=f, stderr=err, check=True, timeout=1200)
            return ''
        p = subprocess.run(args, cwd=cwd, env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1200)
        log.write_text(p.stdout+p.stderr)
        if p.returncode: print((p.stdout+p.stderr)[-4000:],file=sys.stderr)
        p.check_returncode()
        return p.stdout
    for tool in ('git','make','gcc','g++','pkg-config','bgzip'):
        if not shutil.which(tool): raise RuntimeError('missing build dependency: '+tool)
    corpus = json.loads((ROOT/'corpora.json').read_text())['chr1_hg38']
    fa = work/'chr1.fa'
    if not fa.exists():
        tmp = work/'chr1.download'
        with urllib.request.urlopen(corpus['url'], timeout=120) as response, gzip.GzipFile(fileobj=response) as src, tmp.open('wb') as dst:
            shutil.copyfileobj(src,dst,1<<20)
        if digest(tmp,'md5') != corpus['md5']: raise RuntimeError('download MD5 mismatch')
        tmp.replace(fa)
    if fa.stat().st_size != CORPUS_SIZE or digest(fa,'md5') != corpus['md5']: raise RuntimeError('corpus mismatch')
    corpus = dict(corpus, bytes=CORPUS_SIZE, md5_verified=True)
    def checkout(url, sha, path):
        if not path.exists(): run(['git','clone','--no-checkout',url,path])
        elif run(['git','-C',path,'status','--porcelain','--untracked-files=no']).strip(): raise RuntimeError('dirty dependency')
        run(['git','-C',path,'fetch','--depth=1','origin',sha])
        run(['git','-C',path,'checkout','--detach','FETCH_HEAD'])
        if run(['git','-C',path,'rev-parse','HEAD']).strip() != sha: raise RuntimeError('dependency SHA mismatch')
    a, z = work/'aceapex', work/'zstd'
    checkout('https://github.com/yasha1971-coder/aceapex.git', ACEAPEX_SHA, a)
    checkout('https://github.com/facebook/zstd.git', ZSTD_SHA, z)
    trace = work/'compile-trace.jsonl'; trace.unlink(missing_ok=True)
    tracer = [sys.executable,ROOT/'harness/compiler_trace.py','--real']
    cc = shlex.join(map(str,[*tracer,'gcc'])); cxx = shlex.join(map(str,[*tracer,'g++']))
    build_env = {'CABENCH_COMPILE_TRACE':str(trace)}
    run(['make','-C',z/'lib','clean'])
    run(['make','-C',z/'lib','-j2','libzstd.a','CC='+cc],overrides=build_env)
    inc = ['-I'+str(a/'src'),'-I'+str(z/'lib'),'-I'+str(z/'lib/common'),'-I'+str(z/'contrib/seekable_format'),'-DXXH_NAMESPACE=ZSTD_']
    ht = shlex.split(run(['pkg-config','--cflags','--libs','htslib']))
    def compile(compiler, args): run([*tracer,compiler,*args],overrides=build_env)
    run(['make','-C',a,'clean'])
    run(['make','-C',a,'-j2','CXX='+cxx,'ZSTD_CFLAGS=-I'+str(z/'lib'),'ZSTD_LIBS='+str(z/'lib/libzstd.a')],overrides=build_env)
    compressor = work/'seekable_compression'
    compile('gcc',['-O3',*inc,z/'contrib/seekable_format/examples/seekable_compression.c',z/'contrib/seekable_format/zstdseek_compress.c',z/'lib/libzstd.a','-pthread','-o',compressor])
    compile('gcc',['-O3',*inc,'-c',z/'contrib/seekable_format/zstdseek_decompress.c','-o',work/'seek.o'])
    compile('g++',['-O3','-std=c++17','-pthread',*inc,'-c',a/'src/aceapex_api.cpp','-o',work/'api.o'])
    compile('gcc',['-O3',*inc,*ht,'-c',ROOT/'harness/region_latency.c','-o',work/'region.o'])
    compile('g++',[work/'region.o',work/'api.o',work/'seek.o',z/'lib/libzstd.a','-pthread','-ldl',*ht,'-o',work/'region_latency'])
    compile('gcc',['-O3',ROOT/'harness/cg_bgzip.c',*ht,'-o',work/'cg_bgzip'])
    compile('gcc',['-O3',*inc,ROOT/'harness/cg_zstd_restore.c',work/'seek.o',z/'lib/libzstd.a','-pthread','-o',work/'seekable_decompression'])
    specs = [dict(codec='aceapex',repository_root=str(a),expected_commit=ACEAPEX_SHA,required_translation_units=['src/aceapex_main.cpp','src/aceapex_api.cpp']),
             dict(codec='zstd-seekable',repository_root=str(z),expected_commit=ZSTD_SHA,required_translation_units=['contrib/seekable_format/examples/seekable_compression.c','contrib/seekable_format/zstdseek_compress.c','contrib/seekable_format/zstdseek_decompress.c']),
             dict(codec='htslib',status='n/a',reason='installed package, not built from source by this harness',binary=shutil.which('bgzip'),binary_sha256=digest(shutil.which('bgzip')))]
    provenance = verify_sources(trace,specs)
    if '#include "aceapex_main.cpp"' not in (a/'src/aceapex_api.cpp').read_text():
        raise RuntimeError('API no longer includes the Makefile encoder source')
    provenance['api_included_encoder_sha256'] = digest(a/'src/aceapex_main.cpp')
    provenance['binary_sha256'] = {p.name:digest(p) for p in (a/'aceapex',compressor,work/'region_latency',work/'cg_bgzip',work/'seekable_decompression')}
    (work/'source-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    versions = dict(aceapex_sha=ACEAPEX_SHA,zstd_sha=ZSTD_SHA,libzstd='1.5.7 (same pinned static library for both codecs)',
                    compiler=run(['g++','--version']).splitlines()[0],htslib=run(['pkg-config','--modversion','htslib']).strip())
    hardware = dict(platform=platform.platform(),logical_cpus=os.cpu_count(),lscpu=run(['lscpu']))
    return locals()


def literal_layout(path):
    geometry = archive_record(path)
    with path.open('rb') as f:
        f.seek(68 + 64 * geometry['num_blocks'])
        h, second = struct.unpack('<QQ', f.read(16))
    chunked = bool(h & (1 << 61))
    return dict(literal_chunking=chunked, literal_chunk_bytes=second if chunked else None,
                literal_layout='fixed chunks' if chunked else 'legacy coarse partitions',
                literal_header_hex=hex(h), **geometry)


def render(rows):
    names = ['bgzip+htslib', 'zstd-seekable', 'ACEAPEX default', 'ACEAPEX interactive',
             'ACEAPEX dense', 'ACEAPEX explicit legacy']
    if [r['codec'] for r in rows] != names:
        raise ValueError('Incomplete or reordered comparison')
    if len({r['run_id'] for r in rows}) != 1:
        raise ValueError('Mixed runs')
    trace = None
    lines = ['# Default refresh at a194893', '',
             'Same chr1 bytes and runner; complete archive plus required index sizes. One encoder thread requested for every row.', '',
             '| Configuration | block bytes | literal mode | archive+index bytes | ratio | region p50 ms | region p99 ms |',
             '|---|---:|---|---:|---:|---:|---:|']
    for r in rows:
        if not r['full_restore_byte_equal'] or r['restore_md5'] != r['corpus']['md5']:
            raise ValueError('Unverified restore')
        if not math.isclose(r['ratio'], CORPUS_SIZE/r['total_bytes'], rel_tol=1e-12):
            raise ValueError('Invalid archive ratio')
        if r['region_status'] == 'n/a':
            if r['geometry'].get('literal_chunking') is not False or r['p50_ms'] is not None or r['p99_ms'] is not None:
                raise ValueError('Invalid no-chunking annotation')
            p50 = p99 = 'n/a — no literal chunking'
        else:
            samples=r['region_samples']
            if len(samples)!=200 or not all(s['verified'] and s['requested_bytes']==16384 for s in samples):
                raise ValueError('Invalid regional responses')
            t=[(s['query'],s['byte_offset'],s['requested_bytes']) for s in samples]
            if trace is None: trace=t
            elif trace!=t: raise ValueError('Different region trace')
            times=sorted(s['latency_ms'] for s in samples)
            if not all(math.isfinite(t) and t>=0 for t in times) or [r['p50_ms'],r['p99_ms']] != [times[99],times[197]]:
                raise ValueError('Invalid percentiles')
            p50,p99=f"{r['p50_ms']:.6f}",f"{r['p99_ms']:.6f}"
        lines.append(f"| {r['codec']} | {r['geometry']['actual_max_block_bytes']} | {r['geometry'].get('literal_layout','format-native')} | {r['total_bytes']} | {r['ratio']:.6f} | {p50} | {p99} |")
    lines += ['', 'The no-chunking marker describes efficient fine-grained access, not the absence of a callable region API. Historical slow region-API observations remain valid and are not relabeled as full-decode benchmarks.',
              '', 'Default on this DNA input and explicit legacy are distinct rows. No text/Silesia result is inferred from chr1. No encode/full-decode throughput is claimed by this refresh.',
              '', 'The reported owner ratio 3.72329 is not an acceptance target: complete-file accounting may differ from CLI payload accounting.',
              '', '## Provenance', '', '```json', json.dumps({k:rows[0][k] for k in ('run_id','benchmark_commit','corpus','versions','hardware')},indent=2,sort_keys=True), '```', '',
              '## Exact commands', '']
    for r in rows:
        lines += [r['codec'], '```sh', *r['commands'], '```', '']
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--work',type=Path,default=ROOT/'.work/default-refresh')
    p.add_argument('--render',type=Path)
    ns=p.parse_args()
    if ns.render:
        print(render([json.loads(s) for s in ns.render.read_text().splitlines()]),end=''); return
    c=build(ns.work)
    work,fa,a,z,run,commands,compressor=(c[k] for k in ('work','fa','a','z','run','commands','compressor'))
    meta=dict(evidence_group=GROUP,run_id=dt.datetime.now(dt.timezone.utc).isoformat(),
              benchmark_commit=run(['git','rev-parse','HEAD']).strip(),corpus=c['corpus'],
              versions=c['versions'],hardware=c['hardware'],source_provenance=c['provenance'],
              build_commands=commands.copy(),encoder_threads=1)
    configs=[('bgzip+htslib',None),('zstd-seekable',None),('ACEAPEX default',None),
             ('ACEAPEX interactive','interactive'),('ACEAPEX dense','dense'),('ACEAPEX explicit legacy','legacy')]
    rows=[]
    for i,(name,profile) in enumerate(configs):
        arc=work/f'archive-{i}'; restored=work/f'restore-{i}'; start=len(commands)
        overrides={'LIT_CHUNK':'0'} if profile=='legacy' else dict(PROFILES[profile]) if profile in PROFILES else None
        if name.startswith('ACEAPEX'):
            args=[a/'aceapex','c','--in',fa,'--out',arc,'--threads','1']
            run(args,overrides=overrides)
            g=literal_layout(arc);g['actual_max_block_bytes']=g['block_size']
            api='aceapex'
            # The legacy FSE container does not encode its chunk size; supply
            # the documented reader value for explicitly named profiles.
            reader=overrides
            if profile in PROFILES and (g['block_size'] != int(overrides['ACEAPEX_BS']) or g['literal_chunk_bytes'] != int(overrides['LIT_CHUNK'])):
                raise RuntimeError('Encoded geometry does not match explicit profile')
            run([a/'aceapex','d','--in',arc,'--out',restored,'--threads','1'],overrides=reader)
        elif name=='zstd-seekable':
            run([compressor,fa,'16384','3'])
            generated=Path(str(fa)+'.zst');generated.replace(arc)
            commands.append(shlex.join(['mv',str(generated),str(arc)]))
            g=seek_geometry(arc,CORPUS_SIZE,16384)
            run([work/'seekable_decompression',arc],target=restored)
            api=name;reader=None
        else:
            run([work/'cg_bgzip',fa,arc,'65536'])
            g=bgzf_geometry(arc,CORPUS_SIZE,65536)
            run(['bgzip','-d','-c',arc],target=restored)
            api=name;reader=None
        if digest(restored,'md5')!=c['corpus']['md5'] or not filecmp.cmp(fa,restored,shallow=False):
            raise RuntimeError(name+' full restore differs')
        index=Path(str(arc)+'.gzi');total=arc.stat().st_size+(index.stat().st_size if index.exists() else 0)
        r=dict(meta,codec=name,encoder_environment=overrides or {},reader_environment=reader or {},geometry=g,total_bytes=total,archive_bytes=arc.stat().st_size,
               index_bytes=index.stat().st_size if index.exists() else 0,
               archive_sha256=digest(arc),index_sha256=digest(index) if index.exists() else None,
               ratio=CORPUS_SIZE/total,full_restore_byte_equal=True,restore_md5=digest(restored,'md5'),
               p50_ms=None,p99_ms=None,region_status='n/a',region_samples=[])
        if g.get('literal_chunking',True):
            samples_file=work/f'regions-{i}.jsonl'
            run([work/'region_latency',api,arc,fa,'latency'],overrides=reader,target=samples_file)
            ss=[json.loads(l) for l in samples_file.read_text().splitlines()];ts=sorted(s['latency_ms'] for s in ss)
            r.update(region_status='measured',region_samples=ss,samples_sha256=digest(samples_file),p50_ms=ts[99],p99_ms=ts[197])
        r['commands']=commands[start:];rows.append(r);restored.unlink()
        (work/'results.pending.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    text=render(rows)
    (work/'results.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    if render([json.loads(l) for l in (work/'results.jsonl').read_text().splitlines()])!=text:
        raise RuntimeError('Report replay differs')
    (ROOT/'DEFAULT_RESULTS.md').write_text(text)
    print(text)


if __name__=='__main__': main()
