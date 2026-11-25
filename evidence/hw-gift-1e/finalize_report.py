"""Metadata-only final wrapper around the frozen HW-GIFT-1e renderer.

Uses saved, final-audit-bound evidence only. No Git, network, native operation,
encoding or clock is invoked. The base renderer and its CSV remain unchanged.
"""
import argparse
import json
from pathlib import Path

import report as base

HERE = Path(__file__).resolve().parent
SLOW = 'e2965edd107acd0123294e23848cdc00af906468'
FAST = '9420bce8a491e21821c4b372f837bf4bd47e5870'


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def amendment_note(data):
    bound = {(HERE/item['path']).resolve():item['sha256'] for item in data['audit']['source_bindings']}
    own = Path(__file__).resolve()
    require(own in bound and base.sha(own) == bound[own], 'final audit must bind this finalization wrapper')
    search = data['search']
    if search is None or 'source_branch_amendment' not in search:
        return ''
    reference = search['source_branch_amendment']
    require(set(reference) == {'path','sha256'}, 'invalid source-branch amendment reference')
    path = (HERE/reference['path']).resolve()
    require(path.is_relative_to(HERE) and path in bound and base.sha(path) == reference['sha256'] == bound[path],
            'source-branch amendment is not bound by the final audit')
    amendment = base.checked(path,bound)
    protocol = HERE/'SEARCH_AMENDMENT.md'
    require(protocol in bound and base.sha(protocol) == amendment['protocol']['sha256'] == bound[protocol]
            and protocol.read_text(encoding='utf-8').strip(), 'source-branch amendment protocol changed')
    require(amendment['status'] == 'PRE-BUILD SOURCE-ANCESTRY AMENDMENT'
            and amendment['ancestry_exit_code'] == 1 and amendment['candidate_builds_before_amendment'] == 0
            and amendment['prior_total_core_builds'] == 2, 'amendment was not a pre-build ancestry rejection')
    rejected = amendment['rejected_plan']
    base.referenced(HERE,rejected,bound)
    endpoint = amendment['endpoint_admission']
    base.referenced(HERE,endpoint,bound)
    groups = amendment['unchanged_functions']
    require(set(groups) == {'backend','frontend'}, 'unchanged-function proof groups differ')
    functions = [value for group in groups.values() for value in group.values()]
    require(len(functions) == 22 and all(isinstance(item['old_sha256'],str) and len(item['old_sha256']) == 64
            and item['old_sha256'] == item['new_sha256'] for item in functions), '22 unchanged function AST fingerprints required')
    transition = search.get('transition')
    require(isinstance(transition,dict) and transition.get('adjacent_first_parent') is True
            and type(transition.get('on_tag_ancestry_path')) is bool
            and type(transition.get('fast_is_ancestor_of_v157')) is bool
            and search['global_first_fast_claim'] is False, 'transition ancestry qualification missing')
    note = ('Source-ancestry qualification: '+base.link('SEARCH_AMENDMENT.md')+' and '+
            base.link(reference['path'],'the saved pre-build amendment')+f" (SHA-256 `{reference['sha256']}`) "
            'retain the original ancestry-gate rejection before candidate reservation, build or timing; '+
            base.link(rejected['path'],'the rejected plan')+' is preserved. All 22 recorded sampling/native-interface/classifier '
            'function AST fingerprints are unchanged, and the original tag endpoint observations were retained without retiming. ')
    if transition['on_tag_ancestry_path'] is False and transition['fast_is_ancestor_of_v157'] is True:
        note += ('The measured adjacent edge is on a source side branch, **outside the v1.5.4-to-v1.5.7 tag ancestry path**; '
                 'its fast child is an ancestor of v1.5.7. It is a measured first-parent transition on that branch, '
                 'not a direct tag-path bisect boundary or a globally first-fast commit.')
    else:
        note += (f"The recorded tag-path membership is `{transition['on_tag_ancestry_path']}`, and fast-child ancestry of v1.5.7 is "
                 f"`{transition['fast_is_ancestor_of_v157']}`. The result remains local to the measured first-parent edge; "
                 'no globally first-fast commit is established.')
    s1 = search['_audit']['S1']
    if (s1.get('verdict') == 'HIT' and s1.get('passed') is True and s1.get('slow_commit') == SLOW
            and s1.get('fast_commit') == FAST and transition['slow_commit'] == SLOW and transition['fast_commit'] == FAST):
        prefix = 'https://github.com/meta/zstd/blob/'
        note += ('\n\nSource change at the measured S1 SLOW→FAST edge: the '+
                 '[parent reset code]('+prefix+SLOW+'/lib/compress/zstd_compress.c#L1969) uses `memset` to reset the row-tag table; '
                 'the child introduces init-once reuse in '+
                 '[compression reset handling]('+prefix+FAST+'/lib/compress/zstd_compress.c#L1958) and the '+
                 '[workspace allocator]('+prefix+FAST+'/lib/compress/zstd_cwksp.h#L402). '
                 'This is commit-level evidence for the init-once change. The complete commit also changes workspace layout, '
                 'so the experiment does not isolate a `memset`-only ablation or establish a unique instruction-level cause.')
    return note


def insert_once(text, search_block, note):
    require(text.count(search_block) == 1, 'frozen search section must occur exactly once')
    if not note:
        return base.clean(text)
    require(note not in text, 'amendment note already present')
    result = base.clean(text.replace(search_block,search_block+'\n\n'+note,1))
    require(result.count(note) == 1, 'amendment note was not inserted exactly once')
    return result


def render(data):
    note = amendment_note(data)
    block = base.search_text(data)
    results = insert_once(base.results_text(data),block,note)
    original_issue = base.issue_text(data)
    issue = insert_once(original_issue,block,note)
    require(issue.split('\n\n',1)[0] == original_issue.split('\n\n',1)[0], 'first PR #3544 reason paragraph changed')
    require(issue.strip().split('\n\n')[-1] == original_issue.strip().split('\n\n')[-1]
            and issue.count('?') == original_issue.count('?') == 1, 'final single maintainer question changed')
    return {'RESULTS.md':results,'TABLE.csv':base.csv_text(data),'ZSTD_ISSUE_DRAFT.md':issue}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit',type=Path,default=HERE/'audit/final.json')
    parser.add_argument('--output-dir',type=Path,default=HERE)
    args = parser.parse_args()
    try:
        data = base.load_all(args.audit)
        outputs = render(data)
        args.output_dir.mkdir(parents=True,exist_ok=True)
        for name,text in outputs.items():
            destination = args.output_dir/name
            pending = destination.with_name(destination.name+'.writing')
            pending.write_text(text,encoding='utf-8',newline='\n')
            pending.replace(destination)
        print(json.dumps(dict(status='PASS',verified_cells=len(data['cells']),not_run_cells=len(data['missing']),
                              amendment_note=bool(data['search'] and data['search'].get('source_branch_amendment')),files=list(outputs)),sort_keys=True))
        return 0
    except (OSError,ValueError,KeyError,TypeError,StopIteration) as error:
        print(json.dumps(dict(status='INCOMPLETE',reason=str(error)),sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
