#!/usr/bin/env python3
"""Stream exactly the owner's expanded prefix; never claim whole-gzip integrity."""
import argparse
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import time
import urllib.request

URL = 'https://ftp.sra.ebi.ac.uk/vol1/fastq/ERR174/ERR174310/ERR174310_1.fastq.gz'
SIZE = 5368709120
MD5 = 'd628e1c9fb9466fcbd82109c3c7f9f10'
HEADER = '@ERR174310.1 HSQ1008_141:5:1101:1454:3564/1'

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--receipt', type=Path, required=True)
    args = ap.parse_args()
    if args.receipt.exists():
        raise SystemExit('Refusing to replace an existing receipt')
    start = time.monotonic()
    digest, prefix_digest = hashlib.md5(), hashlib.md5()
    count, first_line, progress = 0, '', 0
    receipt = {'schema': 'hw-apex-prefix-identity-v1', 'url': URL,
               'expected_bytes': SIZE, 'expected_md5': MD5,
               'gzip_whole_file_crc_verified': False,
               'compressed_whole_file_md5_verified': False,
               'scope': 'exactly first 5 GiB expanded bytes; incomplete final FASTQ record'}
    try:
        with urllib.request.urlopen(URL, timeout=60) as response:
            receipt['resolved_url'] = response.geturl()
            with gzip.GzipFile(fileobj=response) as stream:
                while count < SIZE:
                    if time.monotonic() - start > 1200:
                        raise TimeoutError('Total verification budget exceeded')
                    chunk = stream.read(min(1048576, SIZE-count))
                    if not chunk:
                        raise EOFError('Source shorter than requested prefix')
                    if count == 0:
                        first_line = chunk.split(b'\n', 1)[0].decode('ascii')
                    if count < 104857600:
                        prefix_digest.update(chunk[:104857600-count])
                    digest.update(chunk)
                    count += len(chunk)
                    if count // 536870912 > progress:
                        progress = count // 536870912
                        print(f'Expanded and hashed {count // 1048576} MiB', flush=True)
        receipt.update(uncompressed_bytes=count, md5=digest.hexdigest(),
                       prefix_100mib_md5=prefix_digest.hexdigest(), first_line=first_line,
                       first_line_match=first_line == HEADER,
                       match=count == SIZE and digest.hexdigest() == MD5 and first_line == HEADER)
    except Exception as exc:
        receipt.update(uncompressed_bytes=count, match=False,
                       error=f'{type(exc).__name__}: {exc}')
    receipt['checked_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    receipt['elapsed_seconds'] = round(time.monotonic()-start, 3)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open('x') as target:
        json.dump(receipt, target, indent=2)
        target.write('\n')
    print(json.dumps(receipt), flush=True)
    raise SystemExit(0 if receipt['match'] else 1)

if __name__ == '__main__':
    main()
