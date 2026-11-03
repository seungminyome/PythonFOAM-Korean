#!/usr/bin/env python3
"""Snapshot matrices saved by the recording and copy runs of one sibling solver.
For each matrix: first column equal to the second?  Across runs: columns from 1 identical, recording's
column 0 equal to copy's column 1 (the overwritten first snapshot equals the second)?"""
import hashlib, json, re, sys
from pathlib import Path
import numpy as np

out, solver, ver = Path(sys.argv[1]), sys.argv[2], sys.argv[3]


def matrices(npz):
    z = np.load(npz)
    if 's' in z:          # AEFoam: (snapshots, cells, 1)
        return {'s': z['s'][:, :, 0].T}
    return {k: z[k] for k in 'uvw'}


def run_info(name):
    c = out / f'case-{name}'
    log = c / f'log.{solver}'
    text = log.read_text(errors='replace') if log.exists() else ''
    info = {'exit': (c / 'exit-status').read_text().strip() if (c / 'exit-status').exists() else None,
            'steps': len(re.findall(r'^Courant Number mean', text, re.M)),
            'snapshot_files': sorted(p.name for p in c.glob('snapshots-*.npz')),
            'python_tracebacks': text.count('Traceback (most recent call last)'),
            'last_log_lines': [l.rstrip() for l in text.splitlines()[-6:]]}
    sig = re.findall(r'(Segmentation fault|signal \d+|Floating point exception|Fatal|Aborted|caught signal \d+|exited on signal \d+)', text)
    info['signals'] = sorted(set(sig))
    return info


report = {'solver': solver, 'version': ver, 'upstream': (out / 'UPSTREAM').read_text().strip(),
          'build': 'ok' if (out / 'bin' / solver).exists() else 'failed',
          'runs': {n: run_info(n) for n in ('recording', 'copy')}, 'snapshots': []}

rec_files = sorted((out / 'case-recording').glob('snapshots-*.npz'))
for pa in rec_files:
    pb = out / 'case-copy' / pa.name
    row = {'file': pa.name}
    ma = matrices(pa)
    mb = matrices(pb) if pb.exists() else None
    for k, a in ma.items():
        r = {'shape_recording': list(a.shape),
             'recording_col0_equals_col1': a.shape[1] > 1 and bool(np.array_equal(a[:, 0], a[:, 1])),
             'recording_col0_minus_col1_max': float(np.abs(a[:, 0] - a[:, 1]).max()) if a.shape[1] > 1 else None}
        if mb is not None:
            b = mb[k]
            r.update({'shape_copy': list(b.shape),
                      'copy_col0_equals_col1': b.shape[1] > 1 and bool(np.array_equal(b[:, 0], b[:, 1])),
                      'copy_col0_minus_col1_max': float(np.abs(b[:, 0] - b[:, 1]).max()) if b.shape[1] > 1 else None,
                      'recording_col0_equals_copy_col1': b.shape[1] > 1 and a.shape == b.shape and bool(np.array_equal(a[:, 0], b[:, 1])),
                      'columns_from_1_identical': a.shape == b.shape and bool(np.array_equal(a[:, 1:], b[:, 1:])),
                      'col0_differs_between_runs': a.shape == b.shape and not bool(np.array_equal(a[:, 0], b[:, 0]))})
        row[k] = r
    report['snapshots'].append(row)

# written flow fields: the two runs solve the same flow, so U/p should match byte for byte
def times(case):
    found = []
    for p in case.iterdir():
        try:
            found.append((float(p.name), p.name))
        except ValueError:
            pass
    return [n for _, n in sorted(found) if n != '0']

ca, cb = out / 'case-recording', out / 'case-copy'
if solver == 'APMOSFoam':
    ca, cb = ca / 'processor0', cb / 'processor0'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
fields = []
if ca.exists() and cb.exists():
    for t in sorted(set(times(ca)) & set(times(cb)), key=float):
        row = {'time': t}
        for f in ('U', 'p'):
            if (ca / t / f).exists() and (cb / t / f).exists():
                row[f + '_identical_bytes'] = sha(ca / t / f) == sha(cb / t / f)
        row['pod_or_rec_files'] = sorted(p.name for p in (ca / t).iterdir() if re.fullmatch(r'[uvw]pod_\d|urec_', p.name))
        fields.append(row)
report['written_fields_recording_vs_copy'] = fields

(out / 'result.json').write_text(json.dumps(report, indent=1))
print(json.dumps(report, indent=1))
