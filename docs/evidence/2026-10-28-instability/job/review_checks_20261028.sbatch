#!/bin/bash
#SBATCH --job-name=instability-review-checks
#SBATCH --account=me5475
#SBATCH --partition=mb
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/picture-test-20261021/review-checks-%j.out
# Checks after the review of the instability test of 2026-10-28, on the commit printed first.
# No model, no GPU.
# 1. unit tests: the documented order, 'unittest discover', and test_instability_test before
#    test_picture_test (the order that failed before the fix);
# 2. the test set built again with the changed instability_test.py and compared with the set
#    of job 24929495 (answer key and every request body); removed again if identical;
# 3. instability_test.py report on the committed results, compared with reports/<job>.md;
# 4. independent-recount.py with the system python3 (standard library only), compared with
#    the committed independent-recount.json;
# 5. flow/domain_max.py: where the largest |U| of each state is (writes flow/domain-max.json).
set -uo pipefail
REPO=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-inst
EV=$REPO/docs/evidence/2026-10-28-instability
SET=/cluster/medbow/gscratch/syome/github_repos/picture-test-20261021/instability-test-20261028
NEW=/cluster/medbow/gscratch/syome/github_repos/picture-test-20261021/instability-rebuild-$SLURM_JOB_ID
export PATH=/gscratch/syome/conda/s4f/bin:$PATH MPLCONFIGDIR=$TMPDIR/mpl OPENBLAS_NUM_THREADS=1
echo "== commit"
git -C "$REPO" rev-parse HEAD
git -C "$REPO" status --short
cd "$REPO/Solver_Examples/PODFoam/llm_demo"
sha256sum instability_test.py test_instability_test.py picture_test.py "$EV/independent-recount.py" "$EV/flow/domain_max.py"
python3 --version; /usr/bin/python3 --version

run_tests() {
    local label=$1; shift
    echo "== unit tests, $label"
    python3 -m unittest "$@" > "$TMPDIR/ut.txt" 2>&1
    echo "exit $?"
    grep -E '^(ERROR|FAIL):|^Ran [0-9]+ tests? in|^(OK|FAILED)( |$)' "$TMPDIR/ut.txt"
}
run_tests "documented order" test_llm_client test_callback test_ablation_runner test_async test_picture_test test_instability_test
run_tests "discover" discover -p 'test_*.py'
run_tests "test_instability_test then test_picture_test" test_instability_test test_picture_test

echo "== test set built again"
python3 instability_test.py build --design "$EV/test-set/design.json" \
    --centres "$REPO/docs/evidence/2026-10-20/pod-llm-async.pp7agC/async-no-llm/llm_observation/step-000250/fields.npz" \
    --output "$NEW"
python3 instability_test.py check --test-set "$NEW"
python3 - "$SET" "$NEW" <<'PY' && rm -rf "$NEW" && echo "identical; removed $NEW"
import hashlib, json, sys
from pathlib import Path
old, new = Path(sys.argv[1]), Path(sys.argv[2])
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
mo, mn = (json.loads((p / "manifest.json").read_text()) for p in (old, new))
key = sha(old / "truth.private.json") == sha(new / "truth.private.json")
ro = {e["name"]: e["request_sha256"] for e in mo["requests"]}
rn = {e["name"]: sha(new / e["file"]) for e in mn["requests"]}
same = sum(ro[n] == rn.get(n) for n in ro)
print(f"answer key identical: {key}; request bodies: {len(ro)} before, {len(rn)} now, {same} identical")
print("manifest entries that differ:", sorted(k for k in set(mo) | set(mn) if mo.get(k) != mn.get(k)))
print("code hashes that differ:", sorted(k for k in mo["code_sha256"] if mo["code_sha256"][k] != mn["code_sha256"].get(k)))
sys.exit(0 if key and same == len(ro) == len(rn) else 1)
PY

echo "== report on the committed results"
for job in 24929533 24929534; do
    python3 instability_test.py report "$EV"/results/window-test-$job/* --test-set "$EV/test-set" \
        --output "$TMPDIR/report-$job.md" > /dev/null
    echo "report exit $?"
    cmp "$TMPDIR/report-$job.md" "$EV/reports/window-test-$job.md" && echo "window-test-$job: same as reports/window-test-$job.md"
done

echo "== independent recount"
cp "$EV/independent-recount.json" "$TMPDIR/recount-committed.json"
(cd "$EV" && /usr/bin/python3 -I independent-recount.py)
cmp "$EV/independent-recount.json" "$TMPDIR/recount-committed.json" && echo "independent-recount.json unchanged"

echo "== domain_max.py"
(cd "$EV/flow" && python3 domain_max.py)
sha256sum "$EV/flow/domain-max.json"
git -C "$REPO" status --short
