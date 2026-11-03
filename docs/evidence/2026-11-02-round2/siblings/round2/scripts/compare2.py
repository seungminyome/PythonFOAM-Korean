#!/usr/bin/env python3
"""Per stage (recording, copy, ported): exit, steps, snapshot files, per matrix col0==col1.
Across stages: recording col0 == copy col1 (overwritten first snapshot equals the second);
ported matrices == copy matrices (owning C++ array gives the same snapshots as the Python-side copy)."""
import hashlib, json, re, sys
from pathlib import Path
import numpy as np

out, solver, ver = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
STAGES = ('recording', 'copy', 'ported')


def matrices(npz):
    z = np.load(npz)
    if 's' in z:
        return {'s': z['s'][:, :, 0].T}
    return {k: z[k] for k in 'uvw'}


def run_info(name):
    c = out / f'case-{name}'
    if not c.exists():
        return None
    log = c / f'log.{solver}'
    text = log.read_text(errors='replace') if log.exists() else ''
    info = {'exit': (c / 'exit-status').read_text().strip() if (c / 'exit-status').exists() else None,
            'steps': len(re.findall(r'^Courant Number mean', text, re.M)),
            'snapshot_files': sorted(p.name for p in c.glob('snapshots-*.npz')),
            'python_tracebacks': text.count('Traceback (most recent call last)'),
            'python_print_lines': len(re.findall(r'Collecting snapshots iteration', text)),
            'last_log_lines': [l.rstrip()[:200] for l in text.splitlines()[-5:]]}
    mats = {}
    for pa in sorted(c.glob('snapshots-*.npz')):
        for k, a in matrices(pa).items():
            mats[f'{pa.name}:{k}'] = {'shape': list(a.shape),
                                     'col0_equals_col1': a.shape[1] > 1 and bool(np.array_equal(a[:, 0], a[:, 1])),
                                     'col0_minus_col1_max': float(np.abs(a[:, 0] - a[:, 1]).max()) if a.shape[1] > 1 else None}
    info['matrices'] = mats
    info['n_matrices'] = len(mats)
    info['n_col0_equals_col1'] = sum(m['col0_equals_col1'] for m in mats.values())
    return info


report = {'solver': solver, 'version': ver, 'upstream': (out / 'UPSTREAM').read_text().strip(),
          'builds': {n: (out / f'bin-{n}' / solver).exists() for n in ('upstream', 'ported') if (out / f'log.build-{n}').exists()},
          'runs': {n: run_info(n) for n in STAGES if run_info(n) is not None}, 'cross': {}}


def load_all(name):
    c = out / f'case-{name}'
    return {f'{pa.name}:{k}': a for pa in sorted(c.glob('snapshots-*.npz')) for k, a in matrices(pa).items()}

have = {n: load_all(n) for n in STAGES if (out / f'case-{n}').exists()}
if 'recording' in have and 'copy' in have:
    r, c = have['recording'], have['copy']
    keys = sorted(set(r) & set(c))
    report['cross']['recording_col0_equals_copy_col1'] = {k: bool(r[k].shape == c[k].shape and np.array_equal(r[k][:, 0], c[k][:, 1])) for k in keys}
    report['cross']['recording_vs_copy_columns_from_1_identical'] = {k: bool(r[k].shape == c[k].shape and np.array_equal(r[k][:, 1:], c[k][:, 1:])) for k in keys}
if 'ported' in have and 'copy' in have:
    p, c = have['ported'], have['copy']
    keys = sorted(set(p) & set(c))
    report['cross']['ported_equals_copy_whole_matrix'] = {k: bool(p[k].shape == c[k].shape and np.array_equal(p[k], c[k])) for k in keys}
if 'ported' in have and 'recording' in have:
    p, r = have['ported'], have['recording']
    keys = sorted(set(p) & set(r))
    report['cross']['ported_vs_recording_columns_from_1_identical'] = {k: bool(p[k].shape == r[k].shape and np.array_equal(p[k][:, 1:], r[k][:, 1:])) for k in keys}


def times(case):
    found = []
    for q in case.iterdir():
        try:
            found.append((float(q.name), q.name))
        except ValueError:
            pass
    return [n for _, n in sorted(found) if n != '0']

sha = lambda q: hashlib.sha256(q.read_bytes()).hexdigest()
fields = {}
names = [n for n in STAGES if (out / f'case-{n}').exists()]
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        ca, cb = out / f'case-{names[i]}', out / f'case-{names[j]}'
        if solver == 'APMOSFoam':
            ca, cb = ca / 'processor0', cb / 'processor0'
        rows = []
        if ca.exists() and cb.exists():
            for t in sorted(set(times(ca)) & set(times(cb)), key=float):
                row = {'time': t}
                for f in ('U', 'p'):
                    if (ca / t / f).exists() and (cb / t / f).exists():
                        row[f + '_identical_bytes'] = sha(ca / t / f) == sha(cb / t / f)
                rows.append(row)
        fields[f'{names[i]}_vs_{names[j]}'] = rows
report['written_fields'] = fields
(out / 'result.json').write_text(json.dumps(report, indent=1))
# short view
print(json.dumps({k: v for k, v in report.items() if k != 'runs'}, indent=1))
for n, info in report['runs'].items():
    print(n, 'exit', info['exit'], 'steps', info['steps'], 'matrices', info['n_matrices'], 'col0==col1 in', info['n_col0_equals_col1'],
          'py_prints', info['python_print_lines'], 'tracebacks', info['python_tracebacks'])
