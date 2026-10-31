// Plane slice of a 3D mesh for mesh_func, which gets each cell as its own
// polygon; a 2D case takes the polygons from its empty patch (PythonCreate.H).
// A 3D case has no empty patch: there the cells
// cut by the plane z = POD_SLICE_Z (default: the middle of the mesh's global z
// range), normal (0 0 1), give the polygons, cut by OpenFOAM's cuttingPlane
// without triangulation, so each cut cell gives one polygon (its section).
// A plane through mesh points lies on the faces between two cells (the middle
// of an even number of uniform layers does); it is then moved halfway to the
// next point plane above (below if there is none above), so that every
// polygon is the section of one cell.
// Collective: every rank calls pythonPlaneSlice with its own cells; the
// master's POD_SLICE_Z is used on every rank.
#ifndef PythonSlice_H
#define PythonSlice_H

#include "cuttingPlane.H"
#include "boundBox.H"
#include "OSspecific.H"
#include <cmath>
#include <string>

struct PythonPlaneSlice
{
    bool ok = false;                    // false: no cut made, see error
    Foam::scalar z = 0;                 // the plane cut
    Foam::scalar requestedZ = 0;        // POD_SLICE_Z, or the middle of the z range
    Foam::scalar zMin = 0, zMax = 0;    // global z range of the mesh points
    bool fromEnvironment = false;       // POD_SLICE_Z was set
    bool moved = false;                 // the requested plane went through mesh points
    Foam::label localCells = 0;         // cut cells of this rank
    std::string error;                  // set on the master only
};

// Fills this rank's polygons (the points of each polygon in order, the
// number of points of each polygon, the local cell of each polygon).
inline PythonPlaneSlice pythonPlaneSlice
(
    const Foam::polyMesh& mesh,
    Foam::pointField& polyPoints,
    Foam::labelList& polySizes,
    Foam::labelList& polyCells
)
{
    using namespace Foam;
    PythonPlaneSlice slice;
    const boundBox bounds(mesh.points(), true);     // reduced over all ranks
    slice.zMin = bounds.min().z();
    slice.zMax = bounds.max().z();
    slice.requestedZ = 0.5*(slice.zMin + slice.zMax);
    label source = 0;   // 0: middle of the z range, 1: POD_SLICE_Z, -1: unreadable POD_SLICE_Z
    if (Pstream::master())
    {
        const std::string text(Foam::getEnv("POD_SLICE_Z"));
        if (!text.empty())
        {
            scalar value = 0;
            if (readScalar(text.c_str(), value) && std::isfinite(value))
            {
                source = 1;
                slice.requestedZ = value;
            }
            else
            {
                source = -1;
                slice.error = "POD_SLICE_Z is not a finite number: '" + text + "'";
            }
        }
    }
    Pstream::scatter(source);
    Pstream::scatter(slice.requestedZ);
    slice.fromEnvironment = (source != 0);
    if (source < 0)
    {
        return slice;
    }
    slice.z = slice.requestedZ;

    // Points closer than tol to the plane count as on it.
    const scalar tol = 1e-9*(slice.zMax - slice.zMin);
    const scalarField pointZ(mesh.points().component(vector::Z));
    scalar nearest = GREAT;
    forAll(pointZ, pointi)
    {
        nearest = min(nearest, mag(pointZ[pointi] - slice.z));
    }
    reduce(nearest, minOp<scalar>());
    if (nearest <= tol)
    {
        scalar above = GREAT;
        scalar below = -GREAT;
        forAll(pointZ, pointi)
        {
            if (pointZ[pointi] > slice.z + tol) above = min(above, pointZ[pointi]);
            if (pointZ[pointi] < slice.z - tol) below = max(below, pointZ[pointi]);
        }
        reduce(above, minOp<scalar>());
        reduce(below, maxOp<scalar>());
        slice.z = 0.5*(slice.z + (above < GREAT ? above : below));
        slice.moved = true;
    }

    const cuttingPlane cut(plane(point(0, 0, slice.z), vector(0, 0, 1)), mesh, false);
    const pointField& cutPoints = cut.points();
    #ifdef OPENFOAM
    const faceList& cutFaces = cut.surfFaces();
    const labelList& cutCells = cut.meshCells();
    #else
    const faceList& cutFaces = cut.faces();
    const labelList& cutCells = cut.cutCells();
    #endif
    label nPts = 0;
    forAll(cutFaces, facei) nPts += cutFaces[facei].size();
    polyPoints.setSize(nPts);
    polySizes.setSize(cutFaces.size());
    polyCells.setSize(cutFaces.size());
    label k = 0;
    forAll(cutFaces, facei)
    {
        const face& f = cutFaces[facei];
        forAll(f, pointi) polyPoints[k++] = cutPoints[f[pointi]];
        polySizes[facei] = f.size();
        polyCells[facei] = cutCells[facei];
    }
    slice.localCells = cutFaces.size();
    slice.ok = true;
    return slice;
}

#endif
