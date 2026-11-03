#!/usr/bin/env python3
"""Extra scenario sets at bf7a06e on v2012, v2106, v2212, 8 (r2/scenarios/scenx-*/extra.json, jobs in JOBS_EXTRA)
against the fae10ba records in pr/review-cpp/scen2-{v2106,8}/scenarios2.json and scen3-{v2106,8}/scenarios3.json.
Prints every row where the four bf7a06e versions disagree, and every row where bf7a06e differs from the fae10ba record of the same version."""
import json
from pathlib import Path
S = Path('/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/scenarios')
RC = Path('/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/pr/review-cpp')
VERS = ('v2012', 'v2106', 'v2212', '8')
KEYS = ('exit', 'timed_out', 'end', 'finalized', 'fatal', 'nan_residual')
EXTRA = ('banner_sigfpe', 'snapshot_calls', 'sigfpe_trace', 'nan_residuals', 'dirs', 't5', 't7', 'proc2_cells', 'proc2_upod')
def load(p):
    return json.loads(p.read_text()) if p.exists() else None
new = {v: load(S/f'scenx-{v}/extra.json') for v in VERS}
old = {}
for v in ('v2106', '8'):
    d = {}
    for f in (RC/f'scen2-{v}/scenarios2.json', RC/f'scen3-{v}/scenarios3.json'):
        x = load(f)
        if x: d.update({k: r for k, r in x.items()})
    old[v] = d
def rows(d):
    out = {}
    for n, lst in (d or {}).items():
        if n == 'driver-errors': continue
        for r in lst:
            out[(n, r.get('build', 'fork'))] = r
    return out
def sig(r): return {k: r.get(k) for k in KEYS} | {k: r[k] for k in EXTRA if k in r}
newrows = {v: rows(d) for v, d in new.items()}
oldrows = {v: rows(d) for v, d in old.items()}
keys = sorted(set().union(*[set(x) for x in newrows.values()]))
report = {'missing_versions': [v for v in VERS if new[v] is None], 'driver_errors': {v: (new[v] or {}).get('driver-errors') for v in VERS}, 'rows': {}}
print('bf7a06e versions loaded:', [v for v in VERS if new[v]], 'rows:', len(keys))
print('driver-errors:', report['driver_errors'])
for k in keys:
    byv = {v: sig(newrows[v][k]) for v in VERS if k in newrows[v]}
    agree = len({json.dumps(x, sort_keys=True) for x in byv.values()}) == 1 and len(byv) == len([v for v in VERS if new[v]])
    rec = {v: sig(oldrows[v][k]) for v in ('v2106', '8') if k in oldrows[v]}
    vs_rec = {v: (byv.get(v) == rec[v]) for v in rec if v in byv}
    report['rows'][f'{k[0]} [{k[1]}]'] = dict(bf7a06e=byv, fae10ba_record=rec, same_as_record=vs_rec, four_versions_agree=agree)
    if not agree or not all(vs_rec.values()):
        print('==', k, 'four agree:', agree, 'same as fae10ba record:', vs_rec)
        for v, s in byv.items(): print('   bf7a06e', v, json.dumps(s)[:300])
        for v, s in rec.items(): print('   fae10ba', v, json.dumps(s)[:300])
        for v in VERS:
            if k in newrows[v]:
                t = [l for l in newrows[v][k].get('tail', []) if any(w in l for w in ('FATAL', 'modes', 'must', 'Non-finite', 'End', 'finalized', 'nan', 'cannot', 'MPI_ERRORS', 'dumped'))][-3:]
                print('   tail', v, t)
(S/'compare_extra.json').write_text(json.dumps(report, indent=1))
