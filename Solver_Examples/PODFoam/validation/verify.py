"""Checks for one validation run; prints a JSON report ending in "status": "PASS"."""
from pathlib import Path
import json
import re
import sys
import numpy as np

NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'
CELLS = 20540


def check(condition, *context):
    """Stop with the context on a failed check (a plain assert is skipped under python -O)."""
    if not condition:
        sys.exit('FAIL: ' + ' '.join(str(c) for c in context))


def field(path, cells=CELLS):
    text = path.read_text()
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    check(not re.search(r'(?i)(?<![\w])[-+]?(?:nan|inf(?:inity)?)(?![\w])', text), 'nan or inf in', path)
    check(np.isfinite(np.array(re.findall(NUMBER, text), dtype=float)).all(), 'non-finite number in', path)
    match = re.search(r'internalField\s+nonuniform\s+List<(scalar|vector)>\s+(\d+)\s*\((.*?)\)\s*;', text, re.S)
    if match:
        components = 3 if match[1] == 'vector' else 1
        values = np.fromstring(match[3].replace('(', ' ').replace(')', ' '), sep=' ')
        check(values.size == int(match[2]) * components, 'field size', path)
        return values.reshape(int(match[2]), components)
    match = re.search(r'internalField\s+uniform\s+(.*?);', text, re.S)
    check(match, 'no internalField in', path)
    values = np.fromstring(match[1].replace('(', ' ').replace(')', ' '), sep=' ')
    check(values.size in (1, 3), 'uniform value size', path)
    return np.tile(values, (cells, 1))


def main(root):
    report = {}
    all_u = {}
    all_p = {}
    for name, logfile in [('fixed-pimple', 'log.pimpleFoam'), ('fixed-pod', 'log.PODFoam')]:
        case = root / name
        log = (case / logfile).read_text()
        times = re.findall(r'^Time = ([^\s]+)', log, re.M)
        check(len(times) == 10, name, 'Time entries', times)
        np.testing.assert_allclose(np.array(times, dtype=float), np.arange(1, 11)*1e-7, rtol=1e-12, atol=0)
        check(re.search(r'^End\s*$', log, re.M) and 'FOAM FATAL' not in log, name, 'did not end normally')
        check(not re.search(r'(?i)\b(?:nan|inf)\b', log), name, 'nan or inf in the log')
        residuals = np.array(re.findall(r'(?:Initial|Final) residual = ([^,\s]+)', log), dtype=float)
        check(residuals.size >= 80 and np.isfinite(residuals).all(), name, 'residuals', residuals.size)
        check('No Iterations 1000' not in log, name, 'a linear solve hit the iteration cap')
        courant = np.array(re.findall(r'Courant Number mean: \S+ max: (\S+)', log), dtype=float)
        check(np.isfinite(courant).all() and courant.max() < 1, name, 'Courant', courant)
        count, max_u, max_p = 0, 0., 0.
        all_u[name] = []
        all_p[name] = []
        for t in times:
            folder = case / t
            check(folder.is_dir(), 'missing time folder', folder)
            u, p = field(folder/'U'), field(folder/'p')
            all_u[name].append(u)
            all_p[name].append(p)
            max_u = max(max_u, float(np.abs(u).max()))
            max_p = max(max_p, float(np.abs(p).max()))
            for path in folder.iterdir():
                if path.is_file() and re.search(r'class\s+(?:vol|surface)\w+Field;', path.read_text()):
                    field(path)
                    count += 1
        check(max_u < 1000, name, 'max |U|', max_u)
        report[name] = dict(steps=len(times), residual_values=int(residuals.size),
                            checked_field_files=count, max_Co=float(courant.max()),
                            max_abs_U=max_u, max_abs_p=max_p, finite=True, normal_exit=True)

    pod = root/'fixed-pod'
    log = (pod/'log.PODFoam').read_text()
    check(len(re.findall(r'^POD snapshot accepted:', log, re.M)) == 10, 'POD snapshot accepted lines')
    check('POD SVD returned to OpenFOAM: rows=61620 modes=5 finite=true' in log, 'POD SVD returned line')
    check('Python finalized successfully' in log, 'Python finalized line')
    check(len(re.findall(r'deltaT = 1e-07', log)) == 10, 'deltaT lines')
    with np.load(pod/'python_svd_audit.npz') as audit:
        snapshots, modes, singular = (audit[k] for k in ('snapshots', 'modes', 'singular_values'))
        check(snapshots.shape == (CELLS, 3, 10) and modes.shape == (3*CELLS, 5), 'audit shapes', snapshots.shape, modes.shape)
        check(np.isfinite(snapshots).all() and np.isfinite(modes).all() and np.isfinite(singular).all(), 'audit finite')
        max_snapshot_error = 0.
        for i, u in enumerate(all_u['fixed-pod']):
            np.testing.assert_allclose(snapshots[:, :, i], u, rtol=1e-10, atol=1e-9)
            max_snapshot_error = max(max_snapshot_error, float(np.max(np.abs(snapshots[:, :, i]-u))))
        max_mode_error = 0.
        for c, prefix in enumerate(('upod_', 'vpod_', 'wpod_')):
            q = modes[c*CELLS:(c+1)*CELLS]
            np.testing.assert_allclose(q.T@q, np.eye(5), rtol=1e-10, atol=1e-10)
            a = snapshots[:, c, :]
            # Check singular values and the returned left singular subspace independently.
            expected_s = np.linalg.svd(a, compute_uv=False)
            np.testing.assert_allclose(singular[c], expected_s, rtol=1e-9, atol=1e-10)
            scale = max(float(singular[c, 0]**2), 1.)
            check(np.linalg.norm(a@(a.T@q) - q*singular[c, :5]**2)/scale < 1e-9, 'eigen-equation', prefix)
            for m in range(5):
                returned = field(pod/'1e-06'/f'{prefix}{m}')[:, 0]
                np.testing.assert_allclose(returned, q[:, m], rtol=1e-10, atol=1e-11)
                max_mode_error = max(max_mode_error, float(np.max(np.abs(returned-q[:, m]))))
        report['bridge'] = dict(snapshots=10, svd_shape=list(modes.shape), returned_field_files=15,
                                max_snapshot_error=max_snapshot_error, max_mode_error=max_mode_error,
                                singular_values=singular.tolist(), python_finalized=True)
    # With the same pressure-solver selection, both solvers give the same solution.
    for reference, actual in zip(all_u['fixed-pimple'], all_u['fixed-pod']):
        np.testing.assert_allclose(actual, reference, rtol=1e-10, atol=1e-9)
    for reference, actual in zip(all_p['fixed-pimple'], all_p['fixed-pod']):
        np.testing.assert_allclose(actual, reference, rtol=1e-10, atol=1e-9)
    report['pimple_POD_velocity_agreement'] = True
    report['pimple_POD_pressure_agreement'] = True
    report['status'] = 'PASS'
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(f'usage: {sys.argv[0]} RUN_DIRECTORY')
    main(Path(sys.argv[1]))
