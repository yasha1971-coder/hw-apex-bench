#!/usr/bin/env python3
"""A8 golden-file acceptance, using preserved A6/A7 native evidence; no measurement."""
import argparse
import json
from pathlib import Path

from tools.build_leaderboard import build

FIXTURE = Path(__file__).resolve().parents[1]/'tests/fixtures/leaderboard'
FILES = ('LEADERBOARD.md', 'leaderboard.csv', 'leaderboard.json')


def acceptance(output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    first = build([FIXTURE/'input'], out/'first')
    second = build([FIXTURE/'input'], out/'second')
    for name in FILES:
        a, b = (out/'first'/name).read_bytes(), (out/'second'/name).read_bytes()
        if a != b or a != (FIXTURE/'expected'/name).read_bytes():
            raise ValueError('determinism/golden mismatch: '+name)
    if first != second or (first['tables'], first['rows']) != (4, 4):
        raise ValueError('golden coverage')
    receipt = {'status': 'PASS', 'golden': 'MATCH', 'rerun': 'BYTE_IDENTICAL', **first}
    (out/'acceptance.json').write_text(json.dumps(receipt, sort_keys=True, indent=2)+'\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    print(json.dumps(acceptance(args.out), sort_keys=True))


if __name__ == '__main__':
    main()
