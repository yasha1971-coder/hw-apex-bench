# SPDX-License-Identifier: Apache-2.0
"""Independent saved-public-data casefix audit; no codecs, clocks or Git.

All reader comparisons use retained public gzip captures. Private artifact
paths are identities only and need not exist on the auditing machine.
"""
import argparse
from decimal import Decimal, localcontext
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
OLD = ROOT / 'evidence/hw-region-1'
CORPORA = ('chr1',) + tuple(f't2t-{i:02d}' for i in range(30))
PROFILES = ('aceapex', 'zstd_seekable', 'bgzip', 'twobit_casefix_mask1', 'twobit_original_mask1', 'twobit_original_mask0')
SEMANTICS = {name: 1 if name == 'twobit_original_mask1' else 2 if name == 'twobit_original_mask0' else 0 for name in PROFILES}
PIN = '58e20daa898a6fc338eae82e5d2ef7108d4fc07f'
LOCK = '/run/lock/ovh-bench.lock'
R = 16384
BINDS, UNIT_COUNTS, BLOCKED_UNITS, CAPTURE_CACHE, EXPECTED_IDENTITIES = {}, {}, {}, {}, {}
HOST = None
SOURCE_MAP = None
NATIVE = None


class Incomplete(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def valid_sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def digest(value):
    return hashlib.sha256(packed(value)).hexdigest()


def bind(path, value):
    path = Path(path).resolve()
    require(path.is_relative_to(ROOT.resolve()) and not path.is_relative_to((ROOT / '.work').resolve()), 'audit must read public repository evidence only')
    name = path.relative_to(ROOT).as_posix()
    require(BINDS.setdefault(name, value) == value, 'evidence changed while being audited: ' + name)


def sha(path):
    path = Path(path)
    if not path.is_file():
        raise Incomplete('missing public evidence: ' + str(path))
    with path.open('rb') as stream:
        value = hashlib.file_digest(stream, 'sha256').hexdigest()
    bind(path, value)
    return value


def unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'duplicate JSON key: ' + key)
        value[key] = item
    return value


def load(path):
    path = Path(path)
    if not path.is_file():
        raise Incomplete('missing public evidence: ' + str(path))
    raw = path.read_bytes()
    bind(path, hashlib.sha256(raw).hexdigest())
    return json.loads(raw, object_pairs_hook=unique)


def public_path(name):
    require(isinstance(name, str) and name, 'missing public path')
    marker = '/evidence/hw-region-2/casefix/'
    name = name.replace('\\', '/')
    if marker in name:
        name = name.split(marker, 1)[1]
    require(not name.startswith('/') and ':' not in name, 'expected a public casefix artifact')
    path = (HERE / name).resolve()
    require(path.is_relative_to(HERE.resolve()), 'casefix reference escaped stage')
    return path


def file_ref(value):
    require(isinstance(value, dict) and {'path', 'sha256'} <= value.keys() and valid_sha(value['sha256']), 'invalid public reference')
    path = public_path(value['path'])
    require(sha(path) == value['sha256'], 'public reference SHA differs: ' + str(path))
    if 'bytes' in value:
        require(integer(value['bytes']) and path.stat().st_size == value['bytes'], 'public reference byte count differs')
    return path


def json_ref(value):
    return load(file_ref(value))


def metadata_ref(value):
    return json.loads(gzip.decompress(file_ref(value).read_bytes()), object_pairs_hook=unique)


