#!/usr/bin/env python3
"""A r4 3D slice run (z3) against r2/slice-3d phase 1 (job 25080032, bf7a06e, v2212): per frame step, the arrays of
fields.npz (U, p, centres, mesh_cells, polygons) equal or not, max |dU| and |dp|, and the sha256 of the PNGs and of fields.npz.
Usage: compare_slice.py RUN_DIR"""
import hashlib, json, sys
from pathlib import Path
import numpy as np
run = Path(sys.argv[1]) / 'z3'
ref = Path('/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/slice-3d/phase1-25080032/z3')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rows = []
for d in sorted((run / 'llm_observation').glob('step-*')):
    r = ref / 'llm_observation' / d.name
    row = {'frame': d.name, 'files': sorted(p.name for p in d.iterdir())}
    with np.load(d / 'fields.npz') as a:
        row['cells'] = int(a['U'].shape[0])
        if r.exists():
            with np.load(r / 'fields.npz') as b:
                row['arrays_equal'] = {k: bool(np.array_equal(a[k], b[k])) for k in a.files if k in b.files}
                row['max_abs_dU'] = float(np.abs(a['U'] - b['U']).max()) if a['U'].shape == b['U'].shape else None
                row['max_abs_dp'] = float(np.abs(a['p'] - b['p']).max()) if a['p'].shape == b['p'].shape else None
            row['png_sha_equal'] = {f: sha(d / f) == sha(r / f) for f in ('U.png', 'p.png') if (d / f).exists() and (r / f).exists()}
            row['fields_npz_sha_equal'] = sha(d / 'fields.npz') == sha(r / 'fields.npz')
    rows.append(row)
log = (run / 'log.PODFoam').read_text(errors='replace')
summary = {'frames': len(rows), 'cut_cells_line': [l for l in log.splitlines() if 'cut cells=' in l],
           'reference_cut_cells_line': [l for l in (ref / 'log.PODFoam').read_text(errors='replace').splitlines() if 'cut cells=' in l],
           'all_arrays_equal_to_reference': all(all(r.get('arrays_equal', {}).values()) and r.get('arrays_equal') for r in rows),
           'rows': rows}
print(json.dumps(summary, indent=1))
