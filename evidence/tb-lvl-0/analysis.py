# SPDX-License-Identifier: Apache-2.0
"""Exact saved-data TB-LVL-0 analysis; no benchmark, native code or clocks.

All speed comparisons use rational MB/s (1 MB = 1000000 input bytes).
The strict frontier here intentionally differs from the historical pick rule.
"""
import argparse
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SIG = "[written by ChatGPT (AI) at the author's request; checked by the author]"
INPUT_BYTES = 211947520
INPUT_SHA256 = 'a667bac80089b3d04d5496772149e632f0758974b0579d743cd8d6e5e0d63eb2'
PROFILES = {
    'aceapex_fast': list(range(1, 9)), 'aceapex': [1, 2, 3, 4],
    'misa77': list(range(6)), 'zxc': list(range(1, 8)), 'lz4': [1, 3, 9, 12],
    'lzav': [1, 2], 'minlz': [1, 3, 7], 'zstd': [1, 3, 9, 15, 19, 22],
    'brotli': [4, 6, 9, 11], 'lzma': [9], 'bsc': ['0e0'], 'kanzi': [5, 6, 7, 8],
}
TBB_HEADER = ('dataset', 'size', 'csize', 'dtime', 'ctime', 'codec', 'level', 'param',
              'cmem', 'dmem', 'cstack', 'dstack', 'time', 'err')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def exact(value):
    require(type(value) in (str, int, Fraction), 'exact integer/rational string required; float/bool rejected')
    result = Fraction(value)
    require(result > 0, 'positive exact quantity required')
    return result


def median(values):
    require(len(values) == 3, 'exactly three external rounds required')
    return sorted(values)[1]


def parse_tbb(raw, config):
    """Read native seconds, never the similarly named rounded CSV MB/s fields."""
    require(isinstance(raw, bytes), 'native .tbb bytes required')
    text = raw.decode('utf-8')
    require('\x00' not in text, 'NUL in native table')
    lines = text.splitlines()
    require(len(lines) == 2 and lines[0].split('\t') == list(TBB_HEADER), 'fresh .tbb requires exact native header and one result row')
    cells = lines[1].split('\t')
    require(len(cells) == len(TBB_HEADER), 'native table field count differs')
    value = dict(zip(TBB_HEADER, cells))
    require(value['dataset'] == 'silesia.ref.tar' and value['codec'] == config['codec'], 'native dataset/codec selection differs')
    level, param = ('0', 'e0') if config['codec'] == 'bsc' and config['level'] == '0e0' else (config['level'], '?')
    require(value['level'] == level and value['param'] == param and value['err'] == '', 'native level/parameter/error differs')
    require(re.fullmatch(r'[0-9]+', value['size']) and re.fullmatch(r'[0-9]+', value['csize']), 'native integer size malformed')
    require(int(value['size']) == INPUT_BYTES and int(value['csize']) > 0, 'native input/compressed size differs')
    require(all(re.fullmatch(r'[0-9]+', value[k]) for k in ('cmem', 'dmem', 'cstack', 'dstack')), 'native memory/stack field malformed')
    for name in ('ctime', 'dtime'):
        require(re.fullmatch(r'[0-9]+\.[0-9]{6}', value[name]) is not None, 'native seconds must retain six decimal places')
        exact(value[name])
    return dict(input_bytes=int(value['size']), compressed_bytes=int(value['csize']),
                ctime_seconds=value['ctime'], dtime_seconds=value['dtime'], native=value)


def canonical_grid(mapping_resolved=False):
    """Literal request until a recorded amendment resolves the level mapping."""
    profiles = dict(PROFILES)
    if not mapping_resolved:
        profiles['aceapex_fast'] = list(range(1, 19))
    rows = []
    for codec, levels in profiles.items():
        for level in levels:
            token = str(level)
            rows.append(dict(id=codec + ',' + token, codec=codec, level=token,
                api_level=int(level) + 10 if codec == 'aceapex_fast' and mapping_resolved else None))
    return sorted(rows, key=lambda row: row['id'])


def execution_order(grid, round_number):
    require(type(round_number) is int and round_number in (1, 2, 3), 'round must be 1/2/3')
    names = sorted(row['id'] for row in grid)
    require(len(names) == len(set(names)), 'duplicate registered configuration')
    if round_number == 2:
        return list(reversed(names))
    if round_number == 3:
        split = len(names) // 2
        return names[split:] + names[:split]
    return names


def summarize_rounds(config, rounds, input_bytes=INPUT_BYTES):
    require(type(input_bytes) is int and input_bytes > 0 and len(rounds) == 3, 'three rounds and positive integer input required')
    require(all(type(r['round']) is int for r in rounds), 'integer external round numbers required')
    require(sorted(r['round'] for r in rounds) == [1, 2, 3], 'duplicate/missing external round')
    ordered = sorted(rounds, key=lambda row: row['round'])
    sizes, cs, ds, normalized = [], [], [], []
    for record in ordered:
        size = record['compressed_bytes']
        require(type(size) is int and size > 0 and record['roundtrip'] is True, 'size or complete byte roundtrip invalid')
        c, d = exact(record['ctime_seconds']), exact(record['dtime_seconds'])
        C, D = Fraction(input_bytes, 1000000) / c, Fraction(input_bytes, 1000000) / d
        sizes.append(size); cs.append(C); ds.append(D)
        normalized.append(dict(round=record['round'], compressed_bytes=size, ctime_seconds=str(c), dtime_seconds=str(d),
            C_MB_s=str(C), D_MB_s=str(D), raw=record.get('raw')))
    size = median(sizes)
    return dict(**config, input_bytes=input_bytes, compressed_bytes=size, archive_percent=str(Fraction(100 * size, input_bytes)),
        C_MB_s=str(median(cs)), D_MB_s=str(median(ds)), size_min=min(sizes), size_max=max(sizes),
        C_min=str(min(cs)), C_max=str(max(cs)), D_min=str(min(ds)), D_max=str(max(ds)), rounds=normalized)


