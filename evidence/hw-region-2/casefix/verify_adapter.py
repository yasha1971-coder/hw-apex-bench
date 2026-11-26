# SPDX-License-Identifier: Apache-2.0
"""Untimed standalone-reader and domain-regression checks; never benchmark."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STATE = ROOT / '.work/hw-region-2/casefix'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def artifact(path):
    path = Path(path).resolve()
    return dict(path=path.relative_to(ROOT).as_posix(), bytes=path.stat().st_size, sha256=sha(path))


def save(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        assert path.read_bytes() == raw, 'existing verification artifact differs'
    else:
        with path.open('xb') as out:
            out.write(raw)


def main():
    assert sys.platform == 'linux' and not os.environ.get('OVH_BENCH_LOCK_HELD')
    os.sched_setaffinity(0, {15})
    source_names = ['codecs/twobit.py', 'codecs/twobit.sh', 'harness/resident_probe.py',
                    'harness/check_adapter.py', 'harness/axis_planner.py',
                    'harness/test_adapter_domains.py', 'harness/test_twobit_sequence.py',
                    'harness/test_check_adapter.py', 'harness/test_axis_planner.py',
                    'harness/test_resident_xz.py', 'evidence/hw-region-2/casefix/verify_adapter.py']
    sources = {name: sha(ROOT / name) for name in source_names}
    assert not subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain', '--', *source_names]).strip()
    receipt = HERE / 'adapter-checks.json'
    if receipt.exists():
        old = json.loads(receipt.read_bytes())
        assert old['status'] == 'PASS' and old['source_sha256'] == sources
        for command in old['commands']:
            for key in ('stdout', 'stderr'):
                item = command[key]
                assert sha(ROOT / item['path']) == item['sha256']
        print('ADAPTER CHECKS cached PASS; no new native calls')
        return
    env = os.environ.copy()
    for name in list(env):
        if name.startswith(('LD_', 'ACEAPEX_', 'LIT_', 'FSE_', 'AX_')):
            env.pop(name)
    build = STATE / 'adapter-reader'
    env.update(HB_PYTHON=sys.executable, HB_TWOBIT_NATIVE_BUILD=str(build / 'build.json'),
               PYTHONPATH=str(ROOT / 'harness'))
    commands = []

    def run(label, argv, expected=0):
        folder = HERE / 'adapter-check-logs' / label
        assert not folder.exists(), 'orphan check; do not silently repeat'
        proc = subprocess.run(list(map(str, argv)), cwd=ROOT, env=env, capture_output=True)
        save(folder / 'stdout', proc.stdout); save(folder / 'stderr', proc.stderr)
        commands.append(dict(label=label, argv=list(map(str, argv)), cwd=str(ROOT),
            returncode=proc.returncode, expected_returncode=expected,
            stdout=artifact(folder / 'stdout'), stderr=artifact(folder / 'stderr')))
        assert proc.returncode == expected, 'check failed: ' + label

    run('shell-syntax', ['bash', '-n', ROOT / 'codecs/twobit.sh'])
    run('standalone-reader', ['bash', ROOT / 'codecs/twobit.sh', 'seq-reader-build', build,
                            '--source-tree', STATE / 'deps/lib2bit'])
    run('correctness', [sys.executable, '-B', '-m', 'unittest', '-v', 'test_twobit_sequence',
                       'test_adapter_domains', 'test_check_adapter', 'test_axis_planner',
                       'test_resident_xz.Capabilities'])
    work = STATE / 'domain-rejection'
    run('generic-check-rejected', ['bash', ROOT / 'run.sh', '--check', ROOT / 'codecs/twobit.sh', '--work', work], 1)
    plan = STATE / 'rejected.plan.json'
    run('generic-plan-rejected', ['bash', ROOT / 'run.sh', '--plan', '--codec', 'twobit', '--work', work, '--output', plan], 1)
    assert not plan.exists()
    assert not list(work.rglob('check.json')) and not list(work.rglob('fixtures-*'))
    for name, expected in sources.items():
        assert sha(ROOT / name) == expected
    value = dict(schema='hw-region-2-casefix-adapter-checks-v1', status='PASS',
                 source_sha256=sources, source_commit=subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).decode().strip(),
                 benchmarks_run=False, query_timers_run=False, native_correctness_fixture_queries=3,
                 cpu_affinity=[15], standalone_build=artifact(build / 'build.json'),
                 environment={name: env[name] for name in ('HB_PYTHON', 'HB_TWOBIT_NATIVE_BUILD', 'PYTHONPATH')}, commands=commands)
    save(receipt, (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode())
    print('ADAPTER CHECKS PASS; untimed; three synthetic native correctness queries')


if __name__ == '__main__':
    main()
