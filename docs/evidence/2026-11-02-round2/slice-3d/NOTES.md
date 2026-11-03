# r2/slice-3d: Gemma 4 12B reading slice pictures of the 3D step case (2026-11-01/02)

Design: design.json (written before the jobs, not changed). Code: worktree wt at bf7a06e (clean, git-status.txt empty).

Phase 1, job 25080032 (CPU, t377, 23 min 49 s, 2026-11-01 23:17 local): build + validation PASS in of2212.sif
(phase1-25080032/validation.log), 4 serial 300-step runs of the 3D case from serial3d/0.10075 of job 24929629 with
POD_SLICE_Z = 0.00079375 / 0.00396875 / 0.00714375 / 0.01031250 m (z1 z3 z5 z7), LLM_ENABLED=0, v2 frames every 50 steps.
Test set phase1-25080032/testset: 24 solver frames + 48 random windows (seed 20261101) = 72 describe requests,
truth.json from the slice arrays, baseline.json (constant answer) before any model ran.

Phase 2, job 25088316 (GPU, mbl40s-002, L40S, 4 min 29 s, 2026-11-02 18:36-18:41 UTC): llama-server b11429, Gemma 4 12B QAT Q4_0
+ projector (sha256 in phase2-25088316/model-sha256.txt), ctx 4096 batch/ubatch 512, image tokens 256; 72/72 answered,
all output_format_valid; per-request wall 3.0-4.1 s. Results: phase2-25088316/results/summary.json, metrics.jsonl,
<set>/<name>/{request_body,response,result,metrics}.json.

| set | n | fastest flow right | baseline | lowest p right | baseline |
|---|---:|---:|---:|---:|---:|
| solver (fixed window) | 24 | 21 | 24 | 24 | 24 |
| window (random) | 48 | 39 | 11 | 47 | 8 |
| all | 72 | 60 | 27 | 71 | 29 |

By slice (18 requests each; fastest / lowest p): z1 18/18, z3 14/18, z5 13/18, z7 15/17.

Misses: 12 fastest-flow misses, 11 of them with answer y = 70..95 % (the model named the upper shear layer where the
truth is the jet at y 20..56 %); 1 lowest-pressure miss at exactly 10.0 % (z7-step000150-w1). List in the orchestrator
report; data in metrics.jsonl.

Caveats (facts from truth.json): the four slices give the same true positions to 0.1 % at every step, and max |U|
differs by at most 2.5 % between z1 and the other three (34.66 vs 35.51 m/s at step 300); the start state had the
walls for only 150 steps and the flow is still nearly 2D. The solver set's baseline is 24/24 because the true cells of
one flow in a fixed window stay within 10 % of one point over 300 steps; only the window set separates the model
from the baseline.
