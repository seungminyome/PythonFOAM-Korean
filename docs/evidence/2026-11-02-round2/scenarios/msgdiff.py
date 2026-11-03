#!/usr/bin/env python3
"""Normalised tail text of each scenario row: v2012 and v2212 against the v2106 record (and 8 for the rows only 8 has).
Normalisation removes version strings, hosts, pids, paths, numbers with exponents and timings."""
import json, re
from pathlib import Path
E = Path('/cluster/medbow/gscratch/syome/github_repos/PythonFOAM/docs/evidence/2026-10-30-versions/schedule')
S = Path('/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/scenarios')
D = {'v2012': json.loads((S/'scen-v2012/scenarios.json').read_text()), 'v2212': json.loads((S/'scen-v2212/scenarios.json').read_text()),
     'v2106': json.loads((E/'ef78700-v2106-24950748/scenarios.json').read_text()), '8': json.loads((E/'ef78700-8-24950749/scenarios.json').read_text())}
def norm(lines):
    out = []
    for l in lines:
        l = re.sub(r'\(openfoam-\d+ patch=\d+\)|OpenFOAM-\S+|openfoam\d+', 'VER', l)
        l = re.sub(r'\[[\w.-]+:\d+\]', '[HOST:PID]', l)
        l = re.sub(r'/cluster/\S+', 'PATH', l)
        l = re.sub(r'-?\d+\.\d+e[-+]\d+|-?\d+\.\d+|\b\d+\b', 'N', l)
        l = re.sub(r'\s+', ' ', l).strip()
        if l and not l.startswith('ExecutionTime') and 'ClockTime' not in l:
            out.append(l)
    return out
rows = {}
for v, d in D.items():
    for n, lst in d.items():
        if n == 'driver-errors': continue
        for r in lst:
            rows.setdefault((n, r.get('build', 'fork')), {})[v] = norm(r.get('tail', []))
same, diff = 0, []
for key in sorted(rows):
    byv = rows[key]
    ref = byv.get('v2106') or byv.get('8')
    bad = {v: t for v, t in byv.items() if v in ('v2012', 'v2212') and t != ref}
    if bad: diff.append((key, ref, bad))
    else: same += 1
print('rows:', len(rows), 'tails equal after normalisation:', same, 'differ:', len(diff))
for key, ref, bad in diff:
    print('==', key)
    print('   ref :', ref[-6:])
    for v, t in bad.items():
        print(f'   {v}:', t[-6:])