def dominates(other, row, axis='D'):
    require(axis in ('C', 'D'), 'unknown comparison axis')
    return other['compressed_bytes'] < row['compressed_bytes'] and exact(other[axis + '_MB_s']) > exact(row[axis + '_MB_s'])


def frontier(rows, axis='D'):
    require(len({r['id'] for r in rows}) == len(rows), 'duplicate median configuration')
    return {r['id']: sorted(o['id'] for o in rows if dominates(o, r, axis)) for r in rows}


def density_band(row):
    size, original = row['compressed_bytes'], row['input_bytes']
    require(type(size) is int and size > 0 and type(original) is int and original > 0, 'integer density coordinates required')
    return 20 if size > original else min(20 * size // original, 19)


def density_bands(rows):
    global_d = frontier(rows, 'D'); result = []
    for index in range(21):
        members = sorted((r for r in rows if density_band(r) == index), key=lambda r: r['id'])
        local = frontier(members, 'D')
        result.append(dict(index=index, label='>100%' if index == 20 else '[' + str(5 * index) + ',' + str(5 * index + 5) + (']%' if index == 19 else ')%'),
            status='POPULATED' if members else 'EMPTY', configurations=[r['id'] for r in members],
            local_front_D=sorted(name for name, dominators in local.items() if not dominators),
            global_front_D_members=sorted(r['id'] for r in members if not global_d[r['id']])))
    return result


def nearest_ace(rows):
    ace = [r for r in rows if r['codec'] in ('aceapex', 'aceapex_fast')]
    result = []
    for target in sorted((r for r in rows if r['codec'] == 'misa77'), key=lambda r: int(r['level'])):
        if not ace:
            result.append(dict(misa77=target['id'], status='UNAVAILABLE', reason='no complete ACE median is available'))
            continue
        chosen = min(ace, key=lambda r: (abs(r['compressed_bytes'] - target['compressed_bytes']),
                                        -exact(r['D_MB_s']), r['compressed_bytes'], r['id']))
        require(chosen['input_bytes'] == target['input_bytes'], 'density-nearest requires identical input')
        gap = chosen['compressed_bytes'] - target['compressed_bytes']
        a, m = exact(chosen['D_MB_s']), exact(target['D_MB_s'])
        result.append(dict(misa77=target['id'], ACE=chosen['id'], absolute_byte_gap=abs(gap), signed_byte_gap=gap,
            signed_archive_gap_pp=str(Fraction(100 * gap, target['input_bytes'])),
            signed_archive_gap_percent_of_misa=str(Fraction(100 * gap, target['compressed_bytes'])),
            misa_D_MB_s=str(m), ACE_D_MB_s=str(a), signed_D_gap_MB_s=str(a - m),
            signed_D_gap_percent_of_misa=str(100 * (a - m) / m)))
    return result


def forecasts(rows, complete):
    if not complete:
        return {p: dict(verdict='NOT TESTED', passed=None, reason='registered grid/mapping is incomplete') for p in ('P1', 'P2')}
    defaults = [r for r in rows if r['codec'] == 'aceapex' and r['level'] in ('1', '2', '3', '4')]
    references = [r for r in rows if r['codec'] in ('zstd', 'brotli', 'lzma')]
    fast = sorted((r for r in rows if r['codec'] == 'aceapex_fast' and r.get('api_level') in range(13, 19)), key=lambda r: r['api_level'])
    require(len(defaults) == 4 and len(references) == 11 and [r['api_level'] for r in fast] == list(range(13, 19)), 'forecast comparison universe incomplete')
    eligible = [r for r in defaults if 27 * r['input_bytes'] <= 100 * r['compressed_bytes'] <= 33 * r['input_bytes']]
    p1_details = {r['id']: sorted(o['id'] for o in references if dominates(o, r, 'D')) for r in eligible}
    p1 = any(not witnesses for witnesses in p1_details.values())
    p2_details = {r['id']: sorted(o['id'] for o in rows if dominates(o, r, 'C')) for r in fast}
    p2 = all(p2_details.values())
    return dict(P1=dict(passed=p1, verdict='HIT' if p1 else 'MISS', probability='75%', eligible_defaults=sorted(p1_details),
        undominated_defaults=sorted(k for k, v in p1_details.items() if not v), D_dominators_within_named_11=p1_details,
        reference_configs=sorted(r['id'] for r in references)),
        P2=dict(passed=p2, verdict='HIT' if p2 else 'MISS', probability='55%', universal_API_levels=list(range(13, 19)),
                C_dominators_within_registered_grid=p2_details))


def analyze(rows, grid=None, mapping_resolved=False, owner_confirmed=False):
    require(type(mapping_resolved) is bool and type(owner_confirmed) is bool and (not owner_confirmed or mapping_resolved), 'explicit mapping/owner booleans required')
    grid = canonical_grid(mapping_resolved) if grid is None else grid
    wanted = {r['id'] for r in grid}; present = {r['id'] for r in rows}
    require(len(wanted) == len(grid) and len(present) == len(rows) and present <= wanted, 'duplicate/unregistered median point')
    if not mapping_resolved:
        require(not rows, 'timing observations exist before recorded level-mapping resolution')
    for row in rows:
        config = next(c for c in grid if c['id'] == row['id'])
        require(all(row.get(k) == config.get(k) for k in ('codec', 'level', 'api_level')), 'configuration/level alias differs from registered grid')
        require(row['input_bytes'] == INPUT_BYTES and type(row['compressed_bytes']) is int and row['compressed_bytes'] > 0,
                'different corpus size or noninteger archive bytes in registered comparison')
        exact(row['C_MB_s']); exact(row['D_MB_s'])
    complete = mapping_resolved and wanted == present
    d, c = frontier(rows, 'D'), frontier(rows, 'C')
    return dict(schema='tb-lvl-0-analysis-v1', analysis_status='PASS', integrity_status='PENDING INDEPENDENT AUDIT',
        status='NEED MAPPING' if not mapping_resolved else 'DATA COMPLETE / AUDIT PENDING' if complete else 'INCOMPLETE',
        grid_complete=complete, mapping_resolved=mapping_resolved, owner_confirmed=owner_confirmed,
        requested_configurations=60, requested_main_roundtrips=180,
        registered_configurations=len(grid) if mapping_resolved else None,
        registered_main_roundtrips=3 * len(grid) if mapping_resolved else None,
        completed_configurations=len(rows), missing_configurations=sorted(wanted - present),
        input_bytes=INPUT_BYTES, input_sha256=INPUT_SHA256, rows=sorted(rows, key=lambda r: r['id']),
        registered_grid=grid if mapping_resolved else None,
        global_front_D=sorted(k for k, v in d.items() if not v), global_D_dominators=d,
        separate_front_C=sorted(k for k, v in c.items() if not v), separate_C_dominators=c,
        frontiers_provisional=not complete, density_bands=density_bands(rows),
        nearest_ACE_to_misa77=nearest_ace(rows) if rows and any(r['codec'] == 'misa77' for r in rows) else [],
        nearest_provisional=not complete,
        forecasts=forecasts(rows, complete),
        definitions=dict(archive_percent='100 * median compressed bytes / input bytes; smaller is denser',
            strict_D='strictly fewer compressed bytes AND strictly greater median D MB/s',
            strict_C='strictly fewer compressed bytes AND strictly greater median C MB/s',
            local_front='recomputed within a fixed five-percentage-point band; may be globally dominated',
            nearest='absolute byte gap, then greater D, then smaller archive, then canonical identifier',
            rounds='three external byte-verified roundtrips; component-wise medians before rounding'))


def math_projection(summary):
    """Stable exact contract for comparison with the independent auditor."""
    keys = ('grid_complete', 'mapping_resolved', 'owner_confirmed', 'requested_configurations', 'requested_main_roundtrips',
            'registered_configurations', 'registered_main_roundtrips', 'completed_configurations', 'missing_configurations',
            'input_bytes', 'input_sha256', 'global_front_D', 'global_D_dominators', 'separate_front_C', 'separate_C_dominators',
            'frontiers_provisional', 'density_bands', 'nearest_ACE_to_misa77', 'nearest_provisional', 'forecasts')
    result = {k: summary[k] for k in keys}
    fields = ('id', 'codec', 'level', 'api_level', 'input_bytes', 'compressed_bytes', 'archive_percent', 'C_MB_s', 'D_MB_s',
              'size_min', 'size_max', 'C_min', 'C_max', 'D_min', 'D_max')
    round_fields = ('round', 'compressed_bytes', 'ctime_seconds', 'dtime_seconds', 'C_MB_s', 'D_MB_s')
    result['rows'] = [dict(**{k: row[k] for k in fields}, rounds=[{k: r[k] for k in round_fields} for r in row['rounds']]) for row in summary['rows']]
    return result


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


class SavedData:
    """SHA-coupled public selection proof; host/deadline grading is separate."""
    def __init__(self, here=HERE):
        self.here = Path(here).resolve(); self.root = self.here.parents[1]
        self.bindings = {}; self.attempts = []; self.started_units = set()

    def read(self, path):
        path = Path(path).resolve()
        require(path.is_relative_to(self.root) and not path.is_relative_to(self.root / '.work'), 'public repository file required')
        raw = path.read_bytes(); digest = hashlib.sha256(raw).hexdigest(); name = path.relative_to(self.root).as_posix()
        require(self.bindings.setdefault(name, digest) == digest, 'input changed while analyzing: ' + name)
        return raw

    def load(self, path):
        return json.loads(self.read(path), object_pairs_hook=unique)

    def deref(self, record):
        require(isinstance(record, dict) and isinstance(record.get('path'), str) and isinstance(record.get('sha256'), str), 'public SHA reference required')
        name = record['path'].replace('\\', '/')
        marker = '/evidence/tb-lvl-0/'
        if marker in name:
            name = name.split(marker, 1)[1]
        require(not name.startswith('/') and ':' not in name, 'private artifact cannot be a public data reference')
        path = (self.here / name).resolve(); require(path.is_relative_to(self.here), 'stage reference escaped')
        raw = self.read(path); require(hashlib.sha256(raw).hexdigest() == record['sha256'], 'referenced SHA differs: ' + name)
        if 'bytes' in record:
            require(type(record['bytes']) is int and len(raw) == record['bytes'], 'referenced size differs')
        return path

    def jref(self, record):
        return self.load(self.deref(record))

    def reference(self, path):
        raw = self.read(path)
        return dict(path=Path(path).resolve().relative_to(self.here).as_posix(), sha256=hashlib.sha256(raw).hexdigest())

    def resolution(self):
        path = self.here / 'grid-amendment.json'
        if not path.exists():
            return None
        value = self.load(path)
        require(value['schema'] == 'tb-lvl-0-grid-amendment-v1' and value['status'] == 'RESOLVED_BY_SOURCE'
                and value['mapping_resolved'] is True and value['owner_confirmed'] is False
                and value['resolved_by'] == 'source inspection / ChatGPT'
                and value['requested_fast_levels'] == list(range(1, 19)) and value['registered_fast_levels'] == list(range(1, 9))
                and value['api_fast_levels'] == list(range(11, 19)) and value['p2_api_levels'] == list(range(13, 19))
                and value['p2_tb_levels'] == list(range(3, 9)) and value['registered_configurations'] == 50
                and value['registered_main_roundtrips'] == 150, 'source-resolved mapping record differs')
        self.read(self.here / 'GRID_AMENDMENT.md')
        return value

    def target(self, config, round_number):
        return dict(kind='method' if round_number == 0 else 'main', round=round_number, config=config,
                    part='method' if round_number == 0 else 'round-' + str(round_number))

    def read_history(self, prep, target, attempts):
        cfg, round_number, part = target['config'], target['round'], target['part']
        identity = dict(**prep['identity'], config=cfg, round=round_number, kind=target['kind'])
        folder = self.here / 'raw' / part / cfg['id']
        require(1 <= len(attempts) <= 3, 'attempt budget exceeded')
        require({p.name for p in folder.iterdir()} == {'attempt-' + str(i) for i in range(1, len(attempts) + 1)}, 'orphan/fourth raw attempt')
        self.started_units.add((part, cfg['id']))
        winner = None
        for index, item in enumerate(attempts, 1):
            require(item['attempt'] == index and type(item['attempt']) is int and item['status'] in ('CLEAN', 'LOADED', 'ERROR', 'DEADLINE'), 'invalid retained attempt')
            require(index == len(attempts) or item['status'] == 'LOADED', 'first CLEAN/error/deadline was retried')
            rp = self.deref(item['receipt'])
            require(rp == folder / ('attempt-' + str(index)) / 'receipt.json', 'receipt belongs to another configuration/round/attempt')
            receipt = self.load(rp)
            require(receipt['schema'] == 'tb-lvl-0-receipt-v1' and receipt['identity'] == identity
                    and receipt['target'] == target and receipt['status'] == item['status'], 'receipt identity/status coupling differs')
            for stream in ('stdout', 'stderr'):
                require(hashlib.sha256(self.read(rp.parent / stream)).hexdigest() == receipt[stream + '_sha256'], 'native stream SHA differs')
            expected_command = ['taskset', '-c', '0', prep['binary']['path'], '-e' + cfg['id'], '-b1073741824B',
                '-B' + str(INPUT_BYTES) + 'B', '-i0,0', '-C3', '-D', '-V0', '-v0', prep['input']['path']]
            if 'command' in receipt or item['status'] in ('CLEAN', 'LOADED'):
                require(receipt['command'] == expected_command, 'retained attempt changed codec, byte oracle, loop count or input')
            require((rp.parent / 'request.json').exists() or item['status'] not in ('CLEAN', 'LOADED'), 'healthy attempt lacks its immutable request')
            if (rp.parent / 'request.json').exists():
                request_path = rp.parent / 'request.json'; request = self.load(request_path)
                require(item['status'] not in ('CLEAN', 'LOADED') or 'request_sha256' in receipt, 'healthy receipt lacks request SHA')
                require(hashlib.sha256(self.read(request_path)).hexdigest() == receipt.get('request_sha256', hashlib.sha256(self.read(request_path)).hexdigest())
                        and request['schema'] == 'tb-lvl-0-request-v1' and request['identity'] == identity and request['target'] == target
                        and request['command'] == expected_command and request['cwd'] == request['folder'] + '/cwd'
                        and request['folder'].endswith('/evidence/tb-lvl-0/' + rp.parent.relative_to(self.here).as_posix()), 'request identity/SHA/fresh directory differs')
            observed = rp.parent / 'result.json'
            healthy = item['status'] in ('CLEAN', 'LOADED')
            completed_native = receipt['command_started'] is True and type(receipt.get('returncode')) is int and receipt['returncode'] == 0
            can_result = bool(item['result'])
            require(observed.exists() is can_result and (not healthy or can_result is completed_native)
                    and (not can_result or completed_native), 'native start/success and raw result presence differ')
            parsed = None
            if can_result:
                require(self.deref(item['result']) == observed, 'native result swapped')
                value = self.load(observed)
                require(value['schema'] == 'tb-lvl-0-result-v1' and value['identity'] == identity and value['config'] == cfg
                        and value['round'] == round_number and self.deref(value['receipt']) == rp, 'result/request/receipt coupling differs')
                native = self.deref(value['raw']); require(native == rp.parent / 'native.tbb', 'fresh native table belongs to another round/attempt')
                require(value['raw']['sha256'] == receipt['tbb_sha256'], 'receipt and native table SHA differ')
                parsed = parse_tbb(self.read(native), cfg)
                require(all(value[k] == parsed[k] for k in ('input_bytes', 'compressed_bytes', 'ctime_seconds', 'dtime_seconds', 'native'))
                        and value['roundtrip'] is True, 'stored result differs from independently parsed native table')
                require(receipt['command'] == expected_command, 'native selection, byte oracle, loop count or memory scope differs')
                parsed.update(round=round_number, roundtrip=True, raw=value['raw'])
            else:
                require(item['status'] != 'CLEAN' and (not healthy or not (rp.parent / 'native.tbb').exists()), 'unstarted healthy attempt supplied a native table')
                if (rp.parent / 'native.tbb').exists():
                    self.read(rp.parent / 'native.tbb')  # Retain fatal output without treating it as a valid round.
            if target['kind'] == 'method' and parsed is not None:
                require(parsed['compressed_bytes'] == 130490328, 'method known-answer size differs')
            if item['status'] == 'CLEAN':
                require(parsed is not None and receipt['returncode'] == 0, 'CLEAN requires an actual byte-verified result')
                winner = parsed
            self.attempts.append(dict(part=part, config=cfg['id'], round=round_number, attempt=index, status=item['status'],
                command_started=receipt['command_started'], receipt=item['receipt'],
                foreign_processes=receipt.get('foreign_cpu_start', {}).get('exceeded', [])))
        return winner

    def selected_unit(self, prep, reference, target):
        path = self.deref(reference); cfg, part = target['config'], target['part']
        require(path == self.here / 'units' / part / (cfg['id'] + '.json'), 'unit path belongs to another round/configuration')
        value = self.load(path)
        require(value['schema'] == 'tb-lvl-0-unit-v1' and value['kind'] == target['kind'] and value['round'] == target['round']
                and value['config'] == cfg and value['identity'] == dict(**prep['identity'], config=cfg, round=target['round'], kind=target['kind'])
                and value['status'] in ('CLEAN', 'BLOCKED: load'), 'unit identity/status differs')
        winner = self.read_history(prep, target, value['attempts'])
        if winner is None:
            require(value['status'] == 'BLOCKED: load' and len(value['attempts']) == 3 and value['selected'] is None
                    and all(r['status'] == 'LOADED' for r in value['attempts']), 'blocked unit requires three retained LOADED and no selected result')
        else:
            require(value['status'] == 'CLEAN' and value['selected'] == value['attempts'][-1]['result'], 'selection is not first CLEAN')
        return winner

    def dataset(self):
        self.read(self.here / 'CALIBRATION.md')
        self.read(Path(__file__).resolve())
        resolution = self.resolution()
        if not (self.here / 'preparation.json').is_file():
            require(not list((self.here / 'units').rglob('*.json')) and not list((self.here / 'raw').rglob('receipt.json')),
                    'timings exist before recorded mapping/preparation')
            result = analyze([], mapping_resolved=resolution is not None, owner_confirmed=False)
            result['need_reason'] = 'No frozen mapping-resolved preparation/grid is available.'
            if resolution:
                result['mapping_resolution'] = resolution
            return self.finish_summary(result)
        prep = self.load(self.here / 'preparation.json'); identity = prep['identity']
        require(prep['schema'] == 'tb-lvl-0-preparation-v1' and prep['status'] == 'PASS' and prep['no_benchmark_calls'] is True,
                'frozen preparation required')
        staging_path = self.here / 'input-staging.json'; staging = self.load(staging_path)
        require(staging['schema'] == 'tb-lvl-0-input-staging-v1' and identity['input_staging_sha256'] == hashlib.sha256(self.read(staging_path)).hexdigest()
                and staging['source']['path'] == '/home/aeterna/golden/mixed/silesia.ref.tar'
                and staging['source']['bytes'] == staging['staged']['bytes'] == INPUT_BYTES
                and staging['source']['sha256'] == staging['staged']['sha256'] == INPUT_SHA256
                and staging['staged']['path'].endswith('/.work/tb-lvl-0/input/silesia.ref.tar'), 'owned input staging/source identity differs')
        require(identity['input_bytes'] == INPUT_BYTES and identity['input_sha256'] == INPUT_SHA256
                and prep['input']['bytes'] == INPUT_BYTES and prep['input']['sha256'] == INPUT_SHA256
                and prep['input']['path'] == staging['staged']['path'], 'input identity differs')
        for name, digest in identity['source_sha256'].items():
            require(hashlib.sha256(self.read(self.root / name)).hexdigest() == digest, 'frozen execution source changed: ' + name)
        controls = self.jref(prep['controls'])
        require(controls['schema'] == 'tb-lvl-0-runner-controls-v1' and controls['status'] == 'PASS'
                and controls['native_benchmark_calls'] == 0 and controls['synthetic_tests_only'] is True
                and controls['source_sha256'] == {k: v for k, v in identity['source_sha256'].items() if k.endswith(('runner.py', 'test_runner.py'))},
                'pre-measurement parser/deadline/load control proof differs')
        self.deref(controls['stdout']); self.deref(controls['stderr'])
        build_path = self.deref(prep['build']); build = self.load(build_path)
        require(prep['build']['sha256'] == identity['build_manifest_sha256'] and build['schema'] == 'tb-lvl-0-static-build-v1'
                and build['status'] == 'PASS' and build['build_only'] is True and build['benchmark_calls'] == 0
                and build['static_elf_verified'] is True and build['turbobench_commit'] == '4aa97c8c37311e399ea3e7782c18c652c5bdb69f'
                and build['aceapex_override'] == 'c53f3a04f3dbac8590e46a1f86c5fded1e69e065'
                and prep['binary']['sha256'] == identity['binary_sha256'] == build['binary']['sha256']
                and prep['binary']['bytes'] == build['binary']['bytes'], 'static build/source/binary coupling differs')
        grid_path = self.deref(prep['grid']); grid_doc = self.load(grid_path); grid = canonical_grid(True)
        require(resolution is not None and grid_doc['schema'] == 'tb-lvl-0-grid-v1' and grid_doc['mapping_resolved'] is True
                and grid_doc['owner_confirmed'] is False and grid_doc['status'] == 'RESOLVED_BY_SOURCE'
                and grid_doc['configurations'] == grid and grid_doc['rounds'] == 3 and grid_doc['main_roundtrips'] == 150
                and grid_doc['order'] == {str(r): execution_order(grid, r) for r in (1, 2, 3)}
                and self.deref(grid_doc['amendment']) == self.here / 'GRID_AMENDMENT.md'
                and self.deref(grid_doc['amendment_record']) == self.here / 'grid-amendment.json', 'resolved grid/order differs')
        run = self.load(self.here / 'run.json')
        require(run['schema'] == 'tb-lvl-0-run-v1' and run['identity'] == identity and self.deref(run['grid']) == grid_path, 'run source/grid differs')
        configs = {c['id']: c for c in grid}
        planned = [self.target(configs['aceapex_fast,1'], 0)]
        planned += [self.target(configs[name], r) for r in (1, 2, 3) for name in execution_order(grid, r)]
        accepted = ([run['method']] if run['method'] else []) + run['units']
        require(len(accepted) <= len(planned) and (not run['units'] or run['method']), 'main run lacks the preceding method known answer')
        samples = {c['id']: [] for c in grid}; expected_units = set(); method = None
        for reference, target in zip(accepted, planned):
            selected = self.selected_unit(prep, reference, target)
            require(selected is not None, 'run accepted a non-CLEAN unit')
            expected_units.add(self.deref(reference))
            if target['kind'] == 'method':
                method = dict(compressed_bytes=selected['compressed_bytes'], unit=reference)
            else:
                samples[target['config']['id']].append(selected)
        current = run['next_unit']
        expected_current = planned[len(accepted)] if len(accepted) < len(planned) else None
        require(current == expected_current, 'run next target skips/reorders a registered roundtrip')
        if current is not None:
            unit_path = self.here / 'units' / current['part'] / (current['config']['id'] + '.json')
            raw_path = self.here / 'raw' / current['part'] / current['config']['id']
            if unit_path.exists():
                require(self.selected_unit(prep, self.reference(unit_path), current) is None, 'CLEAN unit absent from accepted run prefix')
                expected_units.add(unit_path)
            elif raw_path.exists():
                folders = sorted(raw_path.glob('attempt-*'))
                require([p.name for p in folders] == ['attempt-' + str(i) for i in range(1, len(folders) + 1)] and len(folders) <= 3,
                        'unfinished raw budget has a gap/fourth attempt')
                history = []
                for number, folder in enumerate(folders, 1):
                    record = self.load(folder / 'receipt.json'); op = folder / 'result.json'
                    history.append(dict(attempt=number, status=record['status'], receipt=self.reference(folder / 'receipt.json'),
                                        result=self.reference(op) if op.exists() else None))
                require(history and self.read_history(prep, current, history) is None, 'unpublished CLEAN result must first be checkpointed')
        require(set((self.here / 'units').rglob('*.json')) == expected_units, 'orphan/future/duplicate timing unit')
        actual_raw_units = {p for p in (self.here / 'raw').glob('*/*') if p.is_dir()}
        require(actual_raw_units == {self.here / 'raw' / part / name for part, name in self.started_units}, 'unaccounted raw timing configuration')
        rows = [summarize_rounds(configs[name], records) for name, records in samples.items() if len(records) == 3]
        require(all(len(records) <= 3 for records in samples.values()), 'extra main external round')
        result = analyze(rows, grid, True, grid_doc['owner_confirmed'])
        if result['grid_complete']:
            require(len(accepted) == 151 and method is not None and run['status'] == 'COMPLETE', 'complete medians lack complete execution/method evidence')
        result.update(run_status=run['status'], method_known_answer=method,
            mapping_resolution=resolution,
            partial_configuration_rounds={name: len(records) for name, records in samples.items() if 0 < len(records) < 3},
            provenance=dict(preparation=self.reference(self.here / 'preparation.json'), grid=self.reference(grid_path),
                amendment=grid_doc['amendment'], build=prep['build'], run=self.reference(self.here / 'run.json'),
                binary_sha256=identity['binary_sha256'], input_sha256=INPUT_SHA256, source_sha256=identity['source_sha256']))
        return self.finish_summary(result)

    def finish_summary(self, result):
        retaken = sum(sum(a['part'] == part and a['config'] == name for a in self.attempts) > 1 for part, name in self.started_units)
        result['retention'] = dict(logical_units_started=len(self.started_units), actual_attempts=len(self.attempts),
            retaken_units=retaken, loaded_attempts=sum(a['status'] == 'LOADED' for a in self.attempts),
            excluded_attempts=[a for a in self.attempts if a['status'] != 'CLEAN'])
        result['analysis_sha256'] = hashlib.sha256(packed(math_projection(result))).hexdigest()
        required = dict(self.bindings)
        audit_path = self.here / 'audit.json'
        if audit_path.exists():
            audit = self.load(audit_path)
            result['independent_audit'] = self.reference(audit_path)
            if audit['status'] == 'PASS':
                bindings = {r['path']: r['sha256'] for r in audit['source_bindings']}
                require(len(bindings) == len(audit['source_bindings']), 'duplicate independent audit binding')
                outputs = {(self.here / n).relative_to(self.root).as_posix() for n in ('analysis.json', 'RESULTS.md', 'audit.json')}
                require(not (set(bindings) & outputs), 'independent audit binds a generated output and creates a verification cycle')
                current = all(bindings.get(k) == v for k, v in required.items())
                for name, digest in bindings.items():
                    current = (hashlib.sha256(self.read(self.root / name)).hexdigest() == digest) and current
                if current:
                    require(audit['analysis'] == math_projection(result)
                            and audit['analysis_sha256'] == result['analysis_sha256'], 'independent mathematical recomputation disagrees')
                    result['integrity_status'] = 'PASS'
                    if result['grid_complete']:
                        result['status'] = 'COMPLETE'
                else:
                    result['integrity_status'] = 'STALE / PENDING INDEPENDENT AUDIT'
            else:
                result['integrity_status'] = audit['status']
        result['source_binding_base'] = 'repository'
        result['source_bindings'] = [dict(path=k, sha256=v) for k, v in sorted(self.bindings.items())]
        return result


def display(value, places=3, signed=False):
    number = Fraction(value)
    with localcontext() as context:
        context.prec = 60
        result = format(Decimal(number.numerator) / Decimal(number.denominator), '.' + str(places) + 'f')
    return ('+' if signed and number > 0 else '') + result


def render(summary):
    """Render only supplied saved-data analysis; never starts a codec or audit."""
    lines = [SIG, '', '# TB-LVL-0 — density and whole-file speed', '', '**' + summary['status'] + '.**', '',
        'Consumer: Yakov / CROWN-3. Scope: the pinned silesia.ref.tar input (' + str(INPUT_BYTES) + ' B, SHA256 ' + INPUT_SHA256
        + '), ace-core AMD EPYC 4344P / CPU0; input and archives in memory during codec timers. MB/s uses 1,000,000 input bytes. '
        'These are whole-file compression/decompression speeds within the registered configuration grid, not random-access latency or a universal codec frontier.', '']
    if not summary['mapping_resolved']:
        lines += ['The literal request is 60 configurations / 180 main roundtrips. A recorded TurboBench fast-level mapping resolution '
                  'is required before any method or main timing; no unsupported level is invented.', '']
    else:
        lines += [str(summary['completed_configurations']) + '/' + str(summary['registered_configurations'])
                  + ' configurations have three selected CLEAN external roundtrips; planned main roundtrips: '
                  + str(summary['registered_main_roundtrips']) + '. Each round restores and compares the complete input. '
                  'Sizes and C/D throughputs are component-wise medians; all comparisons use exact rationals before the display rounding below.', '']
        lines += ['Mapping owner confirmation: **' + ('yes' if summary['owner_confirmed'] else 'no')
                  + '**. ' + ('The explicit owner reply is recorded in the amendment. ' if summary['owner_confirmed'] else 'RESOLVED_BY_SOURCE is not an owner confirmation. ')
                  + 'The literal request remains documented as 60 rows; unsupported fast labels9–18 are not fabricated.', '']
    lines += ['Independent integrity audit: **' + summary['integrity_status'] + '**. Mathematical analysis status is separate from completion.', '',
        '## Forecasts from Claude, unchanged', '', '| Forecast | Probability | Verdict |', '|---|---:|---|']
    for name, probability in (('P1', '75%'), ('P2', '55%')):
        verdict = summary['forecasts'][name]['verdict']
        if verdict != 'NOT TESTED' and summary['integrity_status'] != 'PASS':
            verdict = 'NOT TESTED (verification pending)'
        lines.append('| ' + name + ' | ' + probability + ' | ' + verdict + ' |')
    lines += ['', 'P1 is existential over default ACE1–4 at 27–33% compressed size inclusive, against the eleven named zstd/brotli/lzma rows only. '
        'P2 requires a compression-axis dominator for each API fast13–18 (source-mapped TB labels3–8), allowing every configuration in the registered grid. '
        'Missing required data means NOT TESTED; it is never a forecast miss.', '',
        '## Configuration medians', '', '| Configuration | Fast API level | Archive B | Archive % of input | C MB/s | D MB/s | Global D-front | Separate C-front | Size range B |',
        '|---|---:|---:|---:|---:|---:|---|---|---|']
    by_id = {r['id']: r for r in summary['rows']}
    grid = summary.get('registered_grid') or []
    for config in grid:
        row = by_id.get(config['id'])
        if row is None:
            lines.append('| ' + config['id'] + ' | ' + str(config.get('api_level') or '—') + ' | NOT RUN/INCOMPLETE | — | — | — | — | — | — |')
            continue
        spread = str(row['size_min']) + '–' + str(row['size_max']) if row['size_min'] != row['size_max'] else 'constant'
        lines.append('| ' + row['id'] + ' | ' + str(row.get('api_level') or '—') + ' | ' + str(row['compressed_bytes']) + ' | '
            + display(row['archive_percent']) + ' | ' + display(row['C_MB_s']) + ' | ' + display(row['D_MB_s']) + ' | '
            + ('yes' if not summary['global_D_dominators'][row['id']] else 'no') + ' | '
            + ('yes' if not summary['separate_C_dominators'][row['id']] else 'no') + ' | ' + spread + ' |')
    lines += ['', 'D-dominance requires strictly fewer archive bytes AND strictly higher D MB/s; equality in either coordinate is not dominance. '
        'C-dominance uses the same strict size rule with C MB/s. Partial-data fronts are provisional over available complete medians.', '',
        '## Fixed density bands — local D-fronts', '', '| Archive % of input | Available configurations | Local D-front | Also globally on D-front |', '|---|---:|---|---|']
    for band in summary['density_bands']:
        lines.append('| ' + band['label'] + ' | ' + str(len(band['configurations'])) + ' | '
            + (', '.join(band['local_front_D']) or 'empty') + ' | ' + (', '.join(band['global_front_D_members']) or 'none') + ' |')
    lines += ['', 'All twenty fixed five-percentage-point bands and the >100% expansion band remain visible. '
        'Each local front is recomputed using only its band; a point can be locally on the front and globally dominated.', '',
        '## Density-nearest ACE for every misa77 level', '',
        '| misa77 | Nearest ACE | Signed byte gap | Archive gap pp of input | Archive gap % of misa | misa D MB/s | ACE D MB/s | D gap MB/s | D gap % of misa |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for match in summary['nearest_ACE_to_misa77']:
        if match.get('status') == 'UNAVAILABLE':
            lines.append('| ' + match['misa77'] + ' | unavailable | — | — | — | — | — | — | — |')
            continue
        lines.append('| ' + match['misa77'] + ' | ' + match['ACE'] + ' | ' + str(match['signed_byte_gap']) + ' | '
            + display(match['signed_archive_gap_pp'], signed=True) + ' | ' + display(match['signed_archive_gap_percent_of_misa'], signed=True)
            + ' | ' + display(match['misa_D_MB_s']) + ' | ' + display(match['ACE_D_MB_s']) + ' | '
            + display(match['signed_D_gap_MB_s'], signed=True) + ' | ' + display(match['signed_D_gap_percent_of_misa'], signed=True) + ' |')
    lines += ['', 'Selection minimizes absolute archive-byte distance, then prefers greater D, then smaller archive, then canonical identifier. '
        'The same ACE point may be selected for several misa77 levels. Positive archive gaps mean ACE is larger; positive D gaps mean ACE decompresses faster. '
        'Partial selections use available complete medians only and remain provisional.', '',
        'Exact medians, all dominance witnesses and retained native references are in [analysis.json](analysis.json). '
        'The independent [audit](audit.json), [calibration](CALIBRATION.md) and recorded [mapping amendment](GRID_AMENDMENT.md) govern final acceptance. '
        'No previous row or clean slow run is excluded because of its speed.', '']
    if summary.get('need_reason'):
        lines += ['Need: ' + summary['need_reason'], '']
    retention = summary.get('retention')
    if retention:
        lines += ['## Retention', '', str(retention['retaken_units']) + ' of ' + str(retention['logical_units_started'])
            + ' started logical units used more than one actual attempt; ' + str(retention['actual_attempts']) + ' actual attempts and '
            + str(retention['loaded_attempts']) + ' LOADED attempts are retained. The method-only known answer is excluded from all main medians.', '']
        if retention['excluded_attempts']:
            lines += ['| Logical unit | Round | Attempt | Excluded status | Native started |', '|---|---:|---:|---|---|']
            for item in retention['excluded_attempts']:
                lines.append('| ' + item['config'] + ' | ' + str(item['round']) + ' | ' + str(item['attempt']) + ' | '
                    + item['status'] + ' | ' + ('yes' if item['command_started'] else 'no') + ' |')
            lines.append('')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=HERE)
    parser.add_argument('--allow-partial', action='store_true', help='return success for an explicitly incomplete saved-data report')
    args = parser.parse_args()
    data = SavedData()
    try:
        summary = data.dataset()
    except (ValueError, KeyError, TypeError, IndexError, OSError) as error:
        summary = analyze([])
        summary.update(status='ANALYSIS FAILED', analysis_status='FAIL', need_reason=type(error).__name__ + ': ' + str(error),
            source_binding_base='repository', source_bindings=[dict(path=k, sha256=v) for k, v in sorted(data.bindings.items())])
    output = args.output_dir.resolve()
    require(output == HERE.resolve(), 'outputs must stay in evidence/tb-lvl-0')
    (output / 'analysis.json').write_bytes(packed(summary))
    (output / 'RESULTS.md').write_bytes(render(summary).encode('utf-8'))
    print(json.dumps({k: summary[k] for k in ('status', 'analysis_status', 'integrity_status', 'completed_configurations', 'registered_configurations', 'forecasts')}, sort_keys=True))
    return 0 if summary['status'] == 'COMPLETE' or (args.allow_partial and summary['analysis_status'] == 'PASS') else 1 if summary['analysis_status'] == 'FAIL' else 2


if __name__ == '__main__':
    raise SystemExit(main())
