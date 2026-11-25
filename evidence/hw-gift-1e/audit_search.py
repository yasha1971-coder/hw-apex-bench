"""Independent saved-data audit of the bounded HW-GIFT-1e core search.

No search/instrument/controller imports, native code, builds, clock reads,
network calls or Git commands. Receipt checks reuse the independent grid
auditor; all search medians, classifications and ancestry are derived here.
"""
import argparse
import ast
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE.parent
PUBLIC = HERE/'search'
OLD = '945f27758c0fd67b636103a38dbf050266c6b90a'
NEW = 'f8745da6ff1ad1e7bab384bd1f9d742439278e99'
S1_SLOW = 'e2965edd107acd0123294e23848cdc00af906468'
S1_FAST = '9420bce8a491e21821c4b372f837bf4bd47e5870'
SALT = '91f4c23e634a1d260f290f00b6d870a56cd59ab6'
PREFIX_SHA = 'e6d287b341ea0dc183fb334ae05e558df4540752bf2be88da9570338fa711585'
BOUND = {}
RECEIPTS = set()
PRIVATE_CHECKED, PRIVATE_UNAVAILABLE = set(), set()


class Incomplete(ValueError):
    pass


def check(ok, reason):
    if not ok:
        raise ValueError(reason)


def valid_sha(value, length=64):
    return isinstance(value,str) and len(value) == length and all(c in '0123456789abcdef' for c in value)


def positive(value):
    return type(value) is int and value > 0


def packed(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()


def bind(path, digest):
    path = Path(path).resolve()
    if path.is_relative_to(EVIDENCE.resolve()):
        import os
        name = os.path.relpath(path,HERE).replace('\\','/')
        check(BOUND.setdefault(name,digest) == digest, 'evidence changed while auditing: '+name)


def sha(path):
    path = Path(path)
    if not path.is_file():
        raise Incomplete('missing evidence: '+str(path))
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream,'sha256').hexdigest()
    bind(path,digest)
    return digest


def load(path):
    path = Path(path)
    if not path.is_file():
        raise Incomplete('missing evidence: '+str(path))
    data = path.read_bytes()
    bind(path,hashlib.sha256(data).hexdigest())
    def unique(pairs):
        value = {}
        for key,item in pairs:
            check(key not in value,'duplicate JSON key: '+key)
            value[key] = item
        return value
    return json.loads(data,object_pairs_hook=unique)


def public(name):
    check(isinstance(name,str) and name,'missing public path')
    path = (HERE/name).resolve()
    check(path.is_relative_to(HERE.resolve()),'search reference escapes experiment')
    return path


def file_ref(value):
    check(isinstance(value,dict) and set(value) == {'path','sha256'} and valid_sha(value['sha256']), 'invalid search reference')
    path = public(value['path'])
    check(sha(path) == value['sha256'],'referenced bytes changed: '+value['path'])
    return path


def json_ref(value):
    path = file_ref(value)
    return load(path),path


def private(name, digest, size=None):
    check(isinstance(name,str) and valid_sha(digest),'invalid private artifact identity')
    path = Path(name)
    if not path.is_file():
        PRIVATE_UNAVAILABLE.add(name)
        return
    if size is not None:
        check(path.stat().st_size == size,'private artifact size differs')
    key = name,digest
    if key not in PRIVATE_CHECKED:
        check(sha(path) == digest,'private artifact SHA differs: '+name)
        PRIVATE_CHECKED.add(key)


def median5(values):
    check(isinstance(values,list) and len(values) == 5 and all(positive(n) for n in values),'five positive integer observations required')
    return sorted(values)[2]


def classify(c, r, s, f):
    check(all(positive(n) for n in (c,r,s,f)),'classifier needs positive integer medians')
    left, right = 100*c*c*f, r*r*s
    return 'FAST' if left < 81*right else 'SLOW' if left > 121*right else 'INDETERMINATE'


