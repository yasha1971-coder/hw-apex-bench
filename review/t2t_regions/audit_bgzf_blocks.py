#!/usr/bin/env python3
"""Inspect actual BGZF BSIZE/ISIZE fields in the verified pilot bundle."""
import collections
import hashlib
import json
import struct
import sys
import zipfile
from pathlib import Path
from sweep import ROOT, PRIOR

path = Path(sys.argv[1])
receipt = json.loads((PRIOR / 'archive-bundle.json').read_text())
assert hashlib.sha256(path.read_bytes()).hexdigest() == receipt['sha256']
rows = [json.loads(l) for l in (PRIOR / 'results.jsonl').read_text().splitlines()]
audit = []
with zipfile.ZipFile(path) as z:
    for r in rows:
        if r['codec'] != 'bgzip':
            continue
        name = next(n for n in r['archive_artifacts'] if n.endswith('.archive'))
        data = z.read('measurement/' + name)
        assert hashlib.sha256(data).hexdigest() == r['archive_artifacts'][name]['sha256']
        off = 0
        sizes = []
        while off < len(data):
            assert data[off:off+4] == b'\x1f\x8b\x08\x04'
            extra = struct.unpack_from('<H', data, off+10)[0]
            pos, end, block = off+12, off+12+extra, None
            while pos < end:
                tag = data[pos:pos+2]
                length = struct.unpack_from('<H', data, pos+2)[0]
                if tag == b'BC':
                    assert length == 2
                    block = struct.unpack_from('<H', data, pos+4)[0] + 1
                pos += 4+length
            assert pos == end and block and block <= 65536
            usize = struct.unpack_from('<I', data, off+block-4)[0]
            assert usize <= 65536
            sizes.append(usize)
            off += block
        assert off == len(data) and sum(sizes) == 2097152
        assert sizes == [65280]*32 + [8192, 0]
        audit.append({'archive': name, 'archive_sha256': r['archive_artifacts'][name]['sha256'],
                      'uncompressed_block_sizes': sizes})
assert len(audit) == 30
out = {'specification': 'https://samtools.github.io/hts-specs/SAMv1.pdf',
       'bundle_sha256': receipt['sha256'], 'archives_checked': 30,
       'per_archive': '32 blocks of 65280 bytes, one 8192-byte tail, one empty EOF block',
       'ace_64k_block_bytes': 65536, 'bgzf_regular_block_bytes': 65280,
       'relative_block_size_difference': 65536/65280-1,
       'interpretation': 'Comparable approximately 64 KiB granularity, not identical boundaries or parameters.',
       'archives': audit}
(ROOT/'evidence/t2t-granularity-20260916/bgzf-block-audit.json').write_text(json.dumps(out, indent=2)+'\n')
print('PASS: 30 BGZF archives: each 32 x 65280 + 8192 + empty EOF; regular blocks differ from 64 KiB by 0.392%')
