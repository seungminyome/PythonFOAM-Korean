#!/bin/bash
#SBATCH --job-name=pod-account
#SBATCH --cpus-per-task=2
#SBATCH --mem=24G
#SBATCH --time=01:00:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/slurm/pod-account-%x-%j.out
# Accounts for every difference between upstream's PODFoam and this fork's on one case with upstream's python_module.py:
#   upstream        upstream's solver, upstream's module (records the snapshot matrix at each SVD)
#   fork            this fork's solver, upstream's module (same record)
#   fork-overwrite  this fork's solver, the module with upstream's first-column overwrite reproduced in Python
#   fork-plainp     openfoam.com only: this fork's solver with upstream's pEqn.solve(), the same overwriting module
# Environment: VER (8, v2106, v2212), KIND (shipped, stabilised), REPO
set -uo pipefail
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030
REPO=${REPO:-/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-compat}
export KIND=${KIND:-stabilised}
case $VER in
  v2012) SIF=$W/images/of-v2012-dev.sif; RC=/usr/lib/openfoam/openfoam2012/etc/bashrc;;
  v2106) SIF=$W/images/of-v2106-dev.sif; RC=/usr/lib/openfoam/openfoam2106/etc/bashrc;;
  v2212) SIF=/cluster/medbow/gscratch/syome/s4f/of2212.sif; RC=/usr/lib/openfoam/openfoam2212/etc/bashrc;;
  8)     SIF=$W/images/of-8.sif; RC=/opt/openfoam8/etc/bashrc;;
  *) echo "unknown VER $VER"; exit 2;;
esac
OUT=$W/account-runs/$KIND-$VER-${SLURM_JOB_ID:-local}; mkdir -p "$OUT"
module load apptainer
git -C "$REPO" rev-parse HEAD > "$OUT/HEAD"; git -C "$REPO" status --short > "$OUT/git-status.txt"; git -C "$REPO" rev-parse upstream/main > "$OUT/UPSTREAM"
for v in upstream fork fork-plainp; do mkdir -p "$OUT/src-$v"; done
git -C "$REPO" archive upstream/main Solver_Examples/PODFoam | tar -x -C "$OUT/src-upstream"
git -C "$REPO" archive HEAD Solver_Examples/PODFoam | tar -x -C "$OUT/src-fork"
git -C "$REPO" archive HEAD Solver_Examples/PODFoam | tar -x -C "$OUT/src-fork-plainp"
/gscratch/syome/conda/s4f/bin/python3 - "$OUT" <<'PY'
import re, sys
from pathlib import Path
out = Path(sys.argv[1])
p = out/'src-fork-plainp/Solver_Examples/PODFoam/pEqn.H'
text = p.read_text()
new, n = re.subn(r'    #ifdef OPENFOAM\n.*?\n    pEqn\.solve\(mesh\.solver.*?\n    #else\n    pEqn\.solve\(\);\n    #endif\n', '    pEqn.solve();\n', text, flags=re.S)
assert n == 1
p.write_text(new)
# upstream's module, recording the snapshot matrices at each SVD
source = (out/'src-upstream/Solver_Examples/PODFoam/Run_Case/python_module.py').read_text()
marker = "def svd_func(rank):\n    \n    global online_mode\n    global iter, u_snapshots, v_snapshots, w_snapshots\n    global init_mode, u_svd_calc, v_svd_calc, w_svd_calc\n"
assert marker in source
record = marker + "    global _svd_count\n    _svd_count += 1\n    np.savez('snapshots-%d.npz' % _svd_count, u=u_snapshots, v=v_snapshots, w=w_snapshots)\n"
recording = source.replace(marker, record).replace("iter = 0\nu_snapshots = None", "_svd_count = 0\niter = 0\nu_snapshots = None", 1)
(out/'module-recording.py').write_text(recording)
# the same with upstream's overwrite: its first column is a view of the C++ buffer, so the next snapshot replaces it
marker2 = "        u_temp = array[:,0].reshape(-1,1)\n        v_temp = array[:,1].reshape(-1,1)\n        w_temp = array[:,2].reshape(-1,1)\n"
assert marker2 in recording
overwrite = recording.replace(marker2, marker2 + "        if iter == 1:\n            u_snapshots = u_temp.copy()\n            v_snapshots = v_temp.copy()\n            w_snapshots = w_temp.copy()\n")
(out/'module-overwrite.py').write_text(overwrite)
PY
apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash "$W/matrix/pod_account_inner.sh" "$OUT" "$VER" "$RC"
echo "inner exit $?"
/gscratch/syome/conda/s4f/bin/python3 "$W/matrix/compare_pod_account.py" "$OUT" "$VER"
