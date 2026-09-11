#!/usr/bin/env python3
"""Verify that mechanically expanded native source equals the published source."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ('/* Mechanical extraction from published main; deliberately included at call sites.\n'
          '   This is a temporary source layout, not an adapter ABI. No include guard. */\n')
SUFFIX = '#else\n#error "unknown native extraction section"\n#endif\n'
MARKER = re.compile(r'\n#define HWAPEX_EXTRACT_SECTION ([0-9]+)\n#include "native/([a-z_]+)\.inc"\n#undef HWAPEX_EXTRACT_SECTION\n')


def verify(root=ROOT):
    manifest = json.loads((root/'harness/native/extraction.json').read_text())
    fragments = {}
    for codec, sections in manifest['fragments'].items():
        raw = (root/'harness/native'/f'{codec}.inc').read_text()
        if not raw.startswith(PREFIX):
            raise ValueError('unexpected code outside fragment sections')
        pos = len(PREFIX)
        for i, section in enumerate(sections):
            directive = f'#{"if" if i==0 else "elif"} HWAPEX_EXTRACT_SECTION == {section["section"]}\n'
            if not raw.startswith(directive, pos):
                raise ValueError('unexpected section directive')
            pos += len(directive)
            # Existing C source is ASCII; offsets are also checked against UTF-8 digest.
            body = raw[pos:pos+section['bytes']]
            if hashlib.sha256(body.encode()).hexdigest() != section['sha256']:
                raise ValueError('moved source changed: '+codec+'/'+section['phase'])
            if 'HWAPEX_EXTRACT_SECTION' in body:
                raise ValueError('nested extraction or macro collision')
            fragments[codec, str(section['section'])] = body
            pos += len(body)
            if raw[pos:pos+1] != '\n':
                raise ValueError('bad section delimiter')
            pos += 1
        if raw[pos:] != SUFFIX:
            raise ValueError('unexpected fragment footer')
    used = []
    for path, source in manifest['sources'].items():
        def expand(match):
            key = match[2], match[1]
            used.append(key)
            return fragments[key]
        expanded = MARKER.sub(expand, (root/path).read_text()).encode()
        original = subprocess.check_output(['git', '-C', str(root), 'show', manifest['base_commit']+':'+path])
        if hashlib.sha256(original).hexdigest() != source['sha256'] or expanded != original:
            raise ValueError('expanded source differs from published main: '+path)
    if sorted(used) != sorted(fragments):
        raise ValueError('unused or duplicate fragment')
    result = (root/'results.jsonl').read_bytes()
    original = subprocess.check_output(['git', '-C', str(root), 'show', manifest['base_commit']+':results.jsonl'])
    if result != original:
        raise ValueError('published measurements changed')
    print(f'PASS: {len(used)} copied sections; {len(manifest["sources"])} sources reconstruct byte-for-byte; {len(result.splitlines())} measurement records unchanged')


if __name__ == '__main__':
    verify()
