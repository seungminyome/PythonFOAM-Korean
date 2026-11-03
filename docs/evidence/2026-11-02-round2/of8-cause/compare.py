#!/usr/bin/env python3
"""Compare pimpleFoam fields at t = 0.1005 (step 100) between runs, and against the PODFoam frames of the
matrix jobs. Usage: compare.py OUT.json  (reads runs/*)"""
import json, re, sys, glob
from pathlib import Path
import numpy as np

R = Path(__file__).resolve().parent
MATRIX = Path('/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/pr/refix/matrix')
FRAMES = {('8', '2d'): MATRIX/'8-24950783/serial2d', ('8', '3d'): MATRIX/'8-24950783/serial3d',
          ('v2212', '2d'): MATRIX/'v2212-24950782/serial2d', ('v2212', '3d'): MATRIX/'v2212-24950782/serial3d'}


def read_internal(path):
    text = Path(path).read_text()
    m = re.search(r'internalField\s+nonuniform\s+List<(\w+)>\s*\n(\d+)\s*\n\(\n(.*?)\n\)\s*;', text, re.S)
    kind, n, body = m.group(1), int(m.group(2)), m.group(3)
    if kind == 'scalar':
        a = np.array(body.split(), dtype=float)
    else:
        a = np.array([l.strip('() ').split() for l in body.splitlines()], dtype=float)
    assert len(a) == n, (path, len(a), n)
    return a


def diff(ua, pa, ub, pb):
    d_u = np.linalg.norm(ua - ub, axis=1)
    d_p = np.abs((pa - pa.mean()) - (pb - pb.mean()))
    return {'U_max': float(d_u.max()), 'U_rms': float(np.sqrt((d_u**2).mean())),
            'U_peak': float(np.linalg.norm(ua, axis=1).max()),
            'p_max': float(d_p.max()), 'p_rms': float(np.sqrt((d_p**2).mean())),
            'p_range': float(pa.max() - pa.min())}


def log_stats(log):
    text = Path(log).read_text(errors='replace')
    it = [int(m) for m in re.findall(r'Solving for p,.*No Iterations (\d+)', text)]
    steps = len(re.findall(r'^Time = ', text, re.M))
    ux = re.findall(r'Solving for Ux, Initial residual = ([\d.e+-]+)', text)
    return {'steps': steps, 'p_solves': len(it), 'p_iterations_per_solve': float(np.mean(it)) if it else None,
            'p_iterations_max': max(it) if it else None, 'p_solves_at_1000': sum(1 for i in it if i >= 1000),
            'Ux_initial_residual_step1': float(ux[0]) if ux else None,
            'end': bool(re.search(r'^End\s*$', text, re.M)), 'fatal': 'FOAM FATAL' in text,
            'warnings': len(re.findall(r'--> FOAM Warning', text))}


runs = {}
for d in sorted((R/'runs').glob('*-*-*')):
    ver, dim, job = d.name.split('-')
    for c in sorted(p for p in d.iterdir() if p.is_dir()):
        t = c/'0.1005'
        entry = {'job': job, 'dir': str(c), 'exit': (c/'exit-status').read_text().strip() if (c/'exit-status').exists() else None,
                 'log': log_stats(c/'log.pimpleFoam') if (c/'log.pimpleFoam').exists() else None, 'wrote_0.1005': t.exists()}
        if t.exists():
            entry['U'] = read_internal(t/'U'); entry['p'] = read_internal(t/'p')
        runs[(ver, dim, c.name)] = entry

out = {'runs': {}, 'pimpleFoam_vs_PODFoam_frame': {}, 'of8_vs_v2212_same_variant': {}, 'cross': {}}
for k, e in runs.items():
    out['runs']['/'.join(k)] = {x: e[x] for x in ('job', 'dir', 'exit', 'log', 'wrote_0.1005')}
for (ver, dim, var), e in runs.items():
    if 'U' not in e or var != 'A':
        continue
    f = FRAMES[(ver, dim)]/'llm_observation/step-000100/fields.npz'
    with np.load(f) as z:
        U, p = e['U'], e['p']
        note = 'frame is the full mesh'
        if z['p'].size != p.size:
            # the 3D frame is the observer's plane slice: match its cell centres to the 3D cells (field C from
            # postProcess -func writeCellCentres, written by centres.sbatch in the v2212 A run)
            # the 3D frame is the observer's plane slice; the frame stores the cell indices (mesh_cells).
            # Check them against the cell centres written by centres.sbatch (job 25080389) in the v2212 A run.
            sel = z['mesh_cells']
            cfile = R/'runs/v2212-3d-25080024/A/0.1005/C'
            C = read_internal(cfile)
            centre_err = float(np.abs(C[sel] - z['centres']).max())
            U, p = U[sel], p[sel]
            note = f'frame is a slice of {sel.size} of {C.shape[0]} cells selected by mesh_cells; max |C[mesh_cells]-centres| = {centre_err:.3e} m using {cfile}'
        out['pimpleFoam_vs_PODFoam_frame'][f'{ver}/{dim}/A'] = dict(diff(U, p, z['U'], z['p']), frame=str(f), frame_time=float(z['time_s']), frame_step=int(z['step']), note=note)
for dim in ('2d', '3d'):
    for var in 'ABCDEF':
        a, b = runs.get(('8', dim, var)), runs.get(('v2212', dim, var))
        if a and b and 'U' in a and 'U' in b:
            out['of8_vs_v2212_same_variant'][f'{dim}/{var}'] = diff(a['U'], a['p'], b['U'], b['p'])
    # the key cross checks: 8 without relaxation against v2212 as is; v2212 with Final factors against 8 as is
    pairs = [('8', 'B', 'v2212', 'A'), ('v2212', 'C', '8', 'A'), ('8', 'E', 'v2212', 'A'), ('8', 'F', 'v2212', 'A'),
             ('8', 'B', '8', 'A'), ('v2212', 'C', 'v2212', 'A'), ('8', 'D', 'v2212', 'D'), ('v2212', 'B', 'v2212', 'A'), ('8', 'C', '8', 'A'),
             ('8', 'D', '8', 'B'), ('v2212', 'D', 'v2212', 'B')]
    for v1, x, v2, y in pairs:
        a, b = runs.get((v1, dim, x)), runs.get((v2, dim, y))
        if a and b and 'U' in a and 'U' in b:
            out['cross'][f'{dim}: {v1}/{x} vs {v2}/{y}'] = diff(a['U'], a['p'], b['U'], b['p'])
Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
for k, v in out['pimpleFoam_vs_PODFoam_frame'].items(): print('frame', k, {x: round(v[x], 6) for x in ('U_max', 'p_max')})
for k, v in out['of8_vs_v2212_same_variant'].items(): print('same-variant', k, {x: round(v[x], 4) for x in ('U_max', 'U_rms', 'U_peak', 'p_max', 'p_rms', 'p_range')})
for k, v in out['cross'].items(): print('cross', k, {x: round(v[x], 4) for x in ('U_max', 'U_rms', 'p_max', 'p_rms')})
for k, v in out['runs'].items(): print('run', k, v['exit'], v['log'] and {x: v['log'][x] for x in ('steps', 'p_iterations_per_solve', 'p_solves_at_1000', 'Ux_initial_residual_step1', 'warnings')})
