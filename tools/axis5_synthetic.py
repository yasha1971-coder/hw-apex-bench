#!/usr/bin/env python3
"""Build real tiny native inputs, exercise Axis 5 CLI and retain all receipts."""
import argparse
import copy
import json
from pathlib import Path
import sys

from review.axis3 import agc_adapter
from review.axis3.verdict_data import load_json, write_json
from tools.axis4_synthetic import acceptance as axis4_acceptance, command, REPO
from tools.axis5_evidence_verify import verify


def acceptance(root, family, library, encoder, source_root, variant=None):
    axis4 = axis4_acceptance(root, family, library, encoder, source_root, variant)
    root = Path(root).resolve()
    plan = load_json(root/'plan.json')
    spec = plan['reader']
    if family == 'agc':
        # A genuinely different stock archive, not a byte copy of target.
        donor = root/'donor.agc'
        creation = agc_adapter.create(Path(encoder).resolve(),
            [('asm1', root/'asm1.fa'), ('asm2', root/'asm2.fa')],
            't2t' if spec['variant'] == 'noref' else 'noref', donor,
            root/'asm1.fa' if spec['variant'] == 'noref' else None)
        write_json(root/'donor-creation.json', creation)
    else:
        donor = root/spec['archives'][1]['archive']['path']
    invocations = []
    def cli(*args):
        argv = [sys.executable, '-m', 'tools.axis5', *map(str, args)]
        got = command(argv, cwd=REPO)
        invocations.append({'argv': argv, 'returncode': got.returncode,
                            'stdout': got.stdout, 'stderr': got.stderr})
        write_json(root/f'axis5-invocation-{len(invocations)}.json', invocations[-1])
        return json.loads(got.stdout)
    prepared = cli('prepare', '--root', root, '--plan', 'plan.json',
                   '--donor', donor.relative_to(root), '--out', 'a7-prepared')
    cli('corrupt', '--root', root, '--prepared', prepared['path'], '--out', 'a7-corrupt')
    cli('run', '--root', root, '--corrupt', 'a7-corrupt/corrupt.json', '--out', 'a7-run')
    evidence = root/'a7-run/evidence.json'
    result = cli('verify', '--root', root, '--evidence', evidence,
                 '--prepared-sha256', prepared['sha256'])
    bad = copy.deepcopy(load_json(evidence))
    bad['rows'][1]['classification'] = ('refusal' if bad['rows'][1]['classification'] != 'refusal' else 'harmless')
    write_json(root/'a7-run/forged.json', bad)
    try:
        verify(root/'a7-run/forged.json', root, prepared['sha256'])
    except ValueError:
        result['forged_classification'] = 'REJECTED'
    else:
        raise AssertionError('forged classification accepted')
    if result['verified'] != 200:
        raise ValueError('synthetic observation count')
    result['axis4'] = axis4
    result['invocations'] = invocations
    write_json(root/'axis5-acceptance.json', result)
    return {k: v for k, v in result.items() if k not in ('invocations', 'axis4')}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('root', 'family', 'library', 'encoder', 'source-root'):
        p.add_argument('--'+key, required=True)
    p.add_argument('--variant')
    a = p.parse_args()
    print(json.dumps(acceptance(a.root, a.family, a.library, a.encoder, a.source_root, a.variant), sort_keys=True))


if __name__ == '__main__':
    main()
