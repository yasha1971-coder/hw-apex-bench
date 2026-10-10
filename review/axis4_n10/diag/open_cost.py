"""Diagnostic only (not a measurement row): wall and CPU seconds of A6 open_reader + close per plan, to explain
the A6 'after' gate refusals (load1 includes the run's own reader-open CPU). Run from the repo root."""
import json, os, resource, sys, time
from pathlib import Path
sys.path.insert(0, os.getcwd())
from tools import axis4  # noqa: E402

root = Path(sys.argv[1]).resolve()
out = {}
for name in sys.argv[2:]:
    _, plan, prepared, _ = axis4.load_plan(root, f'plans/{name}.json')
    t0, c0 = time.monotonic(), resource.getrusage(resource.RUSAGE_SELF)
    r = axis4.open_reader(root, plan['reader'], {'assemblies': prepared['assemblies']})
    t1, c1 = time.monotonic(), resource.getrusage(resource.RUSAGE_SELF)
    r.close()
    out[name] = {'open_wall_s': round(t1 - t0, 3), 'open_cpu_s': round((c1.ru_utime + c1.ru_stime) - (c0.ru_utime + c0.ru_stime), 3),
                 'maxrss_kb_after': c1.ru_maxrss, 'loadavg_after_open': Path('/proc/loadavg').read_text().split()[:3]}
    print(name, json.dumps(out[name]), flush=True)
    time.sleep(90)
