#!/usr/bin/env python3
"""Pages deploy gate: the verified site of a release is deployed from main only if the release contains at least one
measured or official evidence row. Synthetic-only releases (unit fixtures, synthetic native runs) are built and kept as
artifacts but never replace the public homepage.

  python3 -m tools.pages_deploy_gate SITE_DIR [--github-output FILE]

Reads SITE_DIR/downloads/leaderboard.json and SITE_DIR/downloads/RELEASE_MANIFEST.json (written by tools.build_site),
prints one decision line and, with --github-output, appends `deploy=true|false` and `measured_rows=N`. Fails closed
(exit 1, no output written) when the files are missing or malformed."""
import argparse
import collections
import json
import sys
from pathlib import Path

DEPLOYABLE = ('measured', 'official')


def decide(site):
    downloads = Path(site) / 'downloads'
    board = json.loads((downloads / 'leaderboard.json').read_text())
    manifest = json.loads((downloads / 'RELEASE_MANIFEST.json').read_text())
    if not isinstance(board, dict) or not isinstance(board.get('tables'), list):
        raise ValueError('leaderboard.json: tables missing')
    if manifest.get('schema') != 'release-manifest-v1' or manifest.get('mode') not in ('synthetic', 'real'):
        raise ValueError('RELEASE_MANIFEST.json: unexpected schema or mode')
    kinds = collections.Counter()
    for table in board['tables']:
        rows = table.get('rows')
        if not isinstance(rows, list):
            raise ValueError('leaderboard.json: table without rows')
        for row in rows:
            kind = row.get('kind')
            if not isinstance(kind, str):
                raise ValueError('leaderboard.json: row without kind')
            kinds[kind] += 1
    measured = sum(kinds[k] for k in DEPLOYABLE)
    deploy = measured > 0 and manifest['mode'] == 'real'
    summary = ', '.join(f'{k}={kinds[k]}' for k in sorted(kinds)) or 'no rows'
    if deploy:
        line = f'PAGES_DEPLOY_GATE deploy=true measured_rows={measured} mode={manifest["mode"]} kinds: {summary}'
    else:
        line = (f'PAGES_DEPLOY_SKIPPED: release has no measured/official evidence rows (mode={manifest["mode"]}; '
                f'kinds: {summary}); the site is kept as an artifact and the public homepage is not replaced')
    return deploy, measured, line


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site', type=Path)
    parser.add_argument('--github-output', type=Path)
    args = parser.parse_args()
    try:
        deploy, measured, line = decide(args.site)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f'PAGES_DEPLOY_GATE_ERROR: {type(e).__name__}: {e}', file=sys.stderr)
        return 1
    print(line)
    if args.github_output:
        with args.github_output.open('a') as out:
            out.write(f'deploy={"true" if deploy else "false"}\nmeasured_rows={measured}\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
