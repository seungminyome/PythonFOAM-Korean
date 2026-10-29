#!/usr/bin/env python3
"""Make the 3D step case of 2026-10-28 from the 2D step case.

  make_case3d.py dict   <case2d> <case3d> [--nz 8]
      system/blockMeshDict of case3d: the 2D case's blocks with nz cells in z
      (0 to 0.0127 m, as in the 2D mesh) and walls front and back.
  make_case3d.py fields <case2d> <case3d> [--nz 8] [--time 0.1]
      after blockMesh: <time>/U and <time>/p of case3d, each cell taking the
      value of the 2D cell it was extruded from (Uz = 0), boundary conditions
      as the 2D case's with no-slip walls front and back; the cell map goes to
      case3d/map-3d-to-2d.npy.
  make_case3d.py check  <case2d-with-C> <case3d-with-C> <output.json> [--time 0.1]
      after postProcess -func writeCellCentres in both: checks the map
      (same x and y centre, nz cells per 2D cell, one z per layer).

blockMesh numbers the cells block by block, x fastest, then y, then z, so
3D cell start3[b] + i + nx*(j + ny*k) comes from 2D cell start2[b] + i + nx*j;
the check confirms this with the cell centres OpenFOAM computes.
Needs numpy and llm_demo/foam_fields.py (found through the repository).
"""
import argparse
import json
from pathlib import Path
import re
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "Solver_Examples/PODFoam/llm_demo"))
import foam_fields  # noqa: E402

U_BOUNDARY = """boundaryField
{
    inlet
    {
        type            fixedValue;
        value           uniform (32.2 0 0);
    }
    outlet
    {
        type            zeroGradient;
    }
    "(lowerWallStartup|upperWallStartup)"
    {
        type            symmetryPlane;
    }
    "(upperWall|lowerWall|front|back)"
    {
        type            noSlip;
    }
}
"""
P_BOUNDARY = """boundaryField
{
    inlet
    {
        type            zeroGradient;
    }
    outlet
    {
        type            fixedValue;
        value           uniform 0;
    }
    "(lowerWallStartup|upperWallStartup)"
    {
        type            symmetryPlane;
    }
    "(upperWall|lowerWall|front|back)"
    {
        type            zeroGradient;
    }
}
"""
HEADER = """FoamFile
{{
    version     2.0;
    format      ascii;
    class       {cls};
    location    "{time}";
    object      {name};
}}
// made by make_case3d.py from the 2D case at t = {time} s

dimensions      {dimensions};

internalField   nonuniform List<{kind}>
{count}
(
"""
HEX = re.compile(r"(hex\s*\([\d\s]+\)\s*\(\s*\d+\s+\d+\s+)1(\s*\))")


def without_block_comments(text):
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def blocks(case2d):
    """[(nx, ny)] of the 2D case's blocks, in order."""
    text = without_block_comments((Path(case2d) / "system/blockMeshDict").read_text())
    text = re.sub(r"//[^\n]*", "", text)
    found = [(int(nx), int(ny), int(nz)) for nx, ny, nz in
             re.findall(r"hex\s*\([\d\s]+\)\s*\(\s*(\d+)\s+(\d+)\s+(\d+)\s*\)", text)]
    if not found or any(nz != 1 for _, _, nz in found):
        raise ValueError("expected 2D blocks with one cell in z")
    return [(nx, ny) for nx, ny, _ in found]


def cell_map(case2d, nz):
    """2D cell of every 3D cell, in 3D cell order."""
    parts, start2 = [], 0
    for nx, ny in blocks(case2d):
        layer = start2 + np.arange(nx * ny)
        parts.append(np.tile(layer, nz))
        start2 += nx * ny
    return np.concatenate(parts).astype(np.int64)


def make_dict(case2d, case3d, nz):
    text = without_block_comments((Path(case2d) / "system/blockMeshDict").read_text())
    text, hexes = HEX.subn(lambda m: f"{m.group(1)}{nz}{m.group(2)}", text)
    text, walls = re.subn(r"(\n\s*(?:front|back)\s*\{\s*type\s+)empty;", r"\1wall;", text)
    if hexes != len(blocks(case2d)) or walls != 2:
        raise ValueError(f"changed {hexes} blocks and {walls} patches")
    header = (f"// 3D step case of 2026-10-28: the 2D case's blockMeshDict with {nz} cells in z\n"
              "// and walls front and back (make_case3d.py)\n")
    target = Path(case3d) / "system/blockMeshDict"
    target.write_text(header + text)
    print(f"{target}: {hexes} blocks with {nz} cells in z, front and back walls")