def quantile(values, p):
    require(values and all(integer(value, 1) for value in values), 'missing positive integer latency samples')
    return sorted(values)[(len(values) * p + 99) // 100 - 1]


def check_sources(value=None):
    global SOURCE_MAP
    names = ['evidence/hw-region-2/casefix/' + name for name in ('CALIBRATION.md', 'PROTOCOL.md', 'setup.py', 'drive.py', 'ovh_bench.py', 'native.c', 'worker.c', 'coordinate.h', 'controls.py')]
    names += ['evidence/hw-region-2/' + name for name in ('CALIBRATION.md', 'writer.py', 'lib2bit-casefix.patch')]
    expected = {name: sha(ROOT / name) for name in names}
    if SOURCE_MAP is None:
        SOURCE_MAP = expected
    require(expected == SOURCE_MAP, 'frozen source cohort changed during audit')
    if value is not None:
        require(value.get('source_sha256') == expected, 'record belongs to another source cohort')
    require((HERE / 'CALIBRATION.md').read_bytes() == (PARENT / 'CALIBRATION.md').read_bytes(), 'original forecast text changed')
    return expected


def artifact_identity(value):
    require(isinstance(value, dict) and isinstance(value.get('path'), str) and integer(value.get('bytes')) and valid_sha(value.get('sha256')), 'invalid retained artifact identity')


def overlap(intervals_a, intervals_b):
    i = j = count = 0
    first = None
    while i < len(intervals_a) and j < len(intervals_b):
        a, na = intervals_a[i]; b, nb = intervals_b[j]
        lo, hi = max(a, b), min(a + na, b + nb)
        if hi > lo:
            count += hi - lo
            if first is None:
                first = lo
        if a + na <= b + nb:
            i += 1
        else:
            j += 1
    return dict(count=count, first0=first)


def intervals(rows, length):
    end = 0
    for start, size in rows:
        require(integer(start) and integer(size, 1) and end <= start <= length and size <= length - start, 'invalid N/mask interval')
        end = start + size


def writer_metadata(record, input_record, original):
    value = metadata_ref(record)
    require(value['schema'] == 'hw-region-2-original-writer-v1' and value['status'] == 'PASS' and value['license'] == 'Apache-2.0'
            and value['source_sha256'] == sha(PARENT / 'writer.py') and value['clocks'] == value['native_calls'] == 0
            and value['measurements_of_time'] is False, 'wrong writer identity/timing scope')
    sequence, archive = value['sequence'], value['archive']
    require(sequence == input_record['sequence'] and value['fai'] == input_record['fai']
            and sequence['sha256'] == original['sequence_sha256'] and sequence['bytes'] == original['sequence_bytes']
            and sequence['alphabet'] == original['alphabet'] and value['structural_check']['sha256'] == sequence['sha256']
            and value['structural_check']['status'] == 'PASS' and value['structural_check']['case_preserved'] is True
            and value['structural_check']['lib2bit_invoked'] is False, 'full case-preserving structural proof differs')
    require(value['source_fasta']['sha256'] == input_record['sha256'] and value['source_fasta']['bytes'] == input_record['bytes'], 'writer FASTA input differs')
    intervals(archive['n_blocks'], sequence['bytes']); intervals(archive['mask_blocks'], sequence['bytes'])
    both = overlap(archive['n_blocks'], archive['mask_blocks'])
    require(both['count'] == original['alphabet'].get('n', 0) and both['first0'] == original['first_lowercase_n'], 'N/soft-mask overlap does not match exact lowercase-n source')
    require(archive['endianness'] == 'little' and archive['version'] == 0 and archive['length'] == sequence['bytes'], '2bit standard geometry differs')
    start = 16 + 1 + len(archive['name'].encode('ascii')) + 4 + 16 + 8 * (len(archive['n_blocks']) + len(archive['mask_blocks']))
    require(archive['packed_bases_offset'] == start and archive['bytes'] == start + (sequence['bytes'] + 3) // 4, '2bit extent differs')
    return value, both


def setup_stage():
    value = load(HERE / 'setup.json')
    require(value['schema'] == 'hw-region-2-casefix-setup-v1' and value['no_clocks'] is True and value['measurements_of_time'] is False
            and tuple(value['corpus_order']) == CORPORA and set(value['inputs']) == set(CORPORA), 'complete 31-corpus setup required')
    check_sources()
    for name, expected in value['identity']['source_sha256'].items():
        require(sha(ROOT / name) == expected, 'setup source changed: ' + name)
    old = load(PARENT / 'admission.json')
    require(old['status'] == 'KILL' and sha(PARENT / 'admission.json') == value['identity']['original_admission']['sha256'], 'original admission changed')
    require(old['identity']['source_sha256']['evidence/hw-region-2/writer.py'] == sha(PARENT / 'writer.py')
            and old['identity']['source_sha256']['evidence/hw-region-2/CALIBRATION.md'] == sha(PARENT / 'CALIBRATION.md'), 'original writer/calibration no longer immutable')
    patch = (PARENT / 'lib2bit-casefix.patch').read_bytes().splitlines()
    removed = [row[1:].strip() for row in patch if row.startswith(b'-') and not row.startswith(b'---')]
    added = [row[1:].strip() for row in patch if row.startswith(b'+') and not row.startswith(b'+++')]
    require(removed == [b"if(seq[pos] != 'N') seq[pos] = tolower(seq[pos]);"] and added == [b'seq[pos] = tolower(seq[pos]);'], 'casefix is not exactly the authorized one-line change')
    lib = value['lib2bit']
    require(lib['commit'] == PIN and lib['url'] == 'https://github.com/dpryan79/lib2bit.git'
            and lib['patch']['sha256'] == sha(PARENT / 'lib2bit-casefix.patch')
            and lib['original_source']['sha256'] == lib['variants']['original']['source_sha256']
            and lib['variants']['casefix']['source_sha256'] != lib['variants']['original']['source_sha256'], 'original/casefix source identities differ')
    original_c = [record for record in old['dependency']['source_files'] if record['path'].endswith('/2bit.c')]
    require(len(original_c) == 1 and lib['original_source']['sha256'] == original_c[0]['sha256'], 'original upstream source pin changed')
    require(lib['header_sha256'] == old['dependency']['header']['sha256'], 'upstream header pin changed')
    for name in ('original', 'casefix'):
        command = load(HERE / 'commands' / (name + '-compile') / 'command.json')
        variant = lib['variants'][name]
        require(command['status'] == 'COMPLETE' and command['returncode'] == 0
                and command['identity']['argv'] == ['taskset', '-c', '15', 'gcc', '-O3', '-fPIC', '-I' + lib['path'], '-c',
                                                    variant['source_path'], '-o', variant['object']['path']], 'original/casefix compiler flags differ')
        for stream in ('stdout', 'stderr'):
            path = HERE / 'commands' / (name + '-compile') / stream
            candidates = [item for item in command['artifacts'] if item['path'].endswith('/' + stream)]
            require(len(candidates) == 1 and sha(path) == candidates[0]['sha256'], 'casefix compile stream changed')
    preflight = load(PARENT / 'input-preflight.json')
    require(sha(PARENT / 'input-preflight.json') == value['identity']['parent_preflight']['sha256']
            == old['identity']['source_sha256']['evidence/hw-region-2/input-preflight.json'], 'parent preflight changed')
    old_setup = load(OLD / 'setup.json')
    require(sha(OLD / 'setup.json') == value['identity']['region1_setup']['sha256'] and value['deps'] == old_setup['deps']
            and value['binaries'] == old_setup['binaries'], 'accepted REGION-1 dependency/input foundation changed')
    require(sha(OLD / 'archives/chr1-g16384.json') == value['identity']['region1_chr1_archives']['sha256'], 'reused chr1 archive foundation changed')
    originals = {record['corpus']: record for record in preflight['records']}
    overlaps = {}
    for corpus in CORPORA:
        item, original = value['inputs'][corpus], originals[corpus]
        require(item['original'] == old_setup['inputs'][corpus] and item['original']['sha256'] == original['source_sha256']
                and item['original']['bytes'] == original['source_bytes'], 'original input identity changed')
        metadata, both = writer_metadata(item['writer_metadata'], item, original)
        overlaps[corpus] = both
        fai = item['fai']['geometry']
        if corpus == 'chr1':
            require(item['sha256'] == original['source_sha256'] and item['bytes'] == original['source_bytes'], 'chr1 FASTA changed')
        else:
            require(fai == dict(name=corpus, length=2097152, offset=len(corpus) + 2, line_bases=80, line_width=81)
                    and item['bytes'] == len(corpus) + 2 + 2097152 + (2097152 + 79) // 80, 'T2T FASTA wrapping changed')
        trace_stage(corpus, item)
        case_stage(corpus, value)
    return value, overlaps


def trace_stage(corpus, source):
    path = HERE / 'traces' / (corpus + '.json')
    require(sha(path) == source['trace']['sha256'] and path.stat().st_size == source['trace']['bytes'], 'mapped trace artifact changed')
    value = load(path)
    require(value['schema'] == 'hw-region-2-casefix-trace-v1' and value['corpus'] == corpus and value['resampled'] is False
            and value['request_bases'] == R and value['fai_geometry'] == source['fai']['geometry'], 'wrong mapped trace')
    old_path = OLD / 'traces' / (corpus + '.json'); old = load(old_path)
    require(sha(old_path) == value['original_trace']['sha256'] and value['seed_integer'] == old['seed_integer']
            and old['input_sha256'] == source['original']['sha256'] and old['input_bytes'] == source['original']['bytes'], 'old trace was regenerated or changed')
    fai = source['fai']['geometry']
    for key, old_key, count in (('warmups', 'warmup_offsets', 12), ('requests', 'offsets', 1000)):
        mapped, stats = [], dict(header=0, line_terminator=0, clamped=0, terminal=0, end_in_last_packed_byte=0)
        require(len(old[old_key]) == count, 'wrong original trace count')
        require(hashlib.sha256(b''.join(struct.pack('<Q', x) for x in old[old_key])).hexdigest() == old[key]['sha256'], 'old binary trace identity differs')
        for offset in old[old_key]:
            require(integer(offset) and offset <= source['original']['bytes'] - R, 'old offset outside domain')
            if corpus == 'chr1':
                delta = offset - fai['offset']
                if delta < 0:
                    base = 0; stats['header'] += 1
                else:
                    row, column = divmod(delta, fai['line_width'])
                    base = row * fai['line_bases'] + min(column, fai['line_bases'])
                    stats['line_terminator'] += int(column >= fai['line_bases'])
            else:
                base = offset
            start = min(base, fai['length'] - R)
            stats['clamped'] += int(start != base); stats['terminal'] += int(start + R == fai['length'])
            stats['end_in_last_packed_byte'] += int((start + R - 1) // 4 == (fai['length'] - 1) // 4)
            mapped.append(start)
        raw = b''.join(struct.pack('<Q', x) for x in mapped)
        require(value[key]['offsets'] == mapped and value[key]['sha256'] == hashlib.sha256(raw).hexdigest()
                and value[key]['bytes'] == 8 * count and value['statistics'][key] == stats, 'coordinate mapping/order/statistics differ')
        require(stats['terminal'] == stats['end_in_last_packed_byte'] == 0, 'required finite grid reaches unpatched EOF limitation')
    require(value['max_end0'] == max(value['requests']['offsets']) + R, 'trace end summary differs')
    return value


def case_stage(corpus, setup):
    value = load(HERE / 'archives' / (corpus + '.json'))
    source = setup['inputs'][corpus]
    require(value['schema'] == 'hw-region-2-casefix-archives-v1' and value['corpus'] == corpus and value['g'] == R
            and value['request_bases'] == R and value['setup_sha256'] == sha(HERE / 'setup.json')
            and value['sequence'] == source['sequence'] and value['fai'] == source['fai'] and value['trace'] == source['trace']
            and value['writer_metadata'] == source['writer_metadata'] and value['input'] == {k: source[k] for k in ('path', 'bytes', 'sha256')}
            and set(value['formats']) == {'aceapex', 'zstd_seekable', 'bgzip', 'twobit'}, 'archive case scope/input differs')
    for codec, record in value['formats'].items():
        artifact_identity(record)
        require(record['stored_bytes'] == record['bytes'] + sum(index['bytes'] for index in record['indexes']), 'required index bytes omitted')
        if codec == 'twobit':
            require(record['indexes'] == [] and record['sha256'] == source['twobit']['sha256'] and record['structural_bit_perfect'] is True
                    and record['sequence_sha256'] == source['sequence']['sha256'], '2bit case identity differs')
        else:
            require(record['effective_g'] == R and record['level'] == {'aceapex': 2, 'zstd_seekable': 3, 'bgzip': 6}[codec]
                    and record['bit_perfect'] is True and record['restore']['sha256'] == source['sha256']
                    and len(record['indexes']) == (2 if codec == 'bgzip' else 1)
                    and record['indexes'][0]['sha256'] == source['fai']['sha256'], 'codec geometry/restore/index identity differs')
    return value


def native_stage():
    global NATIVE
    value = load(HERE / 'native/build.json')
    require(value['schema'] == 'hw-region-2-casefix-native-v1' and value['status'] == 'PASS'
            and value['identity']['setup_sha256'] == sha(HERE / 'setup.json'), 'native build scope differs')
    check_sources(value['identity'])
    require(set(value['artifacts']['dsos']) == set(PROFILES), 'missing/extra native profile')
    artifact_identity(value['artifacts']['worker'])
    prepared = load(HERE / 'setup.json')
    for profile, record in value['artifacts']['dsos'].items():
        artifact_identity(record)
        command = load(HERE / 'commands' / ('native-' + profile) / 'command.json')
        argv = command['identity']['argv']
        require(command['status'] == 'COMPLETE' and command['returncode'] == 0 and argv[:4] == ['taskset', '-c', '15', 'gcc']
                and '-Wl,-Bsymbolic' in argv and '-fno-lto' in argv and '-DCOORD_LABEL="' + profile + '"' in argv
                and argv[-2:] == ['-o', record['path']] and record in command['artifacts'], 'native DSO build/source-isolation receipt differs')
        if profile.startswith('twobit_'):
            variant = prepared['lib2bit']['variants']['original' if 'original' in profile else 'casefix']
            require(variant['library_path'] in argv and '-DCOORD_STORE_MASKED=' + ('0' if profile.endswith('mask0') else '1') in argv
                    and '-DCOORD_ORIGINAL=' + ('1' if 'original' in profile else '0') in argv, 'native diagnostic/casefix library was substituted')
        for stream in ('stdout', 'stderr'):
            path = HERE / 'commands' / ('native-' + profile) / stream
            expected = [item for item in command['artifacts'] if item['path'].endswith('/' + stream)]
            require(len(expected) == 1 and sha(path) == expected[0]['sha256'], 'native build stdout/stderr changed')
    NATIVE = value
    return value


def capture_checks(observation, semantics, rows, trace_key):
    expected, returned = observation['expected'], observation['returned']
    for record in (expected, returned):
        artifact_identity(record)
        require(record['bytes'] == len(rows) * R, 'raw capture length differs')
    epath, rpath = file_ref(expected['public_gzip']), file_ref(returned['public_gzip'])
    key = (expected['public_gzip']['sha256'], returned['public_gzip']['sha256'], semantics)
    require(EXPECTED_IDENTITIES.setdefault(trace_key, expected['sha256']) == expected['sha256'], 'profiles received different reference strings')
    if key not in CAPTURE_CACHE:
        computed = []
        eh, rh = hashlib.sha256(), hashlib.sha256()
        with gzip.open(epath, 'rb') as left, gzip.open(rpath, 'rb') as right:
            for i in range(len(rows)):
                a, b = left.read(R), right.read(R)
                require(len(a) == len(b) == R, 'truncated public gzip capture')
                eh.update(a); rh.update(b)
                wanted = a.upper() if semantics == 2 else a
                differences = [(x, y) for x, y in zip(wanted, b) if x != y]
                permitted = sum(x == 110 and y == 78 for x, y in differences) if semantics == 1 else 0
                require(len(differences) == permitted, 'captured query violates declared equivalence/diagnostic transformation at query ' + str(i))
                computed.append(permitted)
            require(left.read(1) == right.read(1) == b'', 'capture has unaccounted trailing bytes')
        require(eh.hexdigest() == expected['sha256'] and rh.hexdigest() == returned['sha256'], 'decompressed public capture SHA differs')
        CAPTURE_CACHE[key] = (computed, expected['sha256'], returned['sha256'], len(rows))
    computed, ehash, rhash, n = CAPTURE_CACHE[key]
    require(n == len(rows) and ehash == expected['sha256'] and rhash == returned['sha256'], 'capture cache/raw binding differs')
    for row, permitted in zip(rows, computed):
        require(row['differences'] == row['permitted_n_to_N'] == permitted, 'raw row judgement differs from independently compared strings')


def expected_identity(mode, profile, case, trace, fresh, probe):
    return dict(mode=mode, profile=profile, case_sha256=digest(case), trace_sha256=digest(trace), fresh=fresh, probe=probe,
                source_sha256=SOURCE_MAP, native_build_sha256=sha(HERE / 'native/build.json'), setup_sha256=sha(HERE / 'setup.json'))


def observation(reference, mode, profile, case, trace, fresh=False, probe=False):
    value = json_ref(reference)
    require(value['schema'] == 'hw-region-2-casefix-observation-v1' and value['status'] == 'PASS' and value['profile'] == profile
            and value['identity'] == expected_identity(mode, profile, case, trace, fresh, probe), 'observation request/build identity differs')
    summary, rows = value['summary'], value['rows']
    n, w = len(trace['requests']['offsets']), len(trace['warmups']['offsets'])
    timed, semantics = mode == 'latency', SEMANTICS[profile]
    require(n > 0 and (probe or (n == 1000 and w == 12)), 'unprobed main/AA workload changed')
    require(summary['schema'] == 'hw-region-2-coordinate-summary-v1' and summary['mode'] == mode and summary['status'] == 'PASS'
            and summary['label'] == profile and summary['semantics'] == semantics and summary['byte_equivalent'] is (semantics == 0)
            and summary['fresh_per_request'] is fresh and summary['queries'] == summary['planned_queries'] == n
            and summary['warmups'] == w and summary['request_bases'] == R and summary['measurements_of_time'] is timed
            and summary['no_clocks'] is (not timed) and summary['query_clock_calls'] == (2 * n if timed else 0)
            and summary['opens'] == (n + w if fresh else 1) and len(rows) == n, 'native summary workload/clock/cache lifecycle differs')
    for i, (row, offset) in enumerate(zip(rows, trace['requests']['offsets'])):
        require(row['schema'] == 'hw-region-2-coordinate-row-v1' and row['query'] == i and row['start0'] == offset
                and row['requested_bases'] == R and row['verified'] is True and row['semantics'] == semantics,
                'raw query identity or verification changed')
        require(integer(row['elapsed_ns'], 1) if timed else row['elapsed_ns'] is None, 'wrong per-query clock scope')
        require(integer(row['open_ns'], 1) if timed and fresh else row['open_ns'] is None, 'fresh open timing scope differs')
    for stream in ('native_stdout', 'native_stderr'):
        file_ref(value[stream])
    printed = [json.loads(line, object_pairs_hook=unique) for line in file_ref(value['native_stdout']).read_bytes().splitlines()]
    require(printed == [summary] + rows and file_ref(value['native_stderr']).read_bytes() == b'', 'native raw stdout/stderr differs from observation')
    if timed:
        require(value['quantiles'] == dict(p50_ns=quantile([row['elapsed_ns'] for row in rows], 50), p99_ns=quantile([row['elapsed_ns'] for row in rows], 99)),
                'quantiles differ from all raw integer samples')
        require(summary['open_clock_calls'] == 2 * summary['opens'] and integer(summary['open_ns'], 1)
                and integer(summary['open_ns_total'], summary['open_ns'])
                and all(integer(summary[key], 1) for key in ('rss_before_open_kib', 'rss_after_open_kib', 'rss_after_queries_kib', 'peak_process_rss_kib')),
                'open/process-RSS observation missing')
        if not fresh:
            require(summary['open_ns_total'] == summary['open_ns'], 'one-handle main/AA open count differs')
    else:
        require(value['quantiles'] is None and summary['open_clock_calls'] == 0
                and all(summary[key] is None for key in ('open_ns', 'open_ns_total', 'rss_before_open_kib', 'rss_after_open_kib', 'rss_after_queries_kib', 'peak_process_rss_kib')),
                'untimed check contains open/query/RSS measurement')
    require('not library-exclusive' in summary['memory_scope'], 'peak process RSS was re-labelled as library-only memory')
    expected_memory = case['formats'][profile]['bytes'] if profile in ('aceapex', 'zstd_seekable') else 0
    require(summary['memory_archive_bytes'] == expected_memory, 'resident archive allocation scope differs')
    capture_checks(value, semantics, rows, (digest(case), digest(trace)))
    return value


def process_table(rows):
    result = {}
    require(isinstance(rows, list), 'raw process telemetry missing')
    for row in rows:
        pid = row['pid']; raw = row['raw_stat']; left, right = raw.index('('), raw.rindex(')'); fields = raw[right + 2:].split()
        require(integer(pid, 1) and pid not in result and int(raw[:left].strip()) == pid and row['comm'] == raw[left + 1:right]
                and row['state'] == fields[0] and row['ppid'] == int(fields[1]) and row['ticks'] == int(fields[11]) + int(fields[12])
                and row['start_ticks'] == int(fields[19]) and integer(row['uid']), 'process fields differ from raw /proc/PID/stat')
        result[pid] = row
    return result


def foreign_cpu(value):
    require(integer(value['interval_ns'], 1000000000) and integer(value['hz'], 1), 'foreign CPU observation shorter than one second')
    before, after = process_table(value['before']), process_table(value['after'])
    excluded = value['excluded_ancestry']
    require(excluded == sorted(set(excluded)) and all(integer(pid) for pid in excluded), 'invalid observer ancestry')
    def ancestry(pid, table):
        result = set()
        while pid in table and pid not in result:
            result.add(pid); pid = table[pid]['ppid']
        result.add(pid)
        return result
    leaves = [pid for pid in after if pid in excluded and not any(child in excluded and row['ppid'] == pid for child, row in after.items())]
    require(any(ancestry(pid, before) | ancestry(pid, after) == set(excluded) for pid in leaves), 'excluded PIDs are not the explicit controller ancestry')
    expected = []
    with localcontext() as ctx:
        ctx.prec = 28
        for pid, row in sorted(after.items()):
            if pid in excluded:
                continue
            old = before.get(pid); same = old is not None and old['start_ticks'] == row['start_ticks']
            delta = row['ticks'] - (old['ticks'] if same else 0)
            require(integer(delta), 'process CPU ticks regressed')
            high = 10 * delta * 1000000000 > value['hz'] * value['interval_ns']
            expected.append(dict(pid=pid, start_ticks=row['start_ticks'], uid=row['uid'], comm=row['comm'], ticks_delta=delta,
                observed_since_birth=not same, percent_one_cpu=str(Decimal(100) * delta * 1000000000 / (value['hz'] * value['interval_ns'])), exceeds_ten_percent=high))
    require(value['live_processes'] == expected and value['exceeded'] == [row for row in expected if row['exceeds_ten_percent']]
            and value['exited_pids'] == sorted(set(before) - set(after)) and value['inspection_errors'] == [], 'foreign process admission differs from retained raw ticks')
    return bool(value['exceeded'])


def other_cores(start, end):
    def parse(raw):
        result = {}
        for line in raw.splitlines():
            fields = line.split()
            if fields and fields[0].startswith('cpu') and fields[0][3:].isdigit():
                require(fields[0] not in result and len(fields) >= 9 and all(x.isdigit() for x in fields[1:9]), 'bad raw CPU accounting')
                result[fields[0]] = list(map(int, fields[1:9]))
        require('cpu0' in result, 'CPU0 accounting missing')
        return result
    first, last = parse(start['proc_stat_raw']), parse(end['proc_stat_raw'])
    require(first.keys() == last.keys(), 'CPU set changed')
    cpus = {}
    with localcontext() as ctx:
        ctx.prec = 28
        for name in first:
            if name == 'cpu0':
                continue
            delta = [b - a for a, b in zip(first[name], last[name])]
            require(min(delta) >= 0, 'CPU counters regressed')
            total = sum(delta); busy = total - delta[3] - delta[4]
            cpus[name] = dict(total_jiffies=total, busy_jiffies=busy, idle_jiffies=delta[3], iowait_jiffies=delta[4],
                              busy_percent=str(Decimal(100) * busy / total) if total else None)
    expected = dict(pinned_core=0, observational_only=True, cpus=cpus)
    require(start['other_cpu_delta'] == end['other_cpu_delta'] == expected, 'other-core deltas differ from raw accounting')


def ovh_receipt(record, path, status):
    global HOST
    require(record['schema'] == 'hw-region-2-casefix-ovh-v1' and status in ('CLEAN', 'LOADED') and record['status'] == status
            and record['helper_sha256'] == sha(HERE / 'ovh_bench.py') and record['protocol_sha256'] == sha(HERE / 'PROTOCOL.md')
            and record['calibration_sha256'] == sha(HERE / 'CALIBRATION.md') and record['lock_path'] == LOCK
            and record['timed_threads'] == 1 and record['foreign_cpu_percent_threshold'] == '10.0', 'wrong shared OVH helper/policy')
    argv, command = record['flock_command'], record['command']
    require(argv[:2] == ['flock', LOCK] and argv[3] == '-B' and argv[5:7] == ['_inside', '--receipt']
            and argv[8] == '--' and argv[9:] == command and argv[4].endswith('/evidence/hw-region-2/casefix/ovh_bench.py')
            and argv[7].endswith('/evidence/hw-region-2/casefix/' + path.relative_to(HERE).as_posix()), 'not the blocking external flock invocation')
    foreign = foreign_cpu(record['foreign_cpu_start']); loads = []
    for boundary in (record['start'], record['end']):
        require(boundary['hostname'] == 'ace-core' and 'AMD EPYC 4344P' in boundary['cpu'] and boundary['pinned_core'] == 0
                and boundary['timed_threads'] == 1 and integer(boundary['nproc'], 1) and boundary['date_u'], 'wrong timing host/core/T')
        signature = tuple(boundary[k] for k in ('hostname', 'cpu', 'kernel', 'governor', 'pinned_core', 'host_logical_cpus'))
        if HOST is None:
            HOST = signature
        require(signature == HOST, 'host/kernel/governor changed')
        fields = boundary['loadavg_raw'].split(); require(len(fields) == 5, 'literal load average missing')
        value = Decimal(fields[0]); require(value.is_finite() and value >= 0 and Decimal(boundary['load1_minus_T']) == value - 1, 'load1 minus T differs')
        loads.append(value)
    loaded = foreign or any(value - 1 > Decimal('1.0') for value in loads)
    require(loaded == (status == 'LOADED') and record['command_started'] is (not foreign and loads[0] <= Decimal('2.0')), 'load-only status/start differs')
    require(record['returncode'] == 0 and type(record['returncode']) is int if record['command_started'] else record['returncode'] is None,
            'worker ERROR cannot be retried as LOADED')
    other_cores(record['start'], record['end'])
    for suffix, field in (('.stdout', 'stdout_sha256'), ('.stderr', 'stderr_sha256')):
        require(sha(Path(str(path) + suffix)) == record[field], 'helper output SHA differs')
    require(sha(path.parent / 'worker.stdout') == record['stdout_sha256'] and sha(path.parent / 'worker.stderr') == record['stderr_sha256'], 'delivered worker output differs')
    if loaded:
        require(record['ps_command'] == 'ps -eo pid,user,pcpu,comm --sort=-pcpu | head -8' and record['ps_top8'], 'LOADED top-eight ps capture missing')
    return record


def worker_command(mode, profile, case, trace, prefix, fresh, probe):
    fmt = case['formats']['twobit' if profile.startswith('twobit_') else profile]
    indexes = fmt['indexes']
    result = ['taskset', '-c', '0' if mode == 'latency' else '15', NATIVE['artifacts']['worker']['path'], mode,
              NATIVE['artifacts']['dsos'][profile]['path'], fmt['path'], indexes[0]['path'] if indexes else '-',
              indexes[1]['path'] if profile == 'bgzip' else '-', case['fai']['geometry']['name'], case['input']['path'],
              case['fai']['path'], trace['warmups']['path'], trace['requests']['path'], prefix]
    return result + (['--fresh'] if fresh else []) + (['--probe'] if probe else [])


def trace_binary_identities(trace):
    for group in ('warmups', 'requests'):
        value = trace[group]
        require(all(integer(offset) for offset in value['offsets']), 'non-integer base trace')
        raw = b''.join(struct.pack('<Q', offset) for offset in value['offsets'])
        require(value['bytes'] == len(raw) and value['sha256'] == hashlib.sha256(raw).hexdigest(), 'control/witness binary trace identity differs')


def checked(reference, unit_id, profile, case, trace, fresh=False, probe=False):
    path = file_ref(reference)
    expected_path = HERE / 'checks' / unit_id / profile / 'observation.json'
    require(path == expected_path, 'untimed observation path/coordinate differs')
    trace_binary_identities(trace)
    value = observation(reference, 'check', profile, case, trace, fresh, probe)
    command_path = path.parent / 'command.json'; command = load(command_path)
    require(command['status'] == 'COMPLETE' and command['returncode'] == 0 and command['identity'] == value['identity'], 'untimed native command failed')
    argv = command['command']
    require(len(argv) >= 15 and argv[14].endswith('/.work/hw-region-2/casefix/captures/checks/' + unit_id + '/' + profile + '/out')
            and argv == worker_command('check', profile, case, trace, argv[14], fresh, probe), 'untimed worker command/DSO/index differs')
    return value


def timed_unit(reference, kind, unit_id, profile, case, trace, fresh=False, probe=False, allow_blocked=False):
    path = file_ref(reference); value = load(path)
    require(path == HERE / 'units' / kind / unit_id / (profile + '.json') and value['schema'] == 'hw-region-2-casefix-unit-v1'
            and value['status'] in ('CLEAN', 'BLOCKED: load')
            and value['identity'] == expected_identity('latency', profile, case, trace, fresh, probe), 'timed unit identity differs')
    attempts = value['attempts']; require(1 <= len(attempts) <= 3, 'three-attempt budget exceeded')
    raw_folder = HERE / 'raw' / kind / unit_id / profile
    require(raw_folder.is_dir() and {p.name for p in raw_folder.iterdir()} == {'attempt-' + str(i) for i in range(1, len(attempts) + 1)},
            'fourth/unretained raw attempt exists')
    selected = None
    blocked_attempts, worker_starts, query_clocks, open_clocks = [], 0, 0, 0
    for number, attempt in enumerate(attempts, 1):
        require(attempt['number'] == number and attempt['status'] in ('CLEAN', 'LOADED')
                and (number == len(attempts) or attempt['status'] == 'LOADED'), 'first CLEAN retaken or non-load attempt retried')
        receipt_path = file_ref(attempt['receipt'])
        require(receipt_path == raw_folder / ('attempt-' + str(number)) / 'ovh-bench.json', 'attempt receipt swapped')
        record = ovh_receipt(load(receipt_path), receipt_path, attempt['status'])
        worker_starts += int(record['command_started'])
        blocked_attempts.append(dict(number=number, status=attempt['status'], receipt=attempt['receipt'],
            command_started=record['command_started'], foreign_exceeded=record['foreign_cpu_start']['exceeded'],
            loadavg_start_raw=record['start']['loadavg_raw'], loadavg_end_raw=record['end']['loadavg_raw'],
            ps_top8=record.get('ps_top8'), ps_command=record.get('ps_command')))
        argv = record['command']
        require(len(argv) >= 15 and argv[14].endswith('/.work/hw-region-2/casefix/captures/' + kind + '/' + unit_id + '/' + profile + '/attempt-' + str(number) + '/out')
                and argv == worker_command('latency', profile, case, trace, argv[14], fresh, probe), 'timed native command/DSO/index differs')
        observed_path = receipt_path.parent / 'observation.json'
        require(bool(attempt['observation']) is record['command_started'] and observed_path.exists() is record['command_started'], 'worker start/result presence differs')
        if attempt['observation']:
            require(file_ref(attempt['observation']) == observed_path, 'attempt selected another result')
            observed = observation(attempt['observation'], 'latency', profile, case, trace, fresh, probe)
            query_clocks += observed['summary']['query_clock_calls']
            open_clocks += observed['summary']['open_clock_calls']
            if attempt['status'] == 'CLEAN':
                selected = observed
    if selected is None:
        require(value['status'] == 'BLOCKED: load' and value['selected'] is None and len(attempts) == 3
                and all(item['status'] == 'LOADED' for item in attempts), 'BLOCKED requires exactly three LOADED attempts')
        BLOCKED_UNITS[path.relative_to(HERE).as_posix()] = dict(unit=reference, kind=kind, unit_id=unit_id, profile=profile,
            selected=None, attempts=blocked_attempts, worker_starts=worker_starts, query_clock_calls=query_clocks, open_clock_calls=open_clocks)
        if allow_blocked:
            return None
        raise Incomplete('BLOCKED: load; validated three attempts at ' + str(path.relative_to(HERE)))
    require(value['status'] == 'CLEAN' and value['selected'] == attempts[-1]['observation'], 'winner is not first CLEAN')
    UNIT_COUNTS[path.relative_to(HERE).as_posix()] = dict(attempts=len(attempts), retaken=len(attempts) > 1,
        loaded=sum(item['status'] == 'LOADED' for item in attempts), observations=len(selected['rows']),
        query_clocks=selected['summary']['query_clock_calls'], open_clocks=selected['summary']['open_clock_calls'])
    return selected


def control_trace(trace, case, profile, aligned, crossing):
    require(trace['schema'] == 'hw-region-2-casefix-control-trace-v1' and trace['corpus'] == case['corpus']
            and trace['profile'] == profile and trace['request_bases'] == R and trace['fresh_per_request'] is True and trace['probe'] is True
            and trace['sequence_length'] == case['sequence']['bytes'] and trace['fai_geometry'] == case['fai']['geometry']
            and trace['aligned_base'] == aligned and trace['crossing_base'] == crossing, 'control trace scope differs')
    for key, pairs, role_key in (('warmups', 12, 'warmup_roles'), ('requests', 1000, 'roles')):
        offsets, roles = [], []
        for i in range(pairs):
            order = [('aligned', aligned), ('crossing', crossing)] if i % 2 == 0 else [('crossing', crossing), ('aligned', aligned)]
            for role, offset in order:
                offsets.append(offset); roles.append(role)
        require(trace[key]['offsets'] == offsets and trace[role_key] == roles, 'prespecified AB/BA roles/order differ')
    trace_binary_identities(trace)


def controls_plan(setup):
    value = load(HERE / 'controls-plan.json'); check_sources(value)
    require(value['schema'] == 'hw-region-2-casefix-controls-plan-v1' and value['status'] == 'PREPARED' and value['no_clocks'] is True
            and value['measurements_of_time'] is False and value['native_build_sha256'] == sha(HERE / 'native/build.json')
            and value['setup_sha256'] == sha(HERE / 'setup.json') and tuple(value['profiles']) == PROFILES[:4]
            and set(value['controls']) == set(PROFILES[:4]), 'four untimed controls not prepared')
    refs = []
    for profile in PROFILES[:4]:
        item = value['controls'][profile]; case, trace, selected = item['case'], item['trace'], item['selection']
        require(json_ref(item['trace_ref']) == trace, 'control public trace differs')
        a, b = selected['aligned_base'], selected['crossing_base']
        control_trace(trace, case, profile, a, b)
        if profile != 'twobit_casefix_mask1':
            require(case == case_stage('chr1', setup), 'boundary control used a different chr1 archive')
            fai = case['fai']['geometry']
            def at(base):
                return fai['offset'] + base // fai['line_bases'] * fai['line_width'] + base % fai['line_bases']
            require(b == a - 1 and selected['aligned_byte_span'] == [at(a), at(a + R - 1) + 1]
                    and selected['crossing_byte_span'] == [at(b), at(b + R - 1) + 1]
                    and len(selected['crossing']['native_units']) > len(selected['aligned']['native_units'])
                    and selected['crossing']['cold_materialized_bytes'] > selected['aligned']['cold_materialized_bytes']
                    and selected['archive']['sha256'] == case['formats'][profile]['sha256'], 'metadata control does not add a native unit/cold work')
            if profile == 'aceapex':
                parser = ROOT / 'evidence/hw-region-1/tail.py'
                require(selected['metadata_parser']['sha256'] == sha(parser)
                        and selected['metadata_parser']['bytes'] == parser.stat().st_size, 'ACE metadata parser source changed')
            delta = selected['boundary_byte'] - fai['offset']
            row, column = divmod(max(delta, 0), fai['line_width'])
            require(a == row * fai['line_bases'] + min(column, fai['line_bases']), 'aligned control not first base on/after boundary')
        else:
            require(a == 0 and b == R // 2 and case['corpus'] == 'method-mask-fixture' and case['sequence']['bytes'] == 3 * R + 16
                    and selected['mask_blocks'] == [[R, R]] and selected['n_blocks'] == []
                    and selected['aligned_masked_bases'] == 0 and selected['crossing_masked_bases'] == R // 2,
                    'synthetic mask control differs from declared fixture')
            metadata = metadata_ref(case['writer_metadata'])
            sequence = b'ACGT' * (R // 4) + b'acgt' * (R // 4) + b'ACGT' * ((R + 16) // 4)
            require(metadata['sequence']['sha256'] == hashlib.sha256(sequence).hexdigest() == case['sequence']['sha256']
                    and metadata['archive']['n_blocks'] == [] and metadata['archive']['mask_blocks'] == [[R, R]]
                    and metadata['structural_check']['sha256'] == case['sequence']['sha256'], 'synthetic source/mask/full restore proof differs')
        checked(item['equality_unit'], 'boundary-' + profile, profile, case, trace, fresh=True, probe=True)
        refs.append(item['equality_unit'])
    require(value['evidence_refs'] == refs, 'control equality units omitted')
    return value


def admission_stage(setup):
    value = load(HERE / 'admission.json'); check_sources(value)
    require(value['schema'] == 'hw-region-2-casefix-admission-v1' and value['status'] == 'PASS' and value['no_clocks'] is True
            and value['measurements_of_time'] is False and value['native_build_sha256'] == sha(HERE / 'native/build.json')
            and value['setup_sha256'] == sha(HERE / 'setup.json') and len(value['grid']) == 31 * 6, 'complete correctness admission missing')
    expected_grid = []
    for corpus in CORPORA:
        case = case_stage(corpus, setup); trace = load(HERE / 'traces' / (corpus + '.json'))
        for profile in PROFILES:
            path = HERE / 'checks' / corpus / profile / 'observation.json'
            reference = dict(path=path.relative_to(HERE).as_posix(), sha256=sha(path))
            checked(reference, corpus, profile, case, trace)
            expected_grid.append(reference)
    require(value['grid'] == expected_grid, 'admission grid order/coverage differs')
    case = case_stage('chr1', setup)
    witness_value = json_ref(value['lowercase_n_witness'])
    # This fixed positive point is part of the protocol, not an added EOF test.
    trace = dict(warmups=dict(path=witness_value['identity'].get('unused', ''), offsets=[]),
                 requests=dict(path='', offsets=[121757468 - 8192]))
    command = load(file_ref(value['lowercase_n_witness']).parent / 'command.json')['command']
    for key, position in (('warmups', 12), ('requests', 13)):
        raw = b''.join(struct.pack('<Q', off) for off in trace[key]['offsets'])
        trace[key].update(path=command[position], bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    witness = checked(value['lowercase_n_witness'], 'lowercase-n-witness', 'twobit_casefix_mask1', case, trace, probe=True)
    old = load(PARENT / 'admission.json')
    require(witness['expected']['sha256'] == witness['returned']['sha256'] == old['witness']['outputs']['expected']['sha256'],
            'casefix did not restore exactly the old failing reference string')
    require(file_ref(value['controls_plan']) == HERE / 'controls-plan.json', 'admission control-plan binding differs')
    plan = controls_plan(setup)
    return value, plan


def method_stage(setup, admission, plan):
    aa = load(HERE / 'method-aa.json'); check_sources(aa)
    require(aa['schema'] == 'hw-region-2-casefix-aa-v1' and aa['status'] == 'PASS' and set(aa['profiles']) == set(PROFILES)
            and file_ref(aa['admission']) == HERE / 'admission.json', 'six-profile A/A gate incomplete/failed')
    case = case_stage('chr1', setup); trace = load(HERE / 'traces/chr1.json')
    aa_result = {}
    for profile in PROFILES:
        item = aa['profiles'][profile]
        first = timed_unit(item['first'], 'aa-first', 'chr1', profile, case, trace)
        second = timed_unit(item['second'], 'aa-second', 'chr1', profile, case, trace)
        a, b = first['quantiles']['p50_ns'], second['quantiles']['p50_ns']
        require(item['first_p50_ns'] == a and item['second_p50_ns'] == b and item['strict_under_five_percent'] is True
                and 20 * abs(b - a) < a, 'strict integer A/A <5% failed')
        aa_result[profile] = dict(first_p50_ns=a, second_p50_ns=b, relative_difference=str(Fraction(abs(b - a), a)), passed=True)
    controls = load(HERE / 'controls.json'); check_sources(controls)
    require(controls['schema'] == 'hw-region-2-casefix-controls-v1' and controls['status'] == 'PASS'
            and set(controls['controls']) == set(PROFILES[:4]) and file_ref(controls['plan']) == HERE / 'controls-plan.json'
            and controls['native_build_sha256'] == sha(HERE / 'native/build.json') and controls['setup_sha256'] == sha(HERE / 'setup.json')
            and (HERE / 'controls.json').read_bytes() == (HERE / 'controls-summary.json').read_bytes(), 'boundary gate missing/failed/changed')
    sha(HERE / 'controls-summary.json')
    boundary_result, refs = {}, []
    for profile in PROFILES[:4]:
        item, intended = controls['controls'][profile], plan['controls'][profile]
        observed = timed_unit(item['unit'], 'boundary', 'boundary-' + profile, profile, intended['case'], intended['trace'], fresh=True, probe=True)
        groups = {role: [row['elapsed_ns'] for row, name in zip(observed['rows'], intended['trace']['roles']) if name == role]
                  for role in ('aligned', 'crossing')}
        require(all(len(values) == 1000 for values in groups.values()), 'balanced 1000-pair control changed')
        a, b = quantile(groups['aligned'], 50), quantile(groups['crossing'], 50)
        require(item['aligned_p50_ns'] == a and item['crossing_p50_ns'] == b and item['strictly_more_cost'] is True and b > a
                and item['aligned_p99_ns'] == quantile(groups['aligned'], 99) and item['crossing_p99_ns'] == quantile(groups['crossing'], 99)
                and item['selection'] == intended['selection'] and item['trace'] == intended['trace_ref'], 'strict crossing cost gate or metadata selection differs')
        boundary_result[profile] = dict(aligned_p50_ns=a, crossing_p50_ns=b, passed=True)
        refs.append(item['unit'])
    require(controls['evidence_refs'] == refs, 'boundary unit evidence omitted')
    return dict(AA=aa_result, boundaries=boundary_result)


def main_stage(setup, checkpoint=False):
    rows, case_refs, main_values = [], [], {}
    actual = set((HERE / 'cases').glob('*.json'))
    planned = {HERE / 'cases' / (name + '.json') for name in CORPORA}
    if checkpoint:
        length = 0
        while length < len(CORPORA) and HERE / 'cases' / (CORPORA[length] + '.json') in actual:
            length += 1
        require(0 < length < len(CORPORA) and actual == {HERE / 'cases' / (name + '.json') for name in CORPORA[:length]},
                'checkpoint cases must form one nonempty incomplete contiguous prefix')
        corpora = CORPORA[:length]
    else:
        corpora = CORPORA
    if not checkpoint and planned - actual:
        raise Incomplete('main comparative grid: ' + str(len(actual & planned)) + '/31 complete corpus summaries')
    if not checkpoint:
        require(actual == planned, 'main grid contains extra corpus summaries')
    for index, corpus in enumerate(corpora):
        path = HERE / 'cases' / (corpus + '.json')
        value = load(path); check_sources(value)
        start = index % len(PROFILES)
        require(value['schema'] == 'hw-region-2-casefix-case-v1' and value['status'] == 'COMPLETE' and value['corpus'] == corpus
                and value['order'] == list(PROFILES[start:] + PROFILES[:start]) and set(value['units']) == set(PROFILES), 'main case completion/profile order differs')
        for field, filename in (('admission', 'admission.json'), ('aa', 'method-aa.json'), ('controls', 'controls.json')):
            require(file_ref(value[field]) == HERE / filename, 'main gate reference changed')
        require(file_ref(value['archive_case']) == HERE / 'archives' / (corpus + '.json'), 'main archive-case reference changed')
        case = case_stage(corpus, setup); trace = load(HERE / 'traces' / (corpus + '.json'))
        profiles = {}
        for profile in PROFILES:
            observed = timed_unit(value['units'][profile], 'main', corpus, profile, case, trace)
            summary = observed['summary']
            fmt = case['formats']['twobit' if profile.startswith('twobit_') else profile]
            record = dict(corpus=corpus, profile=profile, byte_equivalent=SEMANTICS[profile] == 0,
                p50_ns=observed['quantiles']['p50_ns'], p99_ns=observed['quantiles']['p99_ns'],
                stored_bytes=fmt['stored_bytes'], archive_bytes=fmt['bytes'], index_bytes=sum(item['bytes'] for item in fmt['indexes']),
                archive_sha256=fmt['sha256'], open_ns=summary['open_ns'], open_observations=1,
                rss_before_open_kib=summary['rss_before_open_kib'], rss_after_open_kib=summary['rss_after_open_kib'],
                rss_after_queries_kib=summary['rss_after_queries_kib'], peak_process_rss_kib=summary['peak_process_rss_kib'],
                memory_scope=summary['memory_scope'], unit=value['units'][profile])
            profiles[profile] = record
            rows.append(record)
        main_values[corpus] = profiles
        case_refs.append(dict(path=path.relative_to(HERE).as_posix(), sha256=sha(path)))
    expected_units = {'units/main/' + corpus + '/' + profile + '.json' for corpus in corpora for profile in PROFILES}
    expected_units |= {'units/' + part + '/chr1/' + profile + '.json' for part in ('aa-first', 'aa-second') for profile in PROFILES}
    expected_units |= {'units/boundary/boundary-' + profile + '/' + profile + '.json' for profile in PROFILES[:4]}
    expected_files = set(expected_units)
    if checkpoint:
        # Only the first profile of the next ordered corpus was attempted in
        # this retained stop; later profiles/corpora must have no hidden units.
        blocked_corpus = CORPORA[len(corpora)]
        blocked_profile = PROFILES[len(corpora) % len(PROFILES)]
        blocked_path = HERE / 'units/main' / blocked_corpus / (blocked_profile + '.json')
        blocked_ref = dict(path=blocked_path.relative_to(HERE).as_posix(), sha256=sha(blocked_path))
        case, trace = case_stage(blocked_corpus, setup), load(HERE / 'traces' / (blocked_corpus + '.json'))
        require(timed_unit(blocked_ref, 'main', blocked_corpus, blocked_profile, case, trace, allow_blocked=True) is None,
                'checkpoint next profile must be BLOCKED with no selected result')
        blocked = BLOCKED_UNITS[blocked_ref['path']]
        require(blocked['worker_starts'] == blocked['query_clock_calls'] == blocked['open_clock_calls'] == 0
                and all(not item['command_started'] for item in blocked['attempts']), 'this checkpoint must contain admission-only LOADED attempts, no benchmark clock')
        expected_files.add(blocked_ref['path'])
    require(set(UNIT_COUNTS) == expected_units and {path.relative_to(HERE).as_posix() for path in (HERE / 'units').rglob('*.json')} == expected_files,
            'accepted/blocked timing-unit coverage differs from declared grid')
    raw_units = {path for path in (HERE / 'raw').glob('*/*/*') if path.is_dir()}
    require(raw_units == {HERE / ('raw/' + name[len('units/'):-len('.json')]) for name in expected_files}, 'orphan/future raw timing unit exists')
    main = main_values['chr1']
    ace, fixed = main['aceapex'], main['twobit_casefix_mask1']
    p1 = 100 * ace['stored_bytes'] <= 95 * fixed['stored_bytes']
    p2 = 4 * fixed['p50_ns'] <= ace['p50_ns']
    wins = [corpus for corpus in corpora[1:] if main_values[corpus]['twobit_casefix_mask1']['p50_ns'] < main_values[corpus]['aceapex']['p50_ns']]
    ties = [corpus for corpus in corpora[1:] if main_values[corpus]['twobit_casefix_mask1']['p50_ns'] == main_values[corpus]['aceapex']['p50_ns']]
    forecasts = dict(P1=dict(passed=p1, verdict='HIT' if p1 else 'MISS', ACE_stored_bytes=ace['stored_bytes'], twobit_stored_bytes=fixed['stored_bytes'],
                             ratio=str(Fraction(ace['stored_bytes'], fixed['stored_bytes'])), lhs=100 * ace['stored_bytes'], rhs=95 * fixed['stored_bytes']),
        P2=dict(passed=p2, verdict='HIT' if p2 else 'MISS', ACE_p50_ns=ace['p50_ns'], casefix_p50_ns=fixed['p50_ns'],
                ratio=str(Fraction(fixed['p50_ns'], ace['p50_ns'])), lhs=4 * fixed['p50_ns'], rhs=ace['p50_ns']),
        P3=dict(passed=len(wins) >= 28, verdict='HIT' if len(wins) >= 28 else 'MISS', wins=len(wins), required=28, total=30, winning_corpora=wins, ties=ties))
    if checkpoint:
        forecasts['P3'].update(passed=None, verdict='PENDING', observed=len(corpora) - 1, pending=31 - len(corpora))
    return rows, case_refs, forecasts


def accounting():
    return dict(timed_logical_units=len(UNIT_COUNTS), attempts=sum(value['attempts'] for value in UNIT_COUNTS.values()),
                retaken=sum(value['retaken'] for value in UNIT_COUNTS.values()), loaded_attempts=sum(value['loaded'] for value in UNIT_COUNTS.values()),
                accepted_query_timing_observations=sum(value['observations'] for value in UNIT_COUNTS.values()),
                accepted_query_clock_calls=sum(value['query_clocks'] for value in UNIT_COUNTS.values()),
                accepted_open_clock_calls=sum(value['open_clocks'] for value in UNIT_COUNTS.values()))


def checkpoint_accounting():
    result = accounting()
    blocked_attempts = sum(len(value['attempts']) for value in BLOCKED_UNITS.values())
    blocked_retaken = sum(len(value['attempts']) > 1 for value in BLOCKED_UNITS.values())
    blocked_loaded = sum(item['status'] == 'LOADED' for value in BLOCKED_UNITS.values() for item in value['attempts'])
    result.update(accepted_unit_attempts=result['attempts'], blocked_unit_attempts=blocked_attempts,
                  accepted_retaken=result['retaken'], blocked_timed_logical_units=len(BLOCKED_UNITS),
                  started_timed_logical_units=len(UNIT_COUNTS) + len(BLOCKED_UNITS),
                  attempts=result['attempts'] + blocked_attempts, retaken=result['retaken'] + blocked_retaken,
                  loaded_attempts=result['loaded_attempts'] + blocked_loaded,
                  blocked_worker_starts=sum(value['worker_starts'] for value in BLOCKED_UNITS.values()),
                  blocked_query_clock_calls=sum(value['query_clock_calls'] for value in BLOCKED_UNITS.values()),
                  blocked_open_clock_calls=sum(value['open_clock_calls'] for value in BLOCKED_UNITS.values()))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('setup', 'admission', 'method', 'checkpoint', 'all'), default='all')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = dict(schema='hw-region-2-casefix-independent-audit-v1', stage=args.stage, saved_data_only=True, no_codecs=True, no_clocks=True,
                  private_paths_required=False, source_binding_base='repository')
    try:
        sha(HERE / 'audit.py')
        for name in ('CALIBRATION.md', 'PROTOCOL.md', 'EXECUTION_NOTE.md'):
            sha(HERE / name)
        if (HERE / 'KILL.json').exists():
            load(HERE / 'KILL.json')
            raise Incomplete('retained KILL prevents full performance completion')
        setup, overlaps = setup_stage()
        result.update(setup=dict(corpora=31, archives=124), N_softmask_overlap=overlaps,
                      original_admission_sha256=sha(PARENT / 'admission.json'), patch_sha256=sha(PARENT / 'lib2bit-casefix.patch'))
        if args.stage != 'setup':
            native_stage()
            admitted, plan = admission_stage(setup)
            result['admission'] = dict(status='PASS', grid_observations=186, grid_captured_queries=186000,
                equivalent_profiles=4, equivalent_grid_queries=124000, diagnostic_grid_queries=62000,
                lowercase_n_witness='PASS', synthetic_and_boundary_query_captures=8000, warmups_verified_by_frozen_worker=True)
        if args.stage in ('method', 'checkpoint', 'all'):
            result['method'] = method_stage(setup, admitted, plan)
        if args.stage == 'checkpoint':
            rows, refs, forecasts = main_stage(setup, checkpoint=True)
            count = checkpoint_accounting()
            require(len(refs) == 16 and len(rows) == 96 and count['timed_logical_units'] == 112
                    and count['blocked_timed_logical_units'] == 1 and count['attempts'] == 115
                    and count['accepted_query_timing_observations'] == 116000,
                    'retained checkpoint scope differs from 16 complete cases plus one three-load admission stop')
            result.update(rows=rows, case_refs=refs, prefix_forecasts=forecasts, completion='BLOCKED: load', integrity_only=True, full_comparison_complete=False,
                          missing_corpora=list(CORPORA[len(refs):]), blocked_units=[BLOCKED_UNITS[name] for name in sorted(BLOCKED_UNITS)])
            for path in HERE.glob('*.py'):
                sha(path)
        if args.stage == 'all':
            rows, refs, forecasts = main_stage(setup)
            result.update(rows=rows, case_refs=refs, forecasts=forecasts)
            count = accounting()
            require(count['timed_logical_units'] == 202 and count['accepted_query_timing_observations'] == 206000, 'complete accepted timing count differs')
            for path in HERE.glob('*.py'):
                sha(path)
        check_sources()
        counts = checkpoint_accounting() if args.stage == 'checkpoint' else accounting()
        result.update(status='PASS', host=HOST, counts=dict(cases=len(result.get('case_refs', [])), rows=len(result.get('rows', [])), **counts),
                      independently_compared_capture_pairs=len(CAPTURE_CACHE))
    except Incomplete as error:
        result.update(status='INCOMPLETE', reason=str(error), counts=accounting())
    except (ValueError, KeyError, TypeError, IndexError, OSError, struct.error) as error:
        result.update(status='FAIL', reason=type(error).__name__ + ': ' + str(error), counts=accounting())
    result['source_bindings'] = [dict(path=name, sha256=value) for name, value in sorted(BINDS.items())]
    raw = packed(result)
    if args.output:
        path = args.output.resolve()
        require(path.is_relative_to((HERE / 'audit').resolve()), 'audit output escaped audit directory')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    print(raw.decode(), end='')
    return 0 if result['status'] == 'PASS' else 2 if result['status'] == 'INCOMPLETE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
