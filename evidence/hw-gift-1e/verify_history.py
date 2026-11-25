"""Independent saved-Git proof of the measured source-branch transition.

No codecs, clocks, network requests or Git mutations. Run after search ends.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
UPSTREAM = ROOT / '.work/hw-gift-1e/upstream'
OLD = '945f27758c0fd67b636103a38dbf050266c6b90a'
NEW = 'f8745da6ff1ad1e7bab384bd1f9d742439278e99'
PARENT = 'e2965edd107acd0123294e23848cdc00af906468'
CHILD = '9420bce8a491e21821c4b372f837bf4bd47e5870'
SALT = '91f4c23e634a1d260f290f00b6d870a56cd59ab6'
BASE = '515266e31b2369f82594d47ff4666f0612382bb7'
COMMANDS = []


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args, expected=0):
    command = ['git', '-C', str(UPSTREAM), *args]
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0')
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    COMMANDS.append(dict(command=command, exitcode=result.returncode,
                         stdout_sha256=sha(result.stdout), stderr_sha256=sha(result.stderr)))
    require(result.returncode == expected, 'unexpected Git exit code: ' + repr(command))
    return result.stdout.decode().strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE/'search/git-history-verification.json')
    args = parser.parse_args()
    history_path, result_path = HERE/'search/history.json', HERE/'search/result.json'
    history_raw, result_raw = history_path.read_bytes(), result_path.read_bytes()
    history, result = json.loads(history_raw), json.loads(result_raw)
    require(git('rev-parse', '--is-shallow-repository') == 'false', 'full local commit history required')
    text = git('log', '--format=%H%x09%P%x09%s', OLD+'..'+NEW)
    text += '\n' + git('show', '-s', '--format=%H%x09%P%x09%s', OLD)
    nodes = {}
    for line in text.splitlines():
        commit, parents, title = line.split('\t', 2)
        require(commit not in nodes, 'duplicate reconstructed commit')
        nodes[commit] = dict(commit=commit, parents=parents.split(), title=title)
    require(history['slow'] == OLD and history['fast'] == NEW and history['nodes'] == nodes,
            'published history differs from exact local Git parents/titles')
    require(result['history'] == dict(path='search/history.json', sha256=sha(history_raw)), 'result history reference differs')
    for commit in (PARENT, CHILD, SALT):
        git('merge-base', '--is-ancestor', commit, NEW)
    git('merge-base', '--is-ancestor', OLD, PARENT, expected=1)
    git('merge-base', '--is-ancestor', OLD, CHILD, expected=1)
    require(git('merge-base', OLD, PARENT) == BASE, 'release/source-branch merge base differs')
    require(git('rev-parse', CHILD+'^1') == PARENT and nodes[CHILD]['parents'][0] == PARENT,
            'measured transition is not the stated first-parent edge')
    require(git('rev-parse', SALT+'^1') == CHILD, 'salt commit parent differs')
    transition = result['transition']
    require(result['status'] == 'ADJACENT TRANSITION' and result['global_first_fast_claim'] is False,
            'result overstates transition scope')
    require(transition['slow_commit'] == PARENT and transition['fast_commit'] == CHILD
            and transition['fast_title'] == nodes[CHILD]['title'] and transition['adjacent_first_parent'] is True
            and transition['on_tag_ancestry_path'] is False and transition['fast_is_ancestor_of_v157'] is True,
            'result transition identity/title/qualification differs from actual Git')
    for tested in result['tested']:
        require(tested['commit'] in nodes and tested['title'] == nodes[tested['commit']]['title'], 'tested commit/title differs')
    proof = dict(schema='hw-gift-1e-git-history-verification-v1', status='PASS', no_clocks=True,
                 no_codecs=True, no_network=True, no_git_mutations=True, source_sha256=sha(Path(__file__).read_bytes()),
                 history_sha256=sha(history_raw), result_sha256=sha(result_raw), node_count=len(nodes),
                 merge_base=BASE, transition=transition, allowlisted_ancestors_of_v157=[PARENT, CHILD, SALT], commands=COMMANDS)
    raw = (json.dumps(proof, sort_keys=True, separators=(',', ':'))+'\n').encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        require(args.output.read_bytes() == raw, 'retained history proof changed')
    else:
        with args.output.open('xb') as stream:
            stream.write(raw)
    print('GIT_HISTORY_PASS', sha(raw), len(nodes), flush=True)


if __name__ == '__main__':
    main()