def receipt_controller():
    """Reuse independently implemented load/counter proof, never experiment code."""
    path = HERE/'audit.py'
    sha(path)
    spec = importlib.util.spec_from_file_location('_gift1e_grid_receipts',path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_closure(audit):
    check(audit.get('status') == 'PASS' and audit.get('saved_data_only') is True,'independent grid audit must pass')
    bindings = audit.get('source_bindings')
    check(isinstance(bindings,list) and bindings,'grid audit source bindings missing')
    for item in bindings:
        path = (HERE/item['path']).resolve()
        check(path.is_relative_to(EVIDENCE.resolve()) and sha(path) == item['sha256'],'grid audit is stale')


def check_request(value):
    check(value.get('schema') == 'hw-gift-1e-search-request-v1' and value.get('input_bytes') == 16777216
          and value.get('input_sha256') == PREFIX_SHA and (value.get('level'),value.get('g')) == (10,256),
          'search request source/scope differs')
    original = dict(value)
    request_id = original.pop('request_id')
    c,r = value['libraries']['C'],value['libraries']['R']
    check(request_id == c['commit']+'-'+hashlib.sha256(packed(original)).hexdigest()[:16],'search request identity changed')
    check(r['commit'] == NEW and valid_sha(c['commit'],40),'fixed reference core changed')
    check(value['endpoint'] is (c['commit'] == OLD),'endpoint/candidate marker differs')
    for record in (c,r):
        check(valid_sha(record['sha256']) and valid_sha(record['build_sha256']),'library/build identity missing')
        private(record['path'],record['sha256'])
    private(value['input_path'],PREFIX_SHA,16777216)
    return value


def check_row(row, request, label, slot, timed):
    check(row['slot'] == slot and row['label'] == label and row['commit'] == request['libraries'][label]['commit'], 'measurement slot/core differs')
    check(row['bit_perfect'] is True and row['seek_checksums_verified'] is True and row['empty_terminal_verified'] is True
          and row['restored_bytes'] == 16777216 and row['restored_sha256'] == PREFIX_SHA,'search restore/checksum proof failed')
    check(row['empty_terminal_frames'] in (0,1) and row['frame_count'] == 65536+row['empty_terminal_frames'], 'prefix frame/terminal geometry differs')
    check(row['seek_checksum_flag'] is True and row['seek_table_bytes'] == 17+12*row['frame_count'],'seek-table metadata differs')
    check(positive(row['archive_bytes']) and valid_sha(row['archive_sha256']),'archive identity missing')
    check(positive(row['compression_ns']) if timed else row['compression_ns'] is None,'wrong timing control scope')
    private(row['archive_path'],row['archive_sha256'],row['archive_bytes'])


def check_worker(value, request, request_sha, pair, order, selfcheck):
    check(value.get('schema') == 'hw-gift-1e-search-worker-v1' and value['request_sha256'] == request_sha
          and value['order'] == order and value['pair_index'] == pair,'search worker identity/order differs')
    check(value['measurements_of_time'] is True and value['clock_calls'] == 4 and value['cpu_affinity'] == [0]
          and value['lock_path'] == '/run/lock/ovh-bench.lock' and value['backend_sha256'] == request['backend_sha256'], 'search clock/core/source scope differs')
    check(len(value['results']) == 2,'search lost a C/R slot')
    baseline = {row['label']:(row['archive_bytes'],row['archive_sha256']) for row in selfcheck['results']}
    for slot,label in enumerate(order):
        row = value['results'][slot]
        check_row(row,request,label,slot,True)
        check((row['archive_bytes'],row['archive_sha256']) == baseline[label],'timed archive differs from untimed control')
    return value['results']


def verify_pairs(path, controller):
    value = load(path)
    if value.get('status') == 'BLOCKED: load':
        raise Incomplete('search stopped BLOCKED: load; no terminal inference')
    check(value.get('schema') == 'hw-gift-1e-search-pairs-v1' and value.get('status') == 'COMPLETE','incomplete search pairs')
    request,request_path = json_ref(value['request'])
    check_request(request)
    check(value['request_sha256'] == sha(request_path),'paired stage request changed')
    control,control_path = json_ref(value['selfcheck'])
    check(control['request_sha256'] == sha(request_path) and control['clock_calls'] == 0
          and control['measurements_of_time'] is False and control['order'] == ['C','C','R']
          and len(control['results']) == 3,'candidate deterministic control scope differs')
    for slot,label in enumerate(('C','C','R')):
        check_row(control['results'][slot],request,label,slot,False)
    check(control['results'][0]['archive_sha256'] == control['results'][1]['archive_sha256']
          and control['results'][0]['archive_bytes'] == control['results'][1]['archive_bytes'],'C/C positive control differs')
    check(len(value['repeats']) == 5,'search needs five logical pairs')
    ns, identities = {'C':[],'R':[]}, {'C':set(),'R':set()}
    counters = dict(logical_repeats=5,attempts=0,retaken=0,loaded_attempts=0)
    maximum = [Decimal(0),Decimal(0)]
    for pair,item in enumerate(value['repeats']):
        order = ['C','R'] if pair%2 == 0 else ['R','C']
        check(item['status'] == 'CLEAN' and item['pair_index'] == pair and item['order'] == order
              and 1 <= len(item['attempts']) <= 3,'round order/retry shape differs')
        counters['retaken'] += len(item['attempts']) > 1
        selected = None
        for number,attempt in enumerate(item['attempts'],1):
            status = 'CLEAN' if number == len(item['attempts']) else 'LOADED'
            check(attempt['attempt'] == number and attempt['status'] == status,'first CLEAN must win')
            files = attempt['files']
            check({'ovh-bench.json','ovh-bench.json.stdout','ovh-bench.json.stderr','worker.stdout'} <= set(files),'raw attempt inventory missing')
            actual = {name:file_ref(reference) for name,reference in files.items()}
            record,receipt_path = json_ref(attempt['receipt'])
            check(receipt_path == actual['ovh-bench.json'] and receipt_path not in RECEIPTS,'receipt reused or misplaced')
            RECEIPTS.add(receipt_path)
            expected_folder = PUBLIC/'raw'/request['request_id']/f'repeat-{pair}'/f'attempt-{number}'
            check(receipt_path.parent == expected_folder and {p.name for p in expected_folder.iterdir()} == set(files),
                  'raw attempt paths/inventory differ')
            check({p.name for p in expected_folder.parent.iterdir()} == {f'attempt-{n}' for n in range(1,len(item['attempts'])+1)},
                  'unretained fourth/repeated CLEAN attempt')
            controller.receipt(record,status)
            for name in ('stdout','stderr'):
                check(sha(actual['ovh-bench.json.'+name]) == record[name+'_sha256'],'helper raw stream changed')
            check(sha(actual['worker.stdout']) == record['stdout_sha256'],'delivered stdout differs')
            for index,boundary in enumerate(('start','end')):
                maximum[index] = max(maximum[index],Decimal(record[boundary]['loadavg_raw'].split()[0]))
            command = record['command']
            check(len(command) == 12 and command[1] == '-B' and command[3:5] == ['worker','--request']
                  and command[6:11] == ['--pair',str(pair),'--order',','.join(order),'--output'], 'search worker command differs')
            check(command[2].replace('\\','/').endswith('/evidence/hw-gift-1e/bisect_core.py')
                  and Path(command[5]).name == request_path.name and Path(command[11]).name == 'result.json', 'search command source/request/output differs')
            if record['command_started']:
                check('result.json' in actual,'started attempt has no result')
                worker = load(actual['result.json'])
                check(load(actual['ovh-bench.json.stdout']) == worker,'stdout/result differs')
                selected = check_worker(worker,request,sha(request_path),pair,order,control)
            else:
                check('result.json' not in actual and actual['ovh-bench.json.stdout'].read_bytes() == b'','unstarted attempt produced output')
            counters['attempts'] += 1
            counters['loaded_attempts'] += status == 'LOADED'
        check(item['selected_receipt'] == item['attempts'][-1]['receipt'] and selected is not None,'selected receipt differs')
        selected_path = file_ref(item['selected_result'])
        check(selected_path == actual['result.json'],'selected raw result is not first CLEAN')
        for row in selected:
            ns[row['label']].append(row['compression_ns'])
            identities[row['label']].add((row['archive_bytes'],row['archive_sha256']))
    check(all(len(items) == 1 for items in identities.values()),'search archives changed across repeats')
    check(value['planned_repeats'] == value['started_repeats'] == 5
          and value['retaken_repeats'] == counters['retaken'] and value['loaded_attempts'] == counters['loaded_attempts'],'search counts differ')
    for label,median_key,min_key in (('C','median_C_ns','min_C_ns'),('R','median_ref_ns','min_ref_ns')):
        check(value[median_key] == median5(ns[label]) and value[min_key] == min(ns[label]),'search medians/minima differ from raw')
    return dict(summary=value,request=request,request_sha256=sha(request_path),counters=counters,
                median_C_ns=median5(ns['C']),median_ref_ns=median5(ns['R']),min_C_ns=min(ns['C']),min_ref_ns=min(ns['R']),
                compression_ns=ns,max_start_load1=str(maximum[0]),max_end_load1=str(maximum[1]))


def node_map(path):
    value = load(path)
    check(value.get('schema') == 'hw-gift-1e-search-history-v1' and value.get('slow') == OLD and value.get('fast') == NEW,
          'retained ancestry endpoints differ')
    nodes = value['nodes']
    check(isinstance(nodes,dict) and {OLD,NEW,S1_SLOW,S1_FAST,SALT} <= set(nodes),'ancestry manifest incomplete')
    for commit,node in nodes.items():
        check(valid_sha(commit,40) and node['commit'] == commit and isinstance(node['title'],str)
              and isinstance(node['parents'],list) and all(valid_sha(p,40) for p in node['parents']), 'invalid ancestry node')
    check(nodes[S1_FAST]['parents'][0] == S1_SLOW and nodes[SALT]['parents'][0] == S1_FAST, 'source-informed first-parent pairs differ')
    check(is_ancestor(nodes,OLD,NEW),'retained endpoints are not an ancestry pair')
    return nodes


def is_ancestor(nodes, slow, fast):
    todo, visited = [fast],set()
    while todo:
        current = todo.pop()
        if current == slow:
            return True
        if current in visited or current not in nodes:
            continue
        visited.add(current)
        todo.extend(nodes[current]['parents'])
    return False


def ancestry_path(nodes, slow, fast):
    if not is_ancestor(nodes,slow,fast):
        return None
    commits, seen = [fast],{fast}
    while commits[-1] != slow:
        choices = [p for p in nodes[commits[-1]]['parents'] if is_ancestor(nodes,slow,p)]
        check(choices and choices[0] not in seen,'retained ancestry path is incomplete/cyclic')
        commits.append(choices[0]); seen.add(choices[0])
    commits.reverse()
    return dict(slow=slow,fast=fast,nodes=[nodes[c] for c in commits],
                edges=[dict(slow=a,fast=b,first_parent=nodes[b]['parents'][0] == a) for a,b in zip(commits,commits[1:])])


def closest(tested, nodes):
    choices = []
    for slow in tested:
        for fast in tested:
            if slow['classifier'] != 'SLOW' or fast['classifier'] != 'FAST':
                continue
            path = ancestry_path(nodes,slow['commit'],fast['commit'])
            if path is not None:
                choices.append((len(path['nodes']),slow['commit'],fast['commit'],path))
    check(choices,'tested cores have no retained slow-to-fast ancestry bracket')
    return min(choices,key=lambda row:row[:3])[3]


def adjacent(tested, nodes):
    slow = {row['commit'] for row in tested if row['classifier'] == 'SLOW'}
    for row in tested:
        if row['classifier'] == 'FAST' and nodes[row['commit']]['parents'] and nodes[row['commit']]['parents'][0] in slow:
            return dict(slow_commit=nodes[row['commit']]['parents'][0],fast_commit=row['commit'],
                        fast_title=nodes[row['commit']]['title'],adjacent_first_parent=True)
    return None


def function_hashes(path):
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    return {node.name:hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
            for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}


def amendment_context(candidate_path):
    if not candidate_path.is_file():
        return None
    candidate = load(candidate_path)
    if 'source_branch_amendment' not in candidate:
        return None
    change,change_path = json_ref(candidate['source_branch_amendment'])
    check(change.get('status') == 'PRE-BUILD SOURCE-ANCESTRY AMENDMENT'
          and change['allowed_source_branch_commits'] == [S1_SLOW,S1_FAST,SALT]
          and change['candidate_builds_before_amendment'] == 0 and change['prior_total_core_builds'] == 2,
          'source-branch amendment widened scope or followed candidate work')
    check(valid_sha(change['protocol']['commit'],40) and change['protocol']['sha256'] == sha(HERE/'SEARCH_AMENDMENT.md'), 'amendment protocol changed')
    original,original_path = json_ref(change['endpoint_admission'])
    superseded,superseded_path = json_ref(change['supersedes'])
    check(candidate['endpoint_admission'] == change['endpoint_admission'] and candidate['supersedes'] == change['supersedes'], 'amendment historical admission refs changed')
    check(superseded['endpoint_admission'] == change['endpoint_admission'],'superseded candidate used another endpoint admission')
    for key in ('decision','setup_sha256','completed_grid','grid_audit','baseline_build','search_protocol'):
        check(original[key] == superseded[key] == candidate[key],'amendment replaced a frozen endpoint root: '+key)
    for key in ('classifier','classifier_commit'):
        check(superseded[key] == candidate[key],'amendment changed the already frozen classifier')
    for module,filename,key,allowed in (('backend','bisect_core','backend_sha256',{'gate','build_candidate'}),
                                        ('frontend','search','frontend_sha256',{'candidates'})):
        old_path = file_ref(change['original_sources'][filename+'.txt'])
        current = HERE/(filename+'.py')
        check(sha(old_path) == original[key] == superseded[key] and change['new_'+key] == sha(current) == candidate[key], 'old/new source hash mapping differs')
        before,after = function_hashes(old_path),function_hashes(current)
        check(set(before) == set(after),'amendment added/removed search functions')
        check(all(before[name] == after[name] for name in before if name not in allowed),'amendment changed sampler/worker/round/classifier/control function AST')
        def constants(path):
            nodes = ast.parse(Path(path).read_text(encoding='utf-8')).body
            return [ast.dump(node,include_attributes=False) for node in nodes
                    if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))
                    and not (isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str))]
        check(constants(old_path) == constants(current),'amendment changed imports, global constants or entrypoint outside permitted policy functions')
        recorded = change['unchanged_functions'][module]
        needed = {'sample','selfcheck','worker','locked_round','native','classify'} if module == 'backend' else {'paired','verify_pairs','checked_classifier','endpoints'}
        check(needed <= set(recorded),'amendment omitted a required unchanged measurement/control function')
        for name,proof in recorded.items():
            check(name in before and proof['old_sha256'] == before[name] == after[name] == proof['new_sha256'],'amendment AST proof differs: '+name)
    old_identity = dict(admission_sha256=sha(superseded_path),frontend_sha256=superseded['frontend_sha256'],
                        backend_sha256=superseded['backend_sha256'],search_protocol=superseded['search_protocol'])
    return dict(receipt=change,receipt_path=change_path,original=original,original_path=original_path,
                superseded=superseded,superseded_path=superseded_path,old_identity=old_identity)


