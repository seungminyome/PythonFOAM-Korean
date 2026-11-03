# Source excerpts: how fvMatrix::solve() picks p or pFinal

Files copied unchanged out of the four images on 2026-11-01 into `r2/pfinal/source/<version>/` (relative paths below are under $WM_PROJECT_DIR of each image). Versions from each image's META-INFO/api-info or etc/bashrc:

- v2012: api=2012 patch=210618 export WM_PROJECT_VERSION=v2012 
- v2106: api=2106 patch=211215 export WM_PROJECT_VERSION=v2106 
- v2212: api=2212 patch=230110 export WM_PROJECT_VERSION=v2212 
- 8: export WM_PROJECT_VERSION=8 

## v2012 (openfoam.com)

### src/finiteVolume/fvMatrices/fvMatrix/fvMatrixSolve.C, lines 324-328
```cpp
template<class Type>
Foam::SolverPerformance<Type> Foam::fvMatrix<Type>::solve()
{
    return this->solve(solverDict());
}
```

### src/finiteVolume/fvMatrices/fvMatrix/fvMatrix.C, lines 995-1006
```cpp
template<class Type>
const Foam::dictionary& Foam::fvMatrix<Type>::solverDict() const
{
    return psi_.mesh().solverDict
    (
        psi_.select
        (
            psi_.mesh().data::template getOrDefault<bool>
            ("finalIteration", false)
        )
    );
}
```

### src/OpenFOAM/fields/GeometricFields/GeometricField/GeometricField.C, lines 1005-1017
```cpp
template<class Type, template<class> class PatchField, class GeoMesh>
Foam::word Foam::GeometricField<Type, PatchField, GeoMesh>::select
(
    bool final
) const
{
    if (final)
    {
        return this->name() + "Final";
    }

    return this->name();
}
```

### src/finiteVolume/cfdTools/general/solutionControl/pimpleControl/pimpleControl.C, lines 202-267 (sets finalIteration)
```cpp
bool Foam::pimpleControl::loop()
{
    read();

    ++corr_;

    if (debug)
    {
        Info<< algorithmName_ << " loop: corr = " << corr_ << endl;
    }

    setFirstIterFlag();

    if (corr_ == nCorrPIMPLE_ + 1)
    {
        if (!residualControl_.empty() && (nCorrPIMPLE_ != 1))
        {
            Info<< algorithmName_ << ": not converged within "
                << nCorrPIMPLE_ << " iterations" << endl;
        }

        corr_ = 0;
        mesh_.data::remove("finalIteration");
        return false;
    }

    bool completed = false;
    if (converged_ || criteriaSatisfied())
    {
        if (converged_)
        {
            Info<< algorithmName_ << ": converged in " << corr_ - 1
                << " iterations" << endl;

            mesh_.data::remove("finalIteration");
            corr_ = 0;
            converged_ = false;

            completed = true;
        }
        else
        {
            Info<< algorithmName_ << ": iteration " << corr_ << endl;
            storePrevIterFields();

            mesh_.data::add("finalIteration", true);
            converged_ = true;
        }
    }
    else
    {
        if (finalIter())
        {
            mesh_.data::add("finalIteration", true);
        }

        if (corr_ <= nCorrPIMPLE_)
        {
            Info<< algorithmName_ << ": iteration " << corr_ << endl;
            storePrevIterFields();
            completed = false;
        }
    }

    return !completed;
}
```

### same file, lines 53-54 (default of finalOnLastPimpleIterOnly)
```cpp
    finalOnLastPimpleIterOnly_ =
        pimpleDict.getOrDefault("finalOnLastPimpleIterOnly", false);
```

### src/finiteVolume/cfdTools/general/solutionControl/pimpleControl/pimpleControlI.H, lines 92-112
```cpp
inline bool Foam::pimpleControl::finalIter() const
{
    return converged_ || (corr_ == nCorrPIMPLE_);
}


inline bool Foam::pimpleControl::finalInnerIter() const
{
    bool finalInnerIter =
        corrPISO_ == nCorrPISO_
     && corrNonOrtho_ == nNonOrthCorr_ + 1;

    if (finalOnLastPimpleIterOnly_)
    {
        return finalInnerIter && finalIter();
    }
    else
    {
        return finalInnerIter;
    }
}
```

