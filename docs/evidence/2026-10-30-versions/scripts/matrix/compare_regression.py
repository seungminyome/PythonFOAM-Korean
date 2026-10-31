#!/usr/bin/env python3
"""Upstream's and this fork's PODFoam on upstream's own case: the written fields, time by time."""
import hashlib, json, re, sys
from pathlib import Path
import numpy as np

out = Path(sys.argv[1])
a, b = out/'case-upstream', out/'case-fork'
number = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'


def values(path):
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', path.read_text(), flags=re.S)
    m = re.search(r'internalField\s+nonuniform\s+List<(scalar|vector)>\s+(\d+)\s*\((.*?)\)\s*;', text, re.S)
    if not m:
        return None
    return np.fromstring(m[3].replace('(', ' ').replace(')', ' '), sep=' ')


def times(case):
    found = []
    for p in case.iterdir():
        try:
            found.append((float(p.name), p.name))
        except ValueError:
            pass
    return [name for _, name in sorted(found) if name != '0']


report = {'exit': {c.name: (c/'exit-status').read_text().strip() if (c/'exit-status').exists() else None for c in (a, b)},
          'steps': {c.name: len(re.findall(r'^Courant Number mean', (c/'log.PODFoam').read_text(), re.M)) if (c/'log.PODFoam').exists() else None for c in (a, b)},
          'times': {c.name: times(c) if c.exists() else None for c in (a, b)}}
rows = []
if a.exists() and b.exists():
    for t in sorted(set(times(a)) & set(times(b)), key=float):
        row = {'time': t}
        for f in ('U', 'p', 'phi'):
            pa, pb = a/t/f, b/t/f
            if pa.exists() and pb.exists():
                same = hashlib.sha256(pa.read_bytes()).digest() == hashlib.sha256(pb.read_bytes()).digest()
                row[f] = {'identical_bytes': same}
                if not same:
                    va, vb = values(pa), values(pb)
                    if va is not None and vb is not None and va.size == vb.size:
                        d = np.abs(va - vb)
                        row[f].update(max_abs_diff=float(d.max()), max_abs_value=float(np.abs(va).max()))
        for f in sorted(p.name for p in (a/t).iterdir() if p.name.startswith(('upod_', 'vpod_', 'wpod_'))):
            pa, pb = a/t/f, b/t/f
            if pb.exists():
                va, vb = values(pa), values(pb)
                if va is not None and vb is not None and va.size == vb.size:
                    row.setdefault('pod', {})[f] = {'identical_bytes': pa.read_bytes() == pb.read_bytes(),
                                                     'abs_cosine': float(abs(va@vb)/max(np.linalg.norm(va)*np.linalg.norm(vb), 1e-300))}
        rows.append(row)
report['written_times'] = rows
print(json.dumps(report, indent=1))
(out/'regression.json').write_text(json.dumps(report, indent=1)+'\n')
