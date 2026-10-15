"""Axis 5 deterministic one-bit probes; no work on import and no benchmarks.

The decoder command is an argv list, not a shell. One fresh process group per
case; timeout kills the whole group. A successful exit never implies correctness.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile

SEED=20261003
CASES=100


def plan(length: int, *, seed=SEED, count=CASES):
    if type(length) is not int or length<=0 or type(count) is not int or count<=0:
        raise ValueError('nonempty archive and positive case count required')
    result=[]
    for i in range(count):
        digest=hashlib.sha256(f'axis5:{seed}:{i}'.encode('ascii')).digest()
        # Same normalized position and same bit for all codec archive lengths.
        pos=int.from_bytes(digest[:8],'big')*length//2**64
        result.append(dict(case_id=i,seed=seed,offset=pos,bit=digest[8]%8))
    return result


def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def decode_once(argv, archive: Path, output: Path, *, truth_sha256: str,
                truth_bytes: int, timeout=10.0, memory_mib=2048):
    if timeout<=0 or memory_mib<64 or truth_bytes<0:
        raise ValueError('invalid watchdog/resource contract')
    command=[x.replace('{archive}',str(archive)).replace('{output}',str(output)) for x in argv]
    if not command:raise ValueError('empty decoder command')
    def limits():
        cap=memory_mib*1024*1024
        resource.setrlimit(resource.RLIMIT_AS,(cap,cap))
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        output_limit=max(1024*1024,truth_bytes*2+1024*1024)
        resource.setrlimit(resource.RLIMIT_FSIZE,(output_limit,output_limit))
    output.unlink(missing_ok=True)
    with tempfile.TemporaryFile() as errors:
        proc=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=errors,
                              start_new_session=True,preexec_fn=limits)
        try:
            rc=proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            proc.wait()
            return dict(outcome='hang',returncode=proc.returncode,signal=signal.SIGKILL)
        errors.seek(0,2);size=errors.tell();errors.seek(max(0,size-4096))
        diagnostic=errors.read().decode('utf-8','replace')
    result=dict(returncode=rc,signal=-rc if rc<0 else None,stderr_tail=diagnostic)
    if rc<0:result['outcome']='crash'
    elif rc>0:result['outcome']='caught'
    else:
        exists=output.is_file();actual=sha256(output) if exists else None
        n=output.stat().st_size if exists else None
        result.update(output_bytes=n,output_sha256=actual)
        result['outcome']='harmless' if actual==truth_sha256 and n==truth_bytes else 'SILENT'
    return result


def run_probes(argv, clean: Path, truth: Path, *, seed=SEED, count=CASES, timeout=10.0):
    original=sha256(clean);expected=sha256(truth);rows=[]
    with tempfile.TemporaryDirectory(prefix='axis5-') as td:
        root=Path(td);output=root/'decoded';arc=root/'mutated'
        baseline=decode_once(argv,clean,output,truth_sha256=expected,truth_bytes=truth.stat().st_size,timeout=timeout)
        if baseline['outcome']!='harmless':raise ValueError('clean archive failed correctness baseline')
        for mutation in plan(clean.stat().st_size,seed=seed,count=count):
            shutil.copyfile(clean,arc)
            with arc.open('r+b') as f:
                f.seek(mutation['offset']);value=f.read(1)
                f.seek(mutation['offset']);f.write(bytes([value[0] ^ (1<<mutation['bit'])]))
            result=decode_once(argv,arc,output,truth_sha256=expected,truth_bytes=truth.stat().st_size,timeout=timeout)
            rows.append(dict(**mutation,archive_sha256=original,mutation_sha256=sha256(arc),**result))
    if sha256(clean)!=original:raise RuntimeError('immutable clean archive was changed')
    return rows
