#!/usr/bin/env python3
"""Generate a JS-free, offline v0.2.0 site exclusively from a verified release.

The canonical A9 filename is leaderboard.json (lowercase), not LEADERBOARD.json.
Methodology links must be retained metadata artifacts; missing links refuse.
No live hardware, decoder, timestamp, network resource or measurement is used.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import posixpath
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import quote, unquote, urlsplit
import xml.etree.ElementTree as ET

import html5lib
import markdown

from review.axis3.verdict_data import load_json, sha256_file
from tools import release_v020
from tools.build_leaderboard import COLUMNS, METRICS, number

AXES = {3: 'Random access and the window law', 4: 'Cohort random access',
        5: 'Application corruption'}
COLORS = {
    'light': {'background': '#ffffff', 'surface': '#f0f4f8', 'text': '#182230',
              'muted': '#465468', 'link': '#124b8b', 'pass': '#065f46',
              'fail': '#991b1b', 'border': '#52667b', 'focus': '#92400e'},
    'dark': {'background': '#111827', 'surface': '#1f2937', 'text': '#f9fafb',
             'muted': '#cbd5e1', 'link': '#93c5fd', 'pass': '#6ee7b7',
             'fail': '#fca5a5', 'border': '#94a3b8', 'focus': '#fbbf24'}}
ACTIVE = {'.html', '.htm', '.js', '.mjs', '.svg'}


def esc(value):
    return html.escape(str(value), quote=True)


def pretty(value):
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)


def row_id(row):
    return hashlib.sha256(pretty(row).encode('utf-8')).hexdigest()


def href(page, target):
    return quote(posixpath.relpath(target, posixpath.dirname(page) or '.'), safe='/.-_~')


def anchor(page, target, label):
    return '<a href="'+esc(href(page, target))+'">'+esc(label)+'</a>'


def css():
    variables = []
    for theme in ('light', 'dark'):
        rule = ':root {'+' '.join('--'+k+': '+v+';' for k, v in COLORS[theme].items())+'}'
        variables.append(rule if theme == 'light' else '@media (prefers-color-scheme: dark) {'+rule+'}')
    return ('\n'.join(variables)+'''
:root {color-scheme: light dark; font-family: system-ui, sans-serif; line-height: 1.6;}
body {margin: 0; color: var(--text); background: var(--background);}
header, main, footer {max-width: 90rem; margin: auto; padding: 1.25rem;}
header, footer {border-block: 1px solid var(--border);}
nav ul {display: flex; flex-wrap: wrap; gap: 1.2rem; list-style: none; padding: 0;}
a {color: var(--link); text-decoration: underline; text-underline-offset: .18em;}
a:hover {text-decoration-thickness: .15em;}
:focus-visible {outline: 3px solid var(--focus); outline-offset: 3px;}
.skip {position: absolute; left: 1rem; top: 0; transform: translateY(-200%);}
.skip:focus {transform: none; background: var(--background); padding: .6rem; z-index: 1;}
.notice, details {background: var(--surface); border: 1px solid var(--border); padding: 1rem;}
.muted {color: var(--muted);}
.pass {color: var(--pass); font-weight: bold;}
.fail {color: var(--fail); font-weight: bold;}
.table-scroll {overflow-x: auto; margin-block: 1rem;}
table {border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums;}
caption {text-align: left; font-weight: bold; padding-block: .6rem;}
th, td {padding: .55rem; border: 1px solid var(--border); vertical-align: top; text-align: left;}
thead, th[scope=row] {background: var(--surface);}
pre {overflow-x: auto; white-space: pre-wrap; overflow-wrap: anywhere; padding: 1rem; background: var(--surface);}
code {font-family: ui-monospace, monospace; overflow-wrap: anywhere;}
dt {font-weight: bold;} dd {margin-inline-start: 1.25rem; overflow-wrap: anywhere;}
summary {cursor: pointer; font-weight: bold;} section {margin-block: 2rem;}
@media (max-width: 40rem) {header, main, footer {padding: .8rem;} nav ul {gap: .8rem;} th, td {padding: .4rem;}}
''').encode('utf-8')


def document(page, title, body):
    links = [('index.html', 'Overview')]+[
        ('axes/'+str(a)+'/index.html', 'Axis '+str(a)) for a in AXES]+[
        ('downloads/index.html', 'Downloads')]
    nav = '<nav aria-label="Primary"><ul>'+''.join('<li>'+anchor(page, p, label)+'</li>' for p, label in links)+'</ul></nav>'
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;self&#39;; '
        'script-src &#39;none&#39;; style-src &#39;self&#39;; img-src &#39;self&#39;; '
        'connect-src &#39;none&#39;; object-src &#39;none&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
        '<title>'+esc(title)+' — hw-apex-bench</title><link rel="stylesheet" href="'+esc(href(page, 'assets/site.css'))+'">'
        '</head><body><a class="skip" href="#main">Skip to content</a>'
        '<header><p>hw-apex-bench v0.2.0 · Evidence, not estimates</p>'+nav+'</header>'
        '<main id="main"><h1>'+esc(title)+'</h1>'+body+'</main>'
        '<footer><p>Source hashes identify bytes, not authorship. A verified scientific FAIL remains visible. '
        'No build timestamp or inferred machine is added.</p></footer></body></html>\n').encode('utf-8')


def table(page, data):
    rows = data['rows']
    cols = ['format', 'variant', 'kind', 'scope', 'machine', 'hash_mode', 'status']+[
        k for k in METRICS if any(k in r for r in rows)]
    text = '<section><h3>'+esc(data['id'])+'</h3><details><summary>Comparison conditions</summary><pre>'+esc(pretty(data['conditions']))+'</pre></details>'
    text += '<div class="table-scroll" tabindex="0" role="region" aria-label="'+esc(data['id'])+' leaderboard">'
    text += '<table data-benchmark="true"><caption>'+esc(data['id'])+' — independently verified sources</caption><thead><tr>'
    text += ''.join('<th scope="col">'+esc(c)+'</th>' for c in cols+['evidence_sha256', 'details'])+'</tr></thead><tbody>'
    for row in rows:
        text += '<tr data-row-id="'+row_id(row)+'">'
        for c in cols:
            tag, scope = ('th', ' scope="row"') if c == 'format' else ('td', '')
            value = row.get(c)
            label = 'Not recorded' if value is None else number(value)
            status_class = 'pass' if value == 'PASS' else 'fail' if value in ('FAIL', 'FAILED') else 'muted'
            status = ' class="'+status_class+'"' if c == 'status' else ''
            text += '<'+tag+scope+status+' data-field="'+esc(c)+'" data-evidence-sha256="'+row['evidence_sha256']+'">'+esc(label)+'</'+tag+'>'
        text += '<td data-field="evidence_sha256" data-evidence-sha256="'+row['evidence_sha256']+'"><code>'+row['evidence_sha256']+'</code></td><td>'+anchor(page, 'rows/'+row_id(row)+'/index.html', 'Evidence and reproduction')+'</td></tr>'
    return text+'</tbody></table></div></section>'


def resolve_method_link(root, url):
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme not in ('https', 'http') or not parsed.netloc:
            raise ValueError('unsafe methodology link scheme')
        return None
    if parsed.query or parsed.fragment:
        raise ValueError('methodology links must identify complete artifact files')
    name = unquote(parsed.path)
    path = release_v020.leaderboard.relative(root/'metadata', name)
    if not path.is_file():
        raise ValueError('missing methodology link artifact')
    return path.relative_to(root).as_posix()


def method_fragment(text, root, page):
    # Raw HTML from evidence-derived documentation is inert, not trusted markup.
    fragment = markdown.markdown(html.escape(text, quote=False), extensions=['tables', 'fenced_code'], output_format='html')
    tree = html5lib.parseFragment(fragment, namespaceHTMLElements=False)
    for element in tree.iter():
        element.attrib.pop('style', None)
        if element.tag == 'a':
            target = resolve_method_link(root, element.attrib['href'])
            if target is not None:
                element.set('href', href(page, 'downloads/release/'+target))
        elif element.tag == 'img':
            target = resolve_method_link(root, element.attrib['src'])
            if target is None:
                raise ValueError('external image resource refused')
            element.set('src', href(page, 'downloads/release/'+target))
            if not element.get('alt'):
                raise ValueError('methodology image requires alternative text')
        elif element.tag == 'th':
            element.set('scope', 'col')
        elif element.tag == 'table':
            caption = ET.Element('caption')
            caption.text = 'Definitions and criteria from the verified methodology'
            element.insert(0, caption)
        elif isinstance(element.tag, str) and re.fullmatch('h[1-6]', element.tag):
            # Methodology follows the page's h2 section; avoid duplicate page h1.
            element.tag = 'h'+str(min(6, int(element.tag[1:])+1))
    return html5lib.serialize(tree, tree='etree', quote_attr_values='always', omit_optional_tags=False,
                             alphabetical_attributes=True)


def method_sections(text, axis):
    sections = re.split(r'(?m)(?=^## )', text)
    common = ('## Canonical bytes and coordinates', '## Same machine and execution boundary')
    if axis == 3:
        if not any(s.startswith('## Window law:') for s in sections):
            raise ValueError('missing Axis 3 methodology section')
        return ''.join(s for s in sections if not s.startswith(('## Axis 4:', '## Axis 5:', '## Deterministic')))
    if not any(s.startswith('## Axis '+str(axis)+':') for s in sections):
        raise ValueError('missing Axis '+str(axis)+' methodology section')
    return ''.join(s for s in sections if s.startswith(common+('## Axis '+str(axis)+':',)))


def file_refs(value, prefix='$'):
    if isinstance(value, dict):
        if set(value) == {'path', 'bytes', 'sha256'}:
            yield prefix, value
        else:
            for key in sorted(value):
                yield from file_refs(value[key], prefix+'.'+key)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from file_refs(child, prefix+'['+str(i)+']')


def associated_files(row, evidence, manifest):
    sha = row['evidence_sha256']
    records = [r for r in manifest['artifacts'] if sha in r['evidence_sha256']]
    for field, ref in file_refs(evidence):
        matches = [r for r in records if (r['bytes'], r['sha256']) == (ref['bytes'], ref['sha256'])
                   and (r['path'] == ref['path'] or r['path'].endswith('/'+ref['path']))]
        if not matches:
            raise ValueError('missing evidence file link: '+field)
    return records


def validate_site(directory):
    """Strict HTML5 parsing plus file/fragment and numeric-provenance checks."""
    root = Path(directory).resolve(strict=True)
    trees, links = {}, []
    board = load_json(root/'downloads/release/leaderboard.json')
    expected = {row_id(r): r for t in board['tables'] for r in t['rows']}
    for path in sorted(root.rglob('*.html')):
        if path.is_relative_to(root/'downloads/release'):
            raise ValueError('active HTML artifact refused')
        parser = html5lib.HTMLParser(strict=True, namespaceHTMLElements=False)
        tree = parser.parse(path.read_text(encoding='utf-8'))
        parents = {child: parent for parent in tree.iter() for child in parent}
        ids = [e.get('id') for e in tree.iter() if e.get('id')]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate HTML id')
        trees[path] = set(ids)
        for element in tree.iter():
            if element.tag in ('script', 'iframe', 'object', 'embed', 'base', 'form'):
                raise ValueError('active element refused')
            if any(k.lower().startswith('on') for k in element.attrib):
                raise ValueError('inline event handler refused')
            for attr in ('href', 'src'):
                if attr in element.attrib:
                    links.append((path, element.tag, element.get(attr)))
            if element.tag == 'table':
                if element.find('caption') is None:
                    raise ValueError('table caption required')
                if any(e.tag == 'th' and e.get('scope') not in ('row', 'col') for e in element.iter()):
                    raise ValueError('table header scope required')
            if element.get('data-field'):
                field = element.get('data-field')
                row = expected.get(parents[element].get('data-row-id'))
                if row is None or field not in COLUMNS or element.get('data-evidence-sha256') != row['evidence_sha256']:
                    raise ValueError('numeric/value cell without evidence provenance')
                value = row.get(field)
                label = 'Not recorded' if value is None else number(value)
                if ''.join(element.itertext()) != label:
                    raise ValueError('displayed value does not match evidence')
            if element.tag == 'table' and element.get('data-benchmark') == 'true':
                for tr in element.findall('./tbody/tr'):
                    for cell in tr:
                        if cell.get('data-field') is None and re.fullmatch(r'[-+]?\d+(?:\.\d+)?', ''.join(cell.itertext())):
                            raise ValueError('number without evidence provenance')
    for path, tag, link in links:
        url = urlsplit(link)
        if url.scheme or url.netloc:
            if url.scheme not in ('https', 'http') or not url.netloc or tag != 'a':
                raise ValueError('external resource or unsafe link refused')
            continue
        if url.query:
            raise ValueError('internal link query refused')
        target = (path.parent/unquote(url.path)).resolve(strict=True) if url.path else path
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError('missing or escaping internal link')
        if url.fragment and (target not in trees or unquote(url.fragment) not in trees[target]):
            raise ValueError('missing internal fragment')
    return {'html_pages': len(trees), 'links': len(links), 'HTML5': 'PASS', 'internal_links': 'PASS'}


def build(directory, output='site', expected_manifest_sha256=None):
    root = Path(directory).resolve(strict=True)
    out = Path(output).resolve()
    if out.exists() or out.is_relative_to(root) or root.is_relative_to(out):
        raise ValueError('output must be new and disjoint from release input')
    snapshots = {p.relative_to(root).as_posix(): sha256_file(p) for p in release_v020.files(root)}
    receipt = release_v020.verify(root, expected_manifest_sha256)
    data = load_json(root/'leaderboard.json')
    manifest = load_json(root/'RELEASE_MANIFEST.json')
    method = (root/'metadata/METHODOLOGY.md').read_text(encoding='utf-8')
    rows = [r for t in data['tables'] for r in t['rows']]
    for row in rows:
        if any(type(v) in (int, float) and k not in ('axis', *METRICS) for k, v in row.items()):
            raise ValueError('number without evidence field')
    # Preflight the entire document, not only the selected section on a page.
    method_fragment(method, root, 'index.html')
    for p in release_v020.files(root):
        if p.suffix.lower() in ACTIVE:
            raise ValueError('active web artifact refused: '+p.name)
    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.site-v020-', dir=out.parent))
    try:
        shutil.copytree(root, staging/'downloads/release')
        for name in ('leaderboard.csv', 'leaderboard.json', 'RELEASE_MANIFEST.json'):
            shutil.copyfile(root/name, staging/'downloads'/name)
        pages = {}
        warning = ('<p class="notice">Synthetic evidence establishes correctness, not performance. '
                  'Unknown machines remain separate; missing values are not zeros. '
                  'Axis 5 v1 supports synthetic experiments only.</p>')
        page = 'index.html'
        body = warning
        for axis, title in AXES.items():
            body += '<section><h2>'+anchor(page, 'axes/'+str(axis)+'/index.html', 'Axis '+str(axis)+' · '+title)+'</h2>'
            body += ''.join(table(page, t) for t in data['tables'] if t['conditions']['axis'] == axis)+'</section>'
        pages[page] = document(page, 'Verified results', body)
        for axis, title in AXES.items():
            page = 'axes/'+str(axis)+'/index.html'
            body = warning+'<h2>Leaderboard</h2>'+''.join(table(page, t) for t in data['tables'] if t['conditions']['axis'] == axis)
            body += '<section><h2>Methodology, definitions and acceptance criteria</h2><p>'
            body += anchor(page, 'downloads/release/metadata/METHODOLOGY.md', 'Complete source methodology')
            body += ' · SHA-256 <code>'+sha256_file(root/'metadata/METHODOLOGY.md')+'</code></p>'
            body += method_fragment(method_sections(method, axis), root, page)+'</section>'
            pages[page] = document(page, 'Axis '+str(axis)+' · '+title, body)
        for row in rows:
            page = 'rows/'+row_id(row)+'/index.html'
            source = load_json(root/row['evidence'])
            records = associated_files(row, source, manifest)
            body = warning+'<h2>Leaderboard row</h2><pre>'+esc(pretty(row))+'</pre><p>'
            body += anchor(page, 'downloads/release/'+row['evidence'], 'Exact evidence JSON')
            body += ' · SHA-256 <code>'+row['evidence_sha256']+'</code></p>'
            body += '<h2>All evidence fields</h2><pre>'+esc(pretty(source))+'</pre>'
            body += '<h2>Hash-bound files</h2><p>Shared input files retain their manifest associations; association is not a machine inference.</p><ul>'
            for record in records:
                body += '<li>'+anchor(page, 'downloads/release/'+record['path'], record['path'])+' · <code>'+record['sha256']+'</code></li>'
            body += '</ul><h2>Reproduce and independently verify</h2><p>Run in the applied benchmark clone, with this complete site at ./site. '
            body += 'The output directory must be new. These commands verify existing evidence and regenerate HTML; they do not rerun measurements.</p><pre>'
            command = 'set -euo pipefail\npython3 -m tools.release_v020 --verify site/downloads/release --manifest-sha256 '+receipt['manifest_sha256']+'\npython3 -m tools.build_site site/downloads/release --out rebuilt-site --manifest-sha256 '+receipt['manifest_sha256']
            body += esc(command)+'</pre>'
            pages[page] = document(page, row['format']+' / '+row['variant']+' / '+row.get('hash_mode', 'access'), body)
        page = 'downloads/index.html'
        body = '<p>Exact verified source bytes, without recalculation or rounded numbers.</p><ul>'
        for name in ('leaderboard.csv', 'leaderboard.json', 'RELEASE_MANIFEST.json'):
            body += '<li>'+anchor(page, 'downloads/'+name, name)+' · SHA-256 <code>'+sha256_file(root/name)+'</code></li>'
        body += '</ul><p>'+anchor(page, 'downloads/release/RELEASE_INPUT.json', 'Release recipe (not release-input-v1 CLI configuration)')+'</p>'
        body += '<p>Full evidence and dependencies are included in the site artifact under downloads/release; keep that tree intact for reproduction.</p>'
        pages[page] = document(page, 'Downloads', body)
        for name, blob in pages.items():
            target = staging/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob)
        (staging/'assets').mkdir()
        (staging/'assets/site.css').write_bytes(css())
        (staging/'.nojekyll').write_bytes(b'')
        validation = validate_site(staging)
        release_v020.verify(staging/'downloads/release', receipt['manifest_sha256'])
        after = {p.relative_to(root).as_posix(): sha256_file(p) for p in release_v020.files(root)}
        if snapshots != after:
            raise ValueError('release changed during site assembly')
        sums = ''.join(sha256_file(p)+'  '+p.relative_to(staging).as_posix()+'\n' for p in release_v020.files(staging))
        (staging/'SITE_SHA256SUMS').write_text(sums, encoding='utf-8')
        staging.rename(out)
        return {'status': 'PASS', 'rows': len(rows), 'manifest_sha256': receipt['manifest_sha256'],
                'site_tree_sha256': hashlib.sha256(sums.encode('utf-8')).hexdigest(), **validation}
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release', type=Path)
    parser.add_argument('--out', type=Path, default=Path('site'))
    parser.add_argument('--manifest-sha256')
    args = parser.parse_args()
    try:
        result = build(args.release, args.out, args.manifest_sha256)
    except Exception as exc:
        parser.exit(1, 'SITE_FAILED '+type(exc).__name__+': '+str(exc)+'\n')
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