def admission(path, controller, endpoint=None, context=None):
    value = load(path)
    expected = context['original'] if endpoint is None and context is not None else None
    check(value['backend_sha256'] == (expected['backend_sha256'] if expected else sha(HERE/'bisect_core.py'))
          and value['frontend_sha256'] == (expected['frontend_sha256'] if expected else sha(HERE/'search.py')), 'search implementation changed')
    check(valid_sha(value['search_protocol']['commit'],40) and value['search_protocol']['sha256'] == sha(HERE/'SEARCH_PROTOCOL.md'), 'search protocol changed')
    check(value['setup_sha256'] == sha(HERE/'setup.json'),'search baseline setup changed')
    grid,_ = json_ref(value['grid_audit'])
    source_closure(grid)
    check(grid.get('stage') == 'all' and grid.get('verified_cells') == 12 and grid.get('grid_status') == 'COMPLETE'
          and grid['literal_verdicts']['search_admitted'] is True,'complete twelve-cell independent grid admission required')
    closure = {item['path']:item['sha256'] for item in grid['source_bindings']}
    decision,_ = json_ref(value['decision'])
    check(closure.get(value['decision']['path']) == value['decision']['sha256'] and decision['search_admitted'] is True
          and decision['Kill']['triggered'] is False,'grid audit does not bind this primary decision')
    check(len(value['completed_grid']) == 12,'admission must bind all twelve cells')
    cells = {}
    for item in value['completed_grid']:
        cell,_ = json_ref(item)
        check(closure.get(item['path']) == item['sha256'] and cell['status'] == 'COMPLETE','admitted cell not bound by grid audit')
        key = cell['core'],cell['scope'],cell['level'],cell['g']
        check(key not in cells,'duplicate admitted grid coordinate')
        cells[key] = cell
    check(set(cells) == {(core,scope,l,g) for core in ('v1.5.4','v1.5.7') for scope in ('full','prefix')
                         for l,g in ((10,256),(10,1024),(3,256))},'admitted grid coordinates differ')
    primary = {}
    for core in ('v1.5.4','v1.5.7'):
        times = {'A':[],'B':[]}
        for repeat in cells[core,'full',10,256]['repeats']:
            worker,_ = json_ref(repeat['selected_result'])
            receipt,_ = json_ref(repeat['selected_receipt'])
            controller.receipt(receipt,'CLEAN')
            for row in worker['results']:
                times[row['variant']].append(row['compression_ns'])
        primary[core] = {v:median5(ns) for v,ns in times.items()}
    check(primary['v1.5.4']['B'] >= 5*primary['v1.5.4']['A'],'P1 does not admit search')
    a,b = primary['v1.5.7']['A'],primary['v1.5.7']['B']
    check(5*max(a,b) < 6*min(a,b),'P2 does not admit search')
    baseline,baseline_path = json_ref(value['baseline_build'])
    check(baseline_path == HERE/'native/v1.5.7/build.json','fixed reference build differs')
    identity = dict(admission_sha256=sha(path),frontend_sha256=value['frontend_sha256'],backend_sha256=value['backend_sha256'],
                    search_protocol=value['search_protocol'])
    if endpoint is not None:
        original,original_path = json_ref(value['endpoint_admission'])
        check(sha(original_path) == endpoint['sha256'],'candidate endpoint admission changed')
        for key in ('decision','setup_sha256','completed_grid','grid_audit','baseline_build','backend_sha256','frontend_sha256','search_protocol'):
            if context is not None and key in ('backend_sha256','frontend_sha256'):
                continue
            check(value[key] == original[key],'candidate admission changed frozen endpoint root: '+key)
        if context is not None:
            check(value['source_branch_amendment'] == dict(path=context['receipt_path'].relative_to(HERE).as_posix(),sha256=sha(context['receipt_path']))
                  and original == context['original'],'candidate source amendment mapping differs')
        classifier,classifier_path = json_ref(value['classifier'])
        check(valid_sha(value['classifier_commit']['commit'],40) and value['classifier_commit']['sha256'] == sha(classifier_path), 'classifier commit receipt differs')
        check(classifier['identity']['admission_sha256'] == endpoint['sha256'],'classifier not bound to original endpoint admission')
    return dict(value=value,path=path,sha256=sha(path),identity=identity,baseline=baseline)


