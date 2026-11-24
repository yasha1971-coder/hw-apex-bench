"""Checkpoint I/O for the preregistered sweep. sweep.py remains the timed worker."""
import argparse
import ctypes
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import struct
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREFIX = 'evidence/hw-gift-1/'
BRANCH = 'refs/remotes/origin/hw-gift-1'
GS = (65536, 262144, 1048576, 4194304, 16777216, 67108864)
NS = (4096, 65536)
CHUNKS = {f'{name}-L{level}': (src, level) for name, src in
          [('enwik8', 'enwik8'), ('silesia', 'silesia.tar')] for level in (3, 19)}
INPUT = {'enwik8': (100000000, '2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8'),
         'silesia.tar': (211947520, 'a667bac80089b3d04d5496772149e632f0758974b0579d743cd8d6e5e0d63eb2')}
FILES = [f'samples-{g}.jsonl.gz' for g in GS] + ['archives.json', 'controls.json', 'run.json']
PIN = 'f8745da6ff1ad1e7bab384bd1f9d742439278e99'
CAL = 'c1a76d31559969d9a5b0e7afec5b83c48d0f37b3'


def check(ok, why):
    if not ok:
        raise ValueError(why)


def packed(x):
    return (json.dumps(x, separators=(',', ':'), sort_keys=True) + '\n').encode()


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write(path, data):
    path = Path(path)
    tmp = path.with_name(path.name + '.writing')
    with tmp.open('wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def keys(n, rep, size):
    rng = random.Random(2026112400 + rep)
    return [rng.randrange(size - n + 1) for _ in range(1000)]


def validate_row(r, src, level, g, n, rep):
    check(tuple(r.get(k) for k in ('src','level','g','n','rep')) == (src,level,g,n,rep), 'row identity')
    if rep == -1:
        check(r.get('negative') == 'native error', 'negative control failed')
        check(len(bytes.fromhex(r['archive_sha256'])) == 32 and r['archive_bytes'] > 0, 'archive identity')
    else:
        s = r['samples']
        check(r['peak_kib'] > 0 and len(s) == 1000, 'incomplete repeat')
        check(all(len(p) == 3 and all(type(t) is int and t >= 0 for t in p) for p in s), 'invalid sample')
        check([p[0] for p in s] == keys(n, rep, INPUT[src][0]), 'offset sequence changed')


def rows_for(blob, src, level, g):
    expect = [(n, rep) for n in NS for rep in range(-1, 5)]
    rows = [json.loads(line) for line in gzip.decompress(blob).splitlines()]
    check(len(rows) == len(expect), 'wrong frame record count')
    for row, (n, rep) in zip(rows, expect):
        validate_row(row, src, level, g, n, rep)
    return rows


def inventory(folder, chunk):
    src, level = CHUNKS[chunk]
    archives, controls = [], []
    for g in GS:
        rows = rows_for((folder/f'samples-{g}.jsonl.gz').read_bytes(), src, level, g)
        neg = [r for r in rows if r['rep'] == -1]
        check(len({(r['archive_sha256'], r['archive_bytes']) for r in neg}) == 1, 'archive changed across widths')
        archives.append({'g': g, 'sha256': neg[0]['archive_sha256'], 'bytes': neg[0]['archive_bytes']})
        controls.extend({k:r[k] for k in ('g','n','archive_sha256','negative')} for r in neg)
    return archives, controls


def sums(folder):
    return ''.join(f'{sha(folder/f)}  {f}\n' for f in sorted(FILES)).encode()


def verify(folder, chunk):
    check({p.name for p in folder.iterdir()} == set(FILES + ['SHA256SUMS']), 'unexpected or missing checkpoint files')
    check((folder/'SHA256SUMS').read_bytes() == sums(folder), 'bad SHA256SUMS')
    a, c = inventory(folder, chunk)
    check(json.loads((folder/'archives.json').read_bytes()) == a, 'archive inventory mismatch')
    check(json.loads((folder/'controls.json').read_bytes()) == c, 'control inventory mismatch')
    src, level = CHUNKS[chunk]
    r = json.loads((folder/'run.json').read_bytes())
    check(r['corpus'] == src and r['level'] == level and (r['input_bytes'], r['input_sha256']) == INPUT[src], 'input mismatch')
    h = r['host']
    check(h['zstd_commit'] == PIN and h['zstd_linked'] == '1.5.7' and h['cpu_affinity'] == [0], 'runtime mismatch')
    return h


def remote_files(chunk):
    records = git('ls-tree', '-r', BRANCH, '--', PREFIX+chunk+'/').decode().splitlines()
    ret = {}
    for rec in records:
        info, path = rec.split('\t', 1)
        mode, typ, oid = info.split()
        check(mode == '100644' and typ == 'blob', 'invalid checkpoint tree')
        ret[path.removeprefix(PREFIX+chunk+'/')] = oid
    if ret:
        check(set(ret) == set(FILES + ['SHA256SUMS']), 'partial checkpoint in branch; stop')
    return ret


def remote_checkpoint(chunk):
    blobs = remote_files(chunk)
    if not blobs:
        return None
    folder = HERE/chunk
    folder.mkdir(exist_ok=True)
    for name, oid in blobs.items():
        dest = folder/name
        if not dest.exists():
            write(dest, git('cat-file', 'blob', oid))
        check(git('hash-object', str(dest)).decode().strip() == oid, 'local/remote checkpoint conflict')
    return verify(folder, chunk)


def host():
    z = os.environ['GIFT_ZSTD']
    dll = ctypes.CDLL(os.environ['GIFT_LIB'])
    dll.hc_version.restype = ctypes.c_char_p
    model = next(x.split(':', 1)[1].strip() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name'))
    result = dict(cpu=model, kernel=platform.release(), os=platform.freedesktop_os_release()['PRETTY_NAME'],
                  host_boot_sha256=hashlib.sha256((platform.node() + '\n' + Path('/proc/sys/kernel/random/boot_id').read_text()).encode()).hexdigest(),
                  cpu_affinity=sorted(os.sched_getaffinity(0)), python=platform.python_version(),
                  cc=subprocess.check_output(['gcc','-dumpfullversion'],text=True).strip(),
                  zstd_cli=subprocess.check_output(['zstd','--version'],text=True).strip(), zstd_linked=dll.hc_version().decode(),
                  zstd_commit=subprocess.check_output(['git','-C',z,'rev-parse','HEAD'],text=True).strip(),
                  encoder_sha256=sha(os.environ['GIFT_ENC']), reader_sha256=sha(os.environ['GIFT_LIB']),
                  worker_sha256=sha(HERE/'sweep.py'), pair_sha256=sha(HERE/'pair.c'),
                  adapter_sha256=sha(ROOT/'codecs/native/zstd_seekable.c'))
    check('AMD EPYC 9V74' in model and 'Debian GNU/Linux 13' in result['os'] and result['zstd_linked']=='1.5.7' and
          '1.5.7' in result['zstd_cli'] and result['zstd_commit']==PIN and result['cpu_affinity']==[0], 'preflight: wrong host or zstd')
    return result


def same_or_write(path, value):
    if path.exists():
        check(path.read_bytes() == value, f'checkpoint changed: {path.name}')
    else:
        write(path, value)


def run(chunk, state, inputs):
    previous = {c:remote_checkpoint(c) for c in CHUNKS}
    if previous[chunk] is not None:
        print('BRANCH_CHECKPOINT_VERIFIED_SKIP', chunk, flush=True)
        return
    src, level = CHUNKS[chunk]
    os.sched_setaffinity(0, {0})
    h = host()
    check(all(v is None or v == h for v in previous.values()), 'run crossed host/build boundary')
    part = state/chunk
    part.mkdir(parents=True, exist_ok=True)
    lock = (part/'lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    check(not (part/'FAILED').exists(), 'prior failed check; stopped')
    folder = HERE/chunk
    if (folder/'SHA256SUMS').exists():
        check(verify(folder, chunk)==h, 'unpublished checkpoint from another run')
        print('LOCAL_CHECKPOINT_READY_TO_PUBLISH', chunk, flush=True)
        return
    for name,(size,digest) in INPUT.items():
        check((inputs/name).stat().st_size==size and sha(inputs/name)==digest,'input SHA/size: '+name)
    receipt = dict(corpus=src, level=level, input_bytes=INPUT[src][0], input_sha256=INPUT[src][1],
                   host=h, protocol_commit=CAL, command=f'python3 chunks.py run {chunk}',
                   encoder_command=f'seekable_compression {src} FRAME_BYTES {level}',
                   worker_command=f'python3 -E -B sweep.py {src} FRAME_BYTES READ_BYTES REP',
                   oracle='both lengths and byte strings vs source; native error required on damaged frame')
    same_or_write(part/'run.json', packed(receipt))
    folder.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='hw-gift-1-',dir='/tmp') as td:
        work=Path(td)
        (work/src).symlink_to(inputs/src)
        archive=work/(src+'.zst')
        for g in GS:
            output=folder/f'samples-{g}.jsonl.gz'
            if output.exists():
                rows_for(output.read_bytes(),src,level,g)
                continue
            subprocess.run([os.environ['GIFT_ENC'],src,str(g),str(level)],cwd=work,check=True)
            identity=sha(archive),archive.stat().st_size
            same_or_write(part/f'archive-{g}.json',packed(identity))
            rows=[]
            for n in NS:
                for rep in range(-1,5):
                    entry=part/f'{g}-{n}-{rep}.json'
                    if not entry.exists():
                        proc=subprocess.run([sys.executable,'-E','-B',str(HERE/'sweep.py'),src,str(g),str(n),str(rep)],
                                            cwd=work,check=True,stdout=subprocess.PIPE)
                        row=dict(src=src,level=level,g=g,n=n,rep=rep,**json.loads(proc.stdout))
                        validate_row(row,src,level,g,n,rep)
                        write(entry,packed(row))
                    r=json.loads(entry.read_bytes())
                    validate_row(r,src,level,g,n,rep)
                    if rep==-1:
                        check((r['archive_sha256'],r['archive_bytes'])==identity,'negative control archive identity')
                    rows.append(packed(r))
            check(sha(archive)==identity[0],'archive changed')
            write(output,gzip.compress(b''.join(rows),compresslevel=6,mtime=0))
    check(sha(inputs/src)==INPUT[src][1],'source changed')
    a,c=inventory(folder,chunk)
    write(folder/'archives.json',packed(a))
    write(folder/'controls.json',packed(c))
    write(folder/'run.json',packed(receipt))
    write(folder/'SHA256SUMS',sums(folder))
    verify(folder,chunk)
    print('LOCAL_CHECKPOINT_READY_TO_PUBLISH',chunk,flush=True)


def final_report():
    hosts=[remote_checkpoint(c) for c in CHUNKS]
    check(all(h is not None and h==hosts[0] for h in hosts),'final reduction requires four matching remote checkpoints')
    raw=b''.join(gzip.decompress((HERE/c/f'samples-{g}.jsonl.gz').read_bytes()) for c in CHUNKS for g in GS)
    out=subprocess.check_output([sys.executable,'-E','-B',str(HERE/'report.py'),'/dev/stdin'],input=raw)
    write(HERE/'RESULTS.md',out)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['run','verify','remote','files','report'])
    parser.add_argument('chunk',nargs='?',choices=CHUNKS)
    a=parser.parse_args()
    if a.action=='report':
        check(a.chunk is None,'no partial report')
        final_report()
        return
    check(a.chunk is not None,'chunk required')
    if a.action=='files':
        print('\n'.join(PREFIX+a.chunk+'/'+f for f in [*FILES,'SHA256SUMS']))
    elif a.action=='verify':
        verify(HERE/a.chunk,a.chunk)
    elif a.action=='remote':
        check(remote_checkpoint(a.chunk) is not None,'checkpoint not in fetched branch')
    else:
        state=Path(os.environ['GIFT_STATE']).resolve()
        inputs=Path(os.environ['GIFT_INPUTS']).resolve()
        check(not state.is_relative_to('/tmp') and not inputs.is_relative_to('/tmp') and
              not HERE.is_relative_to('/tmp'),'durable inputs, logs and evidence must be outside /tmp')
        try:
            run(a.chunk,state,inputs)
        except (ValueError,subprocess.CalledProcessError,AssertionError) as exc:
            part=state/a.chunk
            part.mkdir(parents=True,exist_ok=True)
            write(part/'FAILED',str(exc).encode())
            raise


if __name__=='__main__':
    main()
