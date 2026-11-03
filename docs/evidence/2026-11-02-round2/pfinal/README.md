# pfinal: which pressure-solver dictionary a plain pEqn.solve() picks (2026-11-01)

Claim checked (from `pod-versions-20261030/auto/upstream-pr-draft.md`, "U and p, on openfoam.com only"):
with one outer corrector, a plain `pEqn.solve()` selects `pFinal` at every pressure corrector on openfoam.com
(v2012, v2106, v2212), whereas `pimpleFoam` uses the `p` solver until the last solve of the final corrector;
on OpenFOAM 8 (openfoam.org) `pimpleFoam` has a plain `pEqn.solve()`.

Result: the claim holds in every detail, from source and at runtime, on all four versions.

## (a) Source, copied unchanged out of the four images

`source/<version>/...` holds the files; `source-excerpts.md` quotes the lines with line numbers. Versions
(META-INFO/api-info, etc/bashrc): v2012 patch 210618, v2106 patch 211215, v2212 patch 230110, OpenFOAM 8.

openfoam.com (identical text in v2012, v2106, v2212; line numbers differ in v2212):
- `fvMatrixSolve.C` `fvMatrix<Type>::solve()` is `return this->solve(solverDict());` (v2012/v2106 line 327, v2212 line 345).
- `fvMatrix.C` `solverDict()` returns `psi_.mesh().solverDict(psi_.select(psi_.mesh().data::template getOrDefault<bool>("finalIteration", false)))` (v2012/v2106 lines 996-1006, v2212 1573-1583).
- `GeometricField::select(bool final)` returns `name() + "Final"` when `final`.
- `pimpleControl::loop()` (pimpleControl.C, v2012/v2106 lines 202-267, v2212 200-265) adds `finalIteration` to the mesh data when `finalIter()` is true, i.e. `corr_ == nCorrPIMPLE_`, before the outer iteration runs; it removes the flag only after the last iteration. With `nOuterCorrectors 1` the flag is set for the whole and only outer iteration, so every plain `solve()` in it, U and p alike, uses the `Final` dictionary. `pisoControl` adds nothing (its constructor has the add commented out, line 44).
- `pimpleControl::finalInnerIter()` (pimpleControlI.H lines 98-112) is `corrPISO_ == nCorrPISO_ && corrNonOrtho_ == nNonOrthCorr_ + 1`, and-ed with `finalIter()` only when `finalOnLastPimpleIterOnly` is set (default false, pimpleControl.C lines 53-54).
- `pimpleFoam/pEqn.H` line 51 (v2012, v2106) / 48 (v2212): `pEqn.solve(mesh.solver(p.select(pimple.finalInnerIter())));`. `pimpleFoam/UEqn.H` line 21: `solve(UEqn == -fvc::grad(p));` (plain).

OpenFOAM 8:
- `fvMatrixSolve.C` lines 331-346: `solve()` calls `solve(psi_.mesh().solverDict(psi_.select(psi_.mesh().data::template lookupOrDefault<bool>("finalIteration", false))))`.
- `finalIteration` is set in exactly one place, `singleRegionSolutionControl::updateFinal()` (lines 70-78): remove, then add if `isFinal()`. `updateFinal()` is called by `pimpleControl::loop()`, `pisoControl::correct()` (lines 80-98) and `nonOrthogonalSolutionControl::correctNonOrthogonal()` (lines 76-94), i.e. before every outer, PISO and non-orthogonal iteration.
- `pimpleNoLoopControl::isFinal()` (lines 95-100) = `(!anyPisoIter() && loop_.finalPimpleIter()) || pisoControl::isFinal()`; `pisoControl::isFinal()` (lines 71-77) is true inside the PISO loop only when `finalNonOrthogonalIter() && finalPisoIter()`. So a plain `pEqn.solve()` inside `while (pimple.correctNonOrthogonal())` picks `pFinal` only at the last non-orthogonal iteration of the last PISO corrector, and `UEqn` (solved with `corrPiso_ == 0`) picks `UFinal` on the final outer iteration.
- `pimpleFoam/pEqn.H` line 47: `pEqn.solve();` (plain). `UEqn.H` line 21: `solve(UEqn == -fvc::grad(p));`.

Consequence: on OpenFOAM 8 the plain call behaves like openfoam.com's `p.select(pimple.finalInnerIter())`; on openfoam.com the plain call does not, because there the flag is per outer iteration only. The fork's `#ifdef OPENFOAM` line reproduces `pimpleFoam` on both families.

## (b) Runtime, job 25080017 (1 min 49 s, node ttest02), `demo/runs-25080017/`

Scripts: `demo/run_demo.sbatch`, `demo/inner.sh`, `demo/summarize.py`. Stabilised case and binaries from account runs
24951137 (8), 24951138 (v2012), 24951139 (v2106), 24951140 (v2212): fork bf7a06e, upstream 6fde869. Each run: 2 time
steps, `nCorrectors 2`, `nNonOrthogonalCorrectors 2` (6 pressure solves per outer iteration), and in `fvSolution`
`p` = PCG/DIC (relTol 0.1), `pFinal` = GAMG (tol 1e-8, relTol 0), `U` = smoothSolver, `UFinal` = PBiCGStab/DILU, so the
solver name printed in the log names the dictionary. Builds: `pimpleFoam` of the image, `fork` (fork's line),
`upstream` (plain `pEqn.solve()`), `fork-plainp` (fork with upstream's line, openfoam.com only). `-n1`/`-n2` =
`nOuterCorrectors 1`/`2`. All 30 runs exit 0. Table: `demo/runs-25080017/summary.md` (`summary.json`).

Per time step, pressure solves in order:

| version | pimpleFoam-n1 | fork-n1 | upstream-n1 / fork-plainp-n1 |
|---|---|---|---|
| v2012, v2106, v2212 | DICPCG x5, GAMG | DICPCG x5, GAMG | GAMG x6 |
| 8 | DICPCG x5, GAMG | DICPCG x5, GAMG | DICPCG x5, GAMG (upstream; no fork-plainp build on 8) |

With `nOuterCorrectors 2` (not part of the claim): pimpleFoam and fork give DICPCG x5, GAMG in each of the two outer
iterations on all four versions (`finalOnLastPimpleIterOnly` default false; OF 8 `pisoControl::isFinal()` has no outer
term); upstream/fork-plainp on openfoam.com give DICPCG x6 then GAMG x6; upstream on 8 gives DICPCG x5, GAMG twice.
Ux: with n1 every build on every version uses UFinal (DILUPBiCGStab); with n2, smoothSolver then DILUPBiCGStab.

Residuals in the fork-n1 and pimpleFoam-n1 logs are identical line for line on v2106 (first step: p initial residuals
1, 0.0640935300882, 0.0507975648525, 0.0460022474516, 0.0418107059686, 0.041015064629).

## Not done
- No rebuild of any solver: the binaries are those of jobs 24951137-24951140 (their `src-*/.../pEqn.H` hold the lines compiled).
- Only the stabilised case was run, 2 time steps; the shipped `Run_Case` was not run here.
- No change to any repository, branch or draft.
