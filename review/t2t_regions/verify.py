#!/usr/bin/env python3
"""Verify retained evidence bytes, including original annotation line endings."""
import hashlib,json,sys,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[2];e=root/'evidence/t2t-regions-20260916'
sha=lambda b:hashlib.sha256(b).hexdigest()
m=json.loads((e/'manifest.json').read_text());rows=[json.loads(l) for l in (e/'results.jsonl').read_text().splitlines()]
for path,digest in m['annotations'].items():assert sha((e/Path(path).name).read_bytes())==digest,path
assert len(rows)==90 and len(m['windows'])==30
windows={(w['chromosome'],w['group']):w for w in m['windows']};seen=set()
for r in rows:
 key=(r['chromosome'],r['group'],r['codec']);assert key not in seen;seen.add(key)
 w=windows[key[:2]]
 assert r['input_sha256']==w['input_sha256'] and r['start']==w['start'] and r['end']==w['end']
 assert r['input_bytes']==2097152 and r['stored_bytes']==sum(a['bytes'] for a in r['archive_artifacts'].values())
 assert r['ratio']==r['input_bytes']/r['stored_bytes'] and r['verified']=='byte-exact'
 assert sha((e/'logs'/(r['file']+'.'+r['codec']+'.log')).read_bytes())==r['log_sha256']
if len(sys.argv)>1:
 p=Path(sys.argv[1]);receipt=json.loads((e/'archive-bundle.json').read_text());assert sha(p.read_bytes())==receipt['sha256']
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None
  for w in m['windows']:assert sha(z.read('windows/'+w['file']))==w['input_sha256']
  for r in rows:
   for name,rec in r['archive_artifacts'].items():
    data=z.read('measurement/'+name);assert len(data)==rec['bytes'] and sha(data)==rec['sha256']
print('Annotation bytes, 90 rows/logs and window identities verified'+('; archive bundle verified' if len(sys.argv)>1 else ''))
