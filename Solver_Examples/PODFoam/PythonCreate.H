// Copyright (C) 2021 UChicago Argonne, LLC
// SPDX-License-Identifier: (other)
// Initialize the embedded interpreter and validate the bridge API.
// NumPy's machine-limit probes deliberately overflow during import. Keep
// OpenFOAM traps enabled for PDE work, but use Python's FP semantics here.
Foam::sigFpe::ignore pythonInitFpe;
Py_Initialize();
if (init_numpy() < 0)
{
    PyErr_Print();
    FatalErrorInFunction << "NumPy initialization failed" << exit(FatalError);
}

// Resolve python_module.py from the case even when invoked with -case; in a
// parallel run the case path is processorN/, so the undecomposed case
// directory (globalPath) is added as well.
for (const fileName& dir : {runTime.path(), runTime.globalPath()})
{
    PyObject* casePath = PyUnicode_FromString(dir.c_str());
    if (!casePath || PyList_Insert(PySys_GetObject("path"), 0, casePath) < 0)
    {
        PyErr_Print();
        FatalErrorInFunction << "Cannot add case to Python path" << exit(FatalError);
    }
    Py_DECREF(casePath);
}
PyObject* pModule = PyImport_ImportModule("python_module");
if (!pModule)
{
    PyErr_Print();
    FatalErrorInFunction << "Cannot import python_module" << exit(FatalError);
}
PyObject* snapshot_func = PyObject_GetAttrString(pModule, "snapshot_func");
PyObject* svd_func = PyObject_GetAttrString(pModule, "svd_func");
// Optional in-situ observer/logger. Existing snapshot/SVD-only modules still work.
PyObject* analysis_func = PyObject_GetAttrString(pModule, "analysis_func");
if (!analysis_func)
{
    if (!PyErr_ExceptionMatches(PyExc_AttributeError))
    {
        PyErr_Print();
    }
    PyErr_Clear();
}
else if (!PyCallable_Check(analysis_func))
{
    WarningInFunction << "Ignoring non-callable analysis_func" << endl;
    Py_CLEAR(analysis_func);
}
// In a parallel run the master rank gathers the whole mesh (here) and the
// whole U and p fields (PythonAnalysis.H) and is the only rank that calls
// mesh_func and analysis_func; every rank takes part in the gathers.
// Optional one-time geometry for Python-side rendering of the same-step
// fields (cell centres, volumes, solution directions). Owning copies only;
// Python never aliases mesh storage. Absence or failure only disables images.
if (analysis_func)
{
    PyObject* mesh_func = PyObject_GetAttrString(pModule, "mesh_func");
    if (!mesh_func)
    {
        PyErr_Clear();
    }
    else if (!PyCallable_Check(mesh_func))
    {
        WarningInFunction << "Ignoring non-callable mesh_func" << endl;
        Py_CLEAR(mesh_func);
    }
    if (mesh_func)
    {
        // 2D cases: every face of the first 'empty' patch outlines exactly one
        // cell, so Python can paint true cell polygons (no interpolation).
        // 3D cases (no empty patch): the polygons of a plane slice, one per
        // cut cell (PythonSlice.H), and an eighth argument that says where the
        // plane is; v2 pictures then show the slice cells, v1 keeps its raster.
        label emptyPatch = -1;
        forAll(mesh.boundaryMesh(), patchi)
        {
            if (isA<emptyPolyPatch>(mesh.boundaryMesh()[patchi]))
            {
                emptyPatch = patchi;
                break;
            }
        }
        // This rank's polygons: points, points per face, owner cells.
        pointField localPolyPoints;
        labelList localPolySizes, localPolyCells;
        if (emptyPatch >= 0)
        {
            const polyPatch& pp = mesh.boundaryMesh()[emptyPatch];
            const labelUList& faceCells = pp.faceCells();
            label nPts = 0;
            forAll(pp, facei) nPts += pp[facei].size();
            localPolyPoints.setSize(nPts);
            localPolySizes.setSize(pp.size());
            localPolyCells.setSize(pp.size());
            label k = 0;
            forAll(pp, facei)
            {
                const face& f = pp[facei];
                forAll(f, pointi) localPolyPoints[k++] = mesh.points()[f[pointi]];
                localPolySizes[facei] = f.size();
                localPolyCells[facei] = faceCells[facei];
            }
        }
        const bool sliced = (emptyPatch < 0);
        PythonPlaneSlice planeSlice;
        if (sliced)
        {
            planeSlice = pythonPlaneSlice(mesh, localPolyPoints, localPolySizes, localPolyCells);
            const label nCut = returnReduce(planeSlice.localCells, sumOp<label>());
            if (!planeSlice.ok)
            {
                WarningInFunction << "No plane slice for the observer: "
                    << planeSlice.error.c_str() << endl;
            }
            else
            {
                Info<< "POD observer plane slice: z=" << planeSlice.z
                    << " requested=" << planeSlice.requestedZ
                    << (planeSlice.fromEnvironment ? " (LLM_SLICE_Z)" : " (middle of the mesh z range)")
                    << (planeSlice.moved ? " moved off mesh points" : "")
                    << " mesh z range=(" << planeSlice.zMin << " " << planeSlice.zMax << ")"
                    << " cut cells=" << nCut << endl;
                if (nCut == 0)
                {
                    WarningInFunction << "The observer's plane slice z=" << planeSlice.z
                        << " cuts no cells; v2 pictures will be refused" << endl;
                }
            }
        }
        // Gathered to the master in rank order; cell labels shifted by where
        // each rank's cells start in that order (a no-op in a serial run).
        const labelList cellOffsets(pythonCellOffsets(mesh.nCells()));
        forAll(localPolyCells, i) localPolyCells[i] += cellOffsets[Pstream::myProcNo()];
        const List<vector> allCentres(pythonGatherToMaster(List<vector>(mesh.C().primitiveField())));
        const List<scalar> allVolumes(pythonGatherToMaster(List<scalar>(mesh.V().field())));
        const List<vector> allPolyPoints(pythonGatherToMaster(List<vector>(localPolyPoints)));
        const labelList allPolySizes(pythonGatherToMaster(localPolySizes));
        const labelList allPolyCells(pythonGatherToMaster(localPolyCells));
        if (Pstream::master())
        {
        const label nAllCells = allCentres.size();
        const label nPolyFaces = allPolySizes.size();
        const label nPolyPoints = allPolyPoints.size();
        npy_intp centreDims[] = {nAllCells, 3};
        npy_intp volumeDims[] = {nAllCells};
        PyObject* centres = PyArray_SimpleNew(2, centreDims, NPY_DOUBLE);
        PyObject* volumes = PyArray_SimpleNew(1, volumeDims, NPY_DOUBLE);
        PyObject* solutionD = Py_BuildValue
        (
            "(iii)",
            int(mesh.solutionD()[0]), int(mesh.solutionD()[1]), int(mesh.solutionD()[2])
        );
        npy_intp polyPointDims[] = {nPolyPoints, 3};
        npy_intp polyOffsetDims[] = {nPolyFaces + 1};
        npy_intp polyCellDims[] = {nPolyFaces};
        PyObject* polyPoints = PyArray_SimpleNew(2, polyPointDims, NPY_DOUBLE);
        PyObject* polyOffsets = PyArray_SimpleNew(1, polyOffsetDims, NPY_INT64);
        PyObject* polyCells = PyArray_SimpleNew(1, polyCellDims, NPY_INT64);
        if (polyPoints && polyOffsets && polyCells)
        {
            double* pts = static_cast<double*>
            (
                PyArray_DATA(reinterpret_cast<PyArrayObject*>(polyPoints))
            );
            npy_int64* off = static_cast<npy_int64*>
            (
                PyArray_DATA(reinterpret_cast<PyArrayObject*>(polyOffsets))
            );
            npy_int64* cells = static_cast<npy_int64*>
            (
                PyArray_DATA(reinterpret_cast<PyArrayObject*>(polyCells))
            );
            forAll(allPolyPoints, k)
            {
                pts[3*k] = allPolyPoints[k].x();
                pts[3*k + 1] = allPolyPoints[k].y();
                pts[3*k + 2] = allPolyPoints[k].z();
            }
            off[0] = 0;
            forAll(allPolySizes, facei)
            {
                off[facei + 1] = off[facei] + allPolySizes[facei];
                cells[facei] = allPolyCells[facei];
            }
        }
        // 3D: where the slice is, for the frame records (Python checks the
        // polygons against it); z_m is None when no cut was made.
        PyObject* slicePlane = nullptr;
        if (sliced)
        {
            slicePlane = planeSlice.ok
                ? Py_BuildValue
                (
                    "{s:(ddd),s:d,s:d,s:s,s:O,s:(dd)}",
                    "normal", 0.0, 0.0, 1.0,
                    "z_m", double(planeSlice.z),
                    "requested_z_m", double(planeSlice.requestedZ),
                    "z_source", planeSlice.fromEnvironment
                        ? "LLM_SLICE_Z" : "middle of the mesh z range",
                    "moved_off_mesh_points", planeSlice.moved ? Py_True : Py_False,
                    "mesh_z_range_m", double(planeSlice.zMin), double(planeSlice.zMax)
                )
                : Py_BuildValue
                (
                    "{s:(ddd),s:O,s:s,s:s,s:(dd)}",
                    "normal", 0.0, 0.0, 1.0,
                    "z_m", Py_None,
                    "z_source", "LLM_SLICE_Z",
                    "error", planeSlice.error.c_str(),
                    "mesh_z_range_m", double(planeSlice.zMin), double(planeSlice.zMax)
                );
        }
        PyObject* meshResult = nullptr;
        if (centres && volumes && solutionD && polyPoints && polyOffsets && polyCells
         && (!sliced || slicePlane))
        {
            double* c = static_cast<double*>
            (
                PyArray_DATA(reinterpret_cast<PyArrayObject*>(centres))
            );
            double* v = static_cast<double*>
            (
                PyArray_DATA(reinterpret_cast<PyArrayObject*>(volumes))
            );
            forAll(allCentres, celli)
            {
                for (direction cmpt = 0; cmpt < 3; ++cmpt)
                {
                    c[3*celli + cmpt] = allCentres[celli][cmpt];
                }
                v[celli] = allVolumes[celli];
            }
            meshResult = sliced
                ? PyObject_CallFunction
                (
                    mesh_func, "OOOiOOOO", centres, volumes, solutionD, Pstream::myProcNo(),
                    polyPoints, polyOffsets, polyCells, slicePlane
                )
                : PyObject_CallFunction
                (
                    mesh_func, "OOOiOOO", centres, volumes, solutionD, Pstream::myProcNo(),
                    polyPoints, polyOffsets, polyCells
                );
        }
        Py_XDECREF(centres);
        Py_XDECREF(volumes);
        Py_XDECREF(solutionD);
        Py_XDECREF(polyPoints);
        Py_XDECREF(polyOffsets);
        Py_XDECREF(polyCells);
        Py_XDECREF(slicePlane);
        if (!meshResult)
        {
            PyObject *errorType = nullptr, *errorValue = nullptr, *errorTrace = nullptr;
            PyErr_Fetch(&errorType, &errorValue, &errorTrace);
            PyErr_NormalizeException(&errorType, &errorValue, &errorTrace);
            if (errorType) PyErr_Display(errorType, errorValue, errorTrace);
            Py_XDECREF(errorType);
            Py_XDECREF(errorValue);
            Py_XDECREF(errorTrace);
            PyErr_Clear();
            WarningInFunction << "mesh_func failed; Python image input unavailable"
                << endl;
        }
        else
        {
            Info<< "POD mesh geometry passed to Python: cells=" << nAllCells
                << " solutionD=" << mesh.solutionD()
                << " cellPolygons=" << nPolyFaces
                << " ranks=" << Pstream::nProcs();
            if (sliced && planeSlice.ok)
            {
                Info<< " slice z=" << planeSlice.z;
            }
            else if (sliced)
            {
                Info<< " slice none";
            }
            Info<< endl;
        }
        Py_XDECREF(meshResult);
        }   // master
        Py_DECREF(mesh_func);
    }
}
Py_DECREF(pModule);
if (!snapshot_func || !svd_func
 || !PyCallable_Check(snapshot_func) || !PyCallable_Check(svd_func))
{
    PyErr_Print();
    FatalErrorInFunction << "snapshot_func and svd_func must be callable"
        << exit(FatalError);
}
const int rank = Pstream::myProcNo();
const label num_cells = mesh.nCells();
const label truncation = 5;
// Zero retains the original write-time SVD scheduling.
const label podSvdInterval =
    runTime.controlDict().lookupOrDefault<label>("podSvdInterval", 0);
if (podSvdInterval < 0)
{
    FatalErrorInFunction << "podSvdInterval must be non-negative"
        << exit(FatalError);
}
label podSnapshotCount = 0;
std::feclearexcept(FE_ALL_EXCEPT);
pythonInitFpe.restore();
Info<< "Python and NumPy initialized successfully" << endl;
