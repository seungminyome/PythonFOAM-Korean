// Copyright (C) 2021 UChicago Argonne, LLC
// Copyright (C) 2026 Seungmin Yome
// SPDX-License-Identifier: (other)
//
// Python-OpenFOAM integration
//
// Each step hands a snapshot of U to snapshot_func, or, at a write step with
// snapshots collected, asks svd_func for the modes and writes them as fields.
// The snapshot is an array that NumPy owns and fills from U, so a view the
// module keeps cannot alias the next step's values. The floating-point traps
// are off while Python runs and come back at the end of the block.
{
    PythonFpeOff pythonCallFpe;
    if (mesh.nCells() != num_cells)
    {
        FatalErrorInFunction << "POD requires a fixed cell count: started with "
            << num_cells << " cells, now " << mesh.nCells() << exit(FatalError);
    }
    // podSvdInterval 0: a write step runs the SVD if snapshots have been
    // collected since the last SVD, and collects a snapshot otherwise; with
    // analysis_func, every step collects a snapshot and a write step also runs
    // the SVD. Above 0, every step collects a snapshot and the SVD runs every
    // podSvdInterval snapshots.
    const bool writeStepSvd = !podSvdInterval && runTime.outputTime();
    const bool collectSnapshot = analysis_func || !writeStepSvd || !podSnapshotsSinceSvd;
    if (collectSnapshot)
    {
        clock_gettime(CLOCK_MONOTONIC, &tw1); // POSIX
        npy_intp dims[] = {num_cells, 3};
        PyObject* snapshot = PyArray_SimpleNew(2, dims, NPY_DOUBLE);
        if (!snapshot)
        {
            printPythonError();
            FatalErrorInFunction << "Cannot allocate snapshot" << exit(FatalError);
        }
        double* data = static_cast<double*>
        (
            PyArray_DATA(reinterpret_cast<PyArrayObject*>(snapshot))
        );
        forAll(U, celli)
        {
            for (direction cmpt = 0; cmpt < 3; ++cmpt)
            {
                const double value = U[celli][cmpt];
                if (!std::isfinite(value) || !std::isfinite(p[celli]))
                {
                    FatalErrorInFunction << "Non-finite U/p at cell " << celli
                        << " time " << runTime.timeName() << exit(FatalError);
                }
                data[3*celli + cmpt] = value;
            }
        }
        clock_gettime(CLOCK_MONOTONIC, &tw2); // POSIX
        posix_wall = 1000.0*tw2.tv_sec + 1e-6*tw2.tv_nsec - (1000.0*tw1.tv_sec + 1e-6*tw1.tv_nsec);
        printf("Numpy array cast time: %.2f ms\n", posix_wall);

        clock_gettime(CLOCK_MONOTONIC, &tw1); // POSIX
        PyObject* snapshotResult = PyObject_CallFunction(snapshot_func, "Oi", snapshot, rank);
        Py_DECREF(snapshot);
        if (!snapshotResult)
        {
            printPythonError();
            FatalErrorInFunction << "Python snapshot_func failed" << exit(FatalError);
        }
        Py_DECREF(snapshotResult);
        clock_gettime(CLOCK_MONOTONIC, &tw2); // POSIX
        posix_wall = 1000.0*tw2.tv_sec + 1e-6*tw2.tv_nsec - (1000.0*tw1.tv_sec + 1e-6*tw1.tv_nsec);
        printf("Snapshot collection wall time: %.2f ms\n", posix_wall);
        ++podSnapshotCount;
        ++podSnapshotsSinceSvd;
        Info<< "POD snapshot accepted: " << podSnapshotCount
            << " time=" << runTime.timeName() << " cells=" << num_cells << endl;
    }

    const bool computeSvd = podSvdInterval
        ? (podSnapshotCount % podSvdInterval == 0)
        : writeStepSvd && (analysis_func || !collectSnapshot);
    if (computeSvd)
    {
        podSnapshotsSinceSvd = 0;
        clock_gettime(CLOCK_MONOTONIC, &tw1); // POSIX
        PyObject* result = PyObject_CallFunction(svd_func, "i", rank);
        if (!result)
        {
            printPythonError();
            FatalErrorInFunction << "Python svd_func failed" << exit(FatalError);
        }
        clock_gettime(CLOCK_MONOTONIC, &tw2); // POSIX
        posix_wall = 1000.0*tw2.tv_sec + 1e-6*tw2.tv_nsec - (1000.0*tw1.tv_sec + 1e-6*tw1.tv_nsec);
        printf("SVD Computation wall time: %.2f ms\n", posix_wall);

        clock_gettime(CLOCK_MONOTONIC, &tw1); // POSIX
        // A float64 ndarray only, instead of converting lists or lower precision.
        if (!PyArray_Check(result)
         || PyArray_TYPE(reinterpret_cast<PyArrayObject*>(result)) != NPY_DOUBLE
         || !PyArray_ISNOTSWAPPED(reinterpret_cast<PyArrayObject*>(result)))
        {
            Py_DECREF(result);
            FatalErrorInFunction << "SVD result must be a native float64 ndarray"
                << exit(FatalError);
        }
        PyArrayObject* modes = reinterpret_cast<PyArrayObject*>
        (
            PyArray_FROM_OTF(result, NPY_DOUBLE, NPY_ARRAY_IN_ARRAY)
        );
        Py_DECREF(result);
        if (!modes)
        {
            printPythonError();
            FatalErrorInFunction << "SVD result must be a real numeric array"
                << exit(FatalError);
        }
        // A rank without cells has no modes to give and takes the others' count.
        if (PyArray_NDIM(modes) != 2 || PyArray_DIM(modes, 0) != 3*num_cells
         || (num_cells && PyArray_DIM(modes, 1) < 1))
        {
            FatalErrorInFunction << "Expected SVD shape (" << 3*num_cells
                << ", 1 or more modes), got (";
            for (int d = 0; d < PyArray_NDIM(modes); ++d)
            {
                FatalError << (d ? ", " : "") << label(PyArray_DIM(modes, d));
            }
            FatalError << ")" << exit(FatalError);
        }
        // The first podTruncation columns are written; more columns give one
        // warning in the run.
        const label returnedModes = num_cells ? label(PyArray_DIM(modes, 1)) : 0;
        const label mostReturned = returnReduce(returnedModes, maxOp<label>());
        if (mostReturned > truncation && !podTruncationWarned)
        {
            podTruncationWarned = true;
            WarningInFunction << "svd_func returned " << mostReturned
                << " modes; the first " << truncation << " (podTruncation) are written"
                << endl;
        }
        // The boundary update of each mode exchanges data between the ranks, so
        // they must all write the same number of modes.
        const label localModes = min(returnedModes, truncation);
        const label nModes = returnReduce(localModes, maxOp<label>());
        const label fewestModes = returnReduce(num_cells ? localModes : nModes, minOp<label>());
        if (fewestModes != nModes)
        {
            FatalErrorInFunction << "The ranks returned different numbers of POD modes: from "
                << fewestModes << " to " << nModes << exit(FatalError);
        }
        const double* values = static_cast<const double*>(PyArray_DATA(modes));
        const npy_intp columns = PyArray_DIM(modes, 1);
        for (npy_intp row = 0; row < 3*num_cells; ++row)
        {
            for (label mode = 0; mode < nModes; ++mode)
            {
                if (!std::isfinite(values[row*columns + mode]))
                {
                    FatalErrorInFunction << "Non-finite SVD result" << exit(FatalError);
                }
            }
        }
        // One dimensionless zeroGradient field per mode and component.
        const char* prefixes[] = {"upod_", "vpod_", "wpod_"};
        for (label mode = 0; mode < nModes; ++mode)
        {
            for (direction cmpt = 0; cmpt < 3; ++cmpt)
            {
                volScalarField podField
                (
                    IOobject
                    (
                        word(prefixes[cmpt]) + Foam::name(mode),
                        runTime.timeName(), mesh,
                        IOobject::NO_READ, IOobject::NO_WRITE, false
                    ),
                    mesh, dimensionedScalar("zero", dimless, 0),
                    "zeroGradient"
                );
                forAll(podField, celli)
                {
                    podField[celli] = values[(cmpt*num_cells + celli)*columns + mode];
                }
                podField.correctBoundaryConditions();
                if (!podField.write())
                {
                    FatalErrorInFunction << "Cannot write POD field" << exit(FatalError);
                }
            }
        }
        Py_DECREF(modes);
        clock_gettime(CLOCK_MONOTONIC, &tw2); // POSIX
        posix_wall = 1000.0*tw2.tv_sec + 1e-6*tw2.tv_nsec - (1000.0*tw1.tv_sec + 1e-6*tw1.tv_nsec);
        printf("Data copy back to OF wall time: %.2f ms\n", posix_wall);
        Info<< "POD SVD returned to OpenFOAM: rows=" << 3*num_cells
            << " modes=" << nModes << " finite=true time="
            << runTime.timeName() << endl;
    }
    // The hook's return value is not used.
    #include "PythonAnalysis.H"
    std::feclearexcept(FE_ALL_EXCEPT);
}
