"""Summarise which solver dictionary each pressure/velocity solve used, from the solver logs.
Usage: summarize.py RUNS_DIR  -> writes RUNS_DIR/summary.md and summary.json"""
import json, re, sys
from pathlib import Path
root = Path(sys.argv[1])
rows, out = [], {}
for ver in ['v2012', 'v2106', 'v2212', '8']:
    d = root/ver
    if not d.is_dir():
        continue
    for case in sorted(d.glob('case-*')):
        log = case/'log.solver'
        if not log.exists():
            continue
        status = (case/'exit-status').read_text().strip() if (case/'exit-status').exists() else '?'
        steps, cur = [], None
        # upstream's PODFoam prints no 'Time =' line, so a time step starts at its 'Courant Number' line (all builds print one per step)
        for line in log.read_text(errors='replace').splitlines():
            if line.startswith('Courant Number'):
                cur = {'time': 'step %d' % (len(steps) + 1), 'p': [], 'Ux': []}
                steps.append(cur)
            if line.startswith('Time = ') and cur is not None:
                cur['time'] += ' (t=%s)' % line.split()[2]
            m = re.match(r'^(\w+):\s+Solving for (p|Ux),', line)
            if m and cur is not None:
                cur[m.group(2)].append(m.group(1))
        steps = [s for s in steps if s['p'] or s['Ux']]   # the Courant line printed before the time loop opens no step
        for i, s in enumerate(steps, 1):
            s['time'] = s['time'].replace(s['time'].split(' (')[0], 'step %d' % i)
        name = case.name[5:]
        out.setdefault(ver, {})[name] = {'exit': status, 'steps': steps}
        for s in steps:
            rows.append((ver, name, status, s['time'], ' '.join(s['p']), ' '.join(s['Ux'])))
md = ['# Which solver dictionary each solve used', '',
      'p is `PCG` (DIC), pFinal is `GAMG`; U is `smoothSolver`, UFinal is `PBiCGStab`. The solver name in the log line therefore names the dictionary.',
      'Case: stabilised PODFoam case, nCorrectors 2, nNonOrthogonalCorrectors 2 (6 p solves per outer iteration), 2 time steps.', '',
      '| version | build | exit | time | p solves (in order) | Ux solves |', '|---|---|---|---|---|---|']
for r in rows:
    md.append('| %s | %s | %s | %s | %s | %s |' % r)
(root/'summary.md').write_text('\n'.join(md) + '\n')
(root/'summary.json').write_text(json.dumps(out, indent=1))
print('\n'.join(md))
