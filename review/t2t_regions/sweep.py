#!/usr/bin/env python3
"""Five granularities on frozen T2T windows, retaining complete archive bytes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PRIOR = ROOT / 'evidence/t2t-regions-20260916'
GRID = (16384, 4096, 65536, 262144, 1048576)


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def ace_geometry(data, size, g):
    h = struct.unpack_from('<8sIQII8s4Q', data)
    magic, version, original, block, count, checksum, *streams = h
    assert magic == b'ACEPX2\0\0' and version == 2
    assert original == size and block == g and count == (size + g - 1) // g
    table = count * 64
    assert len(data) == 68 + table + sum(streams)
    off = 68 + table
    literal_header = struct.unpack_from('<Q', data, off)[0]
    chunked = bool(literal_header & (1 << 61))
    return {'header_bytes': 68, 'block_table_bytes': table,
            'metadata_bytes': 68 + table, 'stream_bytes': sum(streams),
            'streams': dict(zip(('literals', 'offsets', 'lengths', 'commands'), streams)),
            'block_count': count, 'literal_chunked': chunked,
            'literal_chunk_bytes': struct.unpack_from('<Q', data, off + 8)[0] if chunked else None}


def zstd_geometry(data, size, g):
    frames, descriptor, magic = struct.unpack_from('<IBI', data, len(data) - 9)
    assert magic == 0x8F92EAB1
    entry_size = 12 if descriptor & 128 else 8
    table_bytes = 8 + frames * entry_size + 9
    start = len(data) - table_bytes
    skip_magic, payload_size = struct.unpack_from('<II', data, start)
    assert skip_magic == 0x184D2A5E and payload_size == table_bytes - 8
    entries = [struct.unpack_from('<II', data, start + 8 + i * entry_size) for i in range(frames)]
    assert sum(c for c, u in entries) == start and sum(u for c, u in entries) == size
    assert all(u <= g for c, u in entries)
    assert sum(u > 0 for c, u in entries) == (size + g - 1) // g
    return {'seek_table_bytes': table_bytes, 'indexed_frames': frames,
            'empty_frames': sum(u == 0 for c, u in entries),
            'empty_frame_bytes': sum(c for c, u in entries if not u),
            'nonempty_frame_bytes': sum(c for c, u in entries if u),
            'checksum_flag': bool(descriptor & 128)}


def main():
    parser = argparse.ArgumentParser()
    for name in ('inputs', 'build', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--baseline-only', action='store_true',
                        help='Measure one whole-input block/frame per frozen window; do not repeat the sweep')
    a = parser.parse_args()
    grid = (2097152,) if a.baseline_only else GRID
    a.out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((PRIOR / 'manifest.json').read_text())
    old = {(r['chromosome'], r['group'], r['codec']): r for r in
           map(json.loads, (PRIOR / 'results.jsonl').read_text().splitlines())}
    bins = {'aceapex': a.build / 'aceapex',
            'seekable': a.build / 'zstd/contrib/seekable_format/examples/seekable_compression',
            'zstd': a.build / 'zstd/programs/zstd'}
    bins = {k: p.resolve() for k, p in bins.items()}
    ace_source = 'aceapex-source' if (a.build / 'aceapex-source').is_dir() else 'ace-source'
    pins = {ace_source: '4915321bf118e564ef3883e58927992c7f9d8dc3',
            'zstd': 'f8745da6ff1ad1e7bab384bd1f9d742439278e99'}
    for directory, pin in pins.items():
        assert subprocess.check_output(['git', '-C', str(a.build / directory), 'rev-parse', 'HEAD'], text=True).strip() == pin
        assert not subprocess.check_output(['git', '-C', str(a.build / directory), 'status', '--porcelain', '--untracked-files=no'], text=True).strip()
    env = {k: v for k, v in os.environ.items() if not k.startswith(('ACEAPEX_', 'LIT_', 'FSE_')) and k != 'MIN_MATCH'}
    provenance = {'schema': 't2t-granularity-sweep-v1', 'pins': pins,
                  'binary_sha256': {k: digest(p) for k, p in bins.items()},
                  'manifest_sha256': digest(PRIOR / 'manifest.json'),
                  'previous_results_sha256': digest(PRIOR / 'results.jsonl'),
                  'grid_execution_order': grid, 'baseline_only': a.baseline_only,
                  'ace_threads': 8, 'ace_level': 2,
                  'zstd_threads': 1, 'zstd_level': 3, 'libzstd': '1.5.7',
                  'other_ace_overrides': 'unset; automatic domain policy retained',
                  'bgzf': 'fixed historical verified files, not remeasured',
                  'platform': platform.platform(), 'timing_claims': False}
    (a.out / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    total = 0
    with (a.out / 'results.jsonl').open('x') as output:
        # First reproduce every 16 KiB archive before proceeding to new sizes.
        for g in grid:
            for w in manifest['windows']:
                inp = (a.inputs / w['file']).resolve()
                raw = inp.read_bytes()
                assert len(raw) == 2097152 and digest(inp) == w['input_sha256']
                for codec in ('aceapex', 'zstd-seekable'):
                    stem = f"{w['file']}.{codec}.g{g}"
                    arc = (a.out / (stem + '.archive')).resolve()
                    restored = (a.out / (stem + '.restored')).resolve()
                    log = a.out / (stem + '.log')
                    run_env = dict(env, ACEAPEX_BS=str(g))
                    if codec == 'aceapex':
                        enc = [str(bins['aceapex']), 'c', '--in', str(inp), '--out', str(arc), '--threads', '8']
                        dec = [str(bins['aceapex']), 'd', '--in', str(arc), '--out', str(restored), '--threads', '8']
                    else:
                        produced = Path(str(inp) + '.zst')
                        assert not produced.exists()
                        enc = [str(bins['seekable']), str(inp), str(g), '3']
                        dec = [str(bins['zstd']), '-d', '-c', str(arc)]
                    with log.open('wb') as f:
                        subprocess.run(enc, env=run_env, check=True, stdout=f, stderr=f, timeout=600)
                        if codec == 'zstd-seekable':
                            produced.rename(arc)
                            with restored.open('xb') as out:
                                subprocess.run(dec, env=run_env, check=True, stdout=out, stderr=f, timeout=600)
                        else:
                            subprocess.run(dec, env=run_env, check=True, stdout=f, stderr=f, timeout=600)
                    assert restored.read_bytes() == raw, 'restore mismatch'
                    restored.unlink()
                    data = arc.read_bytes()
                    geometry = ace_geometry(data, len(raw), g) if codec == 'aceapex' else zstd_geometry(data, len(raw), g)
                    if codec == 'aceapex':
                        assert int(re.search(r'Compressed:\s+(\d+) bytes', log.read_text())[1]) == geometry['stream_bytes']
                    prev = old[w['chromosome'], w['group'], codec]
                    if g == 16384:
                        expected = next(iter(prev['archive_artifacts'].values()))
                        assert len(data) == expected['bytes'] and digest(arc) == expected['sha256'], '16 KiB replay differs'
                    row = {**w, 'codec': codec, 'granularity': g, 'input_bytes': len(raw),
                           'stored_bytes': len(data), 'ratio': len(raw) / len(data),
                           'archive': arc.name, 'archive_sha256': digest(arc),
                           'geometry': geometry, 'encode_command': enc, 'decode_command': dec,
                           'encode_environment': {'ACEAPEX_BS': str(g)}, 'verified': 'byte-exact',
                           'log': log.name, 'log_sha256': digest(log),
                           'bgzf_reference_bytes': old[w['chromosome'], w['group'], 'bgzip']['stored_bytes']}
                    output.write(json.dumps(row, sort_keys=True) + '\n'); output.flush()
                    total += 1
            print(f'g={g}: {total} byte-exact restores; ' +
                  ('whole-window baseline' if a.baseline_only else '16 KiB replay gate passed'), flush=True)
    print('Complete:', total, 'archives', flush=True)


if __name__ == '__main__':
    main()
