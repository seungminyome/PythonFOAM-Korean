"""Write r7 commit messages: r6 subjects, bodies rewrapped at 72 columns, with the
body texts given here where round 6 changed or trimmed them. Usage: wrap_msgs.py r6dir outdir"""
import sys, textwrap
from pathlib import Path
TRAILER = 'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'
NEW = {
 1: ("snapshot_func got a view of a C++ buffer that the next step overwrites, so "
     "the first snapshot of each window that the shipped module keeps held the "
     "second step's values. Each snapshot is now an array NumPy owns, filled "
     "after U and p pass a finite check. A failed import, missing function, "
     "exception or SystemExit stops the run with the traceback. So does a changed "
     "cell count, or an svd_func result that is not finite float64 with 1 or more "
     "columns or whose count differs between ranks. Mode files are dimensionless "
     "zeroGradient fields. podTruncation in controlDict, default 5, caps the modes "
     "written; more columns give one warning. sys.path starts with the case "
     "folder. Py_FinalizeEx at exit waits for non-daemon threads. A write step "
     "right after an SVD now collects a snapshot; the earlier code ran svd_func at "
     "every write step."),
 5: ("On openfoam.com a plain pEqn.solve() takes the pFinal solver throughout the "
     "last outer iteration. With nOuterCorrectors 1, as in Run_Case, that is every "
     "pressure solve. pimpleFoam there solves with "
     "mesh.solver(p.select(pimple.finalInnerIter())), which takes pFinal only on "
     "the last non-orthogonal pass of the final corrector. PODFoam now makes the "
     "same call, so its U and p agree with pimpleFoam's on v2012, v2106 and v2212. "
     "On openfoam.org the call stays plain, as in pimpleFoam there, and OpenFOAM 8 "
     "results do not change."),
 8: ("A python_module.py may define two more functions. mesh_func runs once "
     "before the first step with copies of the cell centres, volumes, solution "
     "directions and cell polygons: in 2D a face of the first empty patch per "
     "cell, in 3D a plane slice of each cell the plane cuts. analysis_func runs "
     "after every step with the time index, snapshot count, residuals, Courant "
     "and continuity numbers and copies of U and p. They change neither U nor p; "
     "with analysis_func the POD step collects a snapshot at every step. Only the "
     "master rank calls them. HOOKS.md has the contract."),
 9: ("python_module.py is an example for the two hooks. At chosen steps it draws "
     "|U| and p and asks a vision-language model on a local llama-server about "
     "them. It records the answer with the arrays; model output never goes back "
     "into the solver. Each request runs in a forked worker with a deadline, so a "
     "slow or dead server cannot hold the solver past it. run_demo.sh runs five "
     "cases, synchronous or asynchronous. verify_demo.py and verify_async.py "
     "check that the written fields equal those of the same run with no model "
     "requests. The unit tests need no solver or model."),
 10: ("These scripts run the asynchronous suite with Gemma 4 12B on a Slurm GPU "
      "node. setup_12b.sh fetches the pinned weights and llama.cpp and checks "
      "their SHA-256. build_llama_cuda.sh builds llama.cpp where the prebuilt "
      "binaries need a newer glibc. start_server.sh and stop_server.sh check that "
      "the pid they handle is a llama-server. async_v2.slurm runs the suite with "
      "OpenFOAM in an Apptainer image; site settings come from the environment. "
      "The runtime lives beside the repository and the job output under "
      "llm_demo/, which its .gitignore covers."),
}
src, out = Path(sys.argv[1]), Path(sys.argv[2])
for i in range(1, 12):
    lines = (src / f'c{i}').read_text().rstrip('\n').split('\n')
    subject = lines[0]
    assert lines[1] == '' and lines[-1] == TRAILER and lines[-2] == ''
    body = ' '.join(lines[2:-2])
    body = NEW.get(i, body)
    wrapped = textwrap.wrap(body, 72, break_on_hyphens=False, break_long_words=False)
    (out / f'c{i}').write_text(subject + '\n\n' + '\n'.join(wrapped) + '\n\n' + TRAILER + '\n')
