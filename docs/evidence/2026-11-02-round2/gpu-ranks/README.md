# 2-rank solver with one real Gemma 4 12B request (2026-11-01, jobs 25080027 and 25080066)

PR code `bf7a06e` (worktree `wt`, branch `r2/gpu-ranks`, no commits). Node mba30-008, NVIDIA A30, one
llama-server (`llm-runtime-12b`, llama.cpp b11429 CUDA, `gemma-4-12b-it-qat-q4_0.gguf` + projector, ctx 4096,
1 slot), started by `hpc/start_server.sh` as in job 24950818. Scripts: `ranks.sbatch` (host), `ranks_inner.sh`
(in the image: build + validation, then the 2D step case 110 steps from 0.1 s with `LLM_ENABLED=1`,
`describe`, v2 picture, request at step 100; serial, then `decomposePar` scotch 2 subdomains and
`mpirun --oversubscribe -np 2 rank_wrap.sh PODFoam -parallel`), `rank_wrap.sh` (per-rank pid file, rank 1's own
log), `check_ranks.py` (writes `run-<job>/ranks.json`, printed in `check.out`). Images: v2212
`/cluster/medbow/gscratch/syome/s4f/of2212.sif` (Open MPI 4.1.2), OpenFOAM 8 `images/of-8.sif` (Open MPI 4.0.3).
The case's `pod_svd.py` rank check is taken out on 2 ranks, as in the matrix runs.

Job 25080027: elapsed 2:21; `rank_wrap.sh` recorded the wrapper pid only (the solver's pid is the `PID :` line of
`log.PODFoam`). Job 25080066: elapsed 2:14; same scripts, `rank_wrap.sh` also records `solver_pid`.
Both jobs, both versions, serial and 2 ranks: exit 0, `End`, `Python finalized successfully`, 110 `Time =` lines,
110 telemetry lines, validation PASS, `llm_result.json` status `ok`, http 200, request at step 100, answer at
step 110, `worker_reaped` true, `body_equals_builder` and `body_images_equal_frame` true.

Only rank 0 sends: `llm_result.json` `parent_pid` == rank 0's `solver_pid` (25080066: v2212 1721007, 8 1724179)
and == `PID :` of `log.PODFoam`; rank 1's log (`log.rank1`, 550 lines) has 110 `PYTHON snapshot` lines and no
`PYTHON LLM`, `llm`, `request` or `http` text; the server's `/metrics` `llamacpp:prompt_tokens_total` rises by
997 (one request) over each of the 4 solver runs of a job, `launch_slot_` appears 4 times in each server log.
Whole gathered fields: `POD mesh geometry passed to Python: cells=20540 ... ranks=2`, frame 20540 cells
(decomposePar 10252 + 10288); cells ordered by position, the 2-rank frame against the serial frame of the same
job: centres differ by at most 4.2e-17 m (v2212) / 2.8e-17 m (8); max |ΔU| 7.78e-4 m/s of peak 37.2 (v2212),
1.19e-3 of 36.9 (8); max |Δp| (mean removed) 0.0187 of range 379 (v2212), 0.0178 of 369 (8). These numbers equal,
to all printed digits, the serial-vs-2-rank differences of the no-model runs 24948778 / 24948779
(`pr/version-compare.json`). The serial frames and request bodies are byte-identical to job 24950818's
(`fields.npz`, `U.png`, `p.png`, `request_sha256`), both versions, both jobs. The 2-rank request body differs
from the serial one (cell order in `fields.npz`, PNG bytes differ), so its SHA-256 differs.
No deadlock: both ranks exit 0 within 11-12 s of starting; solver stall at step 100 0.010-0.016 s; inference
3.96-4.30 s; end wait at step 110 4.1-4.5 s (`callback_wall_s_step110`).
Answers (`structured_output`, scored by `frame_scoring`): see `run-*/ranks.json`; distances 29-34 % of the
window, none within 10 %, like 24950818.
Not done: more than 2 ranks, the 3D slice case, a request on OpenFOAM v2012/v2106 in parallel, L40S.
