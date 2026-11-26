# SPDX-License-Identifier: Apache-2.0
"""Owned, untimed casefix dependencies, FASTA inputs, mapped traces and archives.

CLI: setup.py prepare; setup.py case --corpus chr1|t2t-00..t2t-29.
No import side effects, clocks, performance workers or benchmark lock.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
STATE = ROOT / '.work/hw-region-2/casefix'
OLD = ROOT / 'evidence/hw-region-1'
PIN = '58e20daa898a6fc338eae82e5d2ef7108d4fc07f'
URL = 'https://github.com/dpryan79/lib2bit.git'
OLD_LINE = b"if(seq[pos] != 'N') seq[pos] = tolower(seq[pos]);"
NEW_LINE = b'seq[pos] = tolower(seq[pos]);'
CORPORA = ['chr1'] + [f't2t-{i:02d}' for i in range(30)]
PINS = {'aceapex': 'ce6b6740c7aae8a01720d615ae024c181b7d52b6',
        'zstd': 'f8745da6ff1ad1e7bab384bd1f9d742439278e99',
        'htslib': '4b705e4fada8ee2b6b15746f725ee8ac51631803',
        'libdeflate': 'dd12ff2b36d603dbb7fa8838fe7e7176fcbd4f6f'}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def load(path):
    return json.loads(Path(path).read_bytes())


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def artifact(path):
    path = Path(path).resolve()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def check(record):
    p = Path(record['path'])
    require(p.is_file() and p.stat().st_size == record['bytes'] and sha(p) == record['sha256'], 'artifact changed: ' + str(p))


def check_tree(value):
    if isinstance(value, dict):
        if {'path', 'bytes', 'sha256'} <= value.keys():
            check(value)
        for item in value.values():
            check_tree(item)
    elif isinstance(value, list):
        for item in value:
            check_tree(item)


def immutable(path, raw):
    path = Path(path)
    require(path.resolve().is_relative_to(STATE.resolve()) or path.resolve().is_relative_to(HERE), 'output escaped casefix scope')
    if path.exists():
        require(path.read_bytes() == raw, 'refuse changed/partial output: ' + str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as out:
            out.write(raw)


def copy(record, target):
    check(record)
    target = Path(target)
    require(target.resolve().is_relative_to(STATE.resolve()), 'copy escaped owned state')
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        with Path(record['path']).open('rb') as src, target.open('xb') as dst:
            shutil.copyfileobj(src, dst)
    result = artifact(target)
    require((result['bytes'], result['sha256']) == (record['bytes'], record['sha256']), 'staged copy differs')
    return result


def environment(extra=None):
    blocked = {'LD_PRELOAD', 'LD_LIBRARY_PATH', 'LIBRARY_PATH', 'CPATH', 'C_INCLUDE_PATH', 'CC', 'CXX',
               'CFLAGS', 'CPPFLAGS', 'LDFLAGS', 'MAKEFLAGS', 'ZSTD_CLEVEL', 'ZSTD_NBTHREADS'}
    result = {k: v for k, v in os.environ.items() if k not in blocked
              and not k.startswith(('ACEAPEX_', 'AX_', 'LIT_', 'FSE_'))}
    result.update(extra or {})
    return result


def run(label, argv, *, outputs=(), extra=None, stdout_path=None):
    folder = STATE / 'commands' / label
    receipt = folder / 'command.json'
    identity = dict(argv=['taskset', '-c', '15', *map(str, argv)], environment=extra or {},
                    outputs=list(map(str, outputs)), stdout_path=str(stdout_path) if stdout_path else None)
    if receipt.exists():
        old = load(receipt)
        require(old['status'] == 'COMPLETE' and old['identity'] == identity, 'unfinished/changed command: ' + label)
        check_tree(old['artifacts'])
    else:
        require(not folder.exists() and all(not Path(p).exists() for p in outputs), 'orphan/partial command: ' + label)
        folder.mkdir(parents=True)
        receipt.write_bytes(packed(dict(status='STARTED', identity=identity)))
        out = Path(stdout_path).open('xb') if stdout_path else subprocess.PIPE
        try:
            proc = subprocess.run(identity['argv'], cwd=ROOT, env=environment(extra), stdout=out, stderr=subprocess.PIPE)
        finally:
            if stdout_path:
                out.close()
        immutable(folder / 'stdout', proc.stdout or b'')
        immutable(folder / 'stderr', proc.stderr)
        files = [folder / 'stdout', folder / 'stderr', *[Path(p) for p in outputs if Path(p).is_file()]]
        old = dict(identity=identity, status='COMPLETE' if proc.returncode == 0 else 'ERROR', returncode=proc.returncode,
                   artifacts=[artifact(p) for p in files])
        receipt.write_bytes(packed(old))
    for p in folder.iterdir():
        immutable(HERE / 'commands' / label / p.name, p.read_bytes())
    require(old['status'] == 'COMPLETE', 'command failed: ' + label)
    return old


def git(*args, repo=ROOT):
    return subprocess.check_output(['git', '-C', str(repo), *args], env=environment())


def provenance():
    files = [HERE / n for n in ('CALIBRATION.md', 'PROTOCOL.md', 'setup.py')]
    files += [PARENT / n for n in ('writer.py', 'CALIBRATION.md', 'lib2bit-casefix.patch')]
    for p in files:
        name = p.relative_to(ROOT).as_posix()
        git('ls-files', '--error-unmatch', '--', name)
        require(not git('status', '--porcelain', '--', name).strip(), 'uncommitted setup input: ' + name)
    admission = load(PARENT / 'admission.json')
    require(sha(PARENT / 'writer.py') == admission['identity']['source_sha256']['evidence/hw-region-2/writer.py'], 'original writer changed')
    require(sha(PARENT / 'CALIBRATION.md') == admission['identity']['source_sha256']['evidence/hw-region-2/CALIBRATION.md'], 'original forecasts changed')
    require((HERE / 'CALIBRATION.md').read_bytes() == (PARENT / 'CALIBRATION.md').read_bytes(), 'casefix calibration must preserve the four original lines')
    return dict(source_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in files},
                original_admission=artifact(PARENT / 'admission.json'), region1_setup=artifact(OLD / 'setup.json'),
                parent_preflight=artifact(PARENT / 'input-preflight.json'), region1_chr1_archives=artifact(OLD / 'archives/chr1-g16384.json'))


def reused_dependencies():
    old = load(OLD / 'setup.json')
    require(old['schema'] == 'hw-region-1-setup-v1', 'wrong REGION-1 setup')
    for name, pin in PINS.items():
        r = old['deps'][name]
        require(r['commit'] == pin and git('rev-parse', 'HEAD', repo=r['path']).decode().strip() == pin
                and not git('status', '--porcelain', '--untracked-files=no', repo=r['path']).strip(), 'readonly dependency changed: ' + name)
        for relative, digest in r['headers_sha256'].items():
            require(sha(Path(r['path']) / relative) == digest, 'readonly header changed')
        if 'library_path' in r:
            require(sha(r['library_path']) == r['library_sha256'], 'readonly library changed')
    check_tree(old['binaries'])
    return old


def lib2bit():
    repo = STATE / 'deps/lib2bit'
    if not repo.exists():
        run('lib2bit-clone', ['git', 'clone', '--no-checkout', URL, repo])
        run('lib2bit-checkout', ['git', '-C', repo, 'checkout', '--detach', PIN])
    require(not repo.is_symlink() and repo.resolve().is_relative_to(STATE.resolve()), 'dependency escaped owned state')
    require(git('rev-parse', 'HEAD', repo=repo).decode().strip() == PIN
            and git('remote', 'get-url', 'origin', repo=repo).decode().strip() == URL
            and not git('status', '--porcelain', '--untracked-files=no', repo=repo).strip(), 'lib2bit pin/source differs')
    original = (repo / '2bit.c').read_bytes()
    require(original.count(OLD_LINE) == 1, 'one-line casefix site is not unique')
    modified = original.replace(OLD_LINE, NEW_LINE, 1)
    patch = (PARENT / 'lib2bit-casefix.patch').read_bytes().splitlines()
    removed = [line[1:] for line in patch if line.startswith(b'-') and not line.startswith(b'---')]
    added = [line[1:] for line in patch if line.startswith(b'+') and not line.startswith(b'+++')]
    original_line = next(line for line in original.splitlines() if OLD_LINE in line)
    require(removed == [original_line] and added == [original_line.replace(OLD_LINE, NEW_LINE)], 'committed patch differs from the sole source change')
    run('compiler-version', ['gcc', '--version'])
    run('archiver-version', ['ar', '--version'])
    variants = {}
    for name, raw in (('original', original), ('casefix', modified)):
        folder = STATE / 'build' / name
        source, obj, library = folder / '2bit.c', folder / '2bit.o', folder / 'lib2bit.a'
        immutable(source, raw)
        run(name + '-compile', ['gcc', '-O3', '-fPIC', '-I' + str(repo), '-c', source, '-o', obj], outputs=(obj,))
        run(name + '-static', ['ar', 'rcs', library, obj], outputs=(library,))
        variants[name] = dict(source_path=str(source), source_sha256=sha(source), library_path=str(library),
                              library_sha256=sha(library), object=artifact(obj))
    require(not git('status', '--porcelain', '--untracked-files=no', repo=repo).strip(), 'casefix build modified dependency source')
    return dict(path=str(repo), commit=PIN, url=URL, header_path=str(repo / '2bit.h'), header_sha256=sha(repo / '2bit.h'),
                license=artifact(repo / 'LICENSE'), original_source=artifact(repo / '2bit.c'),
                patch=artifact(PARENT / 'lib2bit-casefix.patch'), variants=variants,
                compiler=dict(gcc=artifact(Path(shutil.which('gcc')).resolve()), ar=artifact(Path(shutil.which('ar')).resolve()),
                              gcc_version=artifact(HERE / 'commands/compiler-version/stdout'),
                              ar_version=artifact(HERE / 'commands/archiver-version/stdout')))


def writer_module():
    spec = importlib.util.spec_from_file_location('hw_region_2_writer', PARENT / 'writer.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mapped_trace(corpus, source, fai):
    old_path = OLD / 'traces' / (corpus + '.json')
    old = load(old_path)
    require(old['input_sha256'] == source['sha256'] and old['input_bytes'] == source['bytes'], 'old trace/source identity differs')
    stats, mapped = {}, {}
    for key, count, old_key in (('warmups', 12, 'warmup_offsets'), ('requests', 1000, 'offsets')):
        offsets = old[old_key]
        require(len(offsets) == count and hashlib.sha256(b''.join(struct.pack('<Q', p) for p in offsets)).hexdigest() == old[key]['sha256'], 'old trace bytes differ')
        counts = dict(header=0, line_terminator=0, clamped=0, terminal=0, end_in_last_packed_byte=0)
        result = []
        for off in offsets:
            require(type(off) is int and 0 <= off <= source['bytes'] - 16384, 'old offset outside original input')
            if corpus == 'chr1':
                delta = off - fai['offset']
                if delta < 0:
                    base = 0; counts['header'] += 1
                else:
                    row, column = divmod(delta, fai['line_width'])
                    counts['line_terminator'] += column >= fai['line_bases']
                    base = row * fai['line_bases'] + min(column, fai['line_bases'])
            else:
                base = off
            start = min(base, fai['length'] - 16384)
            counts['clamped'] += start != base
            counts['terminal'] += start + 16384 == fai['length']
            counts['end_in_last_packed_byte'] += (start + 16383) // 4 == (fai['length'] - 1) // 4
            result.append(start)
        target = STATE / 'traces' / corpus / (key + '.bin')
        immutable(target, b''.join(struct.pack('<Q', p) for p in result))
        mapped[key], stats[key] = dict(**artifact(target), offsets=result), counts
    value = dict(schema='hw-region-2-casefix-trace-v1', corpus=corpus, original_trace=artifact(old_path),
                 seed_integer=old['seed_integer'], resampled=False, request_bases=16384, sequence_length=fai['length'],
                 mapping='chr1: header->0; row*line_bases+min(column,line_bases); clamp to sequence_length-R; T2T: original bases-only offsets unchanged',
                 fai_geometry=fai, statistics=stats, max_end0=max(mapped['requests']['offsets']) + 16384, **mapped)
    target = HERE / 'traces' / (corpus + '.json')
    immutable(target, packed(value))
    return artifact(target)


def prepare():
    identity = provenance()
    old = reused_dependencies()
    public = HERE / 'setup.json'
    if public.exists():
        value = load(public)
        require(value['identity'] == identity and (STATE / 'setup.json').read_bytes() == public.read_bytes(), 'setup identity changed')
        require(lib2bit() == value['lib2bit'], 'cached original/casefix library identity changed')
        check_tree(value['retained_artifacts'])
        return value
    libraries = lib2bit()
    writer = writer_module()
    inputs = {}
    for corpus in CORPORA:
        original = old['inputs'][corpus]
        check(original)
        path = STATE / 'inputs' / (corpus + '.fa')
        if corpus == 'chr1':
            fasta = copy(original, path)
            sequence_sha = next(r['sequence_sha256'] for r in load(PARENT / 'input-preflight.json')['records'] if r['corpus'] == corpus)
        else:
            sequence = Path(original['path']).read_bytes()
            require(len(sequence) == 2097152 and hashlib.sha256(sequence).hexdigest() == original['frozen_window']['input_sha256'], 'frozen window changed')
            immutable(path, ('>' + corpus + '\n').encode() + b''.join(sequence[p:p + 80] + b'\n' for p in range(0, len(sequence), 80)))
            fasta, sequence_sha = artifact(path), original['sha256']
        meta = writer.write_fasta(path, STATE / 'writer' / corpus, fasta['sha256'], sequence_sha)
        compressed = HERE / 'writer-metadata' / (corpus + '.json.gz')
        immutable(compressed, gzip.compress(packed(meta), mtime=0))
        archive = {k: v for k, v in meta['archive'].items() if k not in ('n_blocks', 'mask_blocks')}
        trace = mapped_trace(corpus, original, meta['fai']['geometry'])
        inputs[corpus] = dict(**fasta, original=original, sequence=meta['sequence'], fai=meta['fai'], twobit=archive,
                              writer_metadata=artifact(compressed), trace=trace, structural_check=meta['structural_check'])
    files = [p for folder in (STATE / 'inputs', STATE / 'writer', STATE / 'traces', STATE / 'build') for p in folder.rglob('*') if p.is_file()]
    value = dict(schema='hw-region-2-casefix-setup-v1', identity=identity, deps=old['deps'], binaries=old['binaries'],
                 lib2bit=libraries, inputs=inputs, corpus_order=CORPORA, no_clocks=True, measurements_of_time=False,
                 borrowed_compiler=old['compiler'],
                 retained_artifacts=[artifact(p) for p in files], host=dict(hostname=platform.node(), kernel=platform.release(), cpu_affinity=[15]))
    immutable(STATE / 'setup.json', packed(value)); immutable(public, packed(value))
    return value


def identical(left, right):
    with Path(left).open('rb') as a, Path(right).open('rb') as b:
        while True:
            x, y = a.read(1 << 20), b.read(1 << 20)
            require(x == y, 'full restored bytes differ')
            if not x:
                return


def case(corpus):
    setup = prepare()
    require(corpus in CORPORA, 'unknown corpus')
    source = setup['inputs'][corpus]
    public = HERE / 'archives' / (corpus + '.json')
    if public.exists():
        value = load(public)
        require(value['setup_sha256'] == sha(HERE / 'setup.json'), 'archive setup changed')
        check_tree(value)
        return value
    folder = STATE / 'archives' / corpus
    folder.mkdir(parents=True, exist_ok=True)
    formats = {}
    bins = setup['binaries']
    old_case = load(OLD / 'archives/chr1-g16384.json') if corpus == 'chr1' else None
    for codec in ('aceapex', 'zstd_seekable', 'bgzip'):
        receipt = folder / (codec + '.json')
        if receipt.exists():
            record = load(receipt)
            require(record['setup_sha256'] == sha(HERE / 'setup.json'), 'partial archive setup changed')
            check_tree(record); formats[codec] = record; continue
        fai = copy(source['fai'], folder / (codec + '.fai'))
        if old_case:
            old = old_case['formats'][codec]
            check_tree(old)
            require(old['bit_perfect'] is True and old['effective_g'] == 16384 and old['restore_sha256'] == source['sha256'], 'old chr1 archive identity differs')
            path = Path(old['path'])
            restored = path.parent / (codec + '.restored')
            require(sha(restored) == source['sha256'], 'retained old full restore hash differs')
            identical(source['path'], restored)
            indexes = [fai] + (old['indexes'] if codec == 'bgzip' else [])
        else:
            path = folder / {'aceapex': 'aceapex.aet', 'bgzip': 'bgzf.bgz', 'zstd_seekable': 'source.fa.zst'}[codec]
            if codec == 'aceapex':
                argv = [bins['aceapex']['path'], 'c', '--in', source['path'], '--out', path, '--threads', '1', '--level', '2']
                extra = {'ACEAPEX_BS': '16384', 'LIT_CHUNK': '65536', 'FSE_CHUNK': '4096'}
            elif codec == 'bgzip':
                argv = [bins['bgzf-encode-g']['path'], source['path'], path, '16384']; extra = {}
            else:
                alias = folder / 'source.fa'; copy(source, alias)
                argv = [bins['zstd-seekable-compress']['path'], alias, '16384', '3']; extra = {}
            outputs = (path, Path(str(path) + '.gzi')) if codec == 'bgzip' else (path,)
            run('archive-' + corpus + '-' + codec, argv, outputs=outputs, extra=extra)
            indexes = [fai] + ([artifact(str(path) + '.gzi')] if codec == 'bgzip' else [])
            restored = folder / (codec + '.restored')
            if codec == 'aceapex':
                run('restore-' + corpus + '-' + codec, [bins['aceapex']['path'], 'd', '--in', path, '--out', restored, '--threads', '1'], outputs=(restored,))
            else:
                binary = bins['zstd' if codec == 'zstd_seekable' else 'bgzip']['path']
                run('restore-' + corpus + '-' + codec, [binary, '-d', '-c', path], outputs=(restored,), stdout_path=restored)
            require(sha(restored) == source['sha256'], 'full restore SHA differs')
            identical(source['path'], restored)
        check(source)
        record = dict(**artifact(path), indexes=indexes, stored_bytes=path.stat().st_size + sum(i['bytes'] for i in indexes),
                      effective_g=16384, level={'aceapex': 2, 'zstd_seekable': 3, 'bgzip': 6}[codec],
                      reused_region1=bool(old_case), bit_perfect=True, restore=artifact(restored),
                      setup_sha256=sha(HERE / 'setup.json'))
        immutable(receipt, packed(record)); formats[codec] = record
    formats['twobit'] = dict(**source['twobit'], indexes=[], stored_bytes=source['twobit']['bytes'],
                             structural_bit_perfect=True, sequence_sha256=source['sequence']['sha256'])
    value = dict(schema='hw-region-2-casefix-archives-v1', corpus=corpus, g=16384, request_bases=16384,
                 input={k: source[k] for k in ('path', 'bytes', 'sha256')}, sequence=source['sequence'], fai=source['fai'],
                 trace=source['trace'], writer_metadata=source['writer_metadata'], formats=formats, setup_sha256=sha(HERE / 'setup.json'))
    immutable(public, packed(value))
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('prepare', 'case'))
    p.add_argument('--corpus', choices=CORPORA)
    args = p.parse_args()
    require(sys.platform == 'linux' and platform.node() == 'ace-core', 'ace-core Linux required')
    require(not os.environ.get('OVH_BENCH_LOCK_HELD') and not STATE.is_symlink(), 'untimed owned setup outside benchmark lock required')
    os.sched_setaffinity(0, {15})
    require(os.sched_getaffinity(0) == {15}, 'CPU15 required')
    value = prepare() if args.mode == 'prepare' else case(args.corpus)
    print(args.mode.upper(), value['schema'], args.corpus or len(value['inputs']))


if __name__ == '__main__':
    main()
