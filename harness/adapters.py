#!/usr/bin/env python3
"""Qualification only: subprocesses are never used as performance timers."""
import argparse
import fcntl
import signal
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
AXES = ('ratio', 'encode', 'decode', 'region', 'amplification', 'c_g', 'batch', 'h_alpha', 'break_even')


def validate_metadata(supported, unavailable):
    if len(set(supported)) != len(supported) or set(supported) - set(AXES):
        raise ValueError('duplicate or unknown capability')
    if set(unavailable) != set(AXES) - set(supported):
        raise ValueError('every unsupported axis needs exactly one reason')
    if any(not isinstance(v, str) or not v.strip() for v in unavailable.values()):
        raise ValueError('empty n/a reason')
    if not {'ratio', 'decode'} <= set(supported):
        raise ValueError('qualification requires ratio and full decode')
    if set(supported) & {'h_alpha', 'break_even', 'amplification'} and 'region' not in supported:
        raise ValueError('access-derived axes require region')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(adapter, work):
    adapter = adapter.resolve(strict=True)
    work.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, CABENCH_ROOT=str(ROOT), CABENCH_WORK=str(work))
    log_path = work / (adapter.stem + '-check.log')
    receipt = work / (adapter.stem + '-check.json')
    receipt.unlink(missing_ok=True)  # a failed attempt cannot leave a stale green receipt
    with log_path.open('w') as log:
        def run(args, timeout=120):
            log.write('$ ' + shlex.join(map(str, args)) + '\n'); log.flush()
            p = subprocess.Popen(list(map(str, args)), env=env, stdout=subprocess.PIPE,
                                 stderr=log, text=True, start_new_session=True)
            try:
                stdout, _ = p.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.communicate()
                raise
            if p.returncode:
                log.write(stdout); log.flush()
                raise RuntimeError(f'command failed ({p.returncode}); details: {log_path}')
            return stdout.strip()
        def call(fn, *args, **kwargs):
            return run(['bash', adapter, '_call', fn, *args], **kwargs)
        name, version = call('codec_name'), call('codec_version')
        supported = call('codec_supports').split()
        unavailable = json.loads(call('codec_unavailable'))
        validate_metadata(supported, unavailable)
        constraints = json.loads(call('codec_constraints'))
        minimum = constraints['min_input_bytes']
        if type(minimum) is not int or minimum not in (0, 1):
            raise ValueError('v1 qualification supports minimum input sizes 0 or 1')
        if minimum and not constraints.get('min_input_reason'):
            raise ValueError('minimum input size needs a reason')
        granularity = constraints['granularity']
        if type(granularity) is not int or not 1 <= granularity <= 1048576:
            raise ValueError('invalid qualification granularity')
        sources = json.loads(call('codec_sources'))
        if not sources or any(len(s['sha']) != 40 or any(c not in '0123456789abcdef' for c in s['sha']) for s in sources):
            raise ValueError('dependencies require full commit SHA pins')
        compiler = shlex.split(env.get('CC', 'gcc'))
        run([*compiler, '-O2', ROOT/'harness/adapter_worker.c', '-ldl', '-o', work/'adapter_worker'])
        print(f'{name}: building pinned sources (log: {log_path})', flush=True)
        log.write(call('codec_build', timeout=1200) + '\n'); log.flush()
        library = Path(call('codec_library')).resolve(strict=True)
        native = json.loads(run([work/'adapter_worker', library, 'probe']))
        expected = sum(1 << AXES.index(a) for a in supported)
        if not name or not version or '\n' in name or '\n' in version:
            raise ValueError('codec name/version must be one nonempty line')
        if (native['name'], native['version'], native['capabilities']) != (name, version, expected):
            raise ValueError('native ABI and shell metadata disagree')
        for source in sources:
            dep = work/'deps'/source['directory']
            if run(['git', '-C', dep, 'rev-parse', 'HEAD']) != source['sha']:
                raise ValueError('dependency SHA mismatch')
            if run(['git', '-C', dep, 'status', '--porcelain', '--untracked-files=no']):
                raise ValueError('tracked dependency sources modified')
            source['submodules'] = run(['git', '-C', dep, 'submodule', 'status', '--recursive'])
        corpus = json.loads((ROOT/'corpora.json').read_text())['adapter_smoke']
        downloaded = work/'smoke-corpus'
        if not downloaded.exists() or hashlib.md5(downloaded.read_bytes()).hexdigest() != corpus['md5']:
            with urllib.request.urlopen(corpus['url'], timeout=60) as response:
                payload = response.read(1048577)
            if hashlib.md5(payload).hexdigest() != corpus['md5']:
                raise ValueError('downloaded corpus MD5 mismatch')
            downloaded.write_bytes(payload)
        checks = []
        with tempfile.TemporaryDirectory(prefix='qualification-', dir=work) as tmp:
            tmp = Path(tmp)
            fixtures = [('downloaded', downloaded.read_bytes()),
                        ('binary', bytes(range(256))*1025 + b'\x00\xff\x80'),
                        ('dna', b'>fixture\n'+b'ACGTN'*52429+b'\n'), ('one-byte', b'\xff')]
            if minimum == 0:
                fixtures.append(('empty', b''))
            for label, data in fixtures:
                case = tmp/label; case.mkdir()
                src, arc = case/'input', case/'archive'
                src.write_bytes(data)
                call('codec_compress', src, arc, granularity)
                artifacts = [Path(p).resolve(strict=True) for p in json.loads(call('codec_artifacts', arc))]
                if not artifacts or arc not in artifacts or len(set(artifacts)) != len(artifacts):
                    raise ValueError('archive must be declared exactly once')
                if any(p.parent != case for p in artifacts):
                    raise ValueError('artifacts must be sibling files in the output directory')
                relocated = case/'relocated'; relocated.mkdir()
                for p in artifacts:
                    shutil.move(p, relocated/p.name)
                moved = relocated/'archive'
                result = json.loads(run([work/'adapter_worker', library, 'check', moved, src]))
                restored = case/'restored'
                call('codec_decompress', moved, restored)
                if restored.read_bytes() != data:
                    raise ValueError('shell full restore differs')
                if 'region' in supported:
                    offset = max(0, len(data)-17); length = len(data)-offset
                    call('codec_region', moved, offset, length, restored)
                    if restored.read_bytes() != data[offset:offset+length]:
                        raise ValueError('shell region restore differs')
                result.update(corpus=label, corpus_md5=hashlib.md5(data).hexdigest(),
                              archive_bytes=sum((relocated/p.name).stat().st_size for p in artifacts),
                              relocated=True)
                checks.append(result)
                print(f'{name}: {label}: byte-exact, {result["region_checks"]} region checks', flush=True)
        report = dict(schema='cabench-adapter-check-v1', qualified=True, timed=False,
                      codec=name, version=version, capabilities=supported, unavailable=unavailable,
                      constraints=constraints, native=native, sources=sources, checks=checks,
                      adapter_sha256=digest(adapter), library_sha256=digest(library),
                      worker_sha256=digest(work/'adapter_worker'),
                      compiler=run([*compiler, '--version']).splitlines()[0],
                      command=shlex.join(['./run.sh', '--check', str(adapter.relative_to(ROOT)) if adapter.is_relative_to(ROOT) else str(adapter)]))
        receipt.write_text(json.dumps(report, indent=2)+'\n')
    print('available: ' + ' '.join(supported))
    for axis, reason in unavailable.items():
        print(f'{axis}: n/a — {reason}')
    print(f'PASS (correctness only): {receipt}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', required=True, type=Path)
    parser.add_argument('--work-dir', type=Path, default=ROOT/'.adapter-work')
    args = parser.parse_args()
    try:
        work = args.work_dir.resolve()
        work.mkdir(parents=True, exist_ok=True)
        with (work/'check.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            check(args.check, work)
    except (ValueError, KeyError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
