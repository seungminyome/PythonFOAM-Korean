#!/usr/bin/env python3
"""Where the largest |U| of each state of the 2026-10-28 instability test set is.

For every state the set uses (test-set/manifest.json, extra.flow_states; the SHA-256 of each U
file is checked against it) and for the developed flow at t = 0.1 s (the start state of the six
reruns), this reads U from the run folders and writes:
- the largest |U| over the whole domain, its cell, the cell centre, and whether that cell is
  inside the plotted window;
- the largest |U| inside the window (it must equal the key's max_speed_m_per_s);
- |U| in the owner cells of the symmetry-plane faces at the start of each wall
  (lowerWallStartup, upperWallStartup), where the no-slip walls begin.
It also writes the extent of each patch, so the place of those cells can be read, and a
summary by run: how many states have their largest |U| outside the window, in which cells,
at which steps and how large, and the range of |U| in those startup cells.

Usage (numpy and the repository's llm_demo/foam_fields.py; reads about 160 U files):
  python3 domain_max.py [--root /cluster/medbow/gscratch/syome/github_repos] [--output domain-max.json]
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
sys.path.insert(0, str(REPO / "Solver_Examples" / "PODFoam" / "llm_demo"))
import foam_fields  # noqa: E402

START_STATE = ("developed", "flow-states-20261022/long-100ms/0.1")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def patch_geometry(polymesh, centres):
    """Extent of each patch (face points) and the owner cells of the symmetry-plane faces."""
    points = foam_fields.read_points(polymesh / "points")
    sizes, labels = foam_fields.read_faces(polymesh / "faces")
    owner = foam_fields.read_labels(polymesh / "owner")
    starts = np.concatenate([[0], np.cumsum(sizes)])
    patches, startup = [], []
    for patch in foam_fields.read_boundary(polymesh / "boundary"):
        if patch["type"] == "empty":
            continue
        faces = range(patch["startFace"], patch["startFace"] + patch["nFaces"])
        corners = np.concatenate([points[labels[starts[f]:starts[f + 1]]] for f in faces])
        patches.append({"name": patch["name"], "type": patch["type"], "faces": patch["nFaces"],
                        "x_m": [float(corners[:, 0].min()), float(corners[:, 0].max())],
                        "y_m": [float(corners[:, 1].min()), float(corners[:, 1].max())]})
        if patch["type"] == "symmetryPlane":
            for f in faces:
                face = points[labels[starts[f]:starts[f + 1]]]
                cell = int(owner[f])
                startup.append({"patch": patch["name"], "cell": cell,
                                "face_x_m": [float(face[:, 0].min()), float(face[:, 0].max())],
                                "cell_centre_m": [float(centres[cell, 0]), float(centres[cell, 1])]})
    return patches, startup


def state_record(run, time_dir, centres, inside, startup_cells):
    speed = np.linalg.norm(foam_fields.read_internal_field(time_dir / "U", centres.shape[0]), axis=1)
    cell = int(np.argmax(speed))
    return {"run": run, "time_dir": time_dir.name, "time_s": float(time_dir.name),
            "max_speed_domain_m_per_s": float(speed[cell]), "max_cell": cell,
            "max_cell_centre_m": [float(centres[cell, 0]), float(centres[cell, 1])],
            "max_inside_window": bool(inside[cell]), "max_speed_window_m_per_s": float(speed[inside].max()),
            "speed_in_startup_cells_m_per_s": {str(c): float(speed[c]) for c in startup_cells}}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default="/cluster/medbow/gscratch/syome/github_repos",
                        help="folder the manifest's time_dir paths start from")
    parser.add_argument("--output", default=str(HERE / "domain-max.json"))
    args = parser.parse_args()
    root = Path(args.root)
    manifest = json.loads((EVIDENCE / "test-set" / "manifest.json").read_text())
    truth = json.loads((EVIDENCE / "test-set" / "truth.private.json").read_text())
    centres_path = REPO / manifest["mesh"]["centres_npz"]
    if sha256(centres_path) != manifest["mesh"]["centres_npz_sha256"]:
        raise SystemExit(f"{centres_path}: not the centres the set was built with")
    centres = np.load(centres_path)["centres"]
    polymesh = root / manifest["runs"][0]["case"] / "constant" / "polyMesh"
    for name, digest in manifest["mesh"]["polymesh"].items():
        if sha256(polymesh / name) != digest:
            raise SystemExit(f"{polymesh / name}: not the mesh the set was built with")
    (x0, x1), (y0, y1) = manifest["plotted_range_m"]["x"], manifest["plotted_range_m"]["y"]
    inside = (centres[:, 0] >= x0) & (centres[:, 0] <= x1) & (centres[:, 1] >= y0) & (centres[:, 1] <= y1)
    patches, startup = patch_geometry(polymesh, centres)
    startup_cells = [s["cell"] for s in startup]
    frames = {(key["run"], f["time_s"]): f for key in truth.values() for f in key["frames"]}
    states, key_differs = [], []
    for name, entry in manifest["extra"]["flow_states"].items():
        run = name.split("/", 1)[0]
        time_dir = root / entry["time_dir"]
        if sha256(time_dir / "U") != entry["U_sha256"]:
            raise SystemExit(f"{time_dir / 'U'}: not the file the set was built from")
        record = state_record(run, time_dir, centres, inside, startup_cells)
        frame = frames[(run, record["time_s"])]
        record["run_step"], record["steps_to_crash"] = frame["run_step"], frame["steps_to_crash"]
        if record["max_speed_window_m_per_s"] != frame["max_speed_m_per_s"]:
            key_differs.append(name)
        states.append(record)
    states.sort(key=lambda s: (s["run"], s["time_s"]))
    start = state_record(START_STATE[0], root / START_STATE[1], centres, inside, startup_cells)
    start["U_sha256"] = sha256(root / START_STATE[1] / "U")
    by_run = {}
    for run in dict.fromkeys(s["run"] for s in states):
        mine = [s for s in states if s["run"] == run]
        outside = [s for s in mine if not s["max_inside_window"]]
        in_startup = [s for s in outside if s["max_cell"] in startup_cells]
        before = [s for s in mine if s["steps_to_crash"] is None or s["steps_to_crash"] >= 2]
        startup_speeds = [v for s in before for v in s["speed_in_startup_cells_m_per_s"].values()]
        by_run[run] = {
            "states": len(mine),
            "max_outside_window": len(outside),
            "max_outside_window_in_startup_cells": len(in_startup),
            "cells_holding_the_max_outside_window": dict(Counter(str(s["max_cell"]) for s in outside)),
            "outside_run_steps": [min(s["run_step"] for s in outside), max(s["run_step"] for s in outside)] if outside else None,
            "outside_max_speed_m_per_s": [min(s["max_speed_domain_m_per_s"] for s in outside),
                                          max(s["max_speed_domain_m_per_s"] for s in outside)] if outside else None,
            "speed_in_startup_cells_m_per_s": [min(startup_speeds), max(startup_speeds)],
            "speed_in_startup_cells_over": "every state of a run that ended; for a run that crashed, "
                                           "the states 2 or more steps before the crash",
            "largest_in_startup_cells": max(({"m_per_s": s["max_speed_domain_m_per_s"], "time_s": s["time_s"],
                                              "run_step": s["run_step"]} for s in in_startup),
                                            key=lambda d: d["m_per_s"], default=None)}
    out = {"note": "Largest |U| over the domain and inside the plotted window of every state the test set "
                   "uses, and |U| in the owner cells of the symmetry-plane faces where the walls start "
                   "(flow/domain_max.py). x and y in metres; run_step is the run's own step.",
           "window_m": {"x": [x0, x1], "y": [y0, y1]}, "cells": int(centres.shape[0]),
           "patches": patches, "startup_cells": startup,
           "window_max_differs_from_key": key_differs,
           "start_state": dict(start, path=START_STATE[1]), "by_run": by_run, "states": states}
    Path(args.output).write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({"states": len(states), "window_max_differs_from_key": len(key_differs),
                      "by_run": {r: [v["states"], v["max_outside_window"], v["max_outside_window_in_startup_cells"]]
                                 for r, v in by_run.items()}}))
    return 1 if key_differs else 0


if __name__ == "__main__":
    raise SystemExit(main())
