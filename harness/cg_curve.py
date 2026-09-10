#!/usr/bin/env python3
"""Five measured block sizes; descriptive tradeoffs, never a novelty/winner claim."""
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

ROOT = Path(__file__).resolve().parents[1]
GRID = (4096, 16384, 65536, 262144, 1048576)
ZSTD_SHA = "f8745da6ff1ad1e7bab384bd1f9d742439278e99"
GROUP = "cg-five-point-v1"
CODECS = ("aceapex-cg-default", "zstd-seekable-cg", "bgzip-cg")
CLEAR = tuple(sorted(set(CLEARED_ENV) | {"ZSTD_CLEVEL", "ZSTD_NBTHREADS", "GZIP"}))
FORMULA = "100 * (1 - ratio_g / ratio_whole) = 100 * (1 - bytes_whole / bytes_g)"


def digest(p, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with Path(p).open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def clean_env(env):
    return {k: v for k, v in env.items() if k not in CLEAR and not k.startswith("ACEAPEX_")}


def loss(blocked, whole):
    if blocked <= 0 or whole <= 0: raise ValueError("nonpositive archive size")
    return 100 * (1 - whole / blocked)


def seek_geometry(path, size, g):
    """Read the reference seek table, including checksums and any empty final frame."""
    with path.open("rb") as f:
        f.seek(-9, 2)
        n, flags, magic = struct.unpack("<IBI", f.read(9))
        if magic != 0x8F92EAB1 or flags & 0x7f: raise ValueError("bad seek footer")
        entry = 12 if flags & 0x80 else 8
        table_bytes = 8 + n * entry + 9
        if table_bytes > path.stat().st_size: raise ValueError("oversized seek table")
        f.seek(-table_bytes, 2)
        skippable, payload = struct.unpack("<II", f.read(8))
        if skippable != 0x184D2A5E or payload != table_bytes - 8: raise ValueError("bad seek table")
        entries = [struct.unpack("<" + "I" * (entry // 4), f.read(entry)) for _ in range(n)]
    lengths = [e[1] for e in entries]
    positive = [v for v in lengths if v]
    expected = [min(g, size - p) for p in range(0, size, g)]
    if positive != expected or sum(e[0] for e in entries) + table_bytes != path.stat().st_size:
        raise ValueError("seek geometry/complete-file accounting mismatch")
    return dict(num_blocks=n, nonempty_blocks=len(positive), actual_max_block_bytes=max(positive),
                block_size_histogram=dict(collections.Counter(lengths)), seek_table_bytes=table_bytes,
                seek_table_checksums=bool(flags & 0x80))


def bgzf_geometry(path, size, g):
    lengths = []
    with path.open("rb") as f:
        while head := f.read(18):
            if len(head) != 18 or head[:4] != b"\x1f\x8b\x08\x04" or head[12:16] != b"BC\x02\x00":
                raise ValueError("unexpected BGZF header")
            total = struct.unpack_from("<H", head, 16)[0] + 1
            tail = f.read(total - 18)
            if total < 26 or len(tail) != total - 18: raise ValueError("short BGZF block")
            lengths.append(struct.unpack_from("<I", tail, len(tail) - 4)[0])
    positive = [n for n in lengths if n]
    if sum(positive) != size or not positive or max(positive) > min(g, 65536):
        raise ValueError("BGZF geometry mismatch")
    return dict(num_blocks=len(positive), actual_max_block_bytes=max(positive),
                block_size_histogram=dict(collections.Counter(lengths)))


def validate(rows):
    if len(rows) != len(CODECS) * len(GRID): raise ValueError("incomplete five-point grid")
    seen = set()
    reference_trace = None
    if len({r["run_id"] for r in rows}) != 1: raise ValueError("mixed runs")
    if len({r["benchmark_commit"] for r in rows}) != 1: raise ValueError("mixed benchmark commits")
    for r in rows:
        key = r["codec"], r["g"]
        if key in seen or key[0] not in CODECS or key[1] not in GRID: raise ValueError("duplicate/unexpected point")
        seen.add(key)
        if r["formula"] != FORMULA or r["corpus"]["bytes"] != CORPUS_SIZE or r["corpus"]["md5"] != "9465e0f0df6e2c6eb39729c39cee5465":
            raise ValueError("wrong corpus/formula")
        if r["codec"] == "bgzip-cg":
            if r["value"] is not None or r["status"] != "n/a" or not r.get("reason"):
                raise ValueError("BGZF must not acquire a fictitious strict baseline")
            if r["g"] > 65536:
                if r["point"] is not None: raise ValueError("unsupported BGZF point")
                continue
        p = r["point"]
        if not p or not p["full_restore_byte_equal"] or p["restore_md5"] != r["corpus"]["md5"]:
            raise ValueError("missing exact restore")
        if not p["commands"] or not p["archive_sha256"]: raise ValueError("missing provenance")
        if p['geometry']['actual_max_block_bytes'] > r['g']:
            raise ValueError('independent unit exceeds requested g')
        if not math.isclose(p["ratio"], CORPUS_SIZE / p["total_bytes"], rel_tol=1e-12): raise ValueError("bad ratio")
        samples = p["region_samples"]
        if len(samples) != 200 or not all(s["verified"] and s["requested_bytes"] == 16384 for s in samples):
            raise ValueError("bad region samples")
        times = sorted(s["latency_ms"] for s in samples)
        if not all(math.isfinite(t) and t >= 0 for t in times): raise ValueError("invalid latency")
        if [p["p50_ms"], p["p99_ms"]] != [times[99], times[197]]: raise ValueError("bad quantiles")
        trace = [(s["query"], s["byte_offset"], s["requested_bytes"]) for s in samples]
        if [t[0] for t in trace] != list(range(200)) or any(t[1] < 0 or t[1]+t[2] > CORPUS_SIZE for t in trace):
            raise ValueError('bad query indices/bounds')
        if reference_trace is None: reference_trace = trace
        elif trace != reference_trace: raise ValueError("different byte-region operations")
        if r["codec"] != "bgzip-cg":
            if r['versions']['aceapex_sha'] != ACEAPEX_SHA or r['versions']['zstd_sha'] != ZSTD_SHA:
                raise ValueError('unpinned codec revision')
            b = r["baseline"]
            if not b["full_restore_byte_equal"] or b["restore_md5"] != r["corpus"]["md5"] or not b["commands"]:
                raise ValueError("baseline not verified")
            if b["geometry"].get("nonempty_blocks", b["geometry"]["num_blocks"]) != 1:
                raise ValueError("baseline is not one whole-input block")
            if not math.isclose(b["ratio"], CORPUS_SIZE / b["total_bytes"], rel_tol=1e-12): raise ValueError("bad baseline ratio")
            if r["status"] != "measured" or not math.isclose(r["value"], loss(p["total_bytes"], b["total_bytes"]), abs_tol=1e-10):
                raise ValueError("bad c(g)")
    for codec in CODECS[:2]:
        curve = [r for r in rows if r["codec"] == codec]
        for field in ("configuration", "baseline", "versions", "source_provenance", "hardware"):
            if len({json.dumps(r[field], sort_keys=True) for r in curve}) != 1:
                raise ValueError("changed parameter beyond block size: " + field)
    return rows


def render(rows):
    validate(rows)
    first = rows[0]
    out = ["# Density versus independent-access granularity", "",
           "Five measured sizes, one corpus, identical 16,384-byte API requests. No new measure or predetermined winner is claimed.", "",
           f"Run: {first['run_id']}; benchmark SHA: `{first['benchmark_commit']}`.",
           f"Corpus: chr1 hg38, {CORPUS_SIZE} bytes, MD5 `{first['corpus']['md5']}`.",
           "", "`c(g) = 100 × (1 − ratio_g / ratio_whole) = 100 × (1 − bytes_whole / bytes_g)`.",
           "Ratio counts complete archives plus required indexes. This is ratio loss, not archive-size increase relative to the baseline. Negative values and nonmonotone curves are retained.", "",
           "| Codec | requested g bytes | actual max block | ratio g | ratio whole | archive+index bytes g | baseline bytes | c(g) % | p50 ms | p99 ms | encoder threads |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for codec in CODECS:
        for r in sorted((r for r in rows if r['codec'] == codec), key=lambda r: r['g']):
            p, b = r['point'], r['baseline']
            if p is None:
                out.append(f"| {codec} | {r['g']} | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 1 |")
                continue
            br = f"{b['ratio']:.6f}" if b else "n/a"
            cost = f"{r['value']:.6f}" if r['value'] is not None else "n/a"
            out.append(f"| {codec} | {r['g']} | {p['geometry']['actual_max_block_bytes']} | {p['ratio']:.6f} | {br} | {p['total_bytes']} | {b['total_bytes'] if b else 'n/a'} | {cost} | {p['p50_ms']:.6f} | {p['p99_ms']:.6f} | {r['configuration']['encoder_threads']} |")
    out += ["", "## Measured variation (not a monotone fit)", ""]
    for codec in CODECS[:2]:
        curve = sorted((r for r in rows if r['codec'] == codec), key=lambda r: r['g'])
        vals = [r['value'] for r in curve]
        out.append(f"- {codec}: c(g) range {min(vals):.6f}–{max(vals):.6f}%; span {max(vals)-min(vals):.6f} percentage points over 4 KiB–1 MiB. Raw points, including reversals, are shown above.")
    out += ["", "BGZF: the adapter flushes at 4 KiB, 16 KiB or htslib's safe BGZF_BLOCK_SIZE at the 64 KiB request. Actual geometry is parsed from every archive. 256 KiB and 1 MiB independent BGZF blocks are unsupported. Strict c(g) is n/a at every point: this format/adapter cannot supply a one-block whole-input baseline. A 32 KiB DEFLATE history window is NOT a set of independent blocks.", "",
            "ACEAPEX uses unchanged ee5a37e Makefile-built src/aceapex_main.cpp, default level 2 and 8 requested encoder threads. Only ACEAPEX_BS varies; this is NOT the interactive or dense profile. Its API includes the same src/aceapex_main.cpp, and both translation units are checked in the compiler trace.", "",
            "zstd uses the unchanged reference seekable_compression program, level 3, 1 thread, seek-table checksums enabled, for BOTH sides. The baseline has one nonempty frame spanning the input and a seek table. This is a newly measured baseline, not the earlier CLI-versus-seekable pair. Internal behavior induced by frame size remains part of this operational comparison.", "",
            "Region measurements reuse harness/region_latency.c: resident archive/handle, 10 random warmups plus 2 boundary checks, 200 byte-verified queries, nearest-rank percentiles, API-only timer. API worker policies are codec-owned; no equal-thread full-decode claim is made. No FASTA transformation, batch speed, amplification or plateau throughput is inferred from this sweep.", "",
            "## Provenance and both commands", "", "All records, samples, versions, commands and source hashes are in results.jsonl (evidence group cg-five-point-v1).", ""]
    for codec in CODECS:
        rr = [r for r in rows if r['codec'] == codec]
        r = rr[0]
        out += ["### " + codec, "", "```json", json.dumps({'configuration':r['configuration'], 'versions':r['versions'], 'hardware':r['hardware']}, indent=2), "```"]
        if r['baseline']:
            b = r['baseline']
            out += ["", f"Whole-input baseline: {b['total_bytes']} bytes; ratio {b['ratio']:.12f}.", "```bash", *b['commands'], "```"]
        for row in rr:
            p = row['point']
            if p: out += ["", f"g={row['g']}: {p['total_bytes']} bytes; ratio {p['ratio']:.12f}.", "```bash", *p['commands'], "```"]
    out += ["", "Stop for review. This curve does not establish a corpus-independent law, a novel repetitiveness measure or exclusive superiority. Physical archive splitting is a separate experiment.", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", type=Path, default=ROOT/".work/cg-curve")
    ap.add_argument("--render", type=Path, help="validate/render existing JSONL without rerunning codecs")
    ns = ap.parse_args()
    if ns.render:
        rr = [json.loads(l) for l in ns.render.read_text().splitlines() if l]
        print(render([r for r in rr if r.get('evidence_group') == GROUP]))
        return
    work = ns.work.resolve(); work.mkdir(parents=True, exist_ok=True)
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
    meta = dict(evidence_group=GROUP,run_id=dt.datetime.now(dt.timezone.utc).isoformat(),benchmark_commit=run(['git','rev-parse','HEAD']).strip(),
                corpus=corpus,versions=versions,hardware=hardware,source_provenance=provenance,
                build_commands=commands.copy(),cleared_environment=list(CLEAR),formula=FORMULA,metric='cg_curve_ratio_loss_percent',unit='percent')
    rows = []
    def measure(codec,g,baseline=False):
        label = f'{codec}-{g}'; arc=work/(label+'.archive'); restored=work/(label+'.restore')
        start=len(commands); overrides={'ACEAPEX_BS':str(g)} if codec==CODECS[0] else None
        if codec==CODECS[0]:
            run([a/'aceapex','c','--in',fa,'--out',arc,'--threads','8'],overrides=overrides)
            geometry=archive_record(arc)
            if geometry['block_size'] != g or geometry['num_blocks'] != math.ceil(CORPUS_SIZE/g): raise RuntimeError('ACEAPEX block mismatch')
            geometry['actual_max_block_bytes']=min(g,CORPUS_SIZE)
            run([a/'aceapex','d','--in',arc,'--out',restored,'--threads','8'],overrides=overrides)
        elif codec==CODECS[1]:
            generated=Path(str(fa)+'.zst')
            if generated.exists(): raise RuntimeError('unexpected existing reference output')
            run([compressor,fa,str(g),'3']); generated.replace(arc)
            # Relocation is explicitly retained for exact command replay.
            commands.append(shlex.join(['mv',str(generated),str(arc)]))
            geometry=seek_geometry(arc,CORPUS_SIZE,g)
            # Use the reference seekable decoder for full restore.
            run([work/'seekable_decompression',arc],target=restored)
        else:
            info=json.loads(run([work/'cg_bgzip',fa,arc,str(g)]))
            geometry=dict(bgzf_geometry(arc,CORPUS_SIZE,g),**info)
            run(['bgzip','-d','-c',arc],target=restored)
        if digest(restored,'md5') != corpus['md5'] or not filecmp.cmp(fa,restored,shallow=False): raise RuntimeError(label+' restore mismatch')
        index=Path(str(arc)+'.gzi'); index_bytes=index.stat().st_size if index.exists() else 0
        total=arc.stat().st_size+index_bytes
        rec=dict(archive_bytes=arc.stat().st_size,index_bytes=index_bytes,total_bytes=total,ratio=CORPUS_SIZE/total,
                 archive_sha256=digest(arc),index_sha256=digest(index) if index.exists() else None,geometry=geometry,
                 full_restore_byte_equal=True,restore_md5=corpus['md5'])
        if not baseline:
            api={CODECS[0]:'aceapex',CODECS[1]:'zstd-seekable',CODECS[2]:'bgzip+htslib'}[codec]
            samples_file=work/(label+'-regions.jsonl')
            run([work/'region_latency',api,arc,fa,'latency'],overrides=overrides,target=samples_file)
            samples=[json.loads(l) for l in samples_file.read_text().splitlines()]
            ts=sorted(s['latency_ms'] for s in samples)
            rec.update(region_samples=samples,samples_sha256=digest(samples_file),p50_ms=ts[99],p99_ms=ts[197])
        rec['commands']=commands[start:]
        restored.unlink()
        return rec
    for codec in CODECS:
        baseline=measure(codec,CORPUS_SIZE,True) if codec!=CODECS[2] else None
        config=dict(codec=codec,encoder_threads=8 if codec==CODECS[0] else 1,
                    level=2 if codec==CODECS[0] else 3 if codec==CODECS[1] else 6,
                    profile='default; no overrides except ACEAPEX_BS' if codec==CODECS[0] else None)
        for g in GRID:
            p=measure(codec,g) if codec!=CODECS[2] or g<=65536 else None
            row=dict(meta,codec=codec,g=g,configuration=config,point=p,baseline=baseline,
                     status='measured' if baseline else 'n/a',value=loss(p['total_bytes'],baseline['total_bytes']) if baseline else None,
                     reason=None if baseline else 'BGZF cannot provide a one-block whole-input baseline with only block size changed; requested blocks above 65536 are unsupported')
            rows.append(row)
            (work/'curve.pending.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
            print(f'CG_POINT {codec} g={g}: '+(str(row['value']) if baseline else 'strict n/a'),file=sys.stderr,flush=True)
    validate(rows)
    report=render(rows)
    # Preserve every pre-existing measurement byte for byte, replace only this group.
    dest=ROOT/'results.jsonl'
    previous=dest.read_text().splitlines(keepends=True) if dest.exists() else []
    keep=[l for l in previous if json.loads(l).get('evidence_group')!=GROUP]
    from report import render as render_main
    readme = render_main([json.loads(l) for l in keep] + rows)
    pending=work/'results.complete.jsonl'
    pending.write_text(''.join(keep)+''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    pending.replace(dest)
    (work/'curve.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    (ROOT/'CG_CURVE_RESULTS.md').write_text(report)
    (ROOT/'README.md').write_text(readme)
    print(report)
    print('STOP: five-point curve verified; review before merge.',file=sys.stderr)


if __name__ == '__main__':
    main()
