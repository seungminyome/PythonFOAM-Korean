"""Checks for one validation run; prints a JSON report ending in "status": "PASS"."""
from pathlib import Path
import json
import re
import sys
import numpy as np

if len(sys.argv) != 2:
    sys.exit(f'usage: {sys.argv[0]} RUN_DIRECTORY')
root = Path(sys.argv[1])
number = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'


def field(path, cells=20540):
    text = path.read_text()
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    assert not re.search(r'(?i)(?<![\w])[-+]?(?:nan|inf(?:inity)?)(?![\w])', text), path
    assert np.isfinite(np.array(re.findall(number, text), dtype=float)).all(), path
    match = re.search(r'internalField\s+nonuniform\s+List<(scalar|vector)>\s+(\d+)\s*\((.*?)\)\s*;', text, re.S)
    if match:
        components = 3 if match[1] == 'vector' else 1
        values = np.fromstring(match[3].replace('(', ' ').replace(')', ' '), sep=' ')
        assert values.size == int(match[2]) * components, path
        return values.reshape(int(match[2]), components)
    match = re.search(r'internalField\s+uniform\s+(.*?);', text, re.S)
    assert match, path
    values = np.fromstring(match[1].replace('(', ' ').replace(')', ' '), sep=' ')
    assert values.size in (1, 3), path
    return np.tile(values, (cells, 1))


report = {}
all_u = {}
all_p = {}
for name, logfile in [('fixed-pimple', 'log.pimpleFoam'), ('fixed-pod', 'log.PODFoam')]:
    case = root / name
    log = (case / logfile).read_text()
    times = re.findall(r'^Time = ([^\s]+)', log, re.M)
    assert len(times) == 10, (name, times)
    np.testing.assert_allclose(np.array(times, dtype=float), np.arange(1, 11)*1e-7, rtol=1e-12, atol=0)
    assert re.search(r'^End\s*$', log, re.M) and 'FOAM FATAL' not in log, name
    assert not re.search(r'(?i)\b(?:nan|inf)\b', log), name
    residuals = np.array(re.findall(r'(?:Initial|Final) residual = ([^,\s]+)', log), dtype=float)
    assert residuals.size >= 80 and np.isfinite(residuals).all(), name
    assert 'No Iterations 1000' not in log, name
    courant = np.array(re.findall(r'Courant Number mean: \S+ max: (\S+)', log), dtype=float)
    assert np.isfinite(courant).all() and courant.max() < 1, (name, courant)
    count, max_u, max_p = 0, 0., 0.
    all_u[name] = []
    all_p[name] = []
    for t in times:
        folder = case / t
        assert folder.is_dir(), folder
        u, p = field(folder/'U'), field(folder/'p')
        all_u[name].append(u)
        all_p[name].append(p)
        max_u = max(max_u, float(np.abs(u).max()))
        max_p = max(max_p, float(np.abs(p).max()))
        for path in folder.iterdir():
            if path.is_file() and re.search(r'class\s+(?:vol|surface)\w+Field;', path.read_text()):
                field(path)
                count += 1
    assert max_u < 1000, (name, max_u)
    report[name] = dict(steps=len(times), residual_values=int(residuals.size),
                       checked_field_files=count, max_Co=float(courant.max()),
                       max_abs_U=max_u, max_abs_p=max_p, finite=True, normal_exit=True)

pod = root/'fixed-pod'
log = (pod/'log.PODFoam').read_text()
assert len(re.findall(r'^POD snapshot accepted:', log, re.M)) == 10
assert 'POD SVD returned to OpenFOAM: rows=61620 modes=5 finite=true' in log
assert 'Python finalized successfully' in log
assert len(re.findall(r'deltaT = 1e-07', log)) == 10
with np.load(pod/'python_svd_audit.npz') as audit:
    snapshots, modes, singular = (audit[k] for k in ('snapshots', 'modes', 'singular_values'))
    assert snapshots.shape == (20540, 3, 10) and modes.shape == (61620, 5)
    assert np.isfinite(snapshots).all() and np.isfinite(modes).all() and np.isfinite(singular).all()
    max_snapshot_error = 0.
    for i, u in enumerate(all_u['fixed-pod']):
        np.testing.assert_allclose(snapshots[:, :, i], u, rtol=1e-10, atol=1e-9)
        max_snapshot_error = max(max_snapshot_error, float(np.max(np.abs(snapshots[:, :, i]-u))))
    max_mode_error = 0.
    for c, prefix in enumerate(('upod_', 'vpod_', 'wpod_')):
        q = modes[c*20540:(c+1)*20540]
        np.testing.assert_allclose(q.T@q, np.eye(5), rtol=1e-10, atol=1e-10)
        a = snapshots[:, c, :]
        # Check singular values and the returned left singular subspace independently.
        expected_s = np.linalg.svd(a, compute_uv=False)
        np.testing.assert_allclose(singular[c], expected_s, rtol=1e-9, atol=1e-10)
        scale = max(float(singular[c, 0]**2), 1.)
        assert np.linalg.norm(a@(a.T@q) - q*singular[c, :5]**2)/scale < 1e-9
        for m in range(5):
            returned = field(pod/'1e-06'/f'{prefix}{m}')[:, 0]
            np.testing.assert_allclose(returned, q[:, m], rtol=1e-10, atol=1e-11)
            max_mode_error = max(max_mode_error, float(np.max(np.abs(returned-q[:, m]))))
    report['bridge'] = dict(snapshots=10, svd_shape=list(modes.shape), returned_field_files=15,
                            max_snapshot_error=max_snapshot_error, max_mode_error=max_mode_error,
                            singular_values=singular.tolist(), python_finalized=True)
# with the pFinal fix both solvers give the same solution
for reference, actual in zip(all_u['fixed-pimple'], all_u['fixed-pod']):
    np.testing.assert_allclose(actual, reference, rtol=1e-10, atol=1e-9)
for reference, actual in zip(all_p['fixed-pimple'], all_p['fixed-pod']):
    np.testing.assert_allclose(actual, reference, rtol=1e-10, atol=1e-9)
report['pimple_POD_velocity_agreement'] = True
report['pimple_POD_pressure_agreement'] = True
report['status'] = 'PASS'
print(json.dumps(report, indent=2))
