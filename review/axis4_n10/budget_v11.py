#!/usr/bin/env python3
"""PROTOCOL_AXIS4_N10 v1.1 disk budget. Truth streams from the local .fa.gz (0 bytes); the plain FASTA is still
required by the faidx/plain reader, and the BGZF/zstd/AGC builds read that same materialised FASTA (no second copy).
Usage: budget_v11.py --free-bytes "$(df -B1 --output=avail ~ | tail -1)" > budget_v11.json"""
import argparse, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATE = 20_000_000_000

ap = argparse.ArgumentParser()
ap.add_argument('--free-bytes', type=int, required=True)
a = ap.parse_args()
v1 = json.loads((HERE / 'inputs' / 'budget_n10.json').read_text())
it = v1['items_bytes']
items = {
    'truth_v11_stream_from_fa_gz_hardlinks': 0,
    'fasta_plain_new_for_faidx_exact': it['fasta_uncompressed_new_exact'],
    'fasta_plain_reused_hardlink_vB': 0,
    'faidx_fai_all10_upper': it['faidx_fai_all10_upper'],
    'bgzf_default_new_upper': it['bgzf_default_new_upper'],
    'zstd_seekable_new_upper_fifo': it['zstd_seekable_new_upper'],
    'agc_t2t_10_upper': it['agc_t2t_10_upper'],
    'agc_noref_10_upper': it['agc_noref_10_upper'],
    'agc_native_build_dir_upper': it['agc_native_build_dir_upper'],
    'refrel3_t2t_symlinks': 0,
    'prepared_v2_and_evidence_upper': it['evidence_and_logs_upper'],
}
total = sum(items.values())
need = total + GATE + 1
without_faidx = total - items['fasta_plain_new_for_faidx_exact'] - items['faidx_fai_all10_upper']
print(json.dumps({
    'schema': 'axis4-n10-budget-v1.1', 'items_bytes': items, 'new_bytes_total_upper': total,
    'gate_disk_strictly_above_bytes': GATE, 'required_free_now_bytes': need, 'free_now_bytes': a.free_bytes,
    'shortfall_bytes': max(need - a.free_bytes, 0), 'fits': a.free_bytes >= need,
    'plain_fasta_needed_by': {
        'truth_v1.1': False, 'faidx_plain': True,
        'bgzf_default': 'adapter create() checks source.stat().st_size == BGZF total, so a FIFO source is refused; '
                        'reads the materialised FASTA',
        'zstd_seekable': False, 'agc_create': 'AGC 3.2.4 accepts .fa.gz inputs (README); not needed separately',
        'refrel3': False},
    'note_if_faidx_row_were_not_run': {'new_bytes_upper': without_faidx,
                                       'bgzf_requires_adapter_stream_support': True},
}, indent=1))
