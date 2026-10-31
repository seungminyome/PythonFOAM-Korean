// What the Python hooks need that differs between openfoam.com (OPENFOAM
// defined) and openfoam.org.
#ifndef PythonCompat_H
#define PythonCompat_H

#include <cfenv>
#ifndef OPENFOAM
    #include "Residuals.H"
#endif

// Floating-point traps off inside a scope, as around the calls into Python
// (NumPy's machine-limit probes overflow on purpose); restore() or the end of
// the scope turns them back on.
#ifdef OPENFOAM
typedef Foam::sigFpe::ignore PythonFpeOff;
#else
class PythonFpeOff
{
    int saved_;

public:
    PythonFpeOff()
    :
        saved_(fedisableexcept(FE_ALL_EXCEPT))
    {}

    PythonFpeOff(const PythonFpeOff&) = delete;
    PythonFpeOff& operator=(const PythonFpeOff&) = delete;

    ~PythonFpeOff()
    {
        restore();
    }

    void restore()
    {
        if (saved_ != -1)
        {
            feclearexcept(FE_ALL_EXCEPT);
            feenableexcept(saved_);
            saved_ = -1;
        }
    }
};
#endif

// This time step's linear solves of one field; false if it has none, with two
// limits on openfoam.org. Residuals<Type> clears its lists at the next solve of
// that type, so a field not solved this step still gives an earlier step's list:
// PythonAnalysis.H checks the momentum predictor for U, but other ways to stop a
// field's solves during a run (maxIter 0) are not caught. A mesh motion deletes
// Residuals<Type>, so with moveMeshOuterCorrectors only the last outer corrector's
// solves are listed.
template<class Type>
bool pythonSolverPerformance
(
    const Foam::fvMesh& mesh,
    const Foam::word& name,
    Foam::List<Foam::SolverPerformance<Type>>& solves
)
{
    #ifdef OPENFOAM
    const Foam::dictionary& perf = mesh.solverPerformanceDict();
    if (!perf.found(name))
    {
        return false;
    }
    solves = Foam::List<Foam::SolverPerformance<Type>>(perf.lookup(name));
    #else
    if (!Foam::Residuals<Type>::found(mesh, name))
    {
        return false;
    }
    solves = Foam::Residuals<Type>::field(mesh, name);
    #endif
    return true;
}

#endif
