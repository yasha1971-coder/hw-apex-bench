#!/usr/bin/env python3
"""Untimed archive equivalence experiment; never invokes measurement workers."""
import ctypes as C
import gzip
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'harness'))
from resident_probe import Context
from native_comparison import FROZEN
from qualification import work_directory
from axis_planner import plan_adapter
from native_results import rows
from datetime import datetime, timezone
import platform
import shlex

HTS = '8f7231035d0409d525767c66d9f49f1f967ee1df'
WORK = ROOT / '.work/bgzf-build-audit'
COMMANDS = []


def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with Path(path).open('rb') as src:
        for b in iter(lambda: src.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def run(argv, *, cwd=ROOT, output=None):
    argv = list(map(str, argv))
    COMMANDS.append({'argv': argv, 'cwd': str(cwd), 'stdout_file': str(output) if output else None})
    with (WORK / 'commands.log').open('ab') as log:
        if output:
            with Path(output).open('wb') as out:
                subprocess.run(argv, cwd=cwd, stdout=out, stderr=log, check=True, timeout=900)
        else:
            subprocess.run(argv, cwd=cwd, stdout=log, stderr=log, check=True, timeout=900)


def libraries(binary):
    listing = subprocess.check_output(['ldd', str(binary)], text=True)
    paths = [Path(line.split('=>', 1)[1].strip().split()[0]) for line in listing.splitlines() if '=> /' in line]
    return {'ldd': listing, 'files': {str(p.resolve()): digest(p) for p in paths}}


def build(backend):
    target = WORK / ('htslib-' + backend)
    run(['git', 'init', '-q', target])
    run(['git', 'remote', 'add', 'origin', 'https://github.com/samtools/htslib.git'], cwd=target)
    run(['git', 'fetch', '-q', '--depth=1', '--no-tags', 'origin', HTS], cwd=target)
    run(['git', 'checkout', '-q', '--detach', 'FETCH_HEAD'], cwd=target)
    run(['git', 'submodule', 'update', '--init', '--depth', '1'], cwd=target)
    headers = '#define _XOPEN_SOURCE 700\n#define HAVE_DRAND48 1\n'
    extra = ['-ldeflate'] if backend == 'libdeflate' else []
    if extra:
        headers += '#define HAVE_LIBDEFLATE 1\n'
    (target / 'config.h').write_text(headers)
    libs = ' '.join(extra + ['-lz', '-lm', '-lpthread'])
    (target / 'config.mk').write_text(f'LIBS = {libs}\nHTS_LIBS = {libs}\nNONCONFIGURE_OBJS =\n')
    run(['make', '-j2', 'lib-static', 'bgzip', 'CFLAGS=-O3 -fPIC', 'PACKAGE_VERSION=1.19'], cwd=target)
    library = WORK / ('context-' + backend + '.so')
    run(['gcc', '-O3', '-std=gnu11', '-fPIC', '-shared', '-I' + str(ROOT / 'harness'),
         '-I' + str(target), ROOT / 'codecs/native/bgzip.c', target / 'libhts.a', *extra,
         '-lz', '-lm', '-pthread', '-o', library])
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=target, text=True).strip() == HTS
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=target).strip()
    return target / 'bgzip', library


