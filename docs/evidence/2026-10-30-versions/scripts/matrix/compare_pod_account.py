#!/usr/bin/env python3
"""What differs between upstream's PODFoam and this fork's, and whether each difference is accounted for.
Fields and POD modes at every written time, and the snapshot matrices each module held at each SVD."""
import hashlib, json, re, sys
from pathlib import Path
import numpy as np

out = Path(sys.argv[1]); ver = sys.argv[2]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
CASES = [c for c in ('upstream', 'fork', 'fork-overwrite', 'fork-plainp') if (out/f'case-{c}').exists()]


def values(path):
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', path.read_text(), flags=re.S)
    m = re.search(r'internalField\s+nonuniform\s+List<(scalar|vector)>\s+(\d+)\s*\((.*?)\)\s*;', text, re.S)
    return np.fromstring(m[3].replace('(', ' ').replace(')', ' '), sep=' ') if m else None


def times(case):
    found = []
    for p in case.iterdir():
        try:
            found.append((float(p.name), p.name))
        except ValueError:
            pass
    return [n for _, n in sorted(found) if n != '0']


def compare(a, b):
    a, b = out/f'case-{a}', out/f'case-{b}'
    rows = []
    for t in sorted(set(times(a)) & set(times(b)), key=float):
        row = {'time': t}
        for f in ('U', 'p', 'phi'):
            pa, pb = a/t/f, b/t/f
            same = sha(pa) == sha(pb)
            row[f] = {'identical_bytes': same}
            if not same:
                va, vb = values(pa), values(pb)
                if va is not None and vb is not None and va.size == vb.size:
                    row[f].update(max_abs_diff=float(np.abs(va-vb).max()), max_abs_value=float(np.abs(va).max()))
        modes = sorted(p.name for p in (a/t).iterdir() if re.fullmatch(r'[uvw]pod_\d', p.name))
        pod = {}
        for f in modes:
            va, vb = values(a/t/f), values(b/t/f)
            pod[f] = {'values_identical': bool(np.array_equal(va, vb)), 'max_abs_diff': float(np.abs(va-vb).max()),
                      'abs_cosine': float(abs(va@vb)/max(np.linalg.norm(va)*np.linalg.norm(vb), 1e-300))}
        row['pod_modes'] = len(pod)
        row['pod_values_identical'] = sum(v['values_identical'] for v in pod.values())
        row['pod_max_abs_diff'] = max((v['max_abs_diff'] for v in pod.values()), default=None)
        row['pod_min_abs_cosine'] = min((v['abs_cosine'] for v in pod.values()), default=None)
        rows.append(row)
    return rows


def snapshots(a, b):
    """The snapshot matrices: upstream's first column against its second, the other columns against the fork's."""
    rows = []
    for pa in sorted((out/f'case-{a}').glob('snapshots-*.npz')):
        pb = out/f'case-{b}'/pa.name
        if not pb.exists():
            continue
        za, zb = np.load(pa), np.load(pb)
        row = {'svd': pa.name}
        for k in 'uvw':
            ma, mb = za[k], zb[k]
            row[k] = {'shape_upstream': list(ma.shape), 'shape_fork': list(mb.shape),
                      'upstream_col0_equals_col1': ma.shape[1] > 1 and bool(np.array_equal(ma[:, 0], ma[:, 1])),
                      'fork_col0_equals_col1': mb.shape[1] > 1 and bool(np.array_equal(mb[:, 0], mb[:, 1])),
                      'upstream_col0_equals_fork_col1': mb.shape[1] > 1 and bool(np.array_equal(ma[:, 0], mb[:, 1])),
                      'columns_from_1_identical': ma.shape == mb.shape and bool(np.array_equal(ma[:, 1:], mb[:, 1:])),
                      'fork_col0_minus_col1_max': float(np.abs(mb[:, 0]-mb[:, 1]).max()) if mb.shape[1] > 1 else None}
        rows.append(row)
    return rows


report = {'version': ver, 'HEAD': (out/'HEAD').read_text().strip(), 'upstream': (out/'UPSTREAM').read_text().strip(),
          'git_status': (out/'git-status.txt').read_text().strip(),
          'runs': {c: {'exit': (out/f'case-{c}/exit-status').read_text().strip(),
                       'steps': len(re.findall(r'^Courant Number mean', (out/f'case-{c}/log.PODFoam').read_text(errors='replace'), re.M)),
                       'written': times(out/f'case-{c}')} for c in CASES}}
for c in CASES:
    if c != 'upstream':
        report[f'upstream_vs_{c}'] = compare('upstream', c)
if (out/'case-fork').exists():
    report['snapshots_upstream_vs_fork'] = snapshots('upstream', 'fork')
print(json.dumps(report, indent=1))
(out/'account.json').write_text(json.dumps(report, indent=1)+'\n')
for c in CASES:
    for p in (out/f'case-{c}').glob('snapshots-*.npz'):
        p.unlink()
