// Optional PythonFOAM in-situ observer/logger after the completed PDE step.
// Model responses are recorded in Python; they never control the solver.
// Residuals come from this timestep's OpenFOAM solverPerformance, not log parsing.
if (analysis_func && rank == 0)
{
    const dictionary& perf = mesh.solverPerformanceDict();
    PyObject* residuals = PyDict_New();
    if (residuals && perf.found("U"))
    {
        const List<SolverPerformance<vector>> solves(perf.lookup("U"));
        const char* names[] = {"Ux", "Uy", "Uz"};
        for (direction cmpt = 0; cmpt < 3 && solves.size(); ++cmpt)
        {
            // Empty 2D directions have no equation solve to report.
            if (mesh.solutionD()[cmpt] == -1) continue;
            label iterations = 0;
            forAll(solves, i) iterations += solves[i].nIterations()[cmpt];
            PyObject* summary = Py_BuildValue
            (
                "{s:d,s:d,s:d,s:i,s:i}",
                "initial_first", double(solves.first().initialResidual()[cmpt]),
                "initial_last", double(solves.last().initialResidual()[cmpt]),
                "final_last", double(solves.last().finalResidual()[cmpt]),
                "linear_solves", int(solves.size()),
                "iterations_total", int(iterations)
            );
            if (summary)
            {
                PyDict_SetItemString(residuals, names[cmpt], summary);
                Py_DECREF(summary);
            }
        }
    }
    if (residuals && perf.found("p"))
    {
        const List<SolverPerformance<scalar>> solves(perf.lookup("p"));
        if (solves.size())
        {
            label iterations = 0;
            forAll(solves, i) iterations += solves[i].nIterations();
            PyObject* summary = Py_BuildValue
            (
                "{s:d,s:d,s:d,s:i,s:i}",
                "initial_first", double(solves.first().initialResidual()),
                "initial_last", double(solves.last().initialResidual()),
                "final_last", double(solves.last().finalResidual()),
                "linear_solves", int(solves.size()),
                "iterations_total", int(iterations)
            );
            if (summary)
            {
                PyDict_SetItemString(residuals, "p", summary);
                Py_DECREF(summary);
            }
        }
    }
    PyObject* state = residuals ? Py_BuildValue
    (
        "{s:i,s:d,s:d,s:d,s:i,s:i,s:O}",
        "schema_version", 1,
        "time_s", double(runTime.value()),
        "delta_t_s", double(runTime.deltaTValue()),
        "end_time_s", double(runTime.endTime().value()),
        "step", int(podSnapshotCount),
        "cells", int(num_cells),
        "residuals", residuals
    ) : nullptr;
    Py_XDECREF(residuals);
    // Same-step kinematic pressure for Python-side rendering. U of this step
    // was already copied by snapshot_func above; both are post-step values and
    // PythonComm.H verified them finite. Owning copy; never a view of p.
    if (state)
    {
        npy_intp pDims[] = {num_cells};
        PyObject* pCells = PyArray_SimpleNew(1, pDims, NPY_DOUBLE);
        if (pCells)
        {
            double* pData = static_cast<double*>
            (
                PyArray_DATA(reinterpret_cast<PyArrayObject*>(pCells))
            );
            forAll(p, celli) pData[celli] = p[celli];
            PyDict_SetItemString(state, "p_cells", pCells);
            Py_DECREF(pCells);
        }
        else
        {
            PyErr_Clear();
        }
    }
    // Recompute diagnostics from the completed step's phi. This Courant value
    // is post-step, unlike the pre-step Courant printed by the time controller.
    const scalarField sumPhi(fvc::surfaceSum(mag(phi))().primitiveField());
    const double postCoMax = 0.5*gMax(sumPhi/mesh.V().field())*runTime.deltaTValue();
    const double postCoMean = 0.5*gSum(sumPhi)/gSum(mesh.V().field())*runTime.deltaTValue();
    const volScalarField contErr(fvc::div(phi));
    const double localCont = runTime.deltaTValue()*mag(contErr)().weightedAverage(mesh.V()).value();
    const double globalCont = runTime.deltaTValue()*contErr.weightedAverage(mesh.V()).value();
    PyObject* courant = Py_BuildValue
    (
        "{s:d,s:d,s:s}", "mean", postCoMean, "max", postCoMax,
        "phase", "post_step_phi"
    );
    PyObject* continuity = Py_BuildValue
    (
        "{s:d,s:d,s:d,s:s}", "local", localCont, "global", globalCont,
        "cumulative", double(cumulativeContErr), "phase", "last_pressure_correction"
    );
    if (state && courant && continuity)
    {
        PyDict_SetItemString(state, "courant", courant);
        PyDict_SetItemString(state, "continuity", continuity);
    }
    Py_XDECREF(courant);
    Py_XDECREF(continuity);
    const auto callbackStart = std::chrono::steady_clock::now();
    PyObject* response = state && !PyErr_Occurred()
        ? PyObject_CallFunctionObjArgs(analysis_func, state, nullptr) : nullptr;
    const double callbackSeconds = std::chrono::duration<double>
    (
        std::chrono::steady_clock::now() - callbackStart
    ).count();
    Info<< "POD analysis callback returned: step=" << podSnapshotCount
        << " wall_seconds=" << callbackSeconds << endl;
    Py_XDECREF(state);
    if (!response)
    {
        // Not PyErr_Print: that would exit the process on SystemExit.
        PyObject *errorType = nullptr, *errorValue = nullptr, *errorTrace = nullptr;
        PyErr_Fetch(&errorType, &errorValue, &errorTrace);
        PyErr_NormalizeException(&errorType, &errorValue, &errorTrace);
        if (errorType) PyErr_Display(errorType, errorValue, errorTrace);
        Py_XDECREF(errorType);
        Py_XDECREF(errorValue);
        Py_XDECREF(errorTrace);
        PyErr_Clear();
        WarningInFunction << "analysis_func raised; continuing without it"
            << endl;
    }
    // Ignore the callback's return value: no model-driven field/settings update.
    Py_XDECREF(response);
}
