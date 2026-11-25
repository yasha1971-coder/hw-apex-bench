"""Independent HW-GIFT-1e saved-data controller; no codecs or clocks.

This module does not import setup, instrument, controls or the orchestrator.
It reads retained evidence, independently derives integer predicates, and uses
read-only Git inspection to bind the original preregistration. Only --output
writes a requested JSON audit artifact.
"""
import argparse
import ast
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CALIBRATION = '8b1fba61c325a4020dbad165a058d91848f9f914'
PINS = {'v1.5.4': ('945f27758c0fd67b636103a38dbf050266c6b90a',10504,'48c325656391f471396d57800b0bc99408ae6fbf'),
        'v1.5.7': ('f8745da6ff1ad1e7bab384bd1f9d742439278e99',10507,'ac66b19e6bd6b83238bf008eecc1298105298532')}
CASES = ((10,256),(10,1024),(3,256))
FULL_BYTES, PREFIX_BYTES = 100000000,16777216
FULL_SHA = '2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8'
PREFIX_SHA = 'e6d287b341ea0dc183fb334ae05e558df4540752bf2be88da9570338fa711585'
LOCK = '/run/lock/ovh-bench.lock'
HINT_LINES = (b'    assert(zcs->maxFrameSize < INT_MAX);\n'
              b'    ZSTD_CCtx_setParameter(zcs->cstream, ZSTD_c_srcSizeHint, (int)zcs->maxFrameSize);\n')
SOURCE_BINDINGS = {}
PRIVATE_CHECKED, PRIVATE_UNAVAILABLE = set(),set()
HOST = None
COVERED_RECEIPTS = set()
COVERED_RESULTS = set()


class Incomplete(ValueError):
    pass


def check(ok, reason):
    if not ok:
        raise ValueError(reason)


def positive(value):
    return type(value) is int and value > 0


