#!/usr/bin/env python3
"""Offline check of a prebuilt static site before Pages deployment (no data root needed).

  python3 -m tools.verify_site SITE_DIR [--tree-sha256 HEX] [--github-output FILE]

Checks, in order: SITE_SHA256SUMS lists exactly the site files with their SHA-256 (and, if given, the SHA-256 of
SITE_SHA256SUMS itself equals --tree-sha256); the site size budget; strict HTML5, internal links and numeric provenance
(tools.build_site.validate_site); the Pages deploy gate (real release with measured or official rows). Prints one JSON
receipt; exit 1 on any failure. The full release verification needs the data root and is done where the site is built.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from review.axis3.verdict_data import sha256_file
from tools import build_site, pages_deploy_gate, release_v020


def check_sums(site):
    sums_path = site/'SITE_SHA256SUMS'
    text = sums_path.read_text(encoding='utf-8')
    listed = {}
    for line in text.splitlines():
        digest, sep, name = line.partition('  ')
        if not sep or len(digest) != 64 or name in listed:
            raise ValueError('SITE_SHA256SUMS: malformed or duplicate line')
        listed[name] = digest
    actual = [p for p in release_v020.files(site) if p != sums_path]
    if sorted(listed) != sorted(p.relative_to(site).as_posix() for p in actual):
        raise ValueError('SITE_SHA256SUMS: missing or extra files')
    for p in actual:
        if sha256_file(p) != listed[p.relative_to(site).as_posix()]:
            raise ValueError('SITE_SHA256SUMS: hash differs for '+p.relative_to(site).as_posix())
    return hashlib.sha256(text.encode('utf-8')).hexdigest(), len(actual)


def verify(site, tree_sha256=None):
    site = Path(site).resolve(strict=True)
    tree, count = check_sums(site)
    if tree_sha256 is not None and tree != tree_sha256:
        raise ValueError('site tree SHA-256 differs from the expected value')
    total = build_site.check_budget(site)
    validation = build_site.validate_site(site)
    deploy, measured, line = pages_deploy_gate.decide(site)
    if not deploy:
        raise ValueError(line)
    return {'status': 'PASS', 'site_tree_sha256': tree, 'files': count, 'site_bytes': total,
            'measured_rows': measured, **validation}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site', type=Path)
    parser.add_argument('--tree-sha256')
    parser.add_argument('--github-output', type=Path)
    args = parser.parse_args()
    try:
        receipt = verify(args.site, args.tree_sha256)
    except Exception as e:  # any failure (I/O, mismatch, strict HTML5 parse error) refuses deployment
        print(f'SITE_VERIFY_FAILED {type(e).__name__}: {e}', file=sys.stderr)
        return 1
    print(json.dumps(receipt, sort_keys=True))
    if args.github_output:
        with args.github_output.open('a') as out:
            out.write('deploy=true\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
