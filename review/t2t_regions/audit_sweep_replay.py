#!/usr/bin/env python3
"""Compare two sweep runs, including actual archive bytes, not just row claims."""
import hashlib
import json
from pathlib import Path
import sys
from sweep import ROOT

sha = lambda data: hashlib.sha256(data).hexdigest()
first, second = map(Path, sys.argv[1:3])
runs = []
bad_logs = []
for directory in (first, second):
    rows = [json.loads(l) for l in (directory / 'results.jsonl').read_text().splitlines()]
    assert len(rows) == 300
    records = {}
    bad = []
    for r in rows:
        data = (directory / r['archive']).read_bytes()
        assert len(data) == r['stored_bytes'] and sha(data) == r['archive_sha256']
        key = r['archive']
        assert key not in records
        records[key] = {'bytes': len(data), 'sha256': sha(data)}
        if sha((directory / r['log']).read_bytes()) != r['log_sha256']:
            bad.append(r['log'])
    runs.append(records)
    bad_logs.append(bad)
assert runs[0] == runs[1]
assert not bad_logs[1], 'Accepted-run logs must all match'
receipt = {'matched_archives': 300, 'first_run_results_sha256': sha((first / 'results.jsonl').read_bytes()),
           'accepted_run_results_sha256': sha((second / 'results.jsonl').read_bytes()),
           'first_run_damaged_logs': bad_logs[0],
           'note': 'First-run log hashes changed after measurement; cause not established. '
                   'Accepted run used isolated temporary inputs/output. All 300 actual '
                   'archive sizes and SHA-256 hashes match both runs. Accepted logs verified.',
           'archives': runs[1]}
(ROOT / 'evidence/t2t-granularity-20260916/replay-audit.json').write_text(json.dumps(receipt, indent=2) + '\n')
print('PASS: 300 actual archive files match both runs; accepted logs intact')