### applications/solvers/incompressible/pimpleFoam/pEqn.H, lines 40-57
```cpp

// Non-orthogonal pressure corrector loop
while (pimple.correctNonOrthogonal())
{
    fvScalarMatrix pEqn
    (
        fvm::laplacian(rAtU(), p) == fvc::div(phiHbyA)
    );

    pEqn.setReference(pRefCell, pRefValue);

    pEqn.solve(mesh.solver(p.select(pimple.finalInnerIter())));

    if (pimple.finalNonOrthogonalIter())
    {
        phi = phiHbyA - pEqn.flux();
    }
}
```

### applications/solvers/incompressible/pimpleFoam/UEqn.H, line 21
```cpp
    solve(UEqn == -fvc::grad(p));
```

## v2106 (openfoam.com)

### src/finiteVolume/fvMatrices/fvMatrix/fvMatrixSolve.C, lines 324-328
```cpp
template<class Type>
Foam::SolverPerformance<Type> Foam::fvMatrix<Type>::solve()
{
    return this->solve(solverDict());
}
```

### src/finiteVolume/fvMatrices/fvMatrix/fvMatrix.C, lines 995-1006
```cpp
template<class Type>
const Foam::dictionary& Foam::fvMatrix<Type>::solverDict() const
{
    return psi_.mesh().solverDict
    (
        psi_.select
        (
            psi_.mesh().data::template getOrDefault<bool>
            ("finalIteration", false)
        )
    );
}
```

### src/OpenFOAM/fields/GeometricFields/GeometricField/GeometricField.C, lines 1005-1017
```cpp
template<class Type, template<class> class PatchField, class GeoMesh>
Foam::word Foam::GeometricField<Type, PatchField, GeoMesh>::select
(
    bool final
) const
{
    if (final)
    {
        return this->name() + "Final";
    }

    return this->name();
}
```

### src/finiteVolume/cfdTools/general/solutionControl/pimpleControl/pimpleControl.C, lines 202-267 (sets finalIteration)
```cpp
bool Foam::pimpleControl::loop()
{
    read();

    ++corr_;

    if (debug)
    {
        Info<< algorithmName_ << " loop: corr = " << corr_ << endl;
    }

    setFirstIterFlag();

    if (corr_ == nCorrPIMPLE_ + 1)
    {
        if (!residualControl_.empty() && (nCorrPIMPLE_ != 1))
        {
            Info<< algorithmName_ << ": not converged within "
                << nCorrPIMPLE_ << " iterations" << endl;
        }

        corr_ = 0;
        mesh_.data::remove("finalIteration");
        return false;
    }

    bool completed = false;
    if (converged_ || criteriaSatisfied())
    {
        if (converged_)
        {
            Info<< algorithmName_ << ": converged in " << corr_ - 1
                << " iterations" << endl;

            mesh_.data::remove("finalIteration");
            corr_ = 0;
            converged_ = false;

            completed = true;
        }
        else
        {
            Info<< algorithmName_ << ": iteration " << corr_ << endl;
            storePrevIterFields();

            mesh_.data::add("finalIteration", true);
            converged_ = true;
        }
    }
    else
    {
        if (finalIter())
        {
            mesh_.data::add("finalIteration", true);
        }

        if (corr_ <= nCorrPIMPLE_)
        {
            Info<< algorithmName_ << ": iteration " << corr_ << endl;
            storePrevIterFields();
            completed = false;
        }
    }

    return !completed;
}
```

### same file, lines 53-54 (default of finalOnLastPimpleIterOnly)
```cpp
    finalOnLastPimpleIterOnly_ =
        pimpleDict.getOrDefault("finalOnLastPimpleIterOnly", false);
```

