"""Audit nine-axis coverage from retained evidence; never execute a codec."""
import argparse
import json
import math
from pathlib import Path

from configurations import CODECS
from access_profiles import PROFILES, SIZES
from table_cells import unavailable, validate_tables

ROOT = Path(__file__).resolve().parents[1]
DEFINITIONS = (
    ("ratio", "dimensionless", "Input bytes / complete archive file bytes plus all required sidecar/index bytes; stat the files and verify full byte-exact restore."),
    ("encode", "MB/s", "Input bytes / encoder wall seconds / 10^6; report encoder threads and only promote a rate after the documented load-growth plateau."),
    ("full decode", "MB/s", "Input bytes / full library-decode wall seconds / 10^6; resident archive, prefaulted output, explicit decoder workers, verified plateau."),
    ("region p50/p99", "ms", "Nearest-rank percentiles of 200 identical 16 KiB reads; resident archive and reusable handle, timer around the library API only, byte verification outside timing."),
    ("amplification", "decoded bytes / returned bytes", "Sum actual bytes expanded by the decoder / sum bytes returned; count repeated expansions in a separate instrumented pass."),
    ("c(g)", "%", "100 × (ratio_whole − ratio_g) / ratio_whole; same corpus, codec, settings and container, changing only independent block size; test 4/16/64/256/1024 KiB."),
    ("batch", "ranges/s", "N / median wall seconds for uniform, sorted, clustered, hot-set and Zipf(1.2); same trace and workers; show loop and native batch separately."),
    ("H_alpha", "bits", "Shannon entropy −Σ p_b log2(p_b) of request-start blocks for each batch trace; use actual index boundaries, and retain the common 16 KiB-grid entropy."),
    ("break-even N", "requests", "Intersection N* = median full-decode ms / region p50 ms; report floor(N*)+1 as the first integer where independent seeks cost more than full decode."),
)


def definitions():
    return "\n".join([
        "## Nine-axis measurement contract", "",
        "| Axis | Unit | Definition and procedure |", "|---|---|---|",
        *(f"| {axis} | {unit} | {method} |" for axis, unit, method in DEFINITIONS),
        "", "The disk-size denominator means file lengths, not allocator blocks or the sum of compressed streams. Required indexes always count.",
        "`H_alpha` is this protocol's historical name for Shannon entropy; alpha is not a fitted Rényi-entropy parameter.",
        "A native batch API can be unavailable while a measured single-call loop remains valid. Missing values require a reason in the same cell.",
        "A configuration-specific unsupported result does not transfer measurements from another profile or revision.",
    ])


def audit(rows):
    from cg_curve import validate as validate_curve, GRID
    from stage2_report import render_stage2
    from throughput import render_throughput

    def one(codec, metric, **scope):
        matches = [r for r in rows if r['codec'] == codec and r['metric'] == metric
                   and all(r.get(k) == v for k, v in scope.items())]
        if len(matches) != 1:
            raise ValueError(f"Missing/duplicate axis evidence: {codec} {metric} {scope}")
        row = matches[0]
        if not row.get('commands'):
            raise ValueError(f"Missing reproduction command: {codec} {metric}")
        return row

    core = [r for r in rows if r['codec'] in CODECS]
    if len({r['run_id'] for r in core}) != 1:
        raise ValueError("Core coverage must come from one run")
    for field in ('benchmark_commit', 'hardware', 'versions', 'corpus'):
        if len({json.dumps(r[field], sort_keys=True) for r in core}) != 1:
            raise ValueError('Mixed comparison scope: ' + field)
    render_stage2(rows)  # Complete five-profile, four-N, equal-worker matrix.
    render_throughput(rows)  # Recompute rates, sample stability and plateaus.
    curves = [r for r in rows if r.get('evidence_group') == 'cg-five-point-v1']
    validate_curve(curves)
    if len(curves) != 3 * len(GRID):
        raise ValueError("Three formats must account for every c(g) grid position")
    for codec in CODECS:
        ratio = one(codec, 'ratio')
        if ratio.get('full_restore_byte_equal') is not True:
            raise ValueError("Ratio needs byte-exact full restore")
        actual = ratio['input_bytes'] / (ratio['archive_bytes'] + ratio['index_bytes'])
        if not math.isclose(ratio['value'], actual, rel_tol=1e-12):
            raise ValueError("Ratio must include complete files and required indexes")
        for metric in ('ratio', 'region_p50', 'region_p99'):
            relative = one(codec, metric + '_relative_to_bgzip')
            expected = one(codec, metric)['value'] / one('bgzip+htslib', metric)['value']
            passed = expected >= 0.99 if metric == 'ratio' else expected <= 1.0
            if not math.isclose(relative['value'], expected, rel_tol=1e-12) or relative['status'] != ('pass' if passed else 'fail'):
                raise ValueError('Same-run baseline comparison mismatch')
        for metric in ('region_p50', 'region_p99'):
            region = one(codec, metric)
            if region.get('correctness') != 'pass' or region['protocol']['queries'] != 200:
                raise ValueError("Region evidence must verify 200 queries")
            if region['protocol']['requested_bytes'] != 16384:
                raise ValueError("Region evidence must use 16 KiB byte requests")
        amp = one(codec, 'amplification')
        if amp['requested_bytes_total'] != 200 * 16384 or not math.isclose(
                amp['value'], amp['decoded_bytes_total'] / amp['requested_bytes_total'], rel_tol=1e-12):
            raise ValueError("Amplification must count decoder output, not compressed I/O")
        for metric in ('encode_throughput_mb_s', 'full_decode_throughput_mb_s'):
            summary = one(codec, metric)
            if summary['value'] is None and not summary.get('reason'):
                raise ValueError("Data edge needs an explanation")
        for profile in PROFILES:
            for n in SIZES:
                loop = one(codec, 'batch_throughput', access_profile=profile, n=n, method='loop')
                if not isinstance(loop.get('native_batch_available'), bool):
                    raise ValueError("Missing explicit native-batch capability")
                if not loop['native_batch_available'] and not loop.get('native_batch_reason'):
                    raise ValueError("Unsupported native batch needs a reason")
                if not (0 <= loop['H_alpha'] <= math.log2(n) + 1e-9):
                    raise ValueError("Invalid access entropy")
        one(codec, 'break_even_n')
    return {'axes': len(DEFINITIONS), 'formats': 3, 'configurations': len(CODECS),
            'core_run': core[0]['run_id'], 'curve_run': curves[0]['run_id'],
            'curve_positions': len(curves),
            'supported_curve_positions': sum(r.get('point') is not None for r in curves)}


