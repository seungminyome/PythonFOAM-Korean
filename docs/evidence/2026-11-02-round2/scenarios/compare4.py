#!/usr/bin/env python3
"""Scenario outcomes on four OpenFOAM versions: v2106 and 8 from docs/evidence (jobs 24950748/24950749, code ef78700),
v2012 and v2212 from r2/scenarios (code bf7a06e; same PODFoam C++ and validation/ as ef78700).
Writes compare4.json and prints every row where the four versions do not agree."""
import json, re, sys
from pathlib import Path
E = Path('/cluster/medbow/gscratch/syome/github_repos/PythonFOAM/docs/evidence/2026-10-30-versions/schedule')
S = Path('/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/scenarios')
SRC = {'v2012': S/'scen-v2012/scenarios.json', 'v2106': E/'ef78700-v2106-24950748/scenarios.json',
       'v2212': S/'scen-v2212/scenarios.json', '8': E/'ef78700-8-24950749/scenarios.json'}
KEYS = ('exit', 'timed_out', 'end', 'finalized', 'fatal', 'sigfpe', 'nan_residual')
EXTRA = ('values_match', 'pod_files_with_nan', 'decompose_exit', 'ref_lines', 'refcount_lines', 'variance_lines', 'dirs', 'proc_dirs', 'case_dirs')
MSG = re.compile(r'(modes|must be|SystemExit|ModuleNot|Cannot|callable|FOAM FATAL|sigFpe|Floating|Traceback|returned|finite|refuses|rank|snapshot_func|svd_func|Error|not found|No such|signal|Killed|Terminated|End$|Python finalized)')
data = {v: json.loads(p.read_text()) for v, p in SRC.items() if p.exists()}
missing = [v for v in SRC if v not in data]
names = sorted(set().union(*[set(d) for d in data.values()]))
out, diffs = {}, []
for n in names:
    if n == 'driver-errors':
        out[n] = {v: data[v].get(n) for v in data}
        if any(out[n].values()): diffs.append((n, out[n]))
        continue
    rows = {}
    for v, d in data.items():
        for r in d.get(n, []):
            b = r.get('build', 'fork')
            rows.setdefault(b, {})[v] = r
    out[n] = {}
    for b, byv in rows.items():
        sig = {v: tuple(r.get(k) for k in KEYS) for v, r in byv.items()}
        extra = {v: {k: r[k] for k in EXTRA if k in r} for v, r in byv.items()}
        msgs = {v: [l for l in r.get('tail', []) if MSG.search(l)][-3:] for v, r in byv.items()}
        out[n][b] = dict(sig={v: dict(zip(KEYS, s)) for v, s in sig.items()}, extra=extra, msgs=msgs)
        agree = len(set(sig.values())) == 1 and len(sig) == len(data)
        ex_agree = len({json.dumps(e, sort_keys=True) for e in extra.values()}) == 1
        if not agree or not ex_agree:
            diffs.append((f'{n} [{b}]', dict(sig=sig, extra=extra, msgs=msgs)))
(S/'compare4.json').write_text(json.dumps(dict(sources={v: str(p) for v, p in SRC.items()}, missing=missing, scenarios=out), indent=1))
print('versions loaded:', list(data), 'missing:', missing, 'scenario names:', len(names))
print('rows not identical across versions:', len(diffs))
for n, d in diffs:
    print('==', n)
    if 'sig' in d:
        for v, s in d['sig'].items(): print('  ', v, dict(zip(KEYS, s)), d['extra'].get(v) or '')
        for v, m in d['msgs'].items(): print('   msg', v, m)
    else:
        print('  ', d)