def valid_sha(value):
    return isinstance(value,str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def packed(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()


def bind(path, digest):
    path = Path(path).resolve()
    if path.is_relative_to((ROOT/'evidence').resolve()):
        import os
        name = os.path.relpath(path,HERE).replace('\\','/')
        check(SOURCE_BINDINGS.setdefault(name,digest) == digest, 'evidence changed during audit: '+name)


def sha(path):
    path = Path(path)
    if not path.is_file():
        raise Incomplete('missing evidence: '+str(path))
    with path.open('rb') as stream:
        value = hashlib.file_digest(stream,'sha256').hexdigest()
    bind(path,value)
    return value


def load(path):
    path = Path(path)
    if not path.is_file():
        raise Incomplete('missing evidence: '+str(path))
    raw = path.read_bytes()
    bind(path,hashlib.sha256(raw).hexdigest())
    def unique(pairs):
        value = {}
        for key,item in pairs:
            check(key not in value, 'duplicate JSON key: '+key)
            value[key] = item
        return value
    return json.loads(raw,object_pairs_hook=unique)


def public(name):
    check(isinstance(name,str) and name, 'missing evidence path')
    path = (HERE/name).resolve()
    check(path.is_relative_to(HERE.resolve()), 'evidence path escapes experiment')
    return path


def file_ref(value, allow_prior=False):
    check(isinstance(value,dict) and set(value) == {'path','sha256'} and valid_sha(value['sha256']), 'invalid evidence reference')
    path = (HERE/value['path']).resolve() if allow_prior else public(value['path'])
    check(path.is_relative_to((ROOT/'evidence').resolve()), 'reference escapes benchmark evidence')
    check(sha(path) == value['sha256'], 'referenced bytes changed: '+value['path'])
    return path


def json_ref(value, allow_prior=False):
    path = file_ref(value,allow_prior)
    return load(path),path


def private(name, digest, size=None):
    check(isinstance(name,str) and valid_sha(digest), 'invalid private artifact identity')
    path = Path(name)
    if not path.is_file():
        PRIVATE_UNAVAILABLE.add(name)
        return False
    if size is not None:
        check(path.stat().st_size == size, 'private size differs: '+name)
    if (name,digest) not in PRIVATE_CHECKED:
        check(sha(path) == digest, 'private SHA differs: '+name)
        PRIVATE_CHECKED.add((name,digest))
    return True


def median5(values):
    check(isinstance(values,list) and len(values) == 5 and all(positive(v) for v in values), 'five positive integer observations required')
    return sorted(values)[2]


def index(core, scope, level, g):
    return list(PINS).index(core)*6 + ('full','prefix').index(scope)*3 + CASES.index((level,g))


def order(core, scope, level, g, repeat, method=False):
    if method:
        return ['A','A']
    return ['B','A'] if (index(core,scope,level,g)+repeat)%2 else ['A','B']


def predicates(old, new=None):
    a,b = old['A']['median_ns'],old['B']['median_ns']
    kill = b < 2*a
    p1 = dict(available=True,passed=b >= 5*a,A_ns=a,B_ns=b,ratio=str(Fraction(b,a)))
    p2 = dict(available=False,passed=None)
    if new is not None:
        c,d = new['A']['median_ns'],new['B']['median_ns']
        p2 = dict(available=True,passed=5*max(c,d) < 6*min(c,d),A_ns=c,B_ns=d,ratio=str(Fraction(d,c)))
    return dict(P1=p1,P2=p2,Kill=dict(available=True,triggered=kill),search_admitted=bool(p1['passed'] and p2['passed'] and not kill))


def cpu_delta(start, end):
    def parse(boundary):
        check('proc_stat_raw' in boundary and 'proc_stat_error' in boundary, 'missing per-core observation')
        if boundary['proc_stat_error'] or not isinstance(boundary['proc_stat_raw'],str):
            raise ValueError('capture unavailable')
        values = {}
        for line in boundary['proc_stat_raw'].splitlines():
            fields = line.split()
            if fields and fields[0].startswith('cpu') and fields[0][3:].isdigit():
                if len(fields) < 9 or not all(v.isdigit() for v in fields[1:9]) or fields[0] in values:
                    raise ValueError('invalid per-core counters')
                values[fields[0]] = list(map(int,fields[1:9]))
        if 'cpu0' not in values:
            raise ValueError('missing CPU0')
        return values
    try:
        first,last = parse(start),parse(end)
        if first.keys() != last.keys():
            raise ValueError('CPU set changed')
        cpus = {}
        for name in first:
            if name == 'cpu0':
                continue
            deltas = [b-a for a,b in zip(first[name],last[name])]
            if min(deltas) < 0:
                raise ValueError('counter regression')
            total,idle,wait = sum(deltas),deltas[3],deltas[4]
            busy = total-idle-wait
            cpus[name] = dict(total_jiffies=total,busy_jiffies=busy,idle_jiffies=idle,iowait_jiffies=wait,
                              busy_percent=100.0*busy/total if total else None)
        expected = dict(status='ok',pinned_core=0,cpus=cpus)
    except ValueError:
        expected = None
    actual = start.get('other_cpu_delta')
    check(isinstance(actual,dict) and actual == end.get('other_cpu_delta') and actual.get('pinned_core') == 0,
          'per-core observations differ across boundaries')
    if expected is None:
        check(actual.get('status') == 'unavailable' and actual.get('cpus') == {} and isinstance(actual.get('error'),str), 'unavailable observation not identified')
    else:
        check(actual == expected, 'other-core busy/total differs from raw /proc/stat')


def receipt(value, status):
    global HOST
    check(value.get('schema') == 'ovh-bench-v2' and value.get('load1_threshold') == '2.0'
          and value.get('status') == status and status in ('CLEAN','LOADED'), 'wrong or unsuccessful load receipt')
    check(value.get('lock_path') == LOCK and value.get('helper_sha256') == sha(HERE.parent/'hw-gift-1b/ovh_bench.py'), 'shared lock/helper source changed')
    argv,command = value.get('flock_command'),value.get('command')
    check(isinstance(argv,list) and len(argv) >= 6 and argv[:2] == ['flock',LOCK] and argv[3] == '-B' and argv[5] == '_inside', 'blocking external flock missing')
    check(isinstance(command,list) and command and argv[-len(command):] == command, 'flock command mismatch')
    if value.get('command_started'):
        check(type(value.get('returncode')) is int and value['returncode'] == 0, 'worker ERROR cannot be a load retry')
    else:
        check(value.get('command_started') is False and value.get('returncode') is None and status == 'LOADED', 'unstarted CLEAN command')
    loads = []
    for boundary in (value.get('start'),value.get('end')):
        check(isinstance(boundary,dict) and boundary.get('hostname') == 'ace-core' and boundary.get('pinned_core') == 0
              and isinstance(boundary.get('cpu'),str) and 'AMD EPYC 4344P' in boundary['cpu'], 'wrong host/CPU/core')
        check(isinstance(boundary.get('date_u'),str) and boundary['date_u'] and positive(boundary.get('nproc')),
              'missing literal date/nproc receipt')
        signature = tuple(boundary.get(k) for k in ('hostname','cpu','kernel','governor','pinned_core','nproc'))
        check(all(isinstance(boundary.get(k),str) and boundary[k] for k in ('kernel','governor')), 'missing host/kernel/governor')
        if HOST is None:
            HOST = signature
        check(HOST == signature, 'host/build environment changed across timed rounds')
        raw = boundary.get('loadavg_raw')
        check(isinstance(raw,str) and len(raw.split()) == 5, 'missing literal loadavg receipt')
        number = Decimal(raw.split()[0])
        check(number.is_finite() and number >= 0, 'invalid load1')
        loads.append(number)
    check(any(n > Decimal('2.0') for n in loads) == (status == 'LOADED'), 'load classification differs before rounding')
    check(value['command_started'] == (loads[0] <= Decimal('2.0')), 'start marker contradicts load1')
    cpu_delta(value['start'],value['end'])
    if status == 'LOADED':
        check(value.get('ps_command') == 'ps -eo pid,user,pcpu,comm --sort=-pcpu | head -8'
              and isinstance(value.get('ps_top8'),str) and value['ps_top8'], 'LOADED receipt lacks literal ps top eight')


def verify_setup():
    value = load(HERE/'setup.json')
    check(value.get('schema') == 'hw-gift-1e-setup-v1' and value.get('no_clocks') is True
          and value.get('measurements_of_time') is False and value.get('cflags') == '-O3 -fPIC -fno-lto', 'wrong setup/flags')
    protocol = value['protocol']
    check(protocol['commit'] == CALIBRATION and protocol['sha256'] == sha(HERE/'CALIBRATION.md')
          and protocol['setup_sha256'] == sha(HERE/'setup.py')
          and protocol['bridge_container_sha256'] == sha(HERE.parent/'hw-gift-1c/timing.py'), 'setup source/preregistration changed')
    original = subprocess.check_output(['git','-C',str(ROOT),'show',CALIBRATION+':evidence/hw-gift-1e/CALIBRATION.md'],stderr=subprocess.PIPE)
    check(original == (HERE/'CALIBRATION.md').read_bytes(), 'first CALIBRATION bytes changed')
    check(set(value['cores']) == set(PINS) and value['upstream']['full_commit_history'] is True, 'setup omitted a core/history')
    for core,(commit,version,tag) in PINS.items():
        tagged = value['upstream']['tags'][core]
        check((tagged['commit'],tagged['version'],tagged['tag_object']) == (commit,version,tag)
              and hashlib.sha256(tagged['tag_payload'].encode()).hexdigest() == tagged['tag_payload_sha256'], 'tag object/peeled pin changed')
        build = value['cores'][core]
        check(build['source_clean'] is True and build['commit'] == commit and build['tag_object'] == tag
              and build['version'] == build['expected_version_number'] == version and core[1:] in build['cli_version'], 'core source/CLI version changed')
        check(build['identity']['compiler'] == value['compiler'] and build['identity']['cflags'] == value['cflags']
              and build['identity']['protocol'] == protocol, 'cores use different compiler/setup flags')
        for command in build['build_commands']:
            for stream in ('stdout','stderr'):
                name = Path(command[stream+'_path']).name
                check(sha(HERE/'setup-logs'/name) == command[stream+'_sha256'], 'public setup build log differs')
        private(build['library_path'],build['library_sha256']);private(build['cli_path'],build['cli_sha256'])
        for name,digest in build['headers_sha256'].items():
            private(str(Path(build['path'])/name),digest)
    frozen = value['frozen']
    check(set(frozen['source_sha256']) == {'A-compress.c','B-compress.c','decompress.c','zstd_seekable.h','bridge.c'}, 'frozen source set changed')
    equality = frozen['writer_equality']
    check(equality['tagged_v157_minus_exact_hint_lines_equals_v154'] is True and equality['removed_lines'] == HINT_LINES.decode()
          and equality['hint_lines_sha256'] == hashlib.sha256(HINT_LINES).hexdigest()
          and equality['original_writer_blob'] == '113f6f99ce254e4a47679cdf749840f0670c7738'
          and equality['hinted_writer_blob'] == '4997807d2514a6aee7bab288412610fe99eb53e3', 'frozen writer patch/source identity changed')
    files = {}
    for name,digest in frozen['source_sha256'].items():
        source = Path(frozen['path'])/name
        if private(str(source),digest):
            files[name] = source.read_bytes()
    tree = ast.parse((HERE.parent/'hw-gift-1c/timing.py').read_text(encoding='utf-8'))
    literals = [ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
                and any(isinstance(t,ast.Name) and t.id == 'BRIDGE' for t in n.targets)]
    check(len(literals) == 1 and hashlib.sha256(literals[0].encode()).hexdigest() == frozen['source_sha256']['bridge.c'], 'frozen bridge differs from retained 1c')
    if {'A-compress.c','B-compress.c'} <= files.keys():
        a,b = files['A-compress.c'],files['B-compress.c']
        check(a.count(HINT_LINES) == 1 and a.replace(HINT_LINES,b'') == b and b'ZSTD_c_srcSizeHint' not in b, 'actual B has a setter or source drift')
        for name,key in (('A-compress.c','hinted_writer_blob'),('B-compress.c','original_writer_blob')):
            data = files[name]
            check(hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest() == equality[key], 'actual source Git blob differs')
    return value


def literal(path, name):
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    values = [ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
              and any(isinstance(t,ast.Name) and t.id == name for t in n.targets)]
    check(len(values) == 1, 'missing unique literal: '+name)
    return values[0]


def verify_provenance(value):
    required = {'CALIBRATION.md','PROTOCOL.md','setup.py','instrument.py','controls.py','run.py','../hw-gift-1b/ovh_bench.py'}
    check(value.get('calibration_commit') == CALIBRATION and value.get('calibration_sha256') == sha(HERE/'CALIBRATION.md')
          and value.get('protocol_sha256') == sha(HERE/'PROTOCOL.md') and set(value['source_hashes']) == required,
          'source cohort/preregistration changed')
    for name,digest in value['source_hashes'].items():
        path = (HERE/name).resolve()
        check(path.is_relative_to((ROOT/'evidence').resolve()) and sha(path) == digest, 'source changed: '+name)


def verify_build(core, setup):
    path = HERE/'native'/core/'build.json'
    value = load(path)
    check(value.get('schema') == 'hw-gift-1e-native-v1', 'unknown native build schema')
    ident = value['identity']
    prepared = setup['cores'][core]
    check(ident['core'] == core and ident['core_commit'] == PINS[core][0]
          and ident['instrument_sha256'] == sha(HERE/'instrument.py') and ident['setup_sha256'] == sha(HERE/'setup.json')
          and ident['core_setup'] == prepared and ident['frozen_from_commit'] == PINS['v1.5.4'][0], 'native core/source/setup drift')
    check(ident['protocol']['calibration']['commit'] == CALIBRATION
          and ident['protocol']['calibration']['sha256'] == sha(HERE/'CALIBRATION.md')
          and ident['protocol']['execution_protocol']['sha256'] == sha(HERE/'PROTOCOL.md'), 'native protocol binding changed')
    base = setup['frozen']['source_sha256']
    check(ident['frozen_source_sha256'] == base and ident['hint_A'] == 'setter present' and ident['hint_B'] == 'setter absent'
          and ident['hint_patch_sha256'] == hashlib.sha256(HINT_LINES).hexdigest(), 'writer hint/source fingerprint changed')
    checks = literal(HERE/'instrument.py','UNTIMED_CHECKS')
    bridge = literal(HERE.parent/'hw-gift-1c/timing.py','BRIDGE').encode()
    compiled = dict(base,**{'bridge.c':hashlib.sha256(bridge+checks).hexdigest()})
    check(ident['source_sha256'] == compiled and ident['untimed_checks_sha256'] == hashlib.sha256(checks).hexdigest(),
          'compiled bridge changed beyond common untimed correctness helpers')
    check(ident['static_library_sha256'] == prepared['library_sha256'] and ident['cli_sha256'] == prepared['cli_sha256']
          and ident['cli_version'] == prepared['cli_version'] and ident['loader'] == 'RTLD_LOCAL'
          and ident['flags'] == ['-O3','-fPIC','-fno-lto','-shared','-Wl,-Bsymbolic'], 'native compiler/link/core build changed')
    for name,digest in prepared['headers_sha256'].items():
        check(ident['core_headers_sha256'][name.removeprefix('lib/')] == digest, 'cross-core header drift')
    check(set(value['libraries']) == {'A','B'}, 'missing native variant')
    for variant,item in value['libraries'].items():
        check(item['zstd_version_number'] == PINS[core][1] and item['zstd_version_string'] == core[1:]
              and '-Wl,-Bsymbolic' in item['command'] and '-fno-lto' in item['command'], 'actually linked core version/flags differ')
        private(item['path'],item['sha256'])
        for stream in ('stdout','stderr'):
            sha(HERE/'native'/core/f'{variant}-build.{stream}')
    folder = Path(value['libraries']['A']['path']).parent
    for name,digest in compiled.items():
        private(str(folder/name),digest)
    for name,digest in ident['core_headers_sha256'].items():
        private(str(Path(prepared['path'])/'lib'/name),digest)
    return value


def verify_request(value):
    core,scope,level,g = value['core'],value['scope'],value['level'],value['g']
    check(value.get('schema') == 'hw-gift-1e-cell-v1' and core in PINS and scope in ('full','prefix') and (level,g) in CASES,
          'request outside frozen grid')
    check(value['variants'] == ['A','B'] and value['core_commit'] == PINS[core][0], 'request core/variants changed')
    size,digest = (FULL_BYTES,FULL_SHA) if scope == 'full' else (PREFIX_BYTES,PREFIX_SHA)
    check((value['corpus'],value['input_bytes'],value['input_sha256'],value['full_corpus_bytes'],value['full_corpus_sha256'],value['prefix_bytes'])
          == ('enwik8',size,digest,FULL_BYTES,FULL_SHA,None if scope == 'full' else PREFIX_BYTES), 'request source scope changed')
    check(value['calibration_commit'] == CALIBRATION and value['calibration_sha256'] == sha(HERE/'CALIBRATION.md')
          and value['protocol_sha256'] == sha(HERE/'PROTOCOL.md') and value['instrument_sha256'] == sha(HERE/'instrument.py')
          and value['setup_sha256'] == sha(HERE/'setup.json'), 'request source/protocol binding changed')
    native_path = HERE/'native'/core/'build.json'
    native = load(native_path)
    check(value['native_build_sha256'] == sha(native_path) and value['frozen_source_sha256'] == native['identity']['source_sha256']
          and value['protocol_commit'] == native['identity']['protocol']['execution_protocol']['commit'], 'request native/build protocol changed')
    unsigned = dict(value)
    supplied = unsigned.pop('cell_id')
    label = f'{core}-{scope}-L{level}-G{g}-'
    check(supplied == label+hashlib.sha256(packed(unsigned)).hexdigest()[:16], 'request cell identity changed')
    private(value['input_path'],digest,size)


def verify_row(row, request, variant, slot, timed, size=None, digest=None):
    size = request['input_bytes'] if size is None else size
    digest = request['input_sha256'] if digest is None else digest
    check(row['variant'] == variant and row['slot'] == slot and row.get('bit_perfect') is True
          and (row['decoded_bytes'],row['decoded_sha256']) == (size,digest), 'slot or complete restore differs')
    check((positive(row.get('compression_ns')) if timed else row.get('compression_ns') is None)
          and row.get('decode_ns') is None, 'wrong timing scope')
    count = (size+request['g']-1)//request['g']
    empty = row.get('empty_terminal_frames')
    check(type(empty) is int and empty in (0,1) and (empty == 0 or size%request['g'] == 0)
          and row['frame_count'] == count+empty and row['seek_table_bytes'] == 17+12*row['frame_count']
          and row['seek_checksum_flag'] is True and row.get('seek_checksums_verified') is True
          and row.get('empty_terminal_verified') is True, 'frame/CRC/terminal-empty proof missing')
    check(positive(row['archive_bytes']) and row['archive_bytes'] > row['seek_table_bytes'] and valid_sha(row['archive_sha256']), 'invalid archive identity')
    check(row['header']['dict_id'] == 0 and row['header']['content_size'] in (None,min(size,request['g'])), 'unexpected frame dictionary/content size')
    private(row['archive_path'],row['archive_sha256'],row['archive_bytes'])


def verify_selfcheck(value, request):
    check(value.get('schema') == 'hw-gift-1e-selfcheck-v1' and value.get('status') == 'PASS'
          and value.get('clock_calls') == 0 and value.get('measurements_of_time') is False
          and value['cell_id'] == request['cell_id'] and value['cell_sha256'] == hashlib.sha256(packed(request)).hexdigest()
          and value['core'] == request['core'] and value['scope'] == request['scope'], 'untimed selfcheck scope changed')
    check(len(value['results']) == 2, 'untimed A/B selfcheck missing a variant')
    for slot,variant in enumerate(('A','B')):
        verify_row(value['results'][slot],request,variant,slot,False)
    known = request['core'] == 'v1.5.7' and request['scope'] == 'prefix'
    check(value['known_1d_checked'] is known, 'known-answer eligibility differs')
    if known:
        previous,path = json_ref(value['known_1d_source'],True)
        check(path == HERE.parent/f"hw-gift-1d/cells/train/L{request['level']}-G{request['g']}.json"
              and previous['status'] == 'COMPLETE' and previous['input_sha256'] == request['input_sha256'], 'known 1d source/input differs')
        for row in value['results']:
            prior = previous['variants']['original' if row['variant'] == 'A' else 'nohint']
            check((row['archive_bytes'],row['archive_sha256']) == (prior['archive_bytes'],prior['archive_sha256']), 'known complete 1d archive differs')
    else:
        check(value['known_1d_source'] is None, 'inapplicable known-answer source')


def verify_controls():
    value = load(HERE/'method-controls.json')
    check(value.get('schema') == 'hw-gift-1e-method-controls-v1' and value.get('status') == 'PASS'
          and value.get('clock_calls') == 0 and value.get('measurements_of_time') is False, 'untimed controls did not pass')
    bindings = {'calibration_sha256':'CALIBRATION.md','protocol_sha256':'PROTOCOL.md','instrument_sha256':'instrument.py',
                'controls_sha256':'controls.py','setup_sha256':'setup.json','ovh_helper_sha256':'../hw-gift-1b/ovh_bench.py'}
    for key,name in bindings.items():
        check(value[key] == sha(HERE/name), 'controls source changed: '+name)
    expected_bindings = {key:value[key] for key in bindings}
    check(set(value['cores']) == set(PINS), 'method controls omitted a core')
    setup = load(HERE/'setup.json')
    for core,item in value['cores'].items():
        request,_ = json_ref(item['request']);verify_request(request)
        selfcheck,_ = json_ref(item['selfcheck']);verify_selfcheck(selfcheck,request)
        check(item['status'] == 'PASS' and item['clock_calls'] == 0 and item['measurements_of_time'] is False
              and item['bindings'] == expected_bindings and (request['core'],request['scope'],request['level'],request['g']) == (core,'full',10,256),
              'per-core controls/bindings differ')
        check(item['control_input_bytes'] == 262144 and item['control_input_sha256'] == '0cdfd008d5327addbf5b118b4a8d616a8cc2971627727b10bfb20e97920881e7', 'deterministic control slice changed')
        positive,negative = item['positive'],item['negative_changed_input']
        check(positive['input_bytes'] == negative['input_bytes'] == 262144
              and positive['input_sha256'] == item['control_input_sha256']
              and negative['input_sha256'] != positive['input_sha256'], 'changed-input distinction failed')
        for group,variants in ((positive,['A','A']),(negative,['A'])):
            check(group['clock_calls'] == 0 and group['control_override'] is True and len(group['results']) == len(variants), 'control invokes timers or loses duplicate slots')
            for slot,variant in enumerate(variants):
                verify_row(group['results'][slot],request,variant,slot,False,group['input_bytes'],group['input_sha256'])
        identities = [(r['archive_bytes'],r['archive_sha256']) for r in positive['results']]
        check(identities[0] == identities[1] and negative['results'][0]['archive_sha256'] != identities[0][1]
              and item['corrupt_magic_rejected'] is True, 'positive/negative/corrupt-magic control failed')
        versions = item['runtime_versions']
        check(set(versions['libraries']) == {'A','B'} and all(r == dict(number=PINS[core][1],string=core[1:]) for r in versions['libraries'].values())
              and versions['cli_version'] == setup['cores'][core]['cli_version']
              and versions['cli_sha256'] == setup['cores'][core]['cli_sha256']
              and versions['static_library_sha256'] == setup['cores'][core]['library_sha256'], 'runtime versions differ from prepared core')
    known = value['known_1d']
    request,_ = json_ref(known['request']);verify_request(request)
    selfcheck,_ = json_ref(known['selfcheck']);verify_selfcheck(selfcheck,request)
    check((request['core'],request['scope'],request['level'],request['g']) == ('v1.5.7','prefix',10,256)
          and known['source'] == selfcheck['known_1d_source'] and known['cell_id'] == request['cell_id'], 'known-answer gate scope differs')
    cases = [('1.00','1.00',False),('2.00','2.00',False),('2.01','0.00',True),('0.00','2.01',True)]
    check(len(value['load_gate_cases']) == len(cases), 'missing load gate known answers')
    for row,(start,end,answer) in zip(value['load_gate_cases'],cases):
        actual = any(Decimal(v)>Decimal('2.0') for v in (row['start'],row['end']))
        check((row['start'],row['end'],row['expected_loaded'],row['actual_loaded']) == (start,end,answer,actual), 'load decision known answer failed')
    check(value['other_cpu_known_answer'] == dict(status='ok',pinned_core=0,cpus={'cpu1':dict(total_jiffies=10,busy_jiffies=3,idle_jiffies=7,iowait_jiffies=0,busy_percent=30.0)}),
          'other-core observation known answer failed')
    return value


def verify_preparation():
    setup = verify_setup()
    value = load(HERE/'preparation.json')
    check(value.get('schema') == 'hw-gift-1e-preparation-v1' and value.get('status') == 'PASS', 'preparation did not pass')
    verify_provenance(value['provenance'])
    check(file_ref(value['setup']) == HERE/'setup.json' and file_ref(value['controls']) == HERE/'method-controls.json', 'preparation references different method gates')
    check(set(value['native_builds']) == set(PINS), 'preparation lacks both tagged builds')
    for core in PINS:
        check(file_ref(value['native_builds'][core]) == HERE/'native'/core/'build.json', 'preparation uses different native build')
        verify_build(core,setup)
    verify_controls()
    return value


def verify_worker(value, request, selfcheck, pair, sequence, method):
    check(value.get('schema') == 'hw-gift-1e-worker-v1' and value['core'] == request['core']
          and value['core_commit'] == request['core_commit'] and value['scope'] == request['scope']
          and value['cell_id'] == request['cell_id'] and value['cell_sha256'] == hashlib.sha256(packed(request)).hexdigest()
          and value['pair_index'] == pair and value['order'] == sequence and value['method_control'] is method,
          'worker identity/order/method differs')
    check(value.get('clock_calls') == 2*len(sequence) and value.get('measurements_of_time') is True
          and value.get('control_override') is False and value.get('cpu_affinity') == [0] and value.get('lock_path') == LOCK,
          'worker timing/native/source scope differs')
    for key in ('input_bytes','input_sha256','calibration_sha256','protocol_sha256','instrument_sha256','native_build_sha256'):
        check(value[key] == request[key], 'worker binding differs: '+key)
    check(value['selfcheck_sha256'] == hashlib.sha256(packed(selfcheck)).hexdigest(), 'worker untimed manifest differs')
    check(len(value['results']) == len(sequence), 'worker lost measurement slots')
    baseline = {r['variant']:r for r in selfcheck['results']}
    fields = ('archive_bytes','archive_sha256','header','frame_count','seek_table_bytes','seek_checksum_flag',
              'empty_terminal_frames','seek_checksums_verified','empty_terminal_verified')
    for slot,variant in enumerate(sequence):
        row = value['results'][slot]
        verify_row(row,request,variant,slot,True)
        check(all(row[k] == baseline[variant][k] for k in fields), 'timed archive/frame metadata differs from first untimed manifest')
    return value['results']


def verify_command(value, request_name, result_name, pair, sequence, method, method_name):
    args = value['command']
    check(len(args) == (13 if method else 14) and args[1] == '-B' and args[3:5] == ['worker','--cell']
          and args[6:11] == ['--pair',str(pair),'--order',','.join(sequence),'--output'], 'worker command/arguments differ')
    def suffix(path, name):
        return isinstance(path,str) and path.replace('\\','/').endswith('/evidence/hw-gift-1e/'+name)
    check(suffix(args[2],'instrument.py') and suffix(args[5],request_name) and suffix(args[11],result_name), 'command input/output/source path differs')
    check(args[12:] == ['--method'] if method else args[12] == '--method-check' and suffix(args[13],method_name),
          'worker method gate command differs')


def verify_repeats(summary, request, selfcheck, method):
    records = summary['repeats']
    blocked = summary['status'] == 'BLOCKED: load'
    check(isinstance(records,list) and (1 <= len(records) <= 5 if blocked else len(records) == 5), 'wrong logical repeat count')
    rows = []
    counters = dict(logical_repeats=len(records),attempts=0,retaken=0,loaded_attempts=0)
    for pair,item in enumerate(records):
        sequence = order(request['core'],request['scope'],request['level'],request['g'],pair,method)
        check(item['pair_index'] == pair and item['order'] == sequence and isinstance(item['attempts'],list)
              and 1 <= len(item['attempts']) <= 3, 'repeat order/index/three-attempt budget changed')
        attempts = item['attempts']
        counters['attempts'] += len(attempts)
        counters['retaken'] += len(attempts) > 1
        kind = f"method/{request['core']}" if method else f"cells/{request['core']}/{request['scope']}-L{request['level']}-G{request['g']}"
        folder = HERE/'raw'/kind/f'repeat-{pair}'
        check(folder.is_dir() and {p.name for p in folder.iterdir()} == {f'attempt-{n}' for n in range(1,len(attempts)+1)},
              'unretained/fourth attempt or first CLEAN retaken')
        selected_rows = None
        for number,attempt in enumerate(attempts,1):
            check(attempt['attempt'] == number and attempt['status'] in ('CLEAN','LOADED')
                  and (number == len(attempts) or attempt['status'] == 'LOADED'), 'attempt sequence does not stop at first CLEAN')
            record,path = json_ref(attempt['receipt'])
            wanted = folder/f'attempt-{number}'/'ovh-bench.json'
            check(path == wanted and record == attempt['receipt_data'] and record['status'] == attempt['status'], 'embedded/raw receipt differs')
            COVERED_RECEIPTS.add(path)
            receipt(record,attempt['status'])
            result_name = (wanted.parent/'result.json').relative_to(HERE).as_posix()
            verify_command(record,summary['request_path'],result_name,pair,sequence,method,summary.get('method_check_path'))
            for stream in ('stdout','stderr'):
                check(sha(Path(str(path)+'.'+stream)) == record[stream+'_sha256'], 'raw helper output bytes differ')
            check(sha(path.parent/'worker.stdout') == record['stdout_sha256'], 'delivered raw worker stdout differs')
            if record['command_started']:
                check(attempt['result'] is not None, 'started worker lacks a retained result')
                worker,result_path = json_ref(attempt['result'])
                check(result_path == path.parent/'result.json' and load(Path(str(path)+'.stdout')) == worker, 'stdout/result identity differs')
                COVERED_RESULTS.add(result_path)
                selected_rows = verify_worker(worker,request,selfcheck,pair,sequence,method)
            else:
                check(attempt['result'] is None and not (path.parent/'result.json').exists()
                      and Path(str(path)+'.stdout').read_bytes() == b'', 'unstarted worker has output/result')
            counters['loaded_attempts'] += attempt['status'] == 'LOADED'
        last = attempts[-1]
        if blocked and pair == len(records)-1:
            check(len(attempts) == 3 and all(a['status'] == 'LOADED' for a in attempts)
                  and item['selected_result'] is None and item['selected_receipt'] is None
                  and summary['ps_top8'] == last['receipt_data']['ps_top8'], 'BLOCKED summary lacks three retained LOADED attempts')
        else:
            check(last['status'] == 'CLEAN' and item['selected_result'] == last['result'] and item['selected_receipt'] == last['receipt']
                  and selected_rows is not None, 'selected observation is not the first CLEAN')
            rows.append(selected_rows)
    for key,expected in (('planned_repeats',5),('started_repeats',len(records)),('retaken_repeats',counters['retaken']),('loaded_attempts',counters['loaded_attempts'])):
        check(type(summary.get(key)) is int and summary[key] == expected, 'summary counter differs: '+key)
    return rows,counters


def verify_summary(path, method=False):
    value = load(path)
    schema = 'hw-gift-1e-method-v1' if method else 'hw-gift-1e-cell-v1'
    check(value.get('schema') == schema and value['status'] in (('PASS','FAIL','BLOCKED: load') if method else ('COMPLETE','BLOCKED: load')),
          'unknown/incomplete summary')
    verify_provenance(value['provenance'])
    request,_ = json_ref(dict(path=value['request_path'],sha256=value['request_sha256']))
    verify_request(request)
    selfcheck,_ = json_ref(dict(path=value['selfcheck_path'],sha256=value['selfcheck_sha256']))
    verify_selfcheck(selfcheck,request)
    check(file_ref(value['controls']) == HERE/'method-controls.json', 'summary refers to other controls')
    for key in ('core','core_commit','scope','corpus','level','g','protocol_sha256','calibration_sha256','instrument_sha256',
                'native_build_sha256','setup_sha256','input_bytes','input_sha256','full_corpus_bytes','full_corpus_sha256','prefix_bytes'):
        check(value[key] == request[key], 'summary/request differs: '+key)
    check(value['cell_index'] == index(request['core'],request['scope'],request['level'],request['g']), 'cell index changed')
    if method:
        check((request['scope'],request['level'],request['g']) == ('full',10,256), 'AA control uses another cell')
    else:
        gate,gate_path = json_ref(dict(path=value['method_check_path'],sha256=value['method_check_sha256']))
        check(gate_path == HERE/f"method-{request['core']}.json" and gate['status'] == 'PASS'
              and gate['core'] == request['core'] and gate['native_build_sha256'] == request['native_build_sha256'], 'main timing lacks per-core AA admission')
    rows,counters = verify_repeats(value,request,selfcheck,method)
    derived = {}
    if value['status'] != 'BLOCKED: load':
        if method:
            first,second = [r[0]['compression_ns'] for r in rows],[r[1]['compression_ns'] for r in rows]
            a,b = median5(first),median5(second)
            check(value['first_ns'] == first and value['second_ns'] == second and value['median_first_ns'] == a
                  and value['median_second_ns'] == b and value['status'] == ('PASS' if 20*abs(b-a)<a else 'FAIL'), 'AA medians/verdict differ from raw')
            derived = dict(first_ns=first,second_ns=second,median_first_ns=a,median_second_ns=b,passed=20*abs(b-a)<a)
        else:
            for variant in ('A','B'):
                items = [next(r for r in pair if r['variant'] == variant) for pair in rows]
                times = [r['compression_ns'] for r in items]
                identities = {(r['archive_bytes'],r['archive_sha256']) for r in items}
                check(len(identities) == 1, 'one variant changed archive between repetitions')
                size,digest = identities.pop()
                derived[variant] = dict(compression_ns=times,median_ns=median5(times),min_ns=min(times),archive_bytes=size,archive_sha256=digest)
            check(value['variants'] == derived, 'cell statistics differ from raw integer values')
    return dict(status=value['status'],summary=value,request=request,derived=derived,counters=counters)


def verify_decision(old, new=None):
    expected = predicates(old['derived'],None if new is None else new['derived'])
    value = load(HERE/'decision.json')
    check(value.get('schema') == 'hw-gift-1e-decision-v1' and value['calibration_sha256'] == sha(HERE/'CALIBRATION.md')
          and value['protocol_sha256'] == sha(HERE/'PROTOCOL.md'), 'decision protocol changed')
    for name in ('P1','P2'):
        wanted = {k:v for k,v in expected[name].items() if k != 'ratio'}
        check(value[name] == wanted, 'primary verdict differs before rounding: '+name)
    check(value['Kill'] == expected['Kill'] and value['search_admitted'] is expected['search_admitted'], 'Kill/search admission differs from primary predicates')
    kill = expected['Kill']['triggered']
    check(value['status'] == ('STOP: Kill' if kill else 'PRIMARY COMPLETE' if new is not None else 'PRIMARY INCOMPLETE'), 'decision status differs')
    required = {'v1.5.4'} | ({'v1.5.7'} if new is not None else set())
    check(set(value['primary_cells']) == required, 'decision omits/adds primary cell')
    for core,item in value['primary_cells'].items():
        check(file_ref(item) == HERE/'cells'/core/'full-L10-G256.json', 'decision uses a substitute primary cell')
    absent = []
    if kill:
        for core in PINS:
            for scope in ('full','prefix'):
                for level,g in CASES:
                    if (core,scope,level,g) != ('v1.5.4','full',10,256):
                        absent.append(dict(core=core,scope=scope,level=level,g=g,status='NOT RUN: Kill'))
                        check(not (HERE/'cells'/core/f'{scope}-L{level}-G{g}.json').exists(), 'timing continued after Kill')
        check(not (HERE/'method-v1.5.7.json').exists(), 'new-core AA timing ran after Kill')
    check(value['not_run'] == absent, 'NOT RUN: Kill list is incomplete or fabricated')
    return expected


def bind_1d_report_inputs():
    """Close the renderer's historical inputs by hashes, without reauditing 1d."""
    prior_root = HERE.parent/'hw-gift-1d'
    prior = load(prior_root/'audit/final.json')
    check(prior.get('status') == 'PASS' and prior.get('stage') == 'all'
          and isinstance(prior.get('source_bindings'),list) and prior['source_bindings'], 'saved 1d final audit missing/failed')
    for item in prior['source_bindings']:
        check(set(item) == {'path','sha256'} and valid_sha(item['sha256']), 'invalid saved 1d binding')
        path = (prior_root/item['path']).resolve()
        check(path.is_relative_to((ROOT/'evidence').resolve()) and sha(path) == item['sha256'], 'historical renderer input changed: '+item['path'])
    for phase in ('train','holdout'):
        for level in (3,10,19):
            for g in (256,1024,4096,16384,65536,262144,524288):
                path = prior_root/'cells'/phase/f'L{level}-G{g}.json'
                value = load(path)
                check(value['status'] == 'COMPLETE' and (value['level'],value['g']) == (level,g), 'saved 1d baseline summary incomplete')


def verify_final_proofs(search_admitted):
    """Final-only native/search closure; the earlier grid audit needs neither."""
    if search_admitted:
        result_path = HERE/'search/result.json'
        search_result = load(result_path)
        search_audit = load(HERE/'search/audit.json')
        check(search_audit.get('status') == 'PASS' and search_audit.get('saved_data_only') is True
              and search_audit.get('result_sha256') == sha(result_path), 'separate search audit does not bind the current result')
        sha(HERE/'SEARCH_PROTOCOL.md')
        visited = set()
        def references(value):
            if isinstance(value,dict):
                if set(value) == {'path','sha256'}:
                    path = file_ref(value,True)
                    if path.suffix == '.json' and path not in visited:
                        visited.add(path)
                        references(load(path))
                else:
                    for item in value.values():
                        references(item)
            elif isinstance(value,list):
                for item in value:
                    references(item)
        references(search_result);references(search_audit)
        # Freeze every public attempt/build/admission/classifier payload, even
        # when its hash is represented by a named field rather than a JSON ref.
        for path in sorted((HERE/'search').rglob('*')):
            if path.is_file():
                sha(path)
        for path in sorted(HERE.glob('*.py')):
            sha(path)
    native_path = HERE/'audit/native.json'
    native = load(native_path)
    check(native.get('schema') == 'hw-gift-1e-independent-native-v1' and native.get('status') == 'PASS'
          and native.get('source_sha256') == sha(HERE/'verify_native.py') and native.get('no_clocks') is True
          and native.get('measurements_of_time') is False and native.get('all_attempts') is True
          and type(native.get('encodings_performed')) is int and native['encodings_performed'] == 0,
          'independent native proof source/scope differs')
    check(native['setup_sha256'] == sha(HERE/'setup.json'), 'native proof uses a different setup')
    names = ('archive_references','archive_paths_verified','unique_archives_verified','frame_decodes_verified','restored_bytes_verified')
    check(all(positive(native.get(k)) for k in names)
          and len(native['archive_paths']) == native['archive_paths_verified']
          and len(native['archives']) == native['unique_archives_verified']
          and native['archive_references'] >= native['archive_paths_verified'] >= native['unique_archives_verified'],
          'native proof archive/path counts differ')
    check(sum(p['frame_count'] for p in native['archives']) == native['frame_decodes_verified']
          and sum(p['restored_bytes'] for p in native['archives']) == native['restored_bytes_verified']
          and all(p['seek_checksums_verified'] is True and p['empty_terminal_verified'] is True for p in native['archives']),
          'native proof frame/checksum totals differ')
    documents = native['documents_sha256']
    check(isinstance(documents,dict) and documents, 'native proof has no inspected-document bindings')
    for name,digest in documents.items():
        check(sha(public(name)) == digest, 'native proof document changed: '+name)
    required = {p.relative_to(HERE).as_posix() for p in COVERED_RESULTS}
    required |= {p.relative_to(HERE).as_posix() for p in (HERE/'selfchecks').rglob('*.json')}
    required |= {p.relative_to(HERE).as_posix() for p in (HERE/'cells').rglob('*.json')}
    required |= {p.name for p in HERE.glob('method-v*.json')}
    required |= {'method-controls.json','decision.json'}
    check(required <= set(documents), 'native proof omits selected/excluded output or a method/grid selfcheck')
    return dict(path='audit/native.json',sha256=sha(native_path),source_sha256=native['source_sha256'],
                encodings_performed=0,**{name:native[name] for name in names})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('setup','prepare','method','primary','all'),default='all')
    parser.add_argument('--core',choices=tuple(PINS),default='v1.5.4')
    parser.add_argument('--final',action='store_true',help='also require the post-run native proof and complete search proof closure')
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    result = dict(status='PASS',stage=args.stage,final_verification=False,saved_data_only=True,no_codecs_or_clocks_executed=True)
    try:
        check(not args.final or args.stage == 'all', '--final requires --stage all')
        if args.stage == 'setup':
            verify_setup()
        else:
            verify_preparation()
            if args.stage in ('method','primary','all'):
                method = verify_summary(HERE/f'method-{args.core if args.stage == "method" else "v1.5.4"}.json',True)
                check(method['status'] == 'PASS', 'AA method gate did not pass: '+method['status'])
                result['methods'] = {method['request']['core']:dict(**method['derived'],counters=method['counters'])}
            if args.stage in ('primary','all'):
                old = verify_summary(HERE/'cells/v1.5.4/full-L10-G256.json')
                if old['status'] != 'COMPLETE':
                    raise Incomplete('old primary '+old['status'])
                kill = old['derived']['B']['median_ns'] < 2*old['derived']['A']['median_ns']
                new = None
                cells = {('v1.5.4','full',10,256):old}
                if not kill and (args.stage == 'all' or (HERE/'cells/v1.5.7/full-L10-G256.json').exists()):
                    method_new = verify_summary(HERE/'method-v1.5.7.json',True)
                    check(method_new['status'] == 'PASS', 'new-core AA method gate did not pass')
                    result['methods']['v1.5.7'] = dict(**method_new['derived'],counters=method_new['counters'])
                    new = verify_summary(HERE/'cells/v1.5.7/full-L10-G256.json')
                    if new['status'] != 'COMPLETE':
                        raise Incomplete('new primary '+new['status'])
                    cells['v1.5.7','full',10,256] = new
                result['literal_verdicts'] = verify_decision(old,new)
                if args.stage == 'all' and not kill:
                    for core in PINS:
                        for scope in ('full','prefix'):
                            for level,g in CASES:
                                key = core,scope,level,g
                                if key not in cells:
                                    cells[key] = verify_summary(HERE/'cells'/core/f'{scope}-L{level}-G{g}.json')
                                check(cells[key]['status'] == 'COMPLETE', 'main grid includes a blocked cell')
                result['verified_cells'] = len(cells)
                result['cell_counters'] = {k:sum(c['counters'][k] for c in cells.values()) for k in ('logical_repeats','attempts','retaken','loaded_attempts')}
                if args.stage == 'all':
                    actual = set((HERE/'raw').rglob('ovh-bench.json'))
                    check(actual == COVERED_RECEIPTS, 'unaccounted timed receipts or forbidden post-Kill work')
                    check(set((HERE/'raw').rglob('result.json')) == COVERED_RESULTS, 'unaccounted started worker output')
                    result['grid_status'] = 'STOP: Kill' if kill else 'COMPLETE'
                    result['search_status'] = 'SEPARATE PREREGISTERED STAGE REQUIRED' if result['literal_verdicts']['search_admitted'] else 'NOT ADMITTED'
        result.update(private_artifacts_hash_verified=len(PRIVATE_CHECKED),private_paths_not_available=sorted(PRIVATE_UNAVAILABLE))
        if args.stage == 'all':
            sha(HERE/'report.py')
            bind_1d_report_inputs()
            if args.final:
                result['native_proof'] = verify_final_proofs(result['literal_verdicts']['search_admitted'])
                result['final_verification'] = True
        for name in ('audit.py','SOURCE_PATHS.md'):
            sha(HERE/name)
        result['source_bindings'] = [dict(path=name,sha256=digest) for name,digest in sorted(SOURCE_BINDINGS.items())]
        code = 0
    except Incomplete as error:
        result,code = dict(status='INCOMPLETE',stage=args.stage,reason=str(error),saved_data_only=True),2
    except (ValueError,KeyError,TypeError,OSError,subprocess.CalledProcessError) as error:
        result,code = dict(status='FAIL',stage=args.stage,reason=str(error),saved_data_only=True),1
    text = json.dumps(result,sort_keys=True,separators=(',',':'))+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text,encoding='utf-8',newline='\n')
    else:
        sys.stdout.write(text)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