def render(rows):
    checked = audit(rows)
    core = {r['codec']: r for r in rows if r['metric'] == 'ratio' and r['codec'] in CODECS}
    out = ['# Nine-axis evidence coverage', '',
           'Generated from results.jsonl; this audit does not execute compression or timing.', '',
           definitions(), '', '## Existing core run', '',
           f"Run `{checked['core_run']}`; four configurations, three formats. See README for values, versions, complete configurations and same-run comparisons.", '',
           '| Configuration | Ratio + regions + amplification | Encode + full-decode plateau | Five-profile loop + H_alpha | Native batch | Break-even |',
           '|---|---|---|---|---|---|']
    for codec in CODECS:
        loop = next(r for r in rows if r['codec'] == codec and r['metric'] == 'batch_throughput' and r['method'] == 'loop')
        rates = [next(r for r in rows if r['codec'] == codec and r['metric'] == m)
                 for m in ('encode_throughput_mb_s', 'full_decode_throughput_mb_s')]
        plateau = ' / '.join('verified plateau' if r['plateau_reached'] else unavailable(r['reason']) for r in rates)
        native = '20 verified workloads, one worker' if loop['native_batch_available'] else unavailable(loop['native_batch_reason'])
        out.append(f'| {codec} | byte-verified evidence | {plateau} | 20 verified workloads, one worker | {native} | derived, same run |')
    out += ['', '## Separate controlled c(g) run', '',
            f"Run `{checked['curve_run']}`; exact configurations and complete 15-position table: [docs/CG_CURVE_RESULTS.md](CG_CURVE_RESULTS.md).", '',
            '| Configuration | Grid coverage | Strict c(g) availability |', '|---|---|---|']
    curves = [r for r in rows if r.get('evidence_group') == 'cg-five-point-v1']
    for codec in ('bgzip-cg', 'zstd-seekable-cg', 'aceapex-cg-default'):
        rr = [r for r in curves if r['codec'] == codec]
        numeric = sum(r['value'] is not None for r in rr)
        availability = f'{numeric} measured matched-baseline points' if numeric else unavailable(rr[0]['reason'])
        geometry = f"{sum(r.get('point') is not None for r in rr)} measured geometries; {sum(r.get('point') is None for r in rr)} explicitly unsupported positions"
        out.append(f'| {codec} | {geometry} | {availability} |')
    out += ['', 'The curve uses ACEAPEX ee5a37e default; core profiles use 1b13df3. Neither is relabeled as adaptive default a194893.',
            'The separate a194893 refresh retains its six byte-verified rows in docs/DEFAULT_RESULTS.md; it supplies no unmeasured amplification, batch or plateau values.',
            '', '## Interpretation', '',
            'All nine axes are accounted for as measured/derived evidence or an explicit unsupported result. This is coverage, not a claim that every configuration supports every axis.',
            'Absolute CPU performance is declared. A ratio to bgzip is computed only within its own run, corpus and operation; its predicate retains PASS and FAIL. Normalization does not establish machine invariance.',
            'The original 420 rows are preserved byte-for-byte, followed by 15 original curve records. No benchmark was rerun to construct this report.',
            'Recheck: `./run.sh --audit-axes`.', '']
    result = '\n'.join(out)
    validate_tables(result)
    return result


def render_coverage(rows):
    if not any(r.get('evidence_group') == 'cg-five-point-v1' for r in rows):
        return ('# Nine-axis evidence coverage\n\n'
                'Pending: this run has no complete five-point c(g) group. '
                'Do not claim nine-axis closure or borrow a curve from another configuration.\n\n'
                'Run `./run.sh --audit-axes` to require complete coverage.\n')
    return render(rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=ROOT / 'results.jsonl')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.results.read_text().splitlines()]
    checked = audit(rows)
    if args.out:
        args.out.write_text(render(rows), encoding='utf-8')
    print(json.dumps(checked, sort_keys=True))
