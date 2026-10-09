#!/usr/bin/env python3
"""A10 offline acceptance from A9 release inputs; no codec or network activity."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

import html5lib
import markdown

from review.axis3.verdict_data import file_ref, load_json, sha256_file
from tools import build_site, release_synthetic, release_v020

REPO = Path(__file__).resolve().parents[1]
GOLDEN = REPO/'tests/fixtures/site/expected'
PINNED_RUN_SHA = '8b6e3e8b282c831ada379b5ee923775d503b5e80e13c69b32cc7e7a1bad9de2a'


def prepare(root):
    config = release_synthetic.prepare(root)
    data = load_json(config)
    source = (REPO/'METHODOLOGY.md').read_text()
    tree = html5lib.parseFragment(markdown.markdown(source, extensions=['tables', 'fenced_code']),
                                 namespaceHTMLElements=False)
    names = {r['path'] for r in data['artifacts']}
    for element in tree.iter():
        if element.tag not in ('a', 'img'):
            continue
        url = element.get('href') if element.tag == 'a' else element.get('src')
        # Resolve against repository methodology using the same confined-link rules.
        from urllib.parse import urlsplit, unquote
        parsed = urlsplit(url)
        if parsed.scheme or parsed.netloc:
            continue
        name = unquote(parsed.path)
        path = release_v020.leaderboard.relative(REPO, name)
        if name == 'review/axis3/RUN.md':
            # Synthetic historical fixture only: preserve server runbook overlays.
            path = GOLDEN/'downloads/release/metadata'/name
            if sha256_file(path) != PINNED_RUN_SHA:
                raise ValueError('frozen A9 synthetic RUN.md SHA mismatch')
        if not path.is_file():
            raise ValueError('methodology link missing from source repository')
        if name not in names:
            target = Path(root)/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            data['artifacts'].append(file_ref(root, target))
            names.add(name)
    config.write_bytes(release_v020.encoded(data))
    return config


def snapshot(root):
    root = Path(root).resolve(strict=True)
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in release_v020.files(root)}


def acceptance(output, *, check_golden=True):
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    try:
        with tempfile.TemporaryDirectory(prefix='site-input-', dir=out.parent) as temp:
            config = prepare(Path(temp)/'input')
            release = release_v020.release(config, out/'release')
        first = build_site.build(out/'release', out/'first', release['manifest_sha256'])
        second = build_site.build(out/'release', out/'second', release['manifest_sha256'])
        a = snapshot(out/'first')
        if a != snapshot(out/'second') or first != second:
            raise ValueError('site byte determinism mismatch')
        if check_golden and a != snapshot(GOLDEN):
            raise ValueError('site golden mismatch')
        receipt = {'rerun': 'BYTE_IDENTICAL', 'golden': 'MATCH' if check_golden else 'NOT_CHECKED',
                   'native_execution': False, **first}
        (out/'acceptance.json').write_bytes(release_v020.encoded(receipt))
        return receipt
    except Exception:
        shutil.rmtree(out)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(acceptance(args.out), sort_keys=True))


if __name__ == '__main__':
    main()
