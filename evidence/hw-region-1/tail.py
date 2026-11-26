"""Saved-only ACE tail analysis: archive metadata and exact cache-state replay.

No experiment imports, codecs, native libraries, subprocesses or clocks.
Stop at the first disagreement with the measured materialized-byte counter.
"""
import argparse
import csv
from fractions import Fraction
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = ROOT / '.work/hw-region-1'
DECODER_SHA256 = 'd27e471c0592690a4f7c1675efc9eef256e65f3a043a4de6e1e0b65c222e94df'
SIGNATURE = "[written by ChatGPT (AI) at the author's request; checked by the author]"
STREAMS = ('lit', 'off', 'len', 'cmd')
R, N, WARMUPS = 16384, 1000, 12
MASK48, MASK64 = (1 << 48) - 1, (1 << 64) - 1
CSV_COLUMNS = (
    'case_id', 'corpus', 'g_bytes', 'query', 'offset', 'requested_bytes',
    'elapsed_ns_observed', 'latency_rank_1based', 'is_rank500', 'is_rank990', 'is_upper1percent',
    'materialized_bytes_observed', 'zstd_calls_observed', 'zstd_output_bytes_observed',
    'dctx_calls_observed', 'oneshot_calls_observed', 'stream_calls_observed', 'returned_sha256',
    'outer_blocks_covered_metadata', 'covered_outer_blocks_count_metadata', 'outer_blocks_decoded_replay', 'decoded_outer_blocks_count_replay',
    'outer_boundary_crossed_metadata', 'lit_boundary_crossed_metadata',
    'materialized_bytes_replay', 'chunk_accesses_count_replay', 'chunk_misses_count_replay',
    'lit_chunk_misses_count_replay', 'fse_layout_chunk_misses_count_replay') + tuple(
        name + '_' + stream for stream in STREAMS for name in (
            'required_chunk_ids_metadata', 'accessed_chunk_ids_replay', 'missed_chunk_ids_replay', 'missed_chunk_bytes_replay')) + (
    'archive_sha256', 'request_sha256', 'trace_sha256', 'latency_path', 'counter_path')
NUMERIC_FIELDS = (
    'elapsed_ns_observed', 'materialized_bytes_observed', 'zstd_calls_observed', 'zstd_output_bytes_observed',
    'covered_outer_blocks_count_metadata', 'decoded_outer_blocks_count_replay', 'chunk_accesses_count_replay', 'chunk_misses_count_replay',
    'lit_chunk_misses_count_replay', 'fse_layout_chunk_misses_count_replay')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def valid_sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def load(path):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


def ordered_cases():
    return (['chr1-g16384', 'chr1-g4096', 'chr1-g65536']
            + [f't2t-{i:02d}-g{g}' for i in range(30) for g in (4096, 16384, 65536)]
            + ['enwik8-g16384', 'silesia-g16384'])


def owned_artifact(record):
    require(isinstance(record, dict) and valid_sha(record.get('sha256')), 'invalid private artifact')
    path = Path(record['path']).resolve()
    require(path.is_relative_to(STATE.resolve()) and path.is_file(), 'missing/unowned saved artifact: ' + str(path))
    if 'bytes' in record:
        require(integer(record['bytes']) and path.stat().st_size == record['bytes'], 'saved artifact byte count differs')
    require(sha(path) == record['sha256'], 'saved artifact SHA differs: ' + str(path))
    return path


class Saved:
    def __init__(self, audit_path):
        path = Path(audit_path).resolve()
        require(path.is_relative_to((HERE / 'audit').resolve()), 'audit escaped this study')
        self.audit = load(path)
        require(self.audit.get('schema') == 'hw-region-1-independent-audit-v1'
                and self.audit.get('status') == 'PASS' and self.audit.get('stage') == 'all'
                and self.audit.get('saved_data_only') is True and self.audit.get('no_codecs') is True
                and self.audit.get('no_clocks') is True and self.audit.get('private_artifacts_unavailable') == 0
                and self.audit.get('private_bytes_verified_on_this_host') is True, 'complete private-byte-verified final audit required')
        self.bindings = {}
        for item in self.audit['source_bindings']:
            name, digest = item['path'], item['sha256']
            source = (HERE / name).resolve()
            require(source.is_relative_to(ROOT.resolve()) and not source.is_relative_to((ROOT / '.work').resolve()), 'audit binding escaped public repository')
            require(name not in self.bindings and valid_sha(digest) and sha(source) == digest, 'final audit closure changed: ' + name)
            self.bindings[name] = digest
        require(self.bindings and self.audit['counts']['logical_units'] == 292, 'empty/incomplete final study closure')
        self.audit_reference = dict(path=path.relative_to(HERE).as_posix(), sha256=sha(path))

    def document(self, name):
        path = (HERE / name).resolve()
        require(path.is_relative_to(HERE.resolve()) and self.bindings.get(name) == sha(path), 'tail input not in unchanged final audit: ' + name)
        return load(path)

    def reference(self, record):
        require(isinstance(record, dict) and set(record) == {'path', 'sha256'} and self.bindings.get(record['path']) == record['sha256'],
                'invalid/unbound JSON reference')
        return self.document(record['path'])


