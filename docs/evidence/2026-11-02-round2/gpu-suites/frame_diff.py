"""Frames of the r2 suites against job 24950817 (v2212) at steps 250, 500, 750, async-no-llm, with
compare_versions.difference (cells ordered by position; p after removing each frame's mean)."""
import json, sys
from pathlib import Path
sys.path.insert(0, '/cluster/medbow/gscratch/syome/github_repos/PythonFOAM/docs/evidence/2026-10-30-versions/scripts/matrix')
import numpy as np
from compare_versions import difference
R = Path('/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/gpu-suites')
BASE = Path('/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/pr/refix/gpu-b/pod-async-v2/run-24950817/pod-llm-async.tnX3LI/async-no-llm/llm_observation')
def load(p):
    with np.load(p/'fields.npz') as z: return {k: z[k] for k in z.files}
out = {}
for job, ver in (('25080035', 'v2012'), ('25080036', '8')):
    demo = sorted((R/'pod-async-v2'/f'run-{job}').glob('pod-llm-async.*'))[-1]
    out[f'{ver}-{job}'] = {}
    for step in (250, 500, 750):
        a = load(demo/'async-no-llm/llm_observation'/f'step-{step:06d}'); b = load(BASE/f'step-{step:06d}')
        d = difference(a, b)
        d['step'] = step
        out[f'{ver}-{job}'][str(step)] = d
(R/'records'/'frame-diff-vs-24950817.json').write_text(json.dumps(out, indent=2)+'\n')
for k, v in out.items():
    for s, d in v.items():
        print(f"{k} step {s}: cells {d['cells']} centres_max {d['centres_max_m']:.2e} m | U_max {d['U_max']:.4g} U_rms {d['U_rms']:.4g} of peak {d['U_peak']:.3f} | p_max {d['p_max']:.4g} p_rms {d['p_rms']:.4g} of range {d['p_range']:.1f}")
