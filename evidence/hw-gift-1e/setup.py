"""Build the two pinned cores and freeze historical seekable sources.

No import-time actions, encodings or clocks. Run outside OVH-BENCH after this
file and the protocol are committed. All generated files belong to 1e's .work;
the 1b/1c/1d checkouts and dependencies are never modified.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = ROOT / '.work/hw-gift-1e'
UPSTREAM = STATE / 'upstream'
FROZEN = STATE / 'frozen'
URL = 'https://github.com/meta/zstd.git'
FLAGS = '-O3 -fPIC -fno-lto'
PINS = {
    'v1.5.4': dict(commit='945f27758c0fd67b636103a38dbf050266c6b90a', tag_object='48c325656391f471396d57800b0bc99408ae6fbf', version=10504),
    'v1.5.7': dict(commit='f8745da6ff1ad1e7bab384bd1f9d742439278e99', tag_object='ac66b19e6bd6b83238bf008eecc1298105298532', version=10507),
}
HINT_LINES = (b'    assert(zcs->maxFrameSize < INT_MAX);\n'
              b'    ZSTD_CCtx_setParameter(zcs->cstream, ZSTD_c_srcSizeHint, (int)zcs->maxFrameSize);\n')


def require(ok, why):
    if not ok:
        raise ValueError(why)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def packed(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def load(path):
    return json.loads(Path(path).read_bytes())


def immutable(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == data, 'retained setup bytes changed: ' + str(path))
    else:
        with path.open('xb') as stream:
            stream.write(data)


def git(*args, repo=UPSTREAM):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def captured(command, label):
    """A failed command leaves its raw logs and must be inspected, not rerun."""
    out, err = STATE / 'logs' / (label + '.stdout'), STATE / 'logs' / (label + '.stderr')
    require(not out.exists() and not err.exists(), 'unfinished command logs exist: ' + label)
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    immutable(out, result.stdout)
    immutable(err, result.stderr)
    result.check_returncode()
    return dict(command=command, stdout_path=str(out), stdout_sha256=file_sha(out),
                stderr_path=str(err), stderr_sha256=file_sha(err))


def provenance():
    require(os.name == 'posix' and not os.environ.get('OVH_BENCH_LOCK_HELD'), 'setup must run on Linux outside the benchmark lock')
    relative = 'evidence/hw-gift-1e/CALIBRATION.md'
    calibration_commit = git('rev-parse', '8b1fba6^{commit}', repo=ROOT).decode().strip()
    require(git('show', calibration_commit + ':' + relative, repo=ROOT) == (HERE / 'CALIBRATION.md').read_bytes(), 'first calibration changed')
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', calibration_commit, 'HEAD'], check=True)
    require(git('branch', '--show-current', repo=ROOT).decode().strip() == 'hw-gift-1e', 'wrong experiment branch')
    source_paths = [HERE / 'CALIBRATION.md', Path(__file__), ROOT / 'evidence/hw-gift-1c/timing.py']
    for path in source_paths:
        name = path.relative_to(ROOT).as_posix()
        git('ls-files', '--error-unmatch', '--', name, repo=ROOT)
        require(not git('status', '--porcelain', '--', name, repo=ROOT).strip(), 'uncommitted setup dependency: ' + name)
    return dict(commit=calibration_commit, sha256=file_sha(HERE / 'CALIBRATION.md'),
                setup_sha256=file_sha(__file__), bridge_container_sha256=file_sha(source_paths[-1]))


def compiler_identity():
    compiler = Path(shutil.which('cc') or '').resolve()
    require(compiler.is_file(), 'cc unavailable')
    return dict(command='cc', path=str(compiler), sha256=file_sha(compiler),
                version=subprocess.check_output(['cc', '--version']).decode(),
                make_version=subprocess.check_output(['make', '--version']).decode())


def upstream():
    STATE.mkdir(parents=True, exist_ok=True)
    if not UPSTREAM.exists():
        captured(['git', 'clone', '--filter=blob:none', '--no-checkout', URL, str(UPSTREAM)], 'upstream-clone')
    require(UPSTREAM.resolve().is_relative_to(STATE.resolve()) and not UPSTREAM.is_symlink(), 'upstream escaped private state')
    require(git('remote', 'get-url', 'origin').decode().strip() == URL, 'upstream origin differs')
    require(git('rev-parse', '--is-shallow-repository').strip() == b'false', 'full commit history required')
    tags = {}
    for tag, pin in PINS.items():
        require(git('rev-parse', 'refs/tags/' + tag).decode().strip() == pin['tag_object'], 'annotated tag object changed: ' + tag)
        require(git('rev-parse', 'refs/tags/' + tag + '^{commit}').decode().strip() == pin['commit'], 'peeled tag commit changed: ' + tag)
        tag_bytes = git('cat-file', '-p', pin['tag_object'])
        tags[tag] = dict(**pin, tag_payload_sha256=digest(tag_bytes), tag_payload=tag_bytes.decode())
    subprocess.run(['git', '-C', str(UPSTREAM), 'merge-base', '--is-ancestor', PINS['v1.5.4']['commit'], PINS['v1.5.7']['commit']], check=True)
    return dict(url=URL, path=str(UPSTREAM), full_commit_history=True, tags=tags,
                dag_added_commits=int(git('rev-list', '--count', PINS['v1.5.4']['commit'] + '..' + PINS['v1.5.7']['commit'])))


def freeze():
    base = 'contrib/seekable_format/'
    old, new = PINS['v1.5.4']['commit'], PINS['v1.5.7']['commit']
    b = git('show', old + ':' + base + 'zstdseek_compress.c')
    a = git('show', new + ':' + base + 'zstdseek_compress.c')
    require(a.count(HINT_LINES) == 1 and a.replace(HINT_LINES, b'') == b, 'tagged writers differ beyond the two PR #3544 lines')
    container = ROOT / 'evidence/hw-gift-1c/timing.py'
    tree = ast.parse(container.read_text(encoding='utf-8'))
    literals = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == 'BRIDGE' for target in node.targets)]
    require(len(literals) == 1 and isinstance(literals[0], str), '1c bridge literal changed')
    files = {'B-compress.c': b, 'A-compress.c': a, 'bridge.c': literals[0].encode(),
             'decompress.c': git('show', old + ':' + base + 'zstdseek_decompress.c'),
             'zstd_seekable.h': git('show', old + ':' + base + 'zstd_seekable.h')}
    for name, data in files.items():
        immutable(FROZEN / name, data)
    return dict(path=str(FROZEN), source_sha256={name: digest(data) for name, data in files.items()},
                source_commits={'B-compress.c': old, 'A-compress.c': new, 'decompress.c': old, 'zstd_seekable.h': old},
                writer_equality=dict(tagged_v157_minus_exact_hint_lines_equals_v154=True,
                    removed_lines=HINT_LINES.decode(), hint_lines_sha256=digest(HINT_LINES),
                    original_writer_blob=git('rev-parse', old + ':' + base + 'zstdseek_compress.c').decode().strip(),
                    hinted_writer_blob=git('rev-parse', new + ':' + base + 'zstdseek_compress.c').decode().strip()))


def core(tag, compiler, protocol):
    pin = PINS[tag]
    path = STATE / 'cores' / tag
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        captured(['git', '-C', str(UPSTREAM), 'worktree', 'add', '--detach', str(path), pin['commit']], tag + '-worktree')
    require(path.resolve().is_relative_to((STATE / 'cores').resolve()) and not path.is_symlink(), 'core escaped private state')
    require(git('rev-parse', '--show-toplevel', repo=path).decode().strip() == str(path.resolve())
            and git('rev-parse', 'HEAD', repo=path).decode().strip() == pin['commit'], 'core worktree pin changed')
    require(not git('status', '--porcelain', repo=path).strip(), 'core source worktree is dirty')
    headers = {name: file_sha(path / name) for name in ('lib/zstd.h', 'lib/zstd_errors.h', 'lib/common/mem.h', 'lib/common/xxhash.h')}
    library, cli = path / 'lib/libzstd.a', path / 'programs/zstd'
    record_path = STATE / 'core-receipts' / (tag + '.json')
    identity = dict(tag=tag, **pin, path=str(path), compiler=compiler, cflags=FLAGS, protocol=protocol, headers_sha256=headers)
    if record_path.exists():
        saved = load(record_path)
        require(saved['identity'] == identity and file_sha(library) == saved['library_sha256']
                and file_sha(cli) == saved['cli_sha256'], 'saved core build changed')
        for command in saved['build_commands']:
            require(file_sha(command['stdout_path']) == command['stdout_sha256']
                    and file_sha(command['stderr_path']) == command['stderr_sha256'], 'saved core build logs changed')
        require(subprocess.check_output([str(cli), '-V']).decode().strip() == saved['cli_version'], 'saved CLI version changed')
        return saved
    require(not library.exists() and not cli.exists(), 'unrecorded core binary; inspect before rebuilding')
    common = ['CC=cc', 'CFLAGS=' + FLAGS, 'LDFLAGS=-fno-lto']
    commands = [captured(['make', '-j1', '-C', str(path / 'lib'), 'libzstd.a', *common], tag + '-static'),
                captured(['make', '-j1', '-C', str(path / 'programs'), 'zstd', *common], tag + '-cli')]
    version = subprocess.check_output([str(cli), '-V']).decode().strip()
    require(tag[1:] in version, 'compiled CLI version differs from tag')
    require(not git('status', '--porcelain', repo=path).strip(), 'building changed tracked core sources')
    saved = dict(identity=identity, **pin, path=str(path), library_path=str(library), library_sha256=file_sha(library),
                 cli_path=str(cli), cli_sha256=file_sha(cli), cli_version=version, expected_version_number=pin['version'],
                 headers_sha256=headers, source_clean=True, build_commands=commands)
    immutable(record_path, packed(saved))
    return saved


def verify_receipt(saved, protocol, compiler, archive, frozen):
    require(saved['protocol'] == protocol and saved['compiler'] == compiler and saved['upstream'] == archive
            and saved['frozen'] == frozen, 'setup dependency identity changed')
    for tag in PINS:
        require(saved['cores'][tag] == core(tag, compiler, protocol), 'core receipt changed')


def main():
    protocol, compiler = provenance(), compiler_identity()
    archive, frozen = upstream(), freeze()
    receipt = STATE / 'setup.json'
    if receipt.exists():
        saved = load(receipt)
        verify_receipt(saved, protocol, compiler, archive, frozen)
    else:
        cores = {tag: core(tag, compiler, protocol) for tag in PINS}
        saved = dict(schema='hw-gift-1e-setup-v1', measurements_of_time=False, no_clocks=True,
                     protocol=protocol, compiler=compiler, cflags=FLAGS, upstream=archive, frozen=frozen, cores=cores)
        immutable(receipt, packed(saved))
    immutable(HERE / 'setup.json', receipt.read_bytes())
    for path in sorted((STATE / 'logs').iterdir()):
        require(path.suffix in ('.stdout', '.stderr'), 'unexpected setup log')
        immutable(HERE / 'setup-logs' / path.name, path.read_bytes())
    print('SETUP_PASS', file_sha(receipt), flush=True)


if __name__ == '__main__':
    main()