### src/finiteVolume/cfdTools/general/solutionControl/pimpleControl/pimpleControlI.H, lines 92-112
```cpp
inline bool Foam::pimpleControl::finalIter() const
{
    return converged_ || (corr_ == nCorrPIMPLE_);
}


inline bool Foam::pimpleControl::finalInnerIter() const
{
    bool finalInnerIter =
        corrPISO_ == nCorrPISO_
     && corrNonOrtho_ == nNonOrthCorr_ + 1;

    if (finalOnLastPimpleIterOnly_)
    {
        return finalInnerIter && finalIter();
    }
    else
    {
        return finalInnerIter;
    }
}
```

### applications/solvers/incompressible/pimpleFoam/pEqn.H, lines 40-57
```cpp

// Non-orthogonal pressure corrector loop
while (pimple.correctNonOrthogonal())
{
    fvScalarMatrix pEqn
    (
        fvm::laplacian(rAtU(), p) == fvc::div(phiHbyA)
    );

    pEqn.setReference(pRefCell, pRefValue);

    pEqn.solve(mesh.solver(p.select(pimple.finalInnerIter())));

    if (pimple.finalNonOrthogonalIter())
    {
        phi = phiHbyA - pEqn.flux();
    }
}
```

### applications/solvers/incompressible/pimpleFoam/UEqn.H, line 21
```cpp
    solve(UEqn == -fvc::grad(p));
```

## v2212 (openfoam.com)

### src/finiteVolume/fvMatrices/fvMatrix/fvMatrixSolve.C, lines 342-346
```cpp
template<class Type>
Foam::SolverPerformance<Type> Foam::fvMatrix<Type>::solve()
{
    return this->solve(solverDict());
}
```

### src/finiteVolume/fvMatrices/fvMatrix/fvMatrix.C, lines 1572-1583
```cpp
template<class Type>
const Foam::dictionary& Foam::fvMatrix<Type>::solverDict() const
{
    return psi_.mesh().solverDict
    (
        psi_.select
        (
            psi_.mesh().data::template getOrDefault<bool>
            ("finalIteration", false)
        )
    );
}
```

### src/OpenFOAM/fields/GeometricFields/GeometricField/GeometricField.C, lines 1127-1139
```cpp
template<class Type, template<class> class PatchField, class GeoMesh>
Foam::word Foam::GeometricField<Type, PatchField, GeoMesh>::select
(
    bool final
) const
{
    if (final)
    {
        return this->name() + "Final";
    }

    return this->name();
}
```

### src/finiteVolume/cfdTools/general/solutionControl/pimpleControl/pimpleControl.C, lines 200-265 (sets finalIteration)
```cpp
bool Foam::pimpleControl::loop()
{
    read();

    ++corr_;

    if (debug)
    {
        Info<< algorithmName_ << " loop: corr = " << corr_ << endl;
    }

    setFirstIterFlag();

    if (corr_ == nCorrPIMPLE_ + 1)
    {
        if (!residualControl_.empty() && (nCorrPIMPLE_ != 1))
        {
            Info<< algorithmName_ << ": not converged within "
                << nCorrPIMPLE_ << " iterations" << endl;
        }

        corr_ = 0;
        mesh_.data::remove("finalIteration");
        return false;
    }

    bool completed = false;
    if (converged_ || criteriaSatisfied())
    {
        if (converged_)
        {
            Info<< algorithmName_ << ": converged in " << corr_ - 1
                << " iterations" << endl;

            mesh_.data::remove("finalIteration");
            corr_ = 0;
            converged_ = false;

            completed = true;
        }
        else
        {
            Info<< algorithmName_ << ": iteration " << corr_ << endl;
            storePrevIterFields();

            mesh_.data::add("finalIteration", true);
            converged_ = true;
        }
    }
    else
    {
        if (finalIter())
        {
            mesh_.data::add("finalIteration", true);
        }

        if (corr_ <= nCorrPIMPLE_)
        {
            Info<< algorithmName_ << ": iteration " << corr_ << endl;
            storePrevIterFields();
            completed = false;
        }
    }

    return !completed;
}
```

