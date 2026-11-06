"""Choose a block size using qualified native measurements, not predictions."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

from axis_planner import dispatch_adapter, plan_adapter, resolve_adapter
from native_execution import NativeExecution, digest, execute
from qualification import ROOT, work_directory
from resident_probe import Context

AXES = ['ratio', 'region', 'amplification', 'break_even']


def select(rows, max_p50=None, min_ratio=None):
    measured = [(i, r) for i, r in enumerate(rows) if r['status'] == 'measured']
    for row in rows:
        row['selected'] = False
        row['dominated_by'] = [i for i, other in measured
            if row['status'] == 'measured'
            and other['ratio'] >= row['ratio'] and other['p50_ms'] <= row['p50_ms']
            and (other['ratio'] > row['ratio'] or other['p50_ms'] < row['p50_ms'])]
        row['on_front'] = row['status'] == 'measured' and not row['dominated_by']
        row['p99_ms'] = row.get('evidence', {}).get('region', {}).get('region_p99_ms', row.get('p99_ms'))
    for codec in sorted({r['codec'] for r in rows}):
        available = [r for r in rows if r['codec'] == codec and r['status'] == 'measured']
        if max_p50 is not None:
            eligible = [r for r in available if r['p50_ms'] <= max_p50]
            if not eligible:
                raise ValueError(codec + ': no qualified row meets --max-p50')
            min(eligible, key=lambda r: (-r['ratio'], r['p50_ms'], r['g']))['selected'] = True
        elif min_ratio is not None:
            eligible = [r for r in available if r['ratio'] >= min_ratio]
            if not eligible:
                raise ValueError(codec + ': no qualified row meets --min-ratio')
            min(eligible, key=lambda r: (r['p50_ms'], -r['ratio'], r['g']))['selected'] = True
        else:
            for r in available:
                r['selected'] = r['on_front']


def table(rows):
    lines = ['| Codec | g | ratio | p50 ms | amplification | break-even N | selection / reason |',
             '|---|---|---:|---:|---:|---:|---|']
    for r in rows:
        label = '≤64 KiB, 65 280 B' if r['g'] == 65280 else str(r['g']//1024) + ' KiB'
        values = [format(r[k], '.3g') if r.get(k) is not None else 'n/a'
                  for k in ('ratio', 'p50_ms', 'amplification', 'break_even_N')]
        lines.append('| ' + ' | '.join([r['codec'], label, *values,
            '★' if r.get('selected') else r.get('reason', '')]) + ' |')
    return '\n'.join(lines) + '\n'


def verify_artifacts(state):
    for path, expected in state["artifacts"].items():
        p = Path(path)
        if p.stat().st_size != expected["bytes"] or digest(p) != expected["sha256"]:
            raise ValueError("archive artifact SHA mismatch: " + str(p))


def verify_regions(state, original, raw_samples):
    """Independent SHA oracle outside the measurement timer."""
    verify_artifacts(state)
    ctx = Context(state['library'], state['archive'].read_bytes(), sidecar=state['sidecar'])
    receipt = []
    try:
        if ctx.size != original.stat().st_size:
            raise ValueError('archive size differs from frozen input')
        with original.open('rb') as source:
            for query in raw_samples:
                offset, length = query['byte_offset'], query['requested_bytes']
                source.seek(offset)
                expected = hashlib.sha256(source.read(length)).hexdigest()
                n, answer = ctx.region(offset, length)
                actual = hashlib.sha256(answer).hexdigest()
                if n != length or actual != expected:
                    raise ValueError('region SHA mismatch')
                receipt.append(dict(offset=offset, length=length, sha256=actual))
    finally:
        ctx.close()
    verify_artifacts(state)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--work', type=Path, default=ROOT/'.work/adapter-check')
    parser.add_argument('--output-dir', type=Path)
    limits = parser.add_mutually_exclusive_group()
    limits.add_argument('--max-p50', type=float)
    limits.add_argument('--min-ratio', type=float)
    args = parser.parse_args()
    started = time.monotonic()
    try:
        for value in (args.max_p50, args.min_ratio):
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError('selection limit must be finite and positive')
        source = args.input.resolve()
        initial = digest(source)
        if source.stat().st_size < 16384:
            raise ValueError('input requires at least 16384 bytes')
        out = (args.output_dir or Path(str(source)+'.pick')).resolve()
        out.mkdir(parents=True, exist_ok=False)
        worker = out/'native-measure'
        with (out/'build.log').open('w') as log:
            execute(['gcc','-O3','-std=gnu11','-Wall','-Wextra','-Werror',
                     str(ROOT/'harness/native_measure.c'),'-ldl','-o',str(worker)],
                    stdout=log, stderr=log, timeout=120)
        rows = []
        codec_seconds = {}
        for codec in ('bgzip', 'zstd_seekable', 'xz'):
            adapter = resolve_adapter(codec)
            work = work_directory(adapter, args.work)
            if not (work/'check.json').is_file():
                reason = 'adapter has no --check receipt'
                for g in (4096,16384,65280 if codec == 'bgzip' else 65536):
                    rows.append(dict(codec=codec,g=g,status='n/a',reason=reason))
                continue
            codec_started = time.monotonic()
            plan = plan_adapter(adapter, work, AXES)
            def measure(checked):
                points = []
                for g in (4096,16384,65280 if codec == 'bgzip' else 65536):
                    row = dict(codec=codec,g=g,status='n/a')
                    if codec == 'bgzip' and g != 65280:
                        row['reason'] = 'BGZF block size fixed by adapter'
                        points.append(row)
                        continue
                    directory = out/(codec+'-'+str(g)); directory.mkdir()
                    point = copy.deepcopy(checked)
                    point['configuration']['granularity'] = g
                    runner = NativeExecution(worker, source, directory)
                    ratio = runner.ratio(point)
                    region = runner.measure(point, 'region')
                    amp = runner.amplification(point)
                    be = runner.break_even(point)
                    state = runner.prepare(point)
                    (directory/'archive-state.json').write_text(json.dumps(
                        {key: str(value) if isinstance(value, Path) else value
                         for key, value in state.items() if key in
                         ('archive', 'library', 'sidecar', 'artifacts')}, indent=2)+'\n')
                    raw = [json.loads(s) for s in (directory/region['raw_samples']).read_text().splitlines()]
                    hashes = verify_regions(state, source, raw)
                    (directory/'answers.json').write_text(json.dumps(hashes, indent=2)+'\n')
                    row.update(status='measured',ratio=ratio['ratio'],p50_ms=region['region_p50_ms'],
                               amplification=amp['value'],break_even_N=be['break_even_N'],
                               qualification_sha256=checked['qualification_sha256'],
                               evidence=dict(ratio=ratio,region=region,amplification=amp,break_even=be))
                    points.append(row)
                return points
            # Preserve the original qualified plan throughout dispatch. Vary only
            # the backend's compression granularity, as adapter_curve does.
            result = dispatch_adapter(plan, {axis: (measure if axis == 'ratio' else lambda p: None) for axis in AXES})
            rows.extend(next(r['value'] for r in result if r['axis'] == 'ratio'))
            codec_seconds[codec] = time.monotonic() - codec_started
        if digest(source) != initial:
            raise ValueError('input changed during pick')
        if not any(r['status'] == 'measured' for r in rows):
            raise ValueError('no qualified measurements; run --check first')
        select(rows, args.max_p50, args.min_ratio)
        receipt = dict(schema='cabench-pick-v1',input_sha256=initial,
                       elapsed_seconds=time.monotonic()-started,codec_seconds=codec_seconds,rows=rows)
        (out/'pick.json').write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n')
        rendered = table(rows)
        (out/'pick.md').write_text(rendered)
        print(rendered, end='')
        return 0
    except (ValueError,OSError,KeyError,subprocess.SubprocessError) as exc:
        print('STOP: '+str(exc),file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
