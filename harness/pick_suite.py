"""Run every unittest test*.py directory in a checkout, retaining counts/logs."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('checkout', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
root = a.checkout.resolve()
a.output.mkdir(parents=True, exist_ok=True)
directories = sorted({str(f.parent.relative_to(root)) for top in ('harness','tests','web','review')
                      for f in (root/top).rglob('test*.py')})
runner = '''import json,sys,unittest
s=unittest.defaultTestLoader.discover(sys.argv[1])
n=s.countTestCases()
r=unittest.TextTestRunner(verbosity=2).run(s)
print("SUITE_JSON="+json.dumps(dict(collected=n,run=r.testsRun,skipped=len(r.skipped),failures=len(r.failures),errors=len(r.errors))))
sys.exit(not r.wasSuccessful())
'''
results = []
for directory in directories:
    result = subprocess.run([sys.executable, '-c', runner, directory], cwd=root,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (a.output/(directory.replace('/','-')+'.log')).write_text(result.stdout)
    line = next((x for x in result.stdout.splitlines() if x.startswith('SUITE_JSON=')), None)
    record = json.loads(line.split('=',1)[1]) if line else {}
    record.update(directory=directory,exit=result.returncode)
    results.append(record)
    print(json.dumps(record), flush=True)
report = dict(suites=results, collected=sum(r.get('collected',0) for r in results),
              run=sum(r.get('run',0) for r in results), skipped=sum(r.get('skipped',0) for r in results),
              status='PASS' if all(r['exit']==0 for r in results) else 'FAIL')
(a.output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
sys.exit(report['status'] != 'PASS')