### same file, lines 53-54 (default of finalOnLastPimpleIterOnly)
```cpp
    finalOnLastPimpleIterOnly_ =
        pimpleDict.getOrDefault("finalOnLastPimpleIterOnly", false);
```

### src/finiteVolume/cfdTools/general/solutionControl/pimpleControl/pimpleControlI.H, lines 92-112
```cpp
inline bool Foam::pimpleControl::finalIter() const
{
    return converged_ || (corr_ == nCorrPIMPLE_);
}


inline bool Foam::pimpleControl::finalInnerIter() const
{
    bool finalInnerIter =
        corrPISO_ == nCorrPISO_
     && corrNonOrtho_ == nNonOrthCorr_ + 1;

    if (finalOnLastPimpleIterOnly_)
    {
        return finalInnerIter && finalIter();
    }
    else
    {
        return finalInnerIter;
    }
}
```

### applications/solvers/incompressible/pimpleFoam/pEqn.H, lines 37-54
```cpp

// Non-orthogonal pressure corrector loop
while (pimple.correctNonOrthogonal())
{
    fvScalarMatrix pEqn
    (
        fvm::laplacian(rAtU(), p) == fvc::div(phiHbyA)
    );

    pEqn.setReference(pRefCell, pRefValue);

    pEqn.solve(mesh.solver(p.select(pimple.finalInnerIter())));

    if (pimple.finalNonOrthogonalIter())
    {
        phi = phiHbyA - pEqn.flux();
    }
}
```

### applications/solvers/incompressible/pimpleFoam/UEqn.H, line 21
```cpp
    solve(UEqn == -fvc::grad(p));
```

## OpenFOAM 8 (openfoam.org)

### src/finiteVolume/fvMatrices/fvMatrix/fvMatrixSolve.C, lines 330-347
```cpp
template<class Type>
Foam::SolverPerformance<Type> Foam::fvMatrix<Type>::solve()
{
    return solve
    (
        psi_.mesh().solverDict
        (
            psi_.select
            (
                psi_.mesh().data::template lookupOrDefault<bool>
                (
                    "finalIteration",
                    false
                )
            )
        )
    );
}
```

### src/OpenFOAM/fields/GeometricFields/GeometricField/GeometricField.C, lines 1218-1232
```cpp
template<class Type, template<class> class PatchField, class GeoMesh>
Foam::word Foam::GeometricField<Type, PatchField, GeoMesh>::select
(
    bool final
) const
{
    if (final)
    {
        return this->name() + "Final";
    }
    else
    {
        return this->name();
    }
}
```

### src/finiteVolume/cfdTools/general/solutionControl/solutionControl/singleRegionSolutionControl/singleRegionSolutionControl.C, lines 70-78 (the only place finalIteration is set)
```cpp
void Foam::singleRegionSolutionControl::updateFinal() const
{
    mesh_.data::remove("finalIteration");

    if (isFinal())
    {
        mesh_.data::add("finalIteration", true);
    }
}
```

### src/finiteVolume/cfdTools/general/solutionControl/pimpleControl/pimpleNoLoopControl/pimpleNoLoopControl.C, lines 95-100
```cpp
bool Foam::pimpleNoLoopControl::isFinal() const
{
    return
        (!anyPisoIter() && loop_.finalPimpleIter())
     || pisoControl::isFinal();
}
```

### src/finiteVolume/cfdTools/general/solutionControl/pisoControl/pisoControl.C, lines 71-98 (isFinal, correct)
```cpp
bool Foam::pisoControl::isFinal() const
{
    return
        (!anyNonOrthogonalIter() && finalPisoIter())
     || (finalNonOrthogonalIter() && finalPisoIter())
     || (finalNonOrthogonalIter() && !anyPisoIter());
}


bool Foam::pisoControl::correct()
{
    read();

    if (finalPisoIter())
    {
        corrPiso_ = 0;

        updateFinal();

        return false;
    }

    ++ corrPiso_;

    updateFinal();

    return true;
}
```