def verify_candidate_build(row, candidate_admission, nodes, baseline):
    value,path = json_ref(row['build'])
    commit = row['commit']
    check(path == PUBLIC/'builds'/commit/'build.json' and value.get('schema') == 'hw-gift-1e-search-build-v1'
          and value['commit'] == commit and value['title'] == nodes[commit]['title'],'candidate build identity/title differs')
    check(value['admission_sha256'] == candidate_admission['sha256'] and value['backend_sha256'] == sha(HERE/'bisect_core.py'),'candidate build admission/source differs')
    frozen = baseline['identity']['source_sha256']
    expected = {name:frozen[name] for name in ('bridge.c','B-compress.c','decompress.c','zstd_seekable.h')}
    check(value['source_sha256'] == expected,'candidate changed frozen non-core byte policy')
    check(valid_sha(value['static_library_sha256']) and valid_sha(value['library_sha256']) and valid_sha(value['cli_sha256'])
          and isinstance(value['headers_sha256'],dict) and value['headers_sha256'],'candidate binary/header digests missing')
    check(positive(value['version_number']) and isinstance(value['version_string'],str)
          and value['version_string'] in value['cli_version'],'candidate CLI/runtime versions differ')
    parts = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:[-+].*)?',value['version_string'])
    check(parts and value['version_number'] == int(parts[1])*10000+int(parts[2])*100+int(parts[3]),'candidate numeric/string version differs')
    check(len(value['builds']) == 3,'candidate must retain static/CLI/shared build commands')
    for index,record in enumerate(value['builds']):
        prefix = path.parent/('shared-build' if index == 2 else 'core-build-'+str(index))
        check(sha(Path(str(prefix)+'.stdout')) == record['stdout_sha256']
              and sha(Path(str(prefix)+'.stderr')) == record['stderr_sha256'],'candidate build logs changed')
        args = record['command']
        if index < 2:
            check('CFLAGS=-O3 -fPIC -fno-lto' in args and 'LDFLAGS=-fno-lto' in args,'candidate core build flags differ')
        else:
            check(all(flag in args for flag in ('-O3','-fPIC','-fno-lto','-shared','-Wl,-Bsymbolic')),'candidate shared flags differ')
    private(value['library_path'],value['library_sha256'])
    folder = Path(value['library_path']).parent
    for name,digest in value['source_sha256'].items():
        private(str(folder/name),digest)
    checkout = folder.parent.parent/'cores'/commit
    private(str(checkout/'lib/libzstd.a'),value['static_library_sha256'])
    private(str(checkout/'programs/zstd'),value['cli_sha256'])
    for name,digest in value['headers_sha256'].items():
        check(name.startswith('lib/') and '..' not in Path(name).parts and valid_sha(digest),'candidate header path/digest invalid')
        private(str(checkout/name),digest)
    return value,path


