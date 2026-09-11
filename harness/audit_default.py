#!/usr/bin/env python3
"""Replay a retained default-refresh JSONL and its immutable receipt."""
import argparse
import hashlib
import json
from pathlib import Path

from default_refresh import ACEAPEX_SHA, CORPUS_SIZE, render
from configurations import PROFILES


def audit(directory, report):
    receipt = json.loads((directory / 'receipt.json').read_text())
    raw = (directory / 'results.jsonl').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == receipt['results_sha256']
    rows = [json.loads(line) for line in raw.decode('utf-8').splitlines()]
    from document_data import restore
    original_report = restore(report.read_text())
    assert render(rows) == original_report
    assert hashlib.sha256(original_report.encode()).hexdigest() == receipt['report_sha256']
    for row in rows:
        assert row['benchmark_commit'] == receipt['benchmark_commit']
        assert row['versions']['aceapex_sha'] == ACEAPEX_SHA
        assert row['corpus']['bytes'] == CORPUS_SIZE
        assert row['corpus']['md5'] == '9465e0f0df6e2c6eb39729c39cee5465'
        assert row['total_bytes'] == row['archive_bytes'] + row['index_bytes']
        assert row['hardware'] == rows[0]['hardware']
        assert row['versions'] == rows[0]['versions']
        assert row['source_provenance'] == rows[0]['source_provenance']
        assert row['encoder_environment'] == row['reader_environment']
        if row['codec'].startswith('ACEAPEX '):
            g = row['geometry']
            assert row['archive_bytes'] == g['archive_bytes']
            assert row['archive_sha256'] == g['archive_sha256']
            assert row['archive_bytes'] == g['payload_bytes'] + g['container_overhead_bytes']
        if row['codec'] in ('ACEAPEX interactive', 'ACEAPEX dense'):
            expected = PROFILES[row['codec'].split()[-1]]
            assert row['encoder_environment'] == expected
            assert row['geometry']['block_size'] == int(expected['ACEAPEX_BS'])
            assert row['geometry']['literal_chunk_bytes'] == int(expected['LIT_CHUNK'])
    assert rows[2]['encoder_environment'] == {}
    assert rows[2]['geometry']['literal_chunking'] is True
    assert rows[2]['geometry']['literal_chunk_bytes'] == 65536
    assert rows[5]['encoder_environment'] == {'LIT_CHUNK': '0'}
    assert rows[5]['region_status'] == 'n/a'
    assert sum(len(r['region_samples']) for r in rows) == 1000
    print('Verified: six rows, exact report replay, matched profiles, 1000 region samples.')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('directory', type=Path)
    p.add_argument('report', type=Path)
    args = p.parse_args()
    audit(args.directory, args.report)
