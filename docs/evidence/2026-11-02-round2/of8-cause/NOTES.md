# of8-cause: why OpenFOAM 8 differs from v2212 (2026-11-01/02)

Question (docs/results-20261030.md lines 9-10, 55-61): OpenFOAM 8 vs v2212, same case, same start
(t = 0.1 s), 100 steps: max |dU| 3.11 (2D) / 3.18 (3D slice) of 37.2 m/s, max |dp| 23.2 / 23.5 of
379 / 425; 3D p iterations per solve 64.0 vs 23.5. "Cause not examined."

## Answer

The cause is the `relaxationFactors` block of system/fvSolution (identical in both version runs; it is the
fork's Run_Case dict, `cmp` against pr/refix/matrix/*/serial*/system/fvSolution = same) read differently:

    relaxationFactors { fields { p 0.9; } equations { U 0.9; nuTilda 0.9; } }   with PIMPLE nOuterCorrectors 1

With one outer corrector every PIMPLE iteration is the final one (`finalIteration` = true).
- v2212 (`fvMatrix::relax()`, fvMatrix.C:1255; `GeometricField::relax()`, GeometricField.C:1104) looks up
  only `UFinal` / `pFinal`; they are absent and there is no `default`, so U and p are NOT relaxed.
- OpenFOAM 8 (fvMatrix.C:672; GeometricField.C:1197) looks up `UFinal` / `pFinal` and, when absent, falls
  back to `U` / `p`, so U equation and p field ARE relaxed by 0.9.
Source excerpts: source-excerpts-relax.txt. Neither version prints a warning (0 "FOAM Warning" lines in all
16 pimpleFoam logs and in the 4 matrix PODFoam logs).

## Evidence (plain pimpleFoam, no Python; compare-final.json, written by compare.py)

Variants (dicts/fvSolution.*): A = as in the matrix runs; B = relaxationFactors removed; C = A plus
explicit pFinal 0.9, UFinal 0.9; D = PCG/smoothSolver to 1e-13, relTol 0, no relaxation; E = equations
(U, nuTilda) only; F = field p only. Case from pr/refix/matrix/8-24950783 (0.1 start state), controlDict
endTime 0.1005, writeInterval 100.

1. pimpleFoam reproduces the PODFoam frames exactly: 8/2d/A, 8/3d/A, v2212/2d/A, v2212/3d/A vs
   matrix llm_observation/step-000100/fields.npz: U_max = p_max = 0.0 (section pimpleFoam_vs_PODFoam_frame).
   The difference is in OpenFOAM, not in PODFoam.
2. Same dict, two versions (of8_vs_v2212_same_variant): 2d/A U 3.1104, p 23.235 of 369.2;
   3d/A U 3.1828, p 23.4938 of 416.2 (full-mesh p range; slice range in the report is 424.5).
   2d/B U 0.0000, p 0.0001; 3d/B U 0.0001, p 0.0005; 2d/C 0.0000 / 0.0001; 2d/D 0.0000 / 0.0002.
3. Cross (cross): 8/B vs v2212/A: 2d U 0.0000 p 0.0001; 3d U 0.0001 p 0.0005.
   v2212/C vs 8/A (2d): U 0.0000 p 0.0001. v2212/B vs v2212/A: 0 / 0 (v2212 ignores the block as written).
   8/C vs 8/A: 0 / 0 (explicit Final factors change nothing on 8).
   Split: 8/E (U eq only) vs v2212/A: U 3.1097 p 23.18 -> the U-equation factor carries the difference;
   8/F (p field only) vs v2212/A: U 0.0093 p 0.105.
4. One step (compare-1step.json, runs1/, jobs 25080040-41): 8 vs v2212 with B or D: U 1.0e-10, p 5e-9.
   The discretisation is the same; only the relaxation differs.
5. p iterations: 8/3d/A 67.88 per solve (first 100 steps), 8/3d/B 24.385 = v2212/3d/A 24.385 = v2212/3d/B.
   The report's 64.0 / 23.5 are means over the matrix runs' 110 steps (log.PODFoam: 8 64.0 / 67.883 over
   the first 100; v2212 23.548 / 24.385). The relaxed U matrix (larger diagonal) changes rAU and the p
   equation, and the relaxed p field leaves p further from converged at each corrector.
6. Not the cause: fvSchemes identical (cmp); turbulenceProperties identical, simulationType laminar (no LES
   or SA defaults in play); controlDict differs only by `libs ("libincompressibleTurbulenceModels.so")`
   on v2212; no unknown/defaulted-keyword messages in any log.

## Jobs (all finished before this session; none resubmitted)
25080020 8 2d A-F (t400), 25080023 v2212 2d A-F (t400), 25080021 8 3d A (t287), 25080022 8 3d B (t288),
25080024 v2212 3d A (t290), 25080025 v2212 3d B (t294), 25080040/41 one-step B,D (runs1/),
25080389 writeCellCentres on v2212 3d A. Slurm outputs: slurm/.

## Done this session (2026-11-02)
compare.py: the 3D slice is now selected by the frame's `mesh_cells` (the earlier 9-decimal centre match
failed with a KeyError at 1e-12); max |C[mesh_cells] - centres| is recorded in the note. compare-final.json
written. compare-partial.json / compare-2d.json are the earlier partial outputs (8/3d/A was at step 12).

## Not done
No new Slurm jobs. Variants C-F not run in 3D (2D covers the attribution; 3D A/B confirm it).
Did not test v2012/v2106 (report: frames identical to v2212, so same behaviour). Did not change any repo.
