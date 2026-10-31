#!/usr/bin/env python3
"""One table over the version-check runs: did each OpenFOAM version build, validate and run the observer,
and how far do its fields lie from v2212's on the same start state.

    compare_versions.py OUT.json RUN_DIR [RUN_DIR ...]      each RUN_DIR is matrix-runs/<version>-<job>
"""
import hashlib, json, re, sys
from pathlib import Path
import numpy as np

CASES = ('serial2d', 'serial3d', 'par2d', 'par3d')
# The serial frames of the 2026-10-27 MPI test and the 2026-10-28 slice test, v2212.
REFERENCES = {'serial2d': Path('/cluster/medbow/gscratch/syome/github_repos/pod-mpi-20261027/run-24903786/serial'),
              'serial3d': Path('/cluster/medbow/gscratch/syome/github_repos/pod-3d-20261028/run-24929629/serial3d')}
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def frame_of(case):
    return case/'llm_observation/step-000100'


def load_frame(case):
    path = frame_of(case)/'fields.npz'
    if not path.exists():
        return None
    with np.load(path) as z:
        return {k: z[k] for k in z.files}


def by_position(frame):
    """Cells in a fixed order, because a parallel run gathers them rank by rank."""
    order = np.lexsort(np.round(frame['centres'], 9).T[::-1])
    return frame['centres'][order], frame['U'][order], frame['p'][order]


def difference(a, b):
    """Largest and mean-square-root differences of U and p between two frames of one mesh."""
    if a is None or b is None or a['p'].size != b['p'].size:
        return None
    ca, ua, pa = by_position(a)
    cb, ub, pb = by_position(b)
    d_u = np.linalg.norm(ua - ub, axis=1)
    d_p = np.abs((pa - pa.mean()) - (pb - pb.mean()))
    return {'cells': int(pa.size),
            'centres_max_m': float(np.abs(ca - cb).max()),
            'U_max': float(d_u.max()), 'U_rms': float(np.sqrt((d_u**2).mean())),
            'U_peak': float(np.linalg.norm(ua, axis=1).max()),
            'p_max': float(d_p.max()), 'p_rms': float(np.sqrt((d_p**2).mean())),
            'p_range': float(pa.max() - pa.min())}


def case_summary(case):
    log = case/'log.PODFoam'
    if not log.exists():
        return None
    text = log.read_text(errors='replace')
    telemetry = case/'telemetry.jsonl'
    lines = [json.loads(l) for l in telemetry.read_text().splitlines()] if telemetry.exists() else []
    keys = sorted(lines[-1]['residuals']) if lines else []
    iterations = [int(m) for m in re.findall(r'Solving for p,.*No Iterations (\d+)', text)]
    pde = [float(m) for m in re.findall(r'PDE Compute wall time: ([\d.]+) ms', text)]
    result = json.loads((case/'llm_result.json').read_text()) if (case/'llm_result.json').exists() else {}
    errors = case/'llm_errors.jsonl'
    return {'exit': (case/'exit-status').read_text().strip() if (case/'exit-status').exists() else None,
            'end': bool(re.search(r'^End\s*$', text, re.M)),
            'python_finalized': 'Python finalized successfully' in text,
            'fatal': 'FOAM FATAL' in text,
            'frame': sorted(p.name for p in frame_of(case).iterdir()) if frame_of(case).exists() else [],
            'telemetry_lines': len(lines),
            'telemetry_tmp_left': (case/'telemetry.jsonl.tmp').exists(),
            'residual_keys': keys,
            'mesh_cells': lines[-1]['cells'] if lines else None,
            'callback_errors': len(errors.read_text().splitlines()) if errors.exists() else 0,
            'result_status': result.get('status'),
            'request_step': result.get('request_step'),
            'pde_ms_per_step': float(np.mean(pde)) if pde else None,
            'p_iterations_per_solve': float(np.mean(iterations)) if iterations else None,
            'courant_max_last': lines[-1]['courant']['max'] if lines else None}


def run_summary(run):
    validation = run/'validation.log'
    text = validation.read_text(errors='replace') if validation.exists() else ''
    out = {'dir': str(run),
           'HEAD': (run/'HEAD').read_text().strip() if (run/'HEAD').exists() else None,
           'git_status': (run/'git-status.txt').read_text().strip() if (run/'git-status.txt').exists() else None,
           'image_sha256': (run/'image-sha256.txt').read_text().split()[0] if (run/'image-sha256.txt').exists() else None,
           'node': (run/'node.txt').read_text().strip() if (run/'node.txt').exists() else None,
           'validation_pass': bool(re.search(r'^PASS', text, re.M)),
           'cases': {c: case_summary(run/c) for c in CASES}}
    return out


