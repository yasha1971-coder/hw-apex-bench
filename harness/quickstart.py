"""Download the pinned example, or execute README Quick start verbatim in CI."""
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def download():
    record = json.loads((ROOT / 'corpora.json').read_text())['enwik8']
    with urllib.request.urlopen(record['url'], timeout=90) as response:
        archive = response.read()
    if hashlib.sha256(archive).hexdigest() != record['download_sha256']:
        raise ValueError('enwik8 archive SHA256 mismatch')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        if z.namelist() != ['enwik8']:
            raise ValueError('unexpected ZIP members')
        data = z.read('enwik8')
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != record['uncompressed_bytes'] or digest != record['sha256']:
        raise ValueError('enwik8 source size/SHA256 mismatch')
    target = ROOT / 'enwik8'
    if target.exists():
        raise ValueError('enwik8 already exists; refusing overwrite')
    target.write_bytes(data)
    print('enwik8 sha256=' + digest, flush=True)


def run():
    section = (ROOT / 'README.md').read_text().split('## Quick start\n', 1)[1].split('\n## ', 1)[0]
    blocks = re.findall(r'```bash\n(.*?)\n```', section, re.S)
    if len(blocks) != 1:
        raise ValueError('expected one Quick start shell block')
    lines = blocks[0].splitlines()
    if not 1 <= len(lines) <= 3 or any(not s.strip() for s in lines):
        raise ValueError('expected 1–3 nonempty shell lines')
    started = time.monotonic()
    print(f'quickstart lines={len(lines)}', flush=True)
    try:
        for n, line in enumerate(lines, 1):
            before = time.monotonic()
            print(f'line {n}: {line}', flush=True)
            result = subprocess.run(['bash', '-euo', 'pipefail', '-c', line], cwd=ROOT,
                                    timeout=max(0.001, 600 - (before - started)))
            print(f'line {n}: seconds={time.monotonic()-before:.6f} exit={result.returncode}', flush=True)
            result.check_returncode()
        data = json.loads((ROOT / '.work/quickstart-pick/pick.json').read_text())
        record = json.loads((ROOT / 'corpora.json').read_text())['enwik8']
        if data['input_sha256'] != record['sha256']:
            raise ValueError('pick source SHA256 mismatch')
        if sum(r['status'] == 'measured' for r in data['rows']) != 7:
            raise ValueError('not all seven codec/g pairs measured')
        if time.monotonic() - started > 600:
            raise ValueError('Quick start exceeds 600 seconds')
        print('quickstart PASS exit=0', flush=True)
    finally:
        print(f'quickstart total_seconds={time.monotonic()-started:.6f}', flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['download']:
        download()
    elif sys.argv[1:] == ['run']:
        run()
    else:
        raise SystemExit('usage: quickstart.py download|run')