def bind_pairs(proof, admitted, candidate_build=None):
    request,summary = proof['request'],proof['summary']
    check(summary['identity'] == admitted['identity'] and request['admission_sha256'] == admitted['sha256']
          and request['backend_sha256'] == admitted['value']['backend_sha256'],'paired stage admission/implementation changed')
    check(request['admission_path'].replace('\\','/').endswith('/evidence/hw-gift-1e/'+admitted['path'].relative_to(HERE).as_posix()),
          'request admission path differs')
    fixed = admitted['baseline']['libraries']['B']
    reference = dict(path=fixed['path'],sha256=fixed['sha256'],commit=NEW,build_sha256=sha(HERE/'native/v1.5.7/build.json'))
    check(request['libraries']['R'] == reference,'fixed paired B-v1.5.7 reference changed')
    if candidate_build is None:
        old_path = HERE/'native/v1.5.4/build.json'
        old = load(old_path)['libraries']['B']
        candidate = dict(path=old['path'],sha256=old['sha256'],commit=OLD,build_sha256=sha(old_path))
    else:
        build,path = candidate_build
        candidate = dict(path=build['library_path'],sha256=build['library_sha256'],commit=build['commit'],build_sha256=sha(path))
    check(request['libraries']['C'] == candidate,'candidate paired library/build differs')


