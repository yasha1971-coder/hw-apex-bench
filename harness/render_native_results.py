#!/usr/bin/env python3
"""Generate a candidate run's README from its JSONL, never edit published tables."""
import json
from pathlib import Path
import sys


def render(source,destination):
    rows=[json.loads(s) for s in Path(source).read_text().splitlines()]
    text=['# Native measurement candidate','',
          'Generated from results.jsonl. Absolute timings are declared and host-specific.',
          'Baseline ratios use only this run. Unreached throughput plateaus remain data_edge.','',
          '| Codec / version | Axis / scope | Value | Unit | Baseline ratio |',
          '|---|---|---:|---|---:|']
    def safe(x):return str(x).replace('|','\\|').replace('\n',' ')
    for row in rows:
        scope=row['axis']
        for key in ('profile','ranges','copies','point_granularity'):
            if key in row:scope+=' · '+key+'='+str(row[key])
        value=f'{row["value"]:.9g}' if row['value'] is not None else 'n/a — '+row['reason']
        b=row['baseline_ratio'];relative=f'{b["value"]:.9g}' if b['value'] is not None else 'n/a — '+b['reason']
        text.append('| '+' | '.join(map(safe,[row['codec']+' @ '+row['version'],scope,value,row['unit'],relative]))+' |')
    text+=['','## Reproduction','']
    for i,row in enumerate(rows,1):
        text += [f'{i}. {row["codec"]}: {row["axis"]}', '', '```sh',row['command'],'```','']
    text+=['## License','','Code Apache-2.0; measurements CC BY 4.0.','']
    Path(destination).write_text('\n'.join(text))

if __name__=='__main__':render(sys.argv[1],sys.argv[2])
