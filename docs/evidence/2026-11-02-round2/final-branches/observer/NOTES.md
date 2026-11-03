# OBSERVER-VERIFY on r4/pr-observer (2026-11-02)

Subject: r4/pr-observer 24e9df6f5640594e2dbbd9a817231717fe8310ef (on r4/pr-fix 8954b2544d0f, base 6fde8698071b).
No branch, commit or worktree outside this folder was created or changed. No push, PR or e-mail.

## Sources used by the jobs
- src/unit, src/load-py310, src/load-py312, src/ranks and quick/PythonFOAM are `git archive 24e9df6` exports with
  a HEAD file. `diff -rq` against a fresh archive of 24e9df6 shows only HEAD, validation/runs/ (quick) and a run-time
  `__pycache__` (ranks).
- wt-obs/ is a detached worktree at 24e9df6. `git status --short` is empty; the one ignored file is
  llm_demo/pod-async-v2-25090646.out (Slurm output of the failed suite attempt).

## Results
| Item | Result | Job | File |
|---|---|---|---|
| Unit tests unloaded, ci-py310 3.10.22 | Ran 85 tests OK, 86.2 s | 25090610 | logs/unit-ci-py310-25090610.log |
| Unit tests unloaded, ci-py312 3.12.15 | Ran 85 tests OK, 86.8 s | 25090610 | logs/unit-ci-py312-25090610.log |
| Test counts | test_llm_client 17, test_callback 34, test_async 34 (= `def test_` count in the source) | 25090610 | logs/unit-25090610.out |
| New tests | test_restart_window_is_checked_against_snapshot_count and test_snapshot_count_mismatch_is_an_error ok on both Pythons (test_callback.py lines 328, 335) | 25090610 | same logs, test lines 148 and 195 |
| Load, py310, 8 copies x 50, 4 cpus (t399) | 50/50 rc=0, each "Ran 34 tests" + OK; walls 68.2-77.4 s; node loadavg 8.93-14.27 | 25090611 | load/load-py310-8x50-25090611/job.txt, summary.txt |
| Load, py312, 8 copies x 50, 4 cpus (t400) | 50/50 rc=0, each "Ran 34 tests" + OK; walls 67.5-73.2 s; node loadavg 2.76-5.60 | 25090612 | load/load-py312-8x50-25090612/job.txt, summary.txt |
| Unloaded pass inside each load job | 85 OK (85.5 s py310, 86.5 s py312) | 25090611/12 | load/*/unittest-unloaded.log |
| E2B quick start, v2106, CPU, 8 cpus (t294) | 10/10 steps exit 0 (+06b health) | 25090644 | quick/logs/steps.tsv |
| - 01 pip | dry run would change nothing; 12 "already satisfied" | 25090644 | quick/logs/01-pip.log |
| - 02 unit tests (s4f Python) | Ran 85 tests OK, 78.2 s | 25090644 | quick/logs/02-unittest.log |
| - 03 validation | PASS, max_Co 0.211076243341, snapshot err 5.000089e-11, mode err 4.94174e-13 | 25090644 | quick/PythonFOAM/.../validation/runs/pod-v2106.Ei5t7O/verification.json |
| - 04 observer, no model | PODFoam exit 0, 10 "callback returned" lines, step-000005 has U.png p.png fields.npz readable-metadata.json | 25090644 | quick/logs/04-observer.log |
| - 05 setup | 3 files "OK" by SHA-256; no download (hard links of pr/quick-1910/llm-runtime, link count 2, mtime 2026-10-30) | 25090644 | quick/logs/05-setup.log |
| - 06/06b/07 | server health 4.83 s; {"status": "ok"}; standalone PASS 13.2 s | 25090644 | quick/logs/06-start.log, 06b-health.log, 07-standalone.log |
| - 08 synchronous suite | PASS, 223 s; 5 cases exit 0, 45 files identical to the no-request run in each | 25090644 | quick/pod-llm-demo.ydkRlD/demo-verification.json |
| - 09 asynchronous suite | PASS, 1669 s; 5 cases exit 0, 216 files identical to the no-request run in each | 25090644 | quick/pod-llm-async.y9g7rb/async-verification.json |
| - 10 stop | server PID 1905714 stopped | 25090644 | quick/logs/10-stop.log |
| Reference validation v2212 for the suite | PASS, max_Co 0.211076243341, mode err 4.94174e-13 | 25090645 | logs/ref-v2212-25090645.out |
| 12B GPU suite, v2212, 1000 steps, tree's hpc/async_v2.slurm (A30 mba30-005, bus 41:00.0) | PASS; 5 cases exit 0 (60.5-61.0 s); files_identical_to_no_request_baseline 72 in every case; every frame same_fields True | 25090963 | logs/suite-v2212-25090963.out |
| - independent byte check | all files of the 4 written time folders (84 incl. uniform/) identical to async-no-llm in all 4 request cases; start files and no-request frames 250/500/750 equal jobs 24950817 and 25089703 | 25090963 | suite/compare-25090963.txt (tools/compare_suite.py) |
| - model results | describe ok 3.85 s, sequence ok 3.97 s, server-error error, timeout timeout; solver stall max 0.018 s | 25090963 | suite/compare-25090963.txt |
| - GPU use | 7925 MiB after server start, up to 100 % utilisation during requests; llama-b11429-cuda | 25090963 | pod-async-v2/run-25090963/server/gpu-*.txt, gpu-samples.csv |
| - checkout record | git/HEAD 24e9df6, changes.patch 0 B, git-status empty; WM_PROJECT_VERSION v2212 | 25090963 | pod-async-v2/run-25090963/git/, pod-llm-async.1qq7kg/environment.txt |
| 2-rank 12B request, v2212 (A30 mba30-005) | serial and par2 exit 0, End; status ok, HTTP 200; infer 4.17 s / 4.13 s; stall 0.010 / 0.011 s; rank 1 log 550 lines, 0 LLM lines; ranks end 12.16 s / 12.00 s after start | 25090647 | ranks/run-25090647/ranks.json, check.out |
| - comparisons | serial byte-identical to job 24950818 (fields.npz, U.png, p.png, request); serial vs par2 round-off: U max 7.78e-4 (max speed 37.2 m/s), p max 0.0187 | 25090647 | ranks/run-25090647/ranks.json |

## Jobs (all submitted by the two earlier attempts in this folder; none submitted or touched by this session)
- 25090610 r4o-unit COMPLETED 3:00 (t399)
- 25090611 r4o-load py310 COMPLETED 11:29 (t399); 25090612 r4o-load py312 COMPLETED 11:11 (t400)
- 25090613 quick, 25090614 ref, 25090616 ranks FAILED in 0-5 s (module not found; submitted from zsh); 25090615 suite CANCELLED (dependency on 25090614). Superseded.
- 25090644 r4o-quick COMPLETED 34:55 (t294)
- 25090645 r4o-ref-v2212 COMPLETED 1:05 (t399)
- 25090646 r4o-suite-v2212 FAILED 5:14 (mba30-005): its GPU showed ERR! in nvidia-smi and llama-server logged
  "no CUDA-capable device is detected", so the server ran on the CPU and async-sequence hit an AssertionError. Hardware, not code.
- 25090647 r4o-ranks COMPLETED 1:13 (mba30-005, GPU-376f613c)
- 25090963 r4o-suite-v2212b COMPLETED 6:28 (mba30-005, healthy A30 at bus 41:00.0)

## Findings for the orchestrator
1. llm_demo/README.md line 108-109 (24e9df6) says that on 8 CPUs the synchronous suite took "about 2 minutes" and the
   asynchronous one "15 to 27". This run took 223 s and 1669 s (27.8 min). The five recorded 8-CPU runs give
   103-223 s and 912-1669 s (pr/refix/quick, logs/quick-1910, r3/assemble/quick job 25089658, this job).
   "2 to 4 minutes" and "15 to 28" would cover all five. Doc-only; the r5 rewrite can take it.
2. The py312 load node (t400) had a node loadavg of 2.76-5.60, lower than the py310 node (8.93-14.27) and the r3 runs
   (8-copy jobs 25089961/62: 10.2-15.4). The 8 copies still ran on 4 cpus in both cases.
3. Code depends on two doc passages: setup_12b.sh line 90 points to `build_llama_cuda.sh` in hpc/README.md, and
   python_module.py line 350 cites HOOKS.md for the left-out empty directions. The r5 rewrite should keep both.
   No code or test reads a .md file, so a doc-only r5 keeps these results valid when
   `git diff 24e9df6 <r5 tip> -- ':!*.md'` is empty.

## Not done
- No reruns: every job above finished before this session, and each output was checked against its files.
- No extra margin load run (16 copies) on this tip; no load run of test_callback or test_llm_client.
- No 2-rank run on OpenFOAM 8, no suite on v2012 or 8, no 3D slice run, no Docker run in this task.
- No commits, branches or worktrees made by this session; nothing pushed; no PR; no e-mail.
