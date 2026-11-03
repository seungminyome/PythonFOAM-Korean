#!/usr/bin/env python3
"""Scenario, schedule and extra outcomes at the r4/pr-observer tip on four versions, against the phase-3 records
(r3/solver/scenarios/{scen,sched,scenx}-<ver>, r3/hooks 01eea51, jobs 25089075-78).
Prints (1) rows where the four r4 versions disagree, (2) every row where r4 differs from the phase-3 record of the
same version, with both values."""
import json
from pathlib import Path
R3 = Path('/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r3/solver/scenarios')
S = Path('/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix/scenarios')
VERS = ('v2012', 'v2106', 'v2212', '8')
FILES = {'scen': ('scen', 'scenarios.json'), 'sched': ('sched', 'schedule.json'), 'extra': ('scenx', 'extra.json')}
KEYS = ('exit', 'timed_out', 'end', 'finalized', 'fatal', 'sigfpe', 'nan_residual')
EXTRA = ('values_match', 'pod_files_with_nan', 'decompose_exit', 'ref_lines', 'refcount_lines', 'variance_lines', 'dirs',
         'proc_dirs', 'case_dirs', 'truncation_warnings', 'pod_files', 'snapshot_calls', 'sigfpe_trace', 'nan_residuals')
SKEYS = ('exit', 'finalized', 'fatal', 'schedule', 'modes', 'problems', 'python_collect')
out = {}


def scen_rows(d):
    rows = {}
    for n, lst in d.items():
        if n == 'driver-errors':
            rows[('driver-errors', '')] = lst
            continue
        for r in lst:
            rows[(n, r.get('build', 'fork'))] = ({k: r.get(k) for k in KEYS}, {k: r[k] for k in EXTRA if k in r})
    return rows


def sched_rows(d):
    return {(r.get('build'), r.get('module'), r.get('analysis'), r.get('writeInterval'), r.get('podSvdInterval'), r.get('ranks')):
            {k: r.get(k) for k in SKEYS if k in r} for r in d}


for kind, fn in (('scen', scen_rows), ('extra', scen_rows), ('sched', sched_rows)):
    pre, name = FILES[kind]
    new = {v: json.loads((S/f'{pre}-{v}'/name).read_text()) for v in VERS if (S/f'{pre}-{v}'/name).exists()}
    ref = {v: json.loads((R3/f'{pre}-{v}'/name).read_text()) for v in VERS if (R3/f'{pre}-{v}'/name).exists()}
    nrows = {v: fn(d) for v, d in new.items()}
    rrows = {v: fn(d) for v, d in ref.items()}
    names = sorted(set().union(*[set(r) for r in nrows.values()]) | set().union(*[set(r) for r in rrows.values()]), key=str)
    cross, vsref, same, nver = [], [], 0, 0
    for n in names:
        vals = {v: json.dumps(nrows[v].get(n), sort_keys=True) for v in nrows}
        if len(set(vals.values())) != 1:
            cross.append((n, {v: nrows[v].get(n) for v in nrows}))
        for v in nrows:
            if v not in rrows:
                continue
            nver += 1
            if json.dumps(rrows[v].get(n), sort_keys=True) != vals[v]:
                vsref.append((n, v, rrows[v].get(n), nrows[v].get(n)))
            else:
                same += 1
    out[kind] = dict(rows=len(names), version_rows=nver, same_as_phase3=same, differs_from_phase3=len(vsref),
                     cross_version_differences=len(cross),
                     cross=[(str(n), d) for n, d in cross], vsref=[(str(n), v, a, b) for n, v, a, b in vsref])
    print(f'\n##### {kind}: versions {sorted(new)}; rows {len(names)}; version-rows {nver}; same as phase 3 {same}; '
          f'differ {len(vsref)}; r4 versions disagree on {len(cross)}')
    for n, v, a, b in vsref:
        print('  VSREF', n, v)
        print('      phase3', json.dumps(a)[:400])
        print('      r4    ', json.dumps(b)[:400])
    for n, d in cross:
        print('  CROSS', n)
        for v, x in d.items():
            print('     ', v, json.dumps(x)[:300])
(S/'compare_r4.json').write_text(json.dumps(out, indent=1, default=str))
