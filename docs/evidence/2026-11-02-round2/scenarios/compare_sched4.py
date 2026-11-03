#!/usr/bin/env python3
"""schedule.json on four versions: v2106 and 8 from docs/evidence (ef78700, jobs 24950748/24950749), v2012 and v2212 from r2/scenarios (bf7a06e).
Rows keyed by (build, module, analysis, writeInterval, podSvdInterval); compared on exit, finalized, fatal, schedule, modes, problems, python_collect."""
import json
from pathlib import Path
E = Path('/cluster/medbow/gscratch/syome/github_repos/PythonFOAM/docs/evidence/2026-10-30-versions/schedule')
S = Path('/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/scenarios')
SRC = {'v2012': S/'sched-v2012/schedule.json', 'v2106': E/'ef78700-v2106-24950748/schedule.json',
       'v2212': S/'sched-v2212/schedule.json', '8': E/'ef78700-8-24950749/schedule.json'}
KEYS = ('exit', 'finalized', 'fatal', 'schedule', 'modes', 'problems', 'python_collect')
rows = {}
for v, p in SRC.items():
    for r in json.loads(p.read_text()):
        k = (r.get('build'), r.get('module'), r.get('analysis'), r.get('writeInterval'), r.get('podSvdInterval'), r.get('nprocs'))
        rows.setdefault(k, {})[v] = {x: r.get(x) for x in KEYS if x in r}
same, diff = 0, []
for k in sorted(rows, key=str):
    byv = rows[k]
    sigs = {json.dumps(x, sort_keys=True) for x in byv.values()}
    if len(sigs) == 1 and len(byv) == 4: same += 1
    else: diff.append((k, byv))
print('rows:', len(rows), 'identical on all four:', same, 'differ or missing:', len(diff))
for k, byv in diff:
    print('==', k)
    for v in SRC: print('  ', v, byv.get(v, 'MISSING'))
(S/'compare_sched4.json').write_text(json.dumps({str(k): v for k, v in rows.items()}, indent=1))