def main():
    WORK.mkdir(parents=True, exist_ok=False)
    assert digest(ROOT / 'results.jsonl') == FROZEN
    old = next(r for r in map(json.loads, (ROOT / 'results.jsonl').read_text().splitlines())
               if r['codec'] == 'bgzip+htslib' and r['metric'] == 'ratio')
    old_binary = next(c for c in old['source_provenance']['codecs'] if c['codec'] == 'bgzip+htslib')['binary_sha256']
    report = {'status': 'in_progress', 'timings_collected': False, 'htslib_commit': HTS,
              'historical_results_sha256': FROZEN, 'commands': COMMANDS, 'builds': {}}
    receipt = WORK / 'audit.json'
    try:
        system = Path('/usr/bin/bgzip')
        report['system'] = {'binary_sha256': digest(system), 'historical_binary_sha256': old_binary,
                            'exact_historical_binary': digest(system) == old_binary, 'libraries': libraries(system)}
        report['packages'] = subprocess.check_output(['dpkg-query', '-W', 'tabix', 'libhts3t64', 'libdeflate0', 'zlib1g'], text=True)
        assert report['system']['exact_historical_binary'], 'system binary differs from historical SHA'
        spec = json.loads((ROOT / 'corpora.json').read_text())['chr1_hg38']
        corpus = WORK / 'chr1.fa'
        # Two official UCSC aliases; the immutable uncompressed MD5 is the gate.
        urls = [spec['url'].replace('hgdownload.soe.ucsc.edu','hgdownload.cse.ucsc.edu'), spec['url']]
        report['download_attempts'] = []
        compressed = WORK / 'chr1.fa.gz'
        for url in dict.fromkeys(urls):
            try:
                compressed.unlink(missing_ok=True)
                run(['curl','--ipv4','--fail','--location','--silent','--show-error',
                     '--connect-timeout','20','--max-time','120','--retry','1',
                     '--retry-all-errors','--retry-delay','2',url,'--output',compressed])
                with gzip.open(compressed,'rb') as src, corpus.open('wb') as out:
                    shutil.copyfileobj(src,out,1024*1024)
                if digest(corpus,'md5') != spec['md5']:
                    raise ValueError('downloaded corpus MD5 mismatch')
                report['download_attempts'].append({'url':url,'status':'verified','compressed_sha256':digest(compressed)})
                break
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, EOFError) as error:
                report['download_attempts'].append({'url':url,'status':'failed','error':str(error)})
        else:
            raise ValueError('both official UCSC corpus downloads failed; no compression was run')
        assert digest(corpus, 'md5') == spec['md5']
        report['corpus'] = dict(spec, bytes=corpus.stat().st_size, sha256=digest(corpus))
        run(['./run.sh', '--check', 'codecs/bgzip_1_19.sh'])
        adapter = ROOT / 'codecs/bgzip_1_19.sh'
        qualified_work = work_directory(adapter, ROOT / '.work/adapter-check')
        plan = plan_adapter(adapter, qualified_work, ['ratio'])
        report['qualified_plan'] = plan
        report['pinned_backend'] = json.loads((qualified_work / 'bgzip-build.json').read_text())
        binaries = {'zlib': build('zlib'), 'libdeflate': (qualified_work / 'deps/htslib/bgzip', qualified_work / 'context.so')}
        binaries['system'] = (system, binaries['libdeflate'][1])
        original = corpus.read_bytes()
        for name, (binary, library) in binaries.items():
            print('Verify archive and restoration: ' + name, flush=True)
            archive = WORK / (name + '.bgz')
            index = Path(str(archive) + '.gzi')
            run([binary, '-l', '6', '-@', '1', '-i', '-I', index, '-c', corpus], output=archive)
            restored = WORK / (name + '.restored')
            run([binary, '-d', '-c', archive], output=restored)
            assert digest(restored) == report['corpus']['sha256']
            ctx = Context(library, archive.read_bytes(), sidecar=index)
            try:
                out = C.create_string_buffer(len(original))
                assert ctx.lib.hc_decode(ctx.ptr, out, len(original)) == len(original)
                assert out.raw == original
                rng = random.Random(20260911)
                offsets = [0, 65279, 65280, len(original) - 16384]
                offsets += [rng.randrange(len(original) - 16384 + 1) for _ in range(60)]
                for offset in offsets:
                    n, data = ctx.region(offset, 16384)
                    assert n == 16384 and data == original[offset:offset + 16384]
            finally:
                ctx.close()
            report['builds'][name] = {'binary_sha256': digest(binary), 'libraries': libraries(binary),
                'archive_sha256': digest(archive), 'archive_bytes': archive.stat().st_size,
                'index_sha256': digest(index), 'index_bytes': index.stat().st_size,
                'ratio': len(original) / (archive.stat().st_size + index.stat().st_size),
                'native_library_sha256': digest(library), 'cli_restore': 'byte-exact',
                'native_restore': 'byte-exact', 'regions_verified': len(offsets),
                'matches_historical_archive': digest(archive) == old['archive_sha256'],
                'compress_command':shlex.join(list(map(str,[binary,'-l','6','-@','1','-i','-I',index,'-c',corpus])))+' > '+shlex.quote(str(archive))}
            restored.unlink()
        z, d, s = (report['builds'][n] for n in ('zlib', 'libdeflate', 'system'))
        candidate = json.loads((ROOT / 'review/native-full-comparison.json').read_text())
        zsha = next(r['new'] for r in candidate['deterministic_comparison']['checks']
                    if r['codec'] == 'bgzip+htslib' and r['field'] == 'archive_sha256')
        assert s['matches_historical_archive'] and d['matches_historical_archive']
        assert d['index_sha256'] == s['index_sha256']
        assert z['archive_sha256'] == zsha and not z['matches_historical_archive']
        assert d['ratio'] == old['value'] and d['archive_bytes'] == old['archive_bytes']
        counter = Context(qualified_work/'counter-context.so', (WORK/'libdeflate.bgz').read_bytes(), sidecar=WORK/'libdeflate.bgz.gzi')
        try:
            counter.lib.hc_count_reset.argtypes=[C.c_void_p]
            counter.lib.hc_count_bytes.argtypes=[C.c_void_p]
            counter.lib.hc_count_bytes.restype=C.c_uint64
            counter.lib.hc_count_reset(counter.ptr)
            n, data=counter.region(0,16384)
            assert n==16384 and data==original[:16384]
            count=counter.lib.hc_count_bytes(counter.ptr)
            assert count>=16384, 'libdeflate counter hook missed actual decoder work'
            report['counter_probe']={'requested_bytes':16384,'actual_decoded_bytes':count,'verified':'byte-exact','timings_collected':False}
        finally:
            counter.close()
        audit_manifest={'adapters':[{'plan':plan,'measurements':[{'axis':'ratio','value':{'ratio':d['ratio'],'verified':'byte-exact','n_samples':1,'compress_command':d['compress_command']}}]}],
            'corpus':str(corpus),'corpus_md5':spec['md5'],'run_id':datetime.now(timezone.utc).isoformat(),
            'host':{'os':platform.platform(),'cpu':platform.machine()},'compiler':subprocess.check_output(['gcc','--version'],text=True).splitlines()[0]}
        serialized=rows(audit_manifest,'bgzip_1_19')
        assert serialized[0]['toolchain']['compression_backend']['commit']=='dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f'
        (WORK/'results.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in serialized))
        report['conclusion'] = 'Pinned HTSlib with libdeflate reproduces historical archive and system index; zlib reproduces the full native candidate difference.'
        report['status'] = 'pass'
        assert digest(ROOT / 'results.jsonl') == FROZEN
    except Exception as error:
        report['status'] = 'fail'
        report['error'] = str(error)
        raise
    finally:
        receipt.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