class Cursor:
    """cur_open geometry plus cur_chunk_get's four physical LRU slots."""
    def __init__(self, data, is_lit):
        self.size = self.chunk = self.count = self.kind = self.tagged = 0
        self.compressed_bytes = len(data)
        self.entries, self.compressed_sizes = [], []
        self.slots = [dict(index=None, age=0) for _ in range(4)]
        self.tick = 0
        if len(data) < 8:
            return
        word = struct.unpack_from('<Q', data)[0]
        if is_lit and word & (1 << 62):
            fixed = bool(word & (1 << 61))
            self.kind = 1 if fixed else 2
            self.tagged = int(bool(word & (1 << 60)))
            self.size = word & (MASK64 ^ ((1 << 62) | (1 << 61) | (1 << 60)))
            require(not fixed or len(data) >= 16, 'truncated fixed-chunk LIT header')
            self.chunk = struct.unpack_from('<Q', data, 8)[0] if fixed else (self.size + 3) // 4
            require(self.chunk > 0, 'zero LIT chunk')
            self.count = (self.size + self.chunk - 1) // self.chunk if fixed else 4
            table = 16 if fixed else 8
        else:
            self.size = word & MASK48
            field = (word >> 48) & 0x7fff
            # Reader environment is empty in all accepted units; its legacy
            # fallback is consequently 512 KiB, not encoder FSE_CHUNK=4096.
            self.chunk = field << 12 if field else 524288
            require(self.chunk <= 16 << 20, 'token stream chunk exceeds pinned reader limit')
            self.count = (self.size + self.chunk - 1) // self.chunk
            table = 8
        require(self.count <= (len(data) - table) // 8, 'entropy chunk table escapes stream')
        self.entries = list(struct.unpack_from('<' + str(self.count) + 'Q', data, table)) if self.count else []
        room = len(data) - table - self.count * 8
        total = 0
        for index, entry in enumerate(self.entries):
            if self.kind:
                amount = entry & ((1 << 63) - 1)
            else:
                require(((entry >> 48) & 0x3fff) == 0 and not ((entry >> 63) and ((entry >> 62) & 1)), 'reserved/raw+rANS token entry')
                amount = self.raw_size(index) if entry >> 63 else entry & MASK48
            require(amount <= room - total, 'compressed entropy chunks escape stream')
            total += amount
            self.compressed_sizes.append(amount)
        self.table_bytes = table + 8 * self.count
        self.payload_bytes = total
        self.trailing_bytes = room - total

    def raw_size(self, index):
        require(integer(index) and index < self.count, 'chunk index escapes decoded stream')
        return max(0, min(self.chunk, self.size - index * self.chunk))

    def required(self, start, length):
        require(integer(start) and integer(length) and start <= self.size and length <= self.size - start, 'BO slice escapes decoded entropy stream')
        if length == 0:
            return []
        require(self.chunk > 0, 'nonempty slice in an empty stream')
        result = list(range(start // self.chunk, (start + length - 1) // self.chunk + 1))
        require(result[-1] < self.count, 'BO slice chunk exceeds stream table')
        return result

    def access(self, index):
        """Hit and miss both increment age; first slot wins an age tie."""
        self.raw_size(index)
        slot = next((i for i, item in enumerate(self.slots) if item['index'] == index), None)
        missed = slot is None
        if missed:
            slot = min(range(4), key=lambda i: (self.slots[i]['age'], i))
            self.slots[slot]['index'] = index
        self.tick += 1
        require(self.tick <= (1 << 32) - 1, 'unsupported unsigned cache-tick wrap')
        self.slots[slot]['age'] = self.tick
        return missed, self.raw_size(index) if missed else 0

    def metadata(self):
        return dict(decoded_bytes=self.size, chunk_bytes=self.chunk, chunks=self.count, kind=self.kind,
                    tagged=bool(self.tagged), compressed_stream_bytes=self.compressed_bytes,
                    table_bytes=getattr(self, 'table_bytes', 0), chunk_payload_bytes=getattr(self, 'payload_bytes', 0),
                    trailing_bytes=getattr(self, 'trailing_bytes', self.compressed_bytes))


class Archive:
    def __init__(self, data, expected_size, expected_g):
        require(len(data) >= 68 and data[:8] == b'ACEPX2\0\0' and struct.unpack_from('<I', data, 8)[0] == 2,
                'tail supports the measured version-2 four-stream archives only')
        self.size, self.g, self.count = struct.unpack_from('<QII', data, 12)
        require(self.size == expected_size and self.g == expected_g and 0 < self.g <= 64 << 20
                and self.count == (self.size + self.g - 1) // self.g, 'actual ACE outer geometry differs from request/input')
        position = 68 + 64 * self.count
        require(position <= len(data), 'outer block table escapes archive')
        self.blocks = [struct.unpack_from('<8Q', data, 68 + 64 * index) for index in range(self.count)]
        lengths = struct.unpack_from('<4Q', data, 36)
        self.streams = {}
        for stream, length in zip(STREAMS, lengths):
            require(length <= len(data) - position, 'compressed stream escapes archive')
            self.streams[stream] = Cursor(data[position:position + length], stream == 'lit')
            position += length
        self.trailing_bytes = len(data) - position
        require(self.streams['lit'].size <= self.size
                and all(self.streams[name].size <= self.size * 4 + (1 << 20) for name in STREAMS[1:]), 'decoded-stream size cap differs')
        for block in self.blocks:
            require(all(length <= 4 * self.g + 4096 for length in block[5:]), 'token block slice exceeds pinned limit')
            for index, name in enumerate(STREAMS):
                self.streams[name].required(block[index], block[index + 4])
        self.last_block = None

    def request(self, offset, length=R):
        require(integer(offset) and integer(length, 1) and offset <= self.size and length <= self.size - offset, 'invalid saved byte range')
        covered = list(range(offset // self.g, (offset + length - 1) // self.g + 1))
        required = {name: set() for name in STREAMS}
        accessed, missed = ({name: [] for name in STREAMS} for _ in range(2))
        missed_bytes = {name: 0 for name in STREAMS}
        decoded = []
        for block_id in covered:
            block = self.blocks[block_id]
            chunk_ids = {name: self.streams[name].required(block[index], block[index + 4]) for index, name in enumerate(STREAMS)}
            for name in STREAMS:
                required[name].update(chunk_ids[name])
            if block_id == self.last_block:
                continue
            # dec_block calls cur_get in L/O/N/C order, each ascending chunk.
            decoded.append(block_id)
            self.last_block = None
            for name in STREAMS:
                cursor = self.streams[name]
                for chunk_id in chunk_ids[name]:
                    accessed[name].append(chunk_id)
                    was_miss, amount = cursor.access(chunk_id)
                    if was_miss:
                        missed[name].append(chunk_id)
                        missed_bytes[name] += amount
            self.last_block = block_id
        return dict(covered=covered, decoded=decoded, required={name: sorted(values) for name, values in required.items()},
                    accessed=accessed, missed=missed, missed_bytes=missed_bytes, materialized=sum(missed_bytes.values()),
                    outer_boundary=len(covered) > 1, lit_boundary=len(required['lit']) > 1)

    def metadata(self):
        return dict(version=2, input_bytes=self.size, outer_block_bytes=self.g, outer_blocks=self.count,
                    header_bytes=68, outer_table_bytes=self.count * 64, trailing_bytes=self.trailing_bytes,
                    streams={name: self.streams[name].metadata() for name in STREAMS})

    def public_geometry(self):
        value = self.metadata()
        value['outer_table_field_order'] = ['lit_off', 'off_off', 'len_off', 'cmd_off', 'lit_sz', 'off_sz', 'len_sz', 'cmd_sz']
        value['outer_block_offsets_u64'] = [list(row) for row in self.blocks]
        for name in STREAMS:
            # Decimal strings preserve flag bits for readers with binary64 JSON
            # numbers; these are chunk-table entries, never compressed payload.
            value['streams'][name]['chunk_table_u64_decimal'] = [str(entry) for entry in self.streams[name].entries]
            value['streams'][name]['chunk_compressed_bytes'] = self.streams[name].compressed_sizes
        return value


def rows_join(timed, counted, request, trace, request_sha):
    for value, mode, clocked in ((timed, 'latency', True), (counted, 'counter', False)):
        require(value.get('schema') == 'hw-region-1-observation-v1' and value.get('status') == 'PASS' and value['mode'] == mode
                and value['codec'] == 'aceapex' and value['case_id'] == request['case_id']
                and value['request_id'] == request['request_id'] and value['request_sha256'] == request_sha
                and value['archive_sha256'] == request['archive']['sha256'] and value['input_sha256'] == request['input']['sha256']
                and value['trace_sha256'] == request['trace']['sha256'] and value['passes'] == 1 and value['queries_per_pass'] == N
                and value['warmups'] == WARMUPS and value['measurements_of_time'] is clocked
                and value['clock_calls'] == (2 * N if clocked else 0) and len(value['rows']) == N,
                'saved latency/counter request/header join differs')
        for field in ('instrument_sha256', 'native_build_sha256'):
            require(value[field] == request[field], 'saved observation build differs')
    require(timed['returned']['sha256'] == counted['returned']['sha256'] and timed['returned']['bytes'] == counted['returned']['bytes'] == N * R,
            'timed/counter full returned captures differ')
    pairs = []
    for query, (a, b) in enumerate(zip(timed['rows'], counted['rows'])):
        for row in (a, b):
            require(row['schema'] == 'hw-region-1-native-row-v1' and row['pass'] == 0 and row['query'] == query
                    and row['offset'] == trace['offsets'][query] and row['requested_bytes'] == R and row['verified'] is True
                    and valid_sha(row['returned_sha256']), 'saved raw query/offset/return join differs')
        require(a['returned_sha256'] == b['returned_sha256'] and integer(a['elapsed_ns'], 1) and b['elapsed_ns'] is None,
                'saved per-query elapsed/return identity differs')
        fields = ('materialized_bytes', 'zstd_calls', 'zstd_bytes', 'dctx_calls', 'oneshot_calls', 'stream_calls')
        require(all(a[name] is None and integer(b[name]) for name in fields)
                and b['zstd_calls'] == b['dctx_calls'] and b['oneshot_calls'] == b['stream_calls'] == 0,
                'actual API/count sample differs from frozen method')
        pairs.append((a, b))
    ranked = sorted(range(N), key=lambda query: (pairs[query][0]['elapsed_ns'], query))
    values = [pairs[q][0]['elapsed_ns'] for q in ranked]
    require(timed['quantiles'] == [dict(pass_id=0, p50_ns=values[499], p99_ns=values[989])], 'saved raw p50/p99 ranks differ')
    return pairs, ranked


def mean(values):
    require(values, 'empty aggregate')
    return Fraction(sum(values), len(values))


def median(values):
    require(values, 'empty aggregate')
    values = sorted(values)
    n = len(values)
    return Fraction(values[n // 2]) if n % 2 else Fraction(values[n // 2 - 1] + values[n // 2], 2)


def summarize(case_id, records, ranked):
    middle, p99 = records[ranked[499]], records[ranked[989]]
    upper = [records[query] for query in ranked[990:]]
    aggregates = {field: dict(mean=str(mean([row[field] for row in upper])), median=str(median([row[field] for row in upper]))) for field in NUMERIC_FIELDS}
    central = {field: str(median([row[field] for row in records])) for field in NUMERIC_FIELDS}
    central.update(outer_boundary=str(median([row['outer_boundary_crossed_metadata'] for row in records])),
                   lit_boundary=str(median([row['lit_boundary_crossed_metadata'] for row in records])))
    outer_fraction = Fraction(sum(row['outer_boundary_crossed_metadata'] for row in upper), 10)
    lit_fraction = Fraction(sum(row['lit_boundary_crossed_metadata'] for row in upper), 10)
    def higher(field):
        return Fraction(aggregates[field]['mean']) > Fraction(central[field])
    increased = []
    if higher('covered_outer_blocks_count_metadata') or higher('decoded_outer_blocks_count_replay') or outer_fraction > Fraction(central['outer_boundary']):
        increased.append('outer blocks/crossing')
    if higher('lit_chunk_misses_count_replay') or lit_fraction > Fraction(central['lit_boundary']):
        increased.append('LIT misses/boundary')
    if higher('zstd_calls_observed'):
        increased.append('observed zstd calls')
    if higher('fse_layout_chunk_misses_count_replay'):
        increased.append('off/len/cmd misses')
    if higher('materialized_bytes_observed'):
        increased.append('materialized bytes')
    return dict(case_id=case_id, median_rank500=middle, p99_rank990=p99, all_request_feature_medians=central,
                tail_associations=increased or ['none of these observed features'],
                upper1percent=dict(ranks_1based=[991, 1000], queries=[row['query'] for row in upper], count=10,
                    slowest_first_queries=[row['query'] for row in reversed(upper)],
                    slowest_first_zstd_calls=[row['zstd_calls_observed'] for row in reversed(upper)],
                    aggregates=aggregates,
                    outer_boundary_fraction=str(outer_fraction), lit_boundary_fraction=str(lit_fraction)))


def analyze_case(saved, case_id):
    case = saved.document('cases/' + case_id + '.json')
    require(case['status'] == 'COMPLETE' and case['case_id'] == case_id and case['reader_environment'] == {}, 'invalid/retuned saved case')
    item = case['formats']['aceapex']
    request = saved.reference(item['request'])
    require(request['schema'] == 'hw-region-1-request-v1' and request['case_id'] == case_id and request['codec'] == 'aceapex'
            and request['corpus'] == case['corpus'] and request['g'] == case['g'] and request['effective_g'] == case['g']
            and request['queries'] == N and request['warmups'] == WARMUPS and request['request_bytes'] == R, 'tail request scope differs')
    descriptor = saved.reference(case['archives'])
    require(descriptor['formats']['aceapex'] == request['archive'] and descriptor['input'] == request['input'], 'saved archive descriptor differs')
    archive_path = owned_artifact(request['archive'])
    unit = saved.reference(item['latency_unit'])
    require(unit['status'] == 'COMPLETE' and unit['kind'] == 'latency' and unit['case_id'] == case_id and unit['codec'] == 'aceapex'
            and unit['request'] == item['request'] and 1 <= len(unit['attempts']) <= 3 and unit['attempts'][-1]['status'] == 'CLEAN'
            and all(a['status'] == 'LOADED' for a in unit['attempts'][:-1]) and unit['selected'] == unit['attempts'][-1]['observation'], 'selected latency is not first CLEAN')
    timed, counted, trace = (saved.reference(ref) for ref in (unit['selected'], item['counter'], request['trace']))
    require(len(trace['warmup_offsets']) == WARMUPS and len(trace['offsets']) == N and trace['corpus'] == request['corpus']
            and trace['input_sha256'] == request['input']['sha256'] and trace['input_bytes'] == request['input']['bytes']
            and trace['request_bytes'] == R, 'saved warmup/query trace differs')
    pairs, ranked = rows_join(timed, counted, request, trace, item['request']['sha256'])
    archive = Archive(archive_path.read_bytes(), request['input']['bytes'], request['g'])
    for offset in trace['warmup_offsets']:
        archive.request(offset)
    ranks = {query: rank for rank, query in enumerate(ranked, 1)}
    records = []
    for query, (observed, counters) in enumerate(pairs):
        replay = archive.request(observed['offset'])
        require(replay['materialized'] == counters['materialized_bytes'],
                'STOP materialized-byte mismatch: ' + case_id + ' query ' + str(query) + ' replay '
                + str(replay['materialized']) + ' saved ' + str(counters['materialized_bytes']))
        record = dict(case_id=case_id, corpus=case['corpus'], g_bytes=case['g'], query=query, offset=observed['offset'], requested_bytes=R,
            elapsed_ns_observed=observed['elapsed_ns'], latency_rank_1based=ranks[query], is_rank500=int(ranks[query] == 500),
            is_rank990=int(ranks[query] == 990), is_upper1percent=int(ranks[query] >= 991), materialized_bytes_observed=counters['materialized_bytes'],
            zstd_calls_observed=counters['zstd_calls'], zstd_output_bytes_observed=counters['zstd_bytes'], dctx_calls_observed=counters['dctx_calls'],
            oneshot_calls_observed=counters['oneshot_calls'], stream_calls_observed=counters['stream_calls'], returned_sha256=observed['returned_sha256'],
            outer_blocks_covered_metadata=replay['covered'], covered_outer_blocks_count_metadata=len(replay['covered']),
            outer_blocks_decoded_replay=replay['decoded'], decoded_outer_blocks_count_replay=len(replay['decoded']),
            outer_boundary_crossed_metadata=int(replay['outer_boundary']), lit_boundary_crossed_metadata=int(replay['lit_boundary']),
            materialized_bytes_replay=replay['materialized'], chunk_accesses_count_replay=sum(map(len, replay['accessed'].values())),
            chunk_misses_count_replay=sum(map(len, replay['missed'].values())), lit_chunk_misses_count_replay=len(replay['missed']['lit']),
            fse_layout_chunk_misses_count_replay=sum(len(replay['missed'][name]) for name in STREAMS[1:]), archive_sha256=request['archive']['sha256'],
            request_sha256=item['request']['sha256'], trace_sha256=request['trace']['sha256'], latency_path=unit['selected']['path'], counter_path=item['counter']['path'])
        for name in STREAMS:
            record['required_chunk_ids_metadata_' + name] = replay['required'][name]
            record['accessed_chunk_ids_replay_' + name] = replay['accessed'][name]
            record['missed_chunk_ids_replay_' + name] = replay['missed'][name]
            record['missed_chunk_bytes_replay_' + name] = replay['missed_bytes'][name]
        records.append(record)
    summary = summarize(case_id, records, ranked)
    summary.update(corpus=case['corpus'], g_bytes=case['g'], geometry=archive.metadata(), archive=dict(path=str(archive_path),
                   bytes=request['archive']['bytes'], sha256=request['archive']['sha256']), request=item['request'],
                   latency=unit['selected'], counter=item['counter'], trace=request['trace'])
    geometry = archive.public_geometry()
    geometry.update(case_id=case_id, corpus=case['corpus'], archive=summary['archive'], trace=request['trace'],
                    warmup_offsets=trace['warmup_offsets'], request_offsets=trace['offsets'])
    return records, summary, geometry


def compact(value, places=2):
    value = Fraction(value)
    # Integer scaling/rounding avoids binary float loss in display only.
    scale = 10 ** places
    sign = '-' if value < 0 else ''
    scaled = (abs(value.numerator) * scale * 2 + value.denominator) // (2 * value.denominator)
    return sign + str(scaled // scale) + ('.' + str(scaled % scale).zfill(places) if places else '')


def tail_text(summary):
    cells = summary['cases']
    primary = next(cell for cell in cells if cell['case_id'] == 'chr1-g16384')
    baseline, top = primary['all_request_feature_medians'], primary['upper1percent']
    def contrast(field):
        return compact(baseline[field]) + ' → ' + compact(top['aggregates'][field]['median']) + '/' + compact(top['aggregates'][field]['mean'])
    reason = ('For primary chr1/g16384, all-request feature median → upper-1% median/mean changes materialized B '
              + contrast('materialized_bytes_observed') + ' and LIT misses ' + contrast('lit_chunk_misses_count_replay')
              + ' (LIT crossing ' + baseline['lit_boundary'] + ' → ' + top['lit_boundary_fraction'] + '), with covered outer blocks '
              + contrast('covered_outer_blocks_count_metadata') + ' (outer crossing ' + baseline['outer_boundary'] + ' → '
              + top['outer_boundary_fraction'] + ') and observed zstd calls ' + contrast('zstd_calls_observed')
              + ' (four slowest: ' + ','.join(map(str, top['slowest_first_zstd_calls'][:4]))
              + '); these are tail/work/cache associations, not causal per-call duration measurements.')
    lines = [SIGNATURE, '', '# HW-REGION-1 saved p99 tail', '', reason, '',
        'Scope: the same ace-core / AMD EPYC 4344P host, CPU0, archives in RAM; no new measurements, codec calls, decompression, or cost-model predictions. '
        'Only selected first-CLEAN latency observations are joined to their saved untimed counters by request hash, query, offset and returned SHA256.', '',
        'The p50 query/time is the actual request at rank 500 after sorting (elapsed ns, query id). '
        'Work baselines **f** are instead separate per-feature medians over all 1000 requests, using the average of the central two; '
        'they need not belong to the p50-time query or to any one request and must not be added as a joint decomposition. '
        '**top** is the ten slowest requests, ranks 991–1000; their mean and ordinary median (average of the central two) are labelled. '
        '**p99 is rank 990 and is not a member of this upper 1%.** Work columns show f → top median / mean; '
        'boundary columns show the all-request binary-flag median → top fraction. The actual rank-500 request\'s work remains separately available in JSON/CSV.', '',
        'Metadata means the actual 68-byte header, 64-byte outer BO rows and four decoded-stream chunk tables. '
        'An outer boundary is crossed when the requested byte range covers more than one outer block. '
        'A logical LIT boundary is crossed when the union of required LIT chunk IDs for all covered blocks\' complete BO slices has more than one member '
        '(including a spanning slice or different chunk IDs introduced by successive covered blocks). '
        'These flags are independent of cache hits. Required IDs, actually accessed IDs, misses and bytes are separate CSV columns. '
        'FSE-layout denotes off/len/cmd streams; payloads may be raw or rANS and are not thereby zstd frames.', '',
        'Replay starts with empty caches, serves the twelve saved warmups, then the 1000 saved requests. '
        'It preserves the last decoded outer block and four-entry LRU per stream, exact L/O/N/C access order, ascending chunks, '
        'hit-age updates and first-slot age ties. Every request\'s replayed materialized bytes equals its saved counter, or the parser stops. '
        'Zstd calls/output bytes and elapsed ns below are raw observations, never reconstructed from geometry. '
        'The association column lists features whose top-group mean/fraction exceeds the all-request feature median; '
        'a cell with no such increase is explicitly labelled “none of these observed features”.', '',
        '| Case | p50 query / ns | p99 ns (rank 990) | Top10 time mean / median ns | Materialized B f → top median/mean | Zstd calls f → top median/mean | Zstd output B f → top median/mean | Decoded outer blocks f → top median/mean | LIT+FSE misses f → top median/mean | Outer crossing f → top fraction | LIT crossing f → top fraction | Tail associations |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for cell in cells:
        middle, upper = cell['median_rank500'], cell['upper1percent']
        aggregate = upper['aggregates']
        central = cell['all_request_feature_medians']
        def pair(field):
            return compact(central[field]) + ' → ' + compact(aggregate[field]['median']) + '/' + compact(aggregate[field]['mean'])
        lines.append('| ' + ' | '.join(('[{}](cases/{}.json)'.format(cell['case_id'], cell['case_id']),
            str(middle['query']) + ' / ' + str(middle['elapsed_ns_observed']), str(cell['p99_rank990']['elapsed_ns_observed']),
            compact(aggregate['elapsed_ns_observed']['mean']) + ' / ' + compact(aggregate['elapsed_ns_observed']['median']),
            pair('materialized_bytes_observed'), pair('zstd_calls_observed'), pair('zstd_output_bytes_observed'), pair('decoded_outer_blocks_count_replay'),
            compact(central['lit_chunk_misses_count_replay']) + '+' + compact(central['fse_layout_chunk_misses_count_replay']) + ' → '
            + compact(aggregate['lit_chunk_misses_count_replay']['median']) + '+' + compact(aggregate['fse_layout_chunk_misses_count_replay']['median']) + '/'
            + compact(aggregate['lit_chunk_misses_count_replay']['mean']) + '+' + compact(aggregate['fse_layout_chunk_misses_count_replay']['mean']),
            central['outer_boundary'] + ' → ' + upper['outer_boundary_fraction'], central['lit_boundary'] + ' → ' + upper['lit_boundary_fraction'],
            '; '.join(cell['tail_associations']))) + ' |')
    lines += ['', 'All 95 cells / 95000 requests matched their materialized-byte observations. Exact upper-group means/medians, rank-500 and rank-990 requests, '
              'every required/accessed/missed chunk ID and source references are in [tail/summary.json](tail/summary.json) and '
              '[tail/requests.csv.gz](tail/requests.csv.gz); [tail/geometry.json.gz](tail/geometry.json.gz) contains the public BO8Q/stream tables '
              'and warmup/query offsets needed to replay this without private archives. Display rounding does not affect rank selection or comparisons.', '',
              'Provenance: final audit `' + summary['final_audit']['sha256'] + '`; decoder source `' + DECODER_SHA256 + '`; '
              'saved-only parser `' + summary['source_sha256'] + '`. This tail analysis has its own provenance and does not alter the frozen numerical run.', '']
    return '\n'.join(line.rstrip() for line in lines).rstrip() + '\n'


def build(saved, decoder_source):
    require(sha(decoder_source) == DECODER_SHA256, 'saved decoder source pin differs')
    setup = saved.document('setup.json')
    require(set(setup['cases']) == set(ordered_cases()) and len(setup['inputs']) == 33, '95-cell source grid differs')
    original_source = Path(setup['deps']['aceapex']['path']) / 'c/aceapex_decode.c'
    require(original_source.is_file() and sha(original_source) == DECODER_SHA256, 'actual pinned ACE decoder differs from replay source')
    cases, geometries, count = [], [], 0
    compressed = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=compressed, compresslevel=9, mtime=0) as zipped:
        with io.TextIOWrapper(zipped, encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, lineterminator='\n')
            writer.writeheader()
            for case_id in ordered_cases():
                records, summary, geometry = analyze_case(saved, case_id)
                cases.append(summary)
                geometries.append(geometry)
                for record in records:
                    value = {k: json.dumps(v, separators=(',', ':')) if isinstance(v, list) else v for k, v in record.items()}
                    writer.writerow(value)
                count += len(records)
    require(len(cases) == 95 and count == 95000, 'incomplete replay; no report will be written')
    payload = compressed.getvalue()
    geometry_value = dict(schema='hw-region-1-tail-geometry-v1', source_sha256=sha(__file__), decoder_source_sha256=DECODER_SHA256,
                          final_audit=saved.audit_reference, no_payload_bytes=True, no_codecs=True, no_clocks=True, cases=geometries)
    geometry_stream = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=geometry_stream, compresslevel=9, mtime=0) as zipped:
        zipped.write(packed(geometry_value))
    geometry_payload = geometry_stream.getvalue()
    summary = dict(schema='hw-region-1-tail-v1', status='PASS', saved_data_only=True, no_codecs=True, no_clocks=True, no_new_measurements=True,
        source_sha256=sha(__file__), decoder_source=dict(path=str(Path(decoder_source).resolve()), sha256=DECODER_SHA256),
        actual_decoder_source=dict(path=str(original_source), sha256=DECODER_SHA256), final_audit=saved.audit_reference,
        final_audit_source_closure_sha256=hashlib.sha256(packed(saved.audit['source_bindings'])).hexdigest(),
        definitions=dict(central_request='rank500 sorted(elapsed_ns,query)', p99='rank990 sorted(elapsed_ns,query)',
            work_baseline='separate per-feature median across all1000; mean of central two; not a joint request/decomposition',
            upper1percent='ranks991-1000 sorted(elapsed_ns,query)', upper_median='arithmetic mean of central two of ten',
            outer_boundary='requested range covers >1 outer blocks', lit_boundary='union required LIT chunk IDs of complete BO slices of covered blocks has >1 member',
            observed='elapsed_ns, materialized_bytes, zstd_calls, zstd_output_bytes and API-family counts from saved observations',
            reconstructed='outer/chunk geometry and cache-state accesses/misses; no decompression or API cost predictions'),
        counts=dict(cases=95, requests=95000, replayed_warmup_requests=95 * WARMUPS, exact_materialized_byte_matches=95000, new_measurements=0),
        requests=dict(path='tail/requests.csv.gz', bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(), gzip_mtime=0, rows=95000, columns=list(CSV_COLUMNS)),
        geometry=dict(path='tail/geometry.json.gz', bytes=len(geometry_payload), sha256=hashlib.sha256(geometry_payload).hexdigest(), gzip_mtime=0, cases=95), cases=cases)
    return payload, geometry_payload, summary


def immutable(path, raw):
    path = Path(path)
    if path.exists():
        require(path.read_bytes() == raw, 'refuse to overwrite differing saved tail output: ' + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, default=HERE / 'audit/final.json')
    parser.add_argument('--decoder-source', type=Path, default=STATE / 'tail-decode-saved.c')
    parser.add_argument('--outputdir', type=Path, default=HERE)
    args = parser.parse_args()
    output = args.outputdir.resolve()
    require(output.is_relative_to(HERE.resolve()), 'tail outputs must stay in this experiment')
    decoder = args.decoder_source.resolve()
    require(decoder.is_relative_to(STATE.resolve()) and decoder.is_file(), 'decoder source must be the retained owned source copy')
    saved = Saved(args.audit)
    payload, geometry_payload, summary = build(saved, decoder)
    markdown = tail_text(summary).encode('utf-8')
    # No public output is written until every one of the 95000 checks passes.
    immutable(output / 'tail/requests.csv.gz', payload)
    immutable(output / 'tail/geometry.json.gz', geometry_payload)
    immutable(output / 'tail/summary.json', packed(summary))
    immutable(output / 'TAIL.md', markdown)
    print('TAIL_PASS', len(summary['cases']), summary['counts']['requests'], summary['requests']['sha256'], sha(output / 'tail/summary.json'))


if __name__ == '__main__':
    main()
