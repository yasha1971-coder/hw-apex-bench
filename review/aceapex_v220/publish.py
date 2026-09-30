#!/usr/bin/env python3
"""Publish/check frozen v2.2.0 evidence. Never builds or benchmarks a codec."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import zipfile

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path('evidence/aceapex-v220-cpu-20260930')
REPORT = Path('docs/RESULTS/ACEAPEX_V220_20260930.md')
RUN = 36751391857
RUN_HEAD = 'a22075e3f3b51a012bb6dff34d5e5643e43e428f'
CHECKOUT = '876c0bef8f7b2c2681e9bd9c94bd2c88d2b09688'
BASE = 'ec6cd69a203057ba3c9b8219684f8ac7450c0718'
ACE = '0a143cd64b35a802835f18c361f981968edf25a1'
BINARY = '9d5523717c5d33f9ec2fa0dc670324fecc847d0214dfc5fe85456b5c00497c06'
RECEIPT = 'c08706f95981fb6b1fcfa804e705cb6b5e94a12ff388ca2ed74e4675ab9baa66'
ARTIFACTS = {
    'cpu': (11115186898, 'be1ce4937041678bf396bfd3c98a821417d141f717073a50477920e151681717', 18),
    'qualification': (11115131449, '08d498dda02886a76924f0f59f37c1b13c4bd5687398775d714ff477ef26998a', 6),
}
LEGAL = (4096, 8192, 16384, 32768, 65280)
CODECS = ('ace-interactive', 'ace-open', 'bgzip', 'zstd-seekable')
LABELS = ('ACE v2.2 interactive/l1', 'ACE v2.2 open/l1', 'BGZF', 'zstd-seekable 1.5.7')


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def formatted(data) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + '\n'


def write_exact(path: Path, data: bytes) -> None:
    """Imports are idempotent, and must not overwrite differing evidence."""
    if path.exists():
        require(path.read_bytes() == data, f'existing evidence differs: {path}')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def import_artifacts(root: Path, cpu_zip: Path, qualification_zip: Path) -> None:
    out = root / EVIDENCE
    records = []
    for kind, archive in [('cpu', cpu_zip), ('qualification', qualification_zip)]:
        aid, expected, count = ARTIFACTS[kind]
        require(sha(archive.read_bytes()) == expected, f'{kind}: ZIP digest mismatch')
        with zipfile.ZipFile(archive) as z:
            members = [i for i in z.infolist() if not i.is_dir()]
            require(len(members) == count, f'{kind}: unexpected member count')
            for info in members:
                name = info.filename
                require(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts,
                        f'unsafe artifact member: {name}')
                if kind == 'qualification':
                    relative = 'qualification/' + name
                elif name.startswith('tmp/aceapex-v220/'):
                    relative = name.removeprefix('tmp/aceapex-v220/')
                elif name.startswith('home/runner/work/hw-apex-bench/hw-apex-bench/.work/native/'):
                    relative = 'native/' + name.rsplit('/', 1)[1]
                else:
                    raise ValueError(f'unexpected artifact member: {name}')
                data = z.read(info)
                data.decode('utf-8')  # preserve reviewer-readable source bytes, no ZIP in git
                write_exact(out / relative, data)
                records.append({'artifact_id': aid, 'original_member': name, 'path': relative,
                                'bytes': len(data), 'sha256': sha(data)})
    require(len({r['path'] for r in records}) == len(records), 'duplicate destination')
    receipt = {
        'schema': 'aceapex-v220-publication-receipt-v1', 'date': '2026-09-30',
        'run_id': RUN, 'run_head_sha': RUN_HEAD, 'benchmark_checkout_sha': CHECKOUT,
        'checkout_note': 'GitHub pull-request merge checkout; parents are base and run head',
        'checkout_parents': [BASE, RUN_HEAD], 'cpu_completed_utc': '2026-09-30T17:32:28Z',
        'artifacts': {kind: {'id': val[0], 'sha256': val[1], 'files': val[2]}
                      for kind, val in ARTIFACTS.items()},
        'files': sorted(records, key=lambda x: x['path']),
        'measurements_repeated': False,
        'storage': 'UTF-8 artifact members copied byte-for-byte; original member names mapped above',
    }
    write_exact(out / 'receipt.json', formatted(receipt).encode())


def nearest(values: list[float], q: float) -> float:
    return sorted(values)[math.ceil(q * len(values)) - 1]


def close(a, b, context: str) -> None:
    require(math.isfinite(float(a)) and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12),
            f'{context}: {a!r} != {b!r}')


def validate(root: Path):
    out = root / EVIDENCE
    require(sha((out / 'receipt.json').read_bytes()) == RECEIPT, 'source receipt hash')
    receipt = load(out / 'receipt.json')
    require(receipt['run_id'] == RUN and receipt['run_head_sha'] == RUN_HEAD, 'run identity')
    require(receipt['benchmark_checkout_sha'] == CHECKOUT, 'checkout identity')
    for kind, (aid, digest, count) in ARTIFACTS.items():
        require(receipt['artifacts'][kind] == {'id': aid, 'sha256': digest, 'files': count}, 'artifact identity')
    require(len(receipt['files']) == 24, 'receipt membership')
    for record in receipt['files']:
        p = out / record['path']
        require(p.is_file() and p.stat().st_size == record['bytes'], f'missing/size: {p}')
        require(sha(p.read_bytes()) == record['sha256'], f'member hash: {p}')
    d = load(out / 'results.json')
    require(d['benchmark_commit'] == CHECKOUT and d['date'] == '2026-09-30', 'result identity')
    mg, cg = d['matched_g'], d['c_g']
    require(mg == load(out / 'matched-g/results.json'), 'matched-g copies disagree')
    require(cg == load(out / 'c-g/results.json'), 'c(g) copies disagree')
    rows = {(r['g'], r['codec']): r for r in mg['rows']}
    require(len(mg['rows']) == 20 and set(rows) == {(g, c) for g in LEGAL for c in CODECS}, 'matrix')
    configs = {}
    manifest = load(root / 'evidence/t2t-regions-20260916/manifest.json')
    windows = {w['file'] for w in manifest['windows']}
    require(len(windows) == 30, 'frozen windows')
    for g in LEGAL:
        cc = load(out / f'matched-g/g{g}/configurations.json')
        require(len(cc) == 120 and {x['id'] for x in cc} == set(range(120)), 'config coverage')
        require({(x['window'], x['codec']) for x in cc} == {(w, c) for w in windows for c in CODECS}, 'window coverage')
        for x in cc:
            require(x['g'] == g and x['input_bytes'] == 2097152 and x['full_restore'] == 'byte-exact', 'config identity/restore')
            close(x['ratio_file'], x['input_bytes'] / x['archive_bytes'], 'config ratio')
            if x['codec'].startswith('ace-'):
                env = x['encoder_environment']
                require(env['ACEAPEX_BS'] == str(g) and env['LIT_CHUNK'] == '65536' and env['FSE_CHUNK'] == '4096', 'encoder environment')
                require('AX_ENC' not in env and (env.get('AX_PROFILE') == 'open') == (x['codec'] == 'ace-open'), 'l1/profile')
            configs[g, x['id']] = x
    vals = {'region': defaultdict(list), 'full': defaultdict(list)}
    counts = Counter()
    amp = defaultdict(lambda: [0, 0])
    region_ids, amp_ids, full_ids = set(), set(), set()
    schedules = {}
    for name, kind, digest_key in [
        ('region-samples.jsonl', 'region', 'region_samples_sha256'),
        ('amplification-samples.jsonl', 'amp', 'amplification_samples_sha256'),
        ('full-decode-samples.jsonl', 'full', 'full_decode_samples_sha256'),
    ]:
        p = out / 'matched-g' / name
        require(sha(p.read_bytes()) == mg[digest_key], f'raw hash: {name}')
        with p.open(encoding='utf-8') as f:
            for line in f:
                x = json.loads(line); key = (x['g'], x['codec'])
                require(key in rows, 'unknown raw row')
                counts[kind, key] += 1
                if kind in ('region', 'amp'):
                    require(x['verified'] is True and x['requested_bytes'] == 16384, 'range verification')
                    require(0 <= x['byte_offset'] <= 2097152 - 16384 and 0 <= x['query'] < 200, 'request bounds')
                if kind == 'region':
                    c = configs[x['g'], x['config']]
                    require(c['codec'] == x['codec'] and x['pass'] in (0, 1, 2), 'region config/pass')
                    ident = (x['g'], x['config'], x['pass'], x['query'])
                    require(ident not in region_ids, 'duplicate region'); region_ids.add(ident)
                    schedule = (x['g'], c['window'], x['query'])
                    require(schedules.setdefault(schedule, x['byte_offset']) == x['byte_offset'], 'unequal request schedule')
                    require(math.isfinite(x['latency_ms']) and x['latency_ms'] > 0, 'invalid latency')
                    vals['region'][key].append(x['latency_ms'])
                elif kind == 'amp':
                    require(x['window'] in windows, 'amplification window')
                    ident = (x['g'], x['codec'], x['window'], x['query'])
                    require(ident not in amp_ids, 'duplicate amplification'); amp_ids.add(ident)
                    require(schedules[x['g'], x['window'], x['query']] == x['byte_offset'], 'amplification schedule')
                    require(isinstance(x['decoded_bytes'], int) and x['decoded_bytes'] >= 0, 'decoded-byte count')
                    amp[key][0] += x['decoded_bytes']; amp[key][1] += x['requested_bytes']
                else:
                    require(x['window'] in windows and x['repeat'] in (0, 1, 2), 'full decode identity')
                    ident = (x['g'], x['codec'], x['window'], x['repeat'])
                    require(ident not in full_ids, 'duplicate full decode'); full_ids.add(ident)
                    require(math.isfinite(x['wall_ms']) and x['wall_ms'] > 0, 'invalid full-decode time')
                    vals['full'][key].append(x['wall_ms'])
    for key, r in rows.items():
        g, codec = key
        cc = [x for (gg, _), x in configs.items() if gg == g and x['codec'] == codec]
        require(r['input_bytes'] == sum(x['input_bytes'] for x in cc), 'aggregate input')
        require(r['archive_bytes'] == sum(x['archive_bytes'] for x in cc), 'aggregate archive')
        require(r['required_sidecar_bytes'] == sum(x['sidecar_bytes'] for x in cc), 'sidecars')
        close(r['ratio_file'], r['input_bytes'] / r['archive_bytes'], 'ratio')
        for kind, field, n in [('region', 'region_samples', 18000), ('amp', 'amplification_samples', 6000), ('full', 'full_decode_samples', 90)]:
            require(counts[kind, key] == r[field] == n, 'sample count')
        close(r['region_p50_ms'], nearest(vals['region'][key], .5), 'p50')
        close(r['region_p99_ms'], nearest(vals['region'][key], .99), 'p99')
        close(r['full_decode_p50_ms'], nearest(vals['full'][key], .5), 'full p50')
        require(amp[key] == [r['amplification_decoded_bytes'], r['amplification_requested_bytes']], 'work totals')
        close(r['amplification'], amp[key][0] / amp[key][1], 'amplification')
        require(r['break_even_n'] == math.floor(r['full_decode_p50_ms'] / r['region_p50_ms']) + 1, 'break-even')
    require({r['encoder'] for r in cg['rows']} == {'l1', 'chain'} and len(cg['rows']) == 2, 'encoder rows')
    for r in cg['rows']:
        require(r['g'] == 16384 and r['g16k']['g'] == 16384 and r['whole']['g'] == 253935557, 'c(g) scope')
        for side in ('g16k', 'whole'):
            close(r[side]['ratio'], 253935557 / r[side]['archive_bytes'], 'c(g) ratio')
            env = r[side]['environment']
            require(env['LIT_CHUNK'] == '65536' and env['FSE_CHUNK'] == '4096', 'c(g) fixed streams')
            require(env.get('AX_ENC') == ('chain' if r['encoder'] == 'chain' else None), 'c(g) encoder')
        close(r['c_g_percent'], 100 * (1 - r['g16k']['ratio'] / r['whole']['ratio']), 'c(g)')
    for r in mg['rows'] + cg['rows']:
        p = r['provenance']
        require(p['actions_run_id'] == RUN and p['aceapex_sha'] == ACE and p['ace_binary_sha256'] == BINARY, 'row provenance')
        require('v1.5.7' in p['libzstd_version'], 'libzstd provenance')
    qualifications = list((out / 'qualification').glob('*/check.json'))
    require(len(qualifications) == 2, 'qualification receipts')
    for p in qualifications:
        q = load(p)
        require(q['status'] == 'pass' and ACE in q['version'], 'qualification status')
        if q['codec'].endswith('-interactive'):
            require(q['native_library_sha256'] == mg['rows'][0]['provenance']['ace_context_sha256'], 'qualified interactive decoder differs')
        else:
            require(q['native_library_sha256'] == '44703c39a42397552a1ddf6a728ca565517f67e9ae6ab799def1500109935a19', 'open qualification identity')
        require(all(x['full_restore'] == 'byte-exact' and x['native']['timings_collected'] is False for x in q['cases']), 'qualification correctness')
    summary = {'status': 'pass', 'measurements_repeated': False, 'source_run': RUN,
               'matrix_points': 20, 'archive_configurations': 600, 'c_g_archives': 4,
               'region_samples': len(region_ids), 'amplification_samples': len(amp_ids),
               'full_decode_samples': len(full_ids), 'qualification_receipts': 2,
               'statistics_recomputed_from_retained_samples': True,
               'equal_request_schedules_checked': True}
    return d, summary


def table(headers, lines) -> str:
    return '| ' + ' | '.join(headers) + ' |\n|' + '|'.join(['---'] * len(headers)) + '|\n' + ''.join('| ' + ' | '.join(map(str, r)) + ' |\n' for r in lines) + '\n'


def render(root: Path, d, summary) -> str:
    rows = {(r['g'], r['codec']): r for r in d['matched_g']['rows']}
    ev = '../../' + EVIDENCE.as_posix()
    text = f'''# ACEAPEX v2.2.0 — frozen CPU refresh and external GPU import

Measured 2026-09-30. Publication-only continuation: **no measurements repeated**.

[Raw evidence and import receipt]({ev}/README.md) ·
[Protocol](../../review/aceapex_v220/PROTOCOL.md) ·
[Successful CPU run {RUN}](https://github.com/yasha1971-coder/hw-apex-bench/actions/runs/{RUN}) ·
[Historical v2.1.0/open report — unchanged](ACEAPEX_UPGRADE_20260930.md).

## Scope and reading rules

ADR-020 changes the DNA-default encoder to l1; the ACEPX2 format is unchanged.
This is why encoder-dependent rows were measured afresh in the source run
rather than copied from v2.1.0. This continuation only publishes that frozen run.

CPU: thirty frozen 2 MiB T2T-CHM13v2.0 windows (60 MiB total),
AMD EPYC 7763, Linux Azure runner, timed CPU 0. Exact common g is
4096 / 8192 / 16384 / 32768 / 65280 B; 65280 B is not 64 KiB.
Each codec/g has 18,000 resident 16 KiB region reads, 6,000 separately
instrumented amplification reads, and 90 full-window decode samples.
Setup, allocation, warmup and byte comparison are outside the latency timer.
Quantiles use the original nearest-rank definition, not the mean of the middle two.

All CPU axes below refer to the same successful run. ACE interactive and open
use the v2.2.0 DNA-default l1 encoder, level 2, requested encoder threads 8,
LIT_CHUNK=65536 and FSE_CHUNK=4096. The generic adapter qualification requests
one encoder thread; its receipt is a separate scope, not an eight-thread timing.
The measured shared resident decoder matches the interactive qualification SHA-256;
the open adapter receipt identifies a separate library binary. Both receipts
record the same pinned decoder source; all measured open returns were byte-checked.

**Ratio here is input/archive-file bytes.** Required BGZF .gzi sidecar sizes
and hashes are retained; sidecar bytes are excluded from this assignment's ratio. This is not the
repository's general all-stored-bytes definition; do not splice these ratios
into historical tables or claim a version speedup across different runs.
The p50 win is not a universal latency win; p99 and decoded work remain visible.

## 1. Archive-file ratio (higher is denser)

'''
    text += table(['g (B)', *LABELS], [[g] + [f"{rows[g,c]['ratio_file']:.6f}" for c in CODECS] for g in LEGAL])
    text += table(['g (B)', 'BGZF required .gzi bytes, all 30 windows'], [[g, rows[g,'bgzip']['required_sidecar_bytes']] for g in LEGAL])
    text += '## 2. Resident region latency (p50 / p99 ms; lower is faster)\n\n'
    text += table(['g (B)', *LABELS], [[g] + [f"{rows[g,c]['region_p50_ms']:.6f} / {rows[g,c]['region_p99_ms']:.6f}" for c in CODECS] for g in LEGAL])
    text += '## 3. Decoded-byte amplification (decoded / requested; lower is less work)\n\n'
    text += table(['g (B)', *LABELS], [[g] + [f"{rows[g,c]['amplification']:.6f}" for c in CODECS] for g in LEGAL])
    text += 'Counters run in separate instrumented libraries; no counter-library latency is used above.\n\n'
    text += '## 4. Break-even cost model (N; full-window p50 ms in parentheses)\n\n'
    text += table(['g (B)', *LABELS], [[g] + [f"{rows[g,c]['break_even_n']} ({rows[g,c]['full_decode_p50_ms']:.6f})" for c in CODECS] for g in LEGAL])
    text += '`N = floor(full-window decode p50 / region p50) + 1`, per 2 MiB window.\nThis is arithmetic on measured costs, **not** an observed batch crossover,\na whole-genome decode measurement, or an independent quality ranking.\n\n'
    text += '## 5. Strict c_file(16 KiB): separate full-hg38-chr1 scope\n\n'
    text += 'Input 253,935,557 B; MD5 `9465e0f0df6e2c6eb39729c39cee5465`.\nOne whole-input block is the baseline; fixed stream chunks, level and threads.\n`c_file(g) = 100 * (1 - ratio_g / ratio_whole)`. All four archives restored byte-exactly in the source run.\n\n'
    text += table(['v2.2.0 encoder', 'g16K bytes', 'whole-block bytes', 'ratio g16K', 'ratio whole', 'c_file (%)'], [[r['encoder'], r['g16k']['archive_bytes'], r['whole']['archive_bytes'], f"{r['g16k']['ratio']:.9f}", f"{r['whole']['ratio']:.9f}", f"{r['c_g_percent']:.6f}"] for r in d['c_g']['rows']])
    text += '`AX_ENC=chain` is the old matcher running inside v2.2.0, not a relabelled v2.1.0 measurement.\nThis fixed-configuration whole-block baseline is not the unconstrained release-default archive.\nNo c_file(g) value for full T2T is claimed.\n\n'
    gpu = load(root / 'evidence/aceapex-v220-gpu-20260930/results.json')
    expected = [('chr1','zstd',60442704,3.501,4.547), ('chr1','open',63083287,2.826,3.919), ('T2T-CHM13v2.0','zstd',822393156,35.542,49.759), ('T2T-CHM13v2.0','open',853264869,27.135,31.063)]
    require([(r['corpus'],r['profile'],r['archive_bytes'],r['on_device_ms'],r['h2d_total_ms']) for r in gpu['rows']] == expected, 'GPU import values')
    require(gpu['source_ace_commit'] == '27b61b1430715e47848cea6d54a333b2f1642334' and gpu['external_runner'] == 'Colab', 'GPU source')
    require(gpu['raw_log']['committed_in_upstream_snapshot'] is False, 'GPU raw-log status')
    text += '''## 6. GPU v2.2.0 — measured-import, external runner: Colab

RTX PRO 6000 Blackwell Server Edition; source ACE commit
`27b61b1430715e47848cea6d54a333b2f1642334`; median of 3;
16 KiB blocks, 64 KiB literal chunks, libzstd 1.5.5.
Every row is reported bit-perfect by the upstream source (GPU FNV equals original).
No GPU was executed or independently revalidated by this publication step.
On-device and with-H2D times are separate boundaries; neither implies D2H or disk I/O.

'''
    text += table(['Corpus', 'Profile', 'Archive B', 'On-device ms', 'With H2D ms', 'Pipeline'], [[r['corpus'],r['profile'],r['archive_bytes'],f"{r['on_device_ms']:.3f}",f"{r['h2d_total_ms']:.3f}",'yes' if r['pipeline'] else 'no'] for r in gpu['rows']])
    text += '[GPU records and source metadata](../../evidence/aceapex-v220-gpu-20260930/results.json);\n[retained release text](../../evidence/aceapex-v220-gpu-20260930/source/release-v2.2.0.md);\n[raw-log limitation](../../evidence/aceapex-v220-gpu-20260930/source/limits-2026-09-30.md).\n\n'
    text += '''## What did not reproduce / what is not demonstrated

- CPU open is less dense and slower at p50 and p99 than interactive at all five g.
  It does not reproduce a CPU region-speed advantage; the GPU result is a separate workload.
- Interactive has lower same-run p50 than BGZF at all five g, but worse p99 at
  4096, 8192 and 16384 B, and greater decoded-byte amplification at all five g.
  zstd-seekable has lower p50 than interactive at 32768 and 65280 B.
  There is no universal winner across these axes.
- The 30 September Blackwell raw log is not committed upstream. This is a
  source-attributed measured import, not independently reproduced GPU evidence.
  Missing raw logs are not replaced by reconstructed or invented paths.
- CPU chr1 interactive archive is 60,440,764 B, while imported GPU zstd chr1 is
  60,442,704 B (1,940 B different). Source commits and libzstd versions differ.
  These are separate configurations; no byte-identity claim or cause is inferred.
- The qualification CLI and CPU measurement CLI have different binary hashes;
  both were built from the pinned revision. The measured shared decoder matches
  the interactive qualification binary; the open adapter qualification library is
  separately identified, not asserted byte-identical to the measured library.
  The exact measured CLI hash is recorded per CPU row. The retained archive
  configuration records and source runner attest full-restore checks; publication
  does not claim a new restore or rebuild. Binary executables and generated archives
  were not retained in the original artifact.
- No new encode plateau, whole-T2T c(g), cold-I/O, batch crossover, GPU regional
  latency, or across-host version speedup was measured. Older evidence is not
  silently promoted to v2.2.0.

## Provenance, history and front-page decision

'''
    text += f'''ACE tag: `{ACE}`; DOI: [10.5281/zenodo.23061934](https://doi.org/10.5281/zenodo.23061934).
Measured CLI SHA-256: `{BINARY}`; CPU libzstd 1.5.7.
Run head: `{RUN_HEAD}`. Checked-out PR merge: `{CHECKOUT}`,
with parents `{BASE}` and the run head; this explains the different SHAs.
Every raw aggregate row retains host, libraries, source hashes and build provenance.

[Full aggregate records]({ev}/results.json),
[commands / environments / archive hashes]({ev}/matched-g/g16384/configurations.json),
[qualification receipts]({ev}/qualification),
[publication verification]({ev}/publication-check.json).
Publication independently recomputes all twenty CPU aggregate rows from
{summary['region_samples']:,} region, {summary['amplification_samples']:,} amplification and
{summary['full_decode_samples']:,} full-decode samples, checking hashes, coverage,
request schedules, nearest-rank statistics, ratios, c(g), and the break-even formula.
This is data validation, not another benchmark.

The first screen and its historical v2.1.0 rows are deliberately unchanged.
This report supplies five matched points with scope/date and losses alongside wins;
no new top-level headline or Pages dataset is promoted in this packaging-only change.
The [v2.1.0 report](ACEAPEX_UPGRADE_20260930.md),
[earlier matched-g report](MATCHED_G_INTERACTIVE_20260918.md), original 435 rows,
and historical GPU scopes retain their original bytes. No external posts.
'''
    return text


def publish(root: Path, check: bool) -> dict:
    d, summary = validate(root)
    report = render(root, d, summary)
    readme = f'''# ACEAPEX v2.2.0 CPU evidence — 2026-09-30

Source: [successful Actions run {RUN}](https://github.com/yasha1971-coder/hw-apex-bench/actions/runs/{RUN}).
CPU artifact 11115186898, SHA-256 `{ARTIFACTS['cpu'][1]}`.
Qualification artifact 11115131449, SHA-256 `{ARTIFACTS['qualification'][1]}`.

All 24 source artifact members are committed as unchanged UTF-8 text.
`receipt.json` maps original ZIP paths to repository paths and records each SHA-256.
No measurement was repeated; this evidence survives Actions artifact expiration.
`native/SHA256SUMS` preserves original runner paths and identifies build outputs;
those binaries are not included in the source artifact. `receipt.json` is the
manifest for files actually retained here.

[Per-axis report](../../docs/RESULTS/ACEAPEX_V220_20260930.md).

Offline verification (no builds, network, benchmarks or new codec executions):

```sh
python3 review/aceapex_v220/publish.py --check
```

`publication-check.json` reports sample reaggregation and verification, not new timings.
The original measured `results.json`, configuration and sample files are not rewritten.
'''
    generated = {REPORT: report, EVIDENCE / 'README.md': readme,
                 EVIDENCE / 'publication-check.json': formatted(summary)}
    index = root / 'docs/RESULTS/README.md'
    link = '- [ACEAPEX v2.2.0 refresh, 2026-09-30](ACEAPEX_V220_20260930.md): five separate CPU axes, frozen raw samples, external Blackwell GPU import and explicit limits.\n'
    for rel, text in generated.items():
        p = root / rel
        if check:
            require(p.exists() and p.read_bytes() == text.encode(), f'generated publication differs: {rel}')
        else:
            p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(text.encode())
    if check:
        require(link in index.read_text(), 'results index missing link')
    else:
        text = index.read_text()
        if link not in text:
            require(text.startswith('# Results by scope\n\n'), 'unexpected results index')
            index.write_text(text.replace('# Results by scope\n\n', '# Results by scope\n\n' + link, 1))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=ROOT)
    ap.add_argument('--cpu-zip', type=Path)
    ap.add_argument('--qualification-zip', type=Path)
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    if a.cpu_zip or a.qualification_zip:
        require(a.cpu_zip is not None and a.qualification_zip is not None and not a.check, 'provide both ZIPs in import mode')
        import_artifacts(a.root, a.cpu_zip, a.qualification_zip)
    print(formatted(publish(a.root, a.check)), end='')


if __name__ == '__main__':
    main()