### src/finiteVolume/cfdTools/general/solutionControl/pisoControl/pisoControlI.H, lines 34-55
```cpp
inline bool Foam::pisoControl::anyPisoIter() const
{
    return corrPiso_ != 0;
}


inline bool Foam::pisoControl::firstPisoIter() const
{
    return corrPiso_ == 1;
}


inline bool Foam::pisoControl::finalPisoIter() const
{
    return corrPiso_ >= nCorrPiso_;
}


inline bool Foam::pisoControl::finalInnerIter() const
{
    return finalNonOrthogonalIter() && finalPisoIter();
}
```

### src/finiteVolume/cfdTools/general/solutionControl/solutionControl/nonOrthogonalSolutionControl/nonOrthogonalSolutionControl.C, lines 76-94
```cpp
bool Foam::nonOrthogonalSolutionControl::correctNonOrthogonal()
{
    read();

    if (finalNonOrthogonalIter())
    {
        corrNonOrth_ = 0;

        updateFinal();

        return false;
    }

    ++ corrNonOrth_;

    updateFinal();

    return true;
}
```

### src/finiteVolume/cfdTools/general/solutionControl/solutionControl/nonOrthogonalSolutionControl/nonOrthogonalSolutionControlI.H, lines 34-49
```cpp
inline bool Foam::nonOrthogonalSolutionControl::anyNonOrthogonalIter() const
{
    return corrNonOrth_ != 0;
}


inline bool Foam::nonOrthogonalSolutionControl::firstNonOrthogonalIter() const
{
    return corrNonOrth_ == 1;
}


inline bool Foam::nonOrthogonalSolutionControl::finalNonOrthogonalIter() const
{
    return corrNonOrth_ > nCorrNonOrth_;
}
```

### src/finiteVolume/cfdTools/general/solutionControl/pimpleControl/pimpleControl/pimpleControl.C, lines 81-97
```cpp
bool Foam::pimpleControl::loop()
{
    read();

    if (!pimpleLoop::loop(*this))
    {
        updateFinal();

        return false;
    }

    storePrevIterFields();

    updateFinal();

    return true;
}
```

### src/finiteVolume/cfdTools/general/solutionControl/pimpleControl/pimpleLoop/pimpleLoopI.H, lines 46-49
```cpp
inline bool Foam::pimpleLoop::finalPimpleIter() const
{
    return converged_ || corrPimple_ >= nCorrPimple_;
}
```

### applications/solvers/incompressible/pimpleFoam/pEqn.H, lines 38-53
```cpp
while (pimple.correctNonOrthogonal())
{
    fvScalarMatrix pEqn
    (
        fvm::laplacian(rAtU(), p) == fvc::div(phiHbyA)
    );

    pEqn.setReference(pRefCell, pRefValue);

    pEqn.solve();

    if (pimple.finalNonOrthogonalIter())
    {
        phi = phiHbyA - pEqn.flux();
    }
}
```

### applications/solvers/incompressible/pimpleFoam/UEqn.H, line 21
```cpp
    solve(UEqn == -fvc::grad(p));
```

### applications/solvers/incompressible/pimpleFoam/pimpleFoam.C, lines 90-125 (loop structure)
```cpp
        while (pimple.loop())
        {
            if (pimple.firstPimpleIter() || moveMeshOuterCorrectors)
            {
                mesh.update();

                if (mesh.changing())
                {
                    MRF.update();

                    if (correctPhi)
                    {
                        // Calculate absolute flux
                        // from the mapped surface velocity
                        phi = mesh.Sf() & Uf();

                        #include "correctPhi.H"

                        // Make the flux relative to the mesh motion
                        fvc::makeRelative(phi, U);
                    }

                    if (checkMeshCourantNo)
                    {
                        #include "meshCourantNo.H"
                    }
                }
            }

            #include "UEqn.H"

            // --- Pressure corrector loop
            while (pimple.correct())
            {
                #include "pEqn.H"
            }
```