def forecast(tested):
    by_commit = {row['commit']:row for row in tested}
    a,b = by_commit.get(S1_SLOW),by_commit.get(S1_FAST)
    available = a is not None and b is not None
    passed = (a['classifier'] == 'SLOW' and b['classifier'] == 'FAST') if available else None
    return dict(forecast='Source-informed first-parent pair e2965edd -> 9420bce8 changes from SLOW to FAST',
                verdict=('HIT' if passed else 'MISS') if available else 'NOT TESTED',passed=passed,
                slow_commit=S1_SLOW,fast_commit=S1_FAST,
                slow_classification=a['classifier'] if a else None,fast_classification=b['classifier'] if b else None,
                slow_pair_summary=a['pair_summary'] if a else None,fast_pair_summary=b['pair_summary'] if b else None)


def verify_plans(result, nodes, admitted, context=None):
    reservations = {}
    for path in sorted((PUBLIC/'reservations').glob('*.json')):
        value = load(path)
        commit = value['commit']
        check(path.name == commit+'.json' and valid_sha(commit,40) and commit not in (OLD,NEW)
              and commit not in reservations and value['admission_sha256'] == admitted['sha256'],'invalid/repeated candidate reservation')
        reservations[commit] = value
    check(result['build_count'] == 2+len(reservations) <= 12,'failed/cached build accounting exceeds total twelve-core budget')
    ordered = sorted(reservations,key=lambda c:reservations[c]['total_distinct_core_build_number'])
    check([reservations[c]['total_distinct_core_build_number'] for c in ordered] == list(range(3,3+len(ordered))), 'reservation slots are not unique/contiguous')
    failed = result.get('failed_builds',[])
    check(isinstance(failed,list) and len(failed) <= 1,'first failed/incompatible build must stop search')
    failure_map = {row['commit']:row for row in failed}
    successful = {row['commit']:row for row in result['tested'] if row['commit'] not in (OLD,NEW)}
    check(set(reservations) == set(successful)|set(failure_map) and not (set(successful)&set(failure_map)), 'reservation missing/unreported/failed-as-FAST core')
    if failed:
        check(ordered[-1] == failed[0]['commit'],'candidate builds continued after build failure')
    plans = sorted((PUBLIC/'plans').glob('plan-*.json'))
    steps = sorted((PUBLIC/'steps').glob('step-*.json'))
    offset = 1 if context is not None else 0
    check(len(plans) == len(steps) == len(ordered)+offset,'unrecorded/interrupted plan/step/build')
    prefix = result['tested'][:2]
    failures_so_far = []
    if context is not None:
        rejected_path = file_ref(context['receipt']['rejected_plan'])
        check(plans and rejected_path == plans[0] == PUBLIC/'plans/plan-001.json','historical rejected plan missing')
        rejected,rejection = load(rejected_path),load(steps[0])
        check(rejected['identity'] == context['old_identity'] and rejected['sequence'] == 1
              and rejected['candidate'] == nodes[S1_SLOW] and rejected['selection'] == 'source-informed'
              and rejected['selected_path'] == closest(prefix,nodes)
              and not is_ancestor(nodes,OLD,S1_SLOW) and is_ancestor(nodes,S1_SLOW,NEW),'historical rejection does not match the incorrect ancestry assumption')
        check(rejection['status'] == 'PREBUILD ANCESTRY REJECTION' and rejection['reservation_created'] is False
              and rejection.get('build_count',2) == 2 and rejection['identity'] == admitted['identity']
              and rejection['tested'] == prefix and rejection['failed_builds'] == []
              and file_ref(rejection['plan']) == rejected_path,'pre-build rejection was counted/retried as a build/timing')
    for sequence,(commit,path,step_path) in enumerate(zip(ordered,plans[offset:],steps[offset:]),1+offset):
        plan = load(path)
        check(path.name == f'plan-{sequence:03d}.json' and step_path.name == f'step-{sequence:03d}.json'
              and plan['sequence'] == sequence and plan['identity'] == admitted['identity'],'candidate plan identity/order differs')
        check(adjacent(prefix,nodes) is None and not any(row['classifier']=='INDETERMINATE' for row in prefix)
              and not failures_so_far,'search continued after a terminal observation')
        check(plan['candidate'] == nodes[commit] and file_ref(plan['history']) == PUBLIC/'history.json','planned candidate/history differs')
        bracket = closest(prefix,nodes)
        check(plan['selected_path'] == bracket,'selected ancestry path/titles/tie-break differs')
        seen = {row['commit'] for row in prefix}
        informed = [c for c in (S1_SLOW,S1_FAST,SALT) if c not in seen]
        expected = informed[0] if informed else bracket['nodes'][(len(bracket['nodes'])-1)//2]['commit']
        check(commit == expected and plan['selection'] == ('source-informed' if informed else 'deterministic ancestry midpoint'),
              'candidate selection changed from the preregistered path/order/midpoint')
        if commit in successful:
            prefix.append(successful[commit])
        else:
            item = failure_map[commit]
            check(item['title'] == nodes[commit]['title'] and item['status'] == 'BUILD FAILED OR INCOMPATIBLE'
                  and isinstance(item.get('error'),str) and item['error'] and file_ref(item['plan']) == path,'failed build evidence missing')
            folder = PUBLIC/'builds'/commit
            check(folder.is_dir() and any(folder.glob('*.stderr')) and not (folder/'build.json').exists(),'failed build logs/receipt state differs')
            for log in folder.iterdir():
                check(log.is_file() and log.suffix in ('.stdout','.stderr','.json'),'unexpected failed-build artifact')
                sha(log)
            failures_so_far.append(item)
        step = load(step_path)
        check(step['identity'] == admitted['identity'] and file_ref(step['plan']) == path
              and step['tested'] == prefix and step['failed_builds'] == failures_so_far,'checkpoint does not preserve first accepted candidate evidence')
    check(prefix == result['tested'] and failures_so_far == failed,'terminal tested/failed list differs from checkpoints')
    return reservations


def audit(endpoint_path, candidate_path, result_path, stage):
    controller = receipt_controller()
    context = amendment_context(candidate_path)
    endpoint = admission(endpoint_path,controller,context=context)
    endpoint_pairs = verify_pairs(PUBLIC/'endpoints.json',controller)
    bind_pairs(endpoint_pairs,endpoint)
    classifier = load(PUBLIC/'classifier.json')
    s,f = endpoint_pairs['median_C_ns'],endpoint_pairs['median_ref_ns']
    bracket = s >= 2*f
    check(classifier.get('schema') == 'hw-gift-1e-search-classifier-v1'
          and classifier['status'] == ('BRACKET' if bracket else 'NO BRACKET')
          and file_ref(classifier['endpoint_summary']) == PUBLIC/'endpoints.json'
          and (classifier['endpoint_slow_ns'],classifier['endpoint_reference_ns']) == (s,f)
          and classifier['guard_numerators'] == [81,121] and classifier['denominator'] == 100
          and classifier['boundary_equality'] == 'INDETERMINATE'
          and classifier['identity'] == endpoint['identity'] and classifier['global_first_fast_claim'] is False,
          'frozen classifier differs from fresh endpoint medians/integer rule')
    proofs = {PUBLIC/'endpoints.json':endpoint_pairs}
    if stage == 'endpoints':
        return dict(status='PASS',stage=stage,saved_data_only=True,no_codecs_or_clocks_executed=True,
                    endpoint_bracket=bracket,endpoint_slow_ns=s,endpoint_reference_ns=f,
                    endpoint_counters=endpoint_pairs['counters'],S1=forecast([]))
    result = load(result_path)
    check(result.get('schema') == 'hw-gift-1e-search-result-v1' and result['global_first_fast_claim'] is False
          and result['status'] in ('NO BRACKET','ADJACENT TRANSITION','NARROWED RANGE'),'invalid/missing terminal search result')
    tested = result['tested']
    check(isinstance(tested,list),'terminal tested list missing')
    if not bracket:
        check(result['status'] == 'NO BRACKET' and result['build_count'] == 2 and not tested
              and result['transition'] is None and result['remaining_range'] is None
              and file_ref(result['endpoint_summary']) == PUBLIC/'endpoints.json','NO BRACKET terminal state differs')
        check(not list((PUBLIC/'reservations').glob('*.json')) and not list((PUBLIC/'pairs').glob('*.json'))
              and not list((PUBLIC/'plans').glob('*.json')) and not list((PUBLIC/'builds').glob('*')),'candidate work occurred without a prefix bracket')
    else:
        admitted = admission(candidate_path,controller,endpoint,context)
        check(file_ref(admitted['value']['classifier']) == PUBLIC/'classifier.json','candidate admission uses another classifier')
        check(result['identity'] == admitted['identity'] and len(tested) >= 2,'terminal search admission/tested endpoints differ')
        nodes = node_map(file_ref(result['history']))
        expected_endpoints = [(OLD,'SLOW',s,f,endpoint_pairs['min_C_ns'],endpoint_pairs['min_ref_ns'],'endpoint_candidate'),
                              (NEW,'FAST',f,f,endpoint_pairs['min_ref_ns'],endpoint_pairs['min_ref_ns'],'endpoint_reference')]
        for row,(commit,label,c,r,mc,mr,role) in zip(tested[:2],expected_endpoints):
            check(row['commit'] == commit and row['title'] == nodes[commit]['title'] and row['classifier'] == label
                  and (row['median_C_ns'],row['median_ref_ns'],row['min_C_ns'],row['min_ref_ns']) == (c,r,mc,mr)
                  and row['role'] == role and file_ref(row['pair_summary']) == PUBLIC/'endpoints.json','endpoint test rows fabricate/reuse another observation')
        check(len({row['commit'] for row in tested}) == len(tested),'one tested core was retimed')
        for row in tested[2:]:
            commit = row['commit']
            allowed = context is not None and commit in (S1_SLOW,S1_FAST,SALT)
            check(commit in nodes and (allowed or is_ancestor(nodes,OLD,commit)) and is_ancestor(nodes,commit,NEW)
                  and row['title'] == nodes[commit]['title'],'candidate outside retained endpoint DAG/title differs')
            build = verify_candidate_build(row,admitted,nodes,admitted['baseline'])
            path = file_ref(row['pair_summary'])
            check(path == PUBLIC/'pairs'/(commit+'.json'),'candidate pair path differs')
            proof = verify_pairs(path,controller)
            bind_pairs(proof,admitted,build)
            check(proof['request']['libraries']['C']['commit'] == commit,'candidate pair uses another core')
            for key in ('median_C_ns','median_ref_ns','min_C_ns','min_ref_ns'):
                check(row[key] == proof[key],'tested core statistic differs from raw: '+key)
            check(row['classifier'] == classify(proof['median_C_ns'],proof['median_ref_ns'],s,f), 'classifier differs before rounding')
            proofs[path] = proof
        reservations = verify_plans(result,nodes,admitted,context)
        path = closest(tested,nodes)
        check(result['selected_path'] == path and result['remaining_range'] == dict(slow=path['slow'],fast=path['fast']), 'terminal narrowed path/range differs')
        transition = adjacent(tested,nodes)
        if transition is not None and context is not None:
            transition.update(on_tag_ancestry_path=is_ancestor(nodes,OLD,transition['slow_commit']),
                              fast_is_ancestor_of_v157=is_ancestor(nodes,transition['fast_commit'],NEW),
                              qualification='measured first-parent source-branch edge; not a global first-fast claim')
        if context is not None:
            check(file_ref(result['source_branch_amendment']) == context['receipt_path'],'terminal result omitted its ancestry amendment')
        check(result['transition'] == transition and (result['status'] == 'ADJACENT TRANSITION') == (transition is not None), 'adjacency claim is not measured first-parent SLOW/FAST')
        if transition is None:
            check(bool(result.get('failed_builds')) or any(row['classifier']=='INDETERMINATE' for row in tested)
                  or result['build_count'] == 12 or len(path['nodes']) == 2, 'search stopped before a declared terminal/budget condition')
        s1 = forecast(tested)
        observed = result.get('S1')
        check(isinstance(observed,dict) and observed['available'] == (s1['passed'] is not None)
              and observed['passed'] == s1['passed'] and observed['slow_parent'] == S1_SLOW
              and observed['fast_child'] == S1_FAST and observed['observed_parent'] == s1['slow_classification']
              and observed['observed_child'] == s1['fast_classification'],'frontend local S1 metadata differs')
        expected_counts = {key:sum(proof['counters'][key] for proof in proofs.values()) for key in ('logical_repeats','attempts','retaken','loaded_attempts')}
        check(result['counters'] == expected_counts,'shared endpoint stage counted twice or attempts omitted')
    actual = set((PUBLIC/'raw').rglob('ovh-bench.json'))
    check(actual == RECEIPTS,'unaccounted search receipts or post-stop timing')
    for name,digest in controller.SOURCE_BINDINGS.items():
        check(BOUND.setdefault(name,digest) == digest,'grid receipt dependency changed')
    counts = {key:sum(proof['counters'][key] for proof in proofs.values()) for key in ('logical_repeats','attempts','retaken','loaded_attempts')}
    return dict(status='PASS',stage=stage,saved_data_only=True,no_codecs_or_clocks_executed=True,
                result_sha256=sha(result_path),endpoint_bracket=bracket,endpoint_slow_ns=s,endpoint_reference_ns=f,
                build_count=result['build_count'],tested_cores=len(tested),counters=counts,S1=forecast(tested),
                global_first_fast_claim=False,ancestry_proof='retained search/history.json; no Git command executed by this auditor')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('endpoints','all'),default='all')
    parser.add_argument('--endpoint-admission',type=Path,default=PUBLIC/'endpoint-admission.json')
    parser.add_argument('--candidate-admission',type=Path,default=PUBLIC/'candidate-admission-v2.json')
    parser.add_argument('--result',type=Path,default=PUBLIC/'result.json')
    parser.add_argument('--output',type=Path,default=PUBLIC/'audit.json')
    args = parser.parse_args()
    try:
        result = audit(args.endpoint_admission,args.candidate_admission,args.result,args.stage)
        for name in ('audit_search.py','SEARCH_PROTOCOL.md','bisect_core.py','search.py'):
            sha(HERE/name)
        result.update(private_artifacts_hash_verified=len(PRIVATE_CHECKED),private_paths_not_available=sorted(PRIVATE_UNAVAILABLE),
                      source_bindings=[dict(path=name,sha256=digest) for name,digest in sorted(BOUND.items())])
        code = 0
    except (Incomplete,ValueError,KeyError,TypeError,OSError,IndexError) as error:
        result,code = dict(status='INCOMPLETE',stage=args.stage,reason=str(error),saved_data_only=True),2
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(packed(result))
    print(json.dumps(dict(status=result['status'],stage=args.stage,output=str(args.output),reason=result.get('reason')),sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
