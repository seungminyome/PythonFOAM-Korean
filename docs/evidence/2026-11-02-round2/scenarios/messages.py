#!/usr/bin/env python3
"""For every scenario case folder on v2012 and v2212: exit (from scenarios.json), and the decisive message lines from the full log.fork / log.upstream."""
import json, re, sys
from pathlib import Path
S = Path('/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/scenarios')
PAT = re.compile(r'FOAM FATAL|^\s*(\[\d\] )?(The ranks|svd_func|snapshot_func|analysis_func|mesh_func|python_module|Non-finite|podSvdInterval|Cannot find|Unable to|Python module|POD SVD returned|Python finalized|ModuleNotFoundError|SystemExit|RuntimeError|TypeError|ValueError|ImportError|AttributeError|\w*Error:|Traceback|FOAM exiting|sigFpe|Floating point)|^End$|^\[\d\] (The|svd|snapshot|analysis|mesh|Non|pod|Python)|^(Error|Exception) ', re.M)
out = {}
for ver in ('v2012', 'v2212'):
    res = json.loads((S/f'scen-{ver}/scenarios.json').read_text())
    for name, rows in res.items():
        if name == 'driver-errors': continue
        for r in rows:
            b = r.get('build', 'fork')
            cdir = None
            for cand in (S/f'scen-{ver}'/name, S/f'scen-{ver}'/f'{name}-{b}'):
                if (cand/f'log.{b}').exists(): cdir = cand
            if name.startswith('restart-'):
                cdir = S/f'scen-{ver}'/name.rsplit('-', 1)[0]
            if cdir is None:
                out.setdefault(name, {}).setdefault(b, {})[ver] = dict(exit=r['exit'], msg=['(no log found)']); continue
            text = (cdir/f'log.{b}').read_text(errors='replace')
            lines = [l.strip()[:160] for l in text.splitlines() if PAT.search(l)]
            # de-duplicate per-rank repeats, keep order, keep at most 8
            seen, keep = set(), []
            for l in lines:
                k = re.sub(r'^\[\d\] ', '', re.sub(r'\(openfoam-\d+ patch=\d+\)', '', l)).strip()
                if k and k not in seen: seen.add(k); keep.append(k)
            out.setdefault(name, {}).setdefault(b, {})[ver] = dict(exit=r['exit'], msg=keep[:8])
(S/'messages.json').write_text(json.dumps(out, indent=1))
nd = 0
for name in out:
    for b, byv in out[name].items():
        a, c = byv.get('v2012'), byv.get('v2212')
        tag = 'SAME' if a == c else 'DIFF'
        if tag == 'DIFF': nd += 1
        print(f'== {name} [{b}] {tag} exit v2012={a and a["exit"]} v2212={c and c["exit"]}')
        for l in (a or c)['msg']: print('     ', l)
        if tag == 'DIFF':
            print('   v2212:'); 
            for l in c['msg']: print('     ', l)
print('rows with v2012 != v2212 (exit or message set):', nd)