def main():
    target = Path(sys.argv[1])
    runs = [Path(p) for p in sys.argv[2:]]
    versions = {r.name.rsplit('-', 1)[0]: r for r in runs}
    report = {'versions': {v: run_summary(r) for v, r in versions.items()}}
    frames = {v: {c: load_frame(r/c) for c in CASES} for v, r in versions.items()}
    base = frames.get('v2212', {})
    for v in versions:
        s = report['versions'][v]
        s['serial_vs_parallel'] = {'2d': difference(frames[v]['serial2d'], frames[v]['par2d']),
                                   '3d': difference(frames[v]['serial3d'], frames[v]['par3d'])}
        s['against_v2212'] = {c: difference(base.get(c), frames[v][c]) for c in CASES} if v != 'v2212' else None
    if 'v2212' in versions:
        checks = {}
        for name, ref in REFERENCES.items():
            frame, rframe = frame_of(versions['v2212']/name), frame_of(ref)
            if not frame.exists() or not rframe.exists():
                continue
            files = {}
            for f in ('U.png', 'p.png', 'fields.npz'):
                files[f] = sha(frame/f) == sha(rframe/f)
            a, b = load_frame(versions['v2212']/name), load_frame(ref)
            checks[name] = {'bytes_identical': files,
                            'arrays_identical': all(np.array_equal(a[k], b[k]) for k in a) if a and b and set(a) == set(b) else False,
                            'telemetry_lines_differ_only_in_run_id': telemetry_same(versions['v2212']/name, ref)}
        report['v2212_against_earlier_frames'] = checks
    target.write_text(json.dumps(report, indent=1)+'\n')
    table(report)


def telemetry_same(a, b):
    def rows(case):
        out = []
        for line in (case/'telemetry.jsonl').read_text().splitlines():
            row = json.loads(line)
            row.pop('run_id', None)
            out.append(row)
        return out
    try:
        return rows(a) == rows(b)
    except OSError:
        return None


def table(report):
    print('| Version | Validation | ' + ' | '.join(CASES) + ' |')
    print('|---|---|' + '---|'*len(CASES))
    for v, s in report['versions'].items():
        cells = []
        for c in CASES:
            x = s['cases'][c]
            if x is None:
                cells.append('not run')
                continue
            ok = x['exit'] == '0' and x['end'] and x['frame'] and x['telemetry_lines'] == 110 and not x['callback_errors'] and not x['telemetry_tmp_left']
            cells.append(f"{'ok' if ok else 'PROBLEM'} {'/'.join(x['residual_keys'])} {x['pde_ms_per_step']:.0f} ms/step, p {x['p_iterations_per_solve']:.0f} it")
        print(f"| {v} | {'PASS' if s['validation_pass'] else 'no'} | " + ' | '.join(cells) + ' |')
    for v, s in report['versions'].items():
        print('\n', v, 'HEAD', (s['HEAD'] or '')[:7], 'node', s['node'], 'dirty' if s['git_status'] else 'clean')
        for k, d in s['serial_vs_parallel'].items():
            if d:
                print(f"  serial vs 2 ranks {k}: cells {d['cells']} max |dU| {d['U_max']:.3g} of peak {d['U_peak']:.3g} m/s, rms {d['U_rms']:.3g}; max |dp| {d['p_max']:.3g} of range {d['p_range']:.3g}, rms {d['p_rms']:.3g}")
        if s['against_v2212']:
            for c, d in s['against_v2212'].items():
                if d:
                    print(f"  against v2212 {c}: max |dU| {d['U_max']:.3g} of peak {d['U_peak']:.3g} m/s, rms {d['U_rms']:.3g}; max |dp| {d['p_max']:.3g} of range {d['p_range']:.3g}, rms {d['p_rms']:.3g}; centres {d['centres_max_m']:.2g} m")
    if 'v2212_against_earlier_frames' in report:
        print('\nv2212 against earlier frames:', json.dumps(report['v2212_against_earlier_frames']))


if __name__ == '__main__':
    main()