def number(value):
    return repr(float(value)) if value != 0 else "0"


def write_field(path, name, cls, kind, dimensions, values, time, boundary):
    lines = ([f"({number(x)} {number(y)} 0)" for x, y in values[:, :2]] if kind == "vector"
             else [number(v) for v in values])
    path.write_text(HEADER.format(cls=cls, time=time, name=name, dimensions=dimensions, kind=kind,
                                  count=len(lines))
                    + "\n".join(lines) + "\n)\n;\n\n" + boundary)


def make_fields(case2d, case3d, nz, time):
    case2d, case3d = Path(case2d), Path(case3d)
    cells2 = foam_fields.read_labels(case2d / "constant/polyMesh/owner").max() + 1
    mapping = cell_map(case2d, nz)
    owner3 = foam_fields.read_labels(case3d / "constant/polyMesh/owner")
    if owner3.max() + 1 != mapping.size or mapping.max() + 1 != cells2:
        raise ValueError(f"3D mesh has {owner3.max() + 1} cells, map {mapping.size}; 2D {cells2}")
    u2 = foam_fields.read_internal_field(case2d / time / "U", cells2)
    p2 = foam_fields.read_internal_field(case2d / time / "p", cells2)
    out = case3d / time
    out.mkdir(parents=True, exist_ok=True)
    write_field(out / "U", "U", "volVectorField", "vector", "[0 1 -1 0 0 0 0]", u2[mapping], time, U_BOUNDARY)
    write_field(out / "p", "p", "volScalarField", "scalar", "[0 2 -2 0 0 0 0]", p2[mapping], time, P_BOUNDARY)
    np.save(case3d / "map-3d-to-2d.npy", mapping)
    print(f"{out}: U and p for {mapping.size} cells from {cells2} 2D cells ({nz} per 2D cell)")


def check(case2d, case3d, output, time):
    case2d, case3d = Path(case2d), Path(case3d)
    mapping = np.load(case3d / "map-3d-to-2d.npy")
    c2 = foam_fields.read_internal_field(case2d / time / "C", int(mapping.max()) + 1)
    c3 = foam_fields.read_internal_field(case3d / time / "C", mapping.size)
    counts = np.bincount(mapping)
    layers = np.unique(c3[:, 2])
    report = {
        "cells_2d": int(c2.shape[0]), "cells_3d": int(c3.shape[0]),
        "3d_cells_per_2d_cell": sorted({int(n) for n in counts}),
        "max_abs_xy_difference_m": float(np.abs(c3[:, :2] - c2[mapping, :2]).max()),
        "layer_centres_z_m": [float(z) for z in layers],
        "z_range_of_centres_m": [float(c3[:, 2].min()), float(c3[:, 2].max())],
    }
    # C is written with 12 significant digits (writePrecision 12): x up to 1.65 m in size gives
    # differences up to about 1e-11 m between two rounded centres; the tolerance must stay far
    # below the distance between neighbouring 2D cell centres
    from scipy.spatial import cKDTree
    report["min_distance_between_2d_centres_m"] = float(cKDTree(c2[:, :2]).query(c2[:, :2], k=2)[0][:, 1].min())
    report["xy_tolerance_m"] = 1e-9
    report["map_ok"] = (report["3d_cells_per_2d_cell"] == [mapping.size // c2.shape[0]]
                        and report["max_abs_xy_difference_m"] < report["xy_tolerance_m"]
                        < report["min_distance_between_2d_centres_m"] / 100)
    Path(output).write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))
    if not report["map_ok"]:
        raise SystemExit("cell map check failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["dict", "fields", "check"])
    parser.add_argument("case2d")
    parser.add_argument("case3d")
    parser.add_argument("output", nargs="?")
    parser.add_argument("--nz", type=int, default=8)
    parser.add_argument("--time", default="0.1")
    args = parser.parse_args()
    if args.action == "dict":
        make_dict(args.case2d, args.case3d, args.nz)
    elif args.action == "fields":
        make_fields(args.case2d, args.case3d, args.nz, args.time)
    else:
        check(args.case2d, args.case3d, args.output, args.time)


if __name__ == "__main__":
    main()
