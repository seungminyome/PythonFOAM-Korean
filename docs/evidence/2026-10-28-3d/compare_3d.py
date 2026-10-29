#!/usr/bin/env python3
"""Checks of the 2026-10-28 slice test (slice_test.sbatch); writes <OUT>/frame-comparison.json.

  compare_3d.py <OUT> <reference 2D frame folder>

- the serial and the 2-rank slice frames at step 100: the same cells (by mesh cell label,
  through decomposePar's cellProcAddressing, and sorted by centre), U and p differences;
- each frame against the fields the solver wrote at that step (t = 0.1005 s);
- the written fields of the serial run with the observer against the run without it;
- the frame tools on a slice frame: hash check (load_frame), answer key (picture_test),
  the request body against the builder applied to the frame;
- the run with LLM_SLICE_Z=0.002, the refused runs (LLM_SLICE_Z=abc, LLM_SLICE_Z=1.0);
- the 2D frame of the new build against the 2D frame of 2026-10-27 (job 24903786), file by file;
- the slice against the 2D frame at the same step (cells matched through the extrusion map).
"""
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "Solver_Examples/PODFoam/llm_demo"))
import foam_fields  # noqa: E402
import llm_client  # noqa: E402
import picture_test  # noqa: E402
import readable_request  # noqa: E402

FRAME_TIME = "0.1005"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frame(case, step):
    return readable_request.load_frame(Path(case) / "llm_observation" / f"step-{step:06d}")


def sort_by_centre(centres):
    return np.lexsort((np.round(centres[:, 1], 10), np.round(centres[:, 0], 10)))


def written(case, cells):
    u = foam_fields.read_internal_field(Path(case) / FRAME_TIME / "U", cells)
    p = foam_fields.read_internal_field(Path(case) / FRAME_TIME / "p", cells)
    return u, p


def against_written(arrays, u, p, rows):
    du = np.abs(arrays["U"] - u[rows])
    dp = np.abs(arrays["p"] - p[rows])
    return {"time": FRAME_TIME, "cells": int(len(rows)),
            "max_abs_diff_U": float(du.max()), "max_abs_diff_p": float(dp.max()),
            "max_rel_diff_U": float((du / np.maximum(np.abs(u[rows]), 1e-300)).max()),
            "max_rel_diff_p": float((dp / np.maximum(np.abs(p[rows]), 1e-300)).max()),
            "equal_within_rtol_1e-11": bool(np.allclose(arrays["U"], u[rows], rtol=1e-11, atol=0)
                                             and np.allclose(arrays["p"], p[rows], rtol=1e-11, atol=0)),
            "note": "the written fields have 12 significant digits (writePrecision 12)"}


def tree(folder):
    return {str(p.relative_to(folder)): sha256(p) for p in sorted(Path(folder).rglob("*")) if p.is_file()}


def run_info(case):
    log = (Path(case) / "log.PODFoam").read_text(errors="replace")
    result = Path(case) / "llm_result.json"

    def summary(values):
        return ({"lines": len(values), "sum": float(sum(values)), "median": float(np.median(values)),
                 "max": float(max(values))} if values else None)

    info = {"end": bool(re.search(r"^End$", log, re.M)),
            "python_finalized": "Python finalized successfully" in log,
            "steps": len(re.findall(r"^POD snapshot accepted", log, re.M)),
            # printed by every rank (printf); the callback line by the master only
            "pde_compute_wall_ms": summary([float(v) for v in re.findall(r"PDE Compute wall time: (\S+) ms", log)]),
            "callback_wall_s": summary([float(v) for v in re.findall(
                r"POD analysis callback returned: step=\d+ wall_seconds=(\S+)", log)]),
            "solver_lines": [line for line in log.splitlines() if re.search(
                r"POD observer plane slice|No plane slice|POD mesh geometry|PYTHON LLM mesh|PYTHON LLM step=|"
                r"PYTHON LLM callback failed", line)]}
    if result.exists():
        record = json.loads(result.read_text())
        info["llm_result"] = {k: record.get(k) for k in ("status", "error", "step", "arrived_at_step",
                                                           "image_input", "solver_stall_s")}
    return info


def main(out, reference_2d):
    out = Path(out)
    report = {"run_folder": str(out)}
    _, meta_s, s = frame(out / "serial3d", 100)
    _, meta_p, q = frame(out / "par3d", 100)
    cells3 = int(meta_s["slice"]["mesh_cells_total"])
    report["slice_serial"] = {"frame_cells": meta_s["cells"], "slice": meta_s["slice"],
                              "z_of_slice_cell_centres_m": [float(s["centres"][:, 2].min()),
                                                            float(s["centres"][:, 2].max())],
                              "plotted_range_m": meta_s["plotted_range_m"],
                              "domain_extent_m": meta_s["domain_extent_m"],
                              "images": {i["field"]: {k: i[k] for k in ("sha256", "bytes", "colour_range")}
                                         for i in meta_s["images"]}}
    report["slice_par2"] = {"frame_cells": meta_p["cells"], "slice": meta_p["slice"]}

    # serial against 2 ranks: cells by label through cellProcAddressing, then sorted by centre
    per_rank = [foam_fields.read_labels(out / "par3d" / f"processor{r}/constant/polyMesh/cellProcAddressing")
                for r in (0, 1)]
    addressing = np.concatenate(per_rank)            # gathered (rank-order) cell -> serial cell
    par_cells = addressing[q["mesh_cells"]]          # serial labels of the 2-rank slice cells
    position = {int(c): k for k, c in enumerate(s["mesh_cells"])}
    same = sorted(position) == sorted(int(c) for c in par_cells)
    by_label = {"same_cells": same}
    if same:
        rows = np.array([position[int(c)] for c in par_cells])

        def polygon(arrays, k):
            points = arrays["polygon_points"][arrays["polygon_offsets"][k]:arrays["polygon_offsets"][k + 1]]
            return points[np.lexsort((points[:, 1], points[:, 0]))]   # vertex order may differ

        gaps = [np.abs(polygon(s, r) - polygon(q, k)).max() if len(polygon(s, r)) == len(polygon(q, k))
                else np.inf for k, r in enumerate(rows)]
        by_label.update(max_abs_diff_centres_m=float(np.abs(s["centres"][rows] - q["centres"]).max()),
                        max_abs_diff_U=float(np.abs(s["U"][rows] - q["U"]).max()),
                        max_abs_diff_p=float(np.abs(s["p"][rows] - q["p"]).max()),
                        max_abs_diff_polygon_vertices_m=float(max(gaps)),
                        identical_U_cells=int((s["U"][rows] == q["U"]).all(axis=1).sum()))
    os_, op = sort_by_centre(s["centres"]), sort_by_centre(q["centres"])
    report["serial_vs_par2"] = {
        "cells": [int(len(s["centres"])), int(len(q["centres"]))],
        "by_mesh_cell_label": by_label,
        "sorted_by_centre": {"max_abs_diff_centres_m": float(np.abs(s["centres"][os_] - q["centres"][op]).max()),
                             "max_abs_diff_U": float(np.abs(s["U"][os_] - q["U"][op]).max()),
                             "max_abs_diff_p": float(np.abs(s["p"][os_] - q["p"][op]).max())},
        "max_abs_U": float(np.abs(s["U"]).max()), "max_abs_p": float(np.abs(s["p"]).max()),
        "par2_slice_cells_per_rank": [int((q["mesh_cells"] < len(per_rank[0])).sum()),
                                      int((q["mesh_cells"] >= len(per_rank[0])).sum())],
        "par2_mesh_cells_per_rank": [int(len(a)) for a in per_rank]}

    # each frame against the fields written at its step
    u, p = written(out / "serial3d", cells3)
    report["frame_vs_written_fields"] = {"serial": against_written(s, u, p, s["mesh_cells"])}
    u, p = written(out / "par3d", cells3)
    report["frame_vs_written_fields"]["par2_reconstructed"] = against_written(q, u, p, par_cells)

    # the observer does not change what the solver writes
    times = sorted(d.name for d in (out / "noobs3d").iterdir() if re.fullmatch(r"0\.\d+", d.name) and d.name != "0.1")
    with_obs = {t: tree(out / "serial3d" / t) for t in times}
    without = {t: tree(out / "noobs3d" / t) for t in times}
    files = [(t, name) for t in times for name in sorted(set(with_obs[t]) | set(without[t]))]
    differing = [f"{t}/{name}" for t, name in files if with_obs[t].get(name) != without[t].get(name)]
    report["observer_vs_no_observer"] = {
        "times": times, "files": len(files), "identical": len(files) - len(differing), "differing": differing,
        "same_time_directories": sorted(d.name for d in (out / "serial3d").iterdir()
                                        if re.fullmatch(r"0\.\d+", d.name)) == ["0.1"] + times}

    # downstream tools on a slice frame
    frame_s, truth = picture_test.load_v2(out / "serial3d/llm_observation/step-000100")
    body = (out / "serial3d/llm_request_body.json").read_bytes()
    rebuilt = llm_client.encode_json(readable_request.describe_v2_payload(frame_s))
    report["frame_tools"] = {
        "load_frame_hashes_checked": True,
        "request_body_equals_builder_applied_to_frame": body == rebuilt,
        "request_note": json.loads(json.loads(body)["messages"][1]["content"][0]["text"]),
        "answer_key": {k: truth[k] for k in ("cells_in_window", "max_speed_m_per_s", "min_pressure_m2_per_s2",
                                             "fastest_flow", "lowest_pressure")}}
    _, meta_z, z = frame(out / "slicez3d", 5)
    report["slice_at_LLM_SLICE_Z_0.002"] = {"frame_cells": meta_z["cells"], "slice": meta_z["slice"],
                                            "z_of_slice_cell_centres_m": [float(z["centres"][:, 2].min()),
                                                                          float(z["centres"][:, 2].max())]}

    # the 2D frame of this build against the 2D frame of 2026-10-27
    new2d = out / "serial2d/llm_observation/step-000100"
    names = sorted(p.name for p in Path(reference_2d).iterdir())
    report["frame_2d_vs_2026_10_27"] = {
        "reference": str(reference_2d),
        "files": {n: {"sha256_new": sha256(new2d / n), "sha256_reference": sha256(Path(reference_2d) / n)}
                  for n in names},
        "new_files": sorted(p.name for p in new2d.iterdir())}
    report["frame_2d_vs_2026_10_27"]["all_identical"] = (
        report["frame_2d_vs_2026_10_27"]["new_files"] == names
        and all(v["sha256_new"] == v["sha256_reference"] for v in report["frame_2d_vs_2026_10_27"]["files"].values()))
    ref_body = Path(reference_2d).parents[1] / "llm_request_body.json"
    report["frame_2d_vs_2026_10_27"]["request_body_identical"] = (
        sha256(out / "serial2d/llm_request_body.json") == sha256(ref_body))

    # the slice against the 2D flow at the same step (3D cell -> the 2D cell it was extruded from)
    mapping = np.load(out / "case3d/map-3d-to-2d.npy")
    _, _, flat = frame(out / "serial2d", 100)
    two = mapping[s["mesh_cells"]]
    report["slice_vs_2d_frame"] = {
        "slice_cells": int(len(two)), "distinct_2d_cells": int(np.unique(two).size),
        "cells_2d": int(len(flat["centres"])),
        "max_abs_diff_xy_centres_m": float(np.abs(s["centres"][:, :2] - flat["centres"][two, :2]).max()),
        "max_abs_diff_Ux_Uy": float(np.abs(s["U"][:, :2] - flat["U"][two, :2]).max()),
        "max_abs_Uz_slice": float(np.abs(s["U"][:, 2]).max()),
        "max_abs_diff_p": float(np.abs(s["p"] - flat["p"][two]).max()),
        "max_speed_slice_2d": [float(np.linalg.norm(s["U"], axis=1).max()), float(np.linalg.norm(flat["U"], axis=1).max())],
        "p_range_slice": [float(s["p"].min()), float(s["p"].max())],
        "p_range_2d": [float(flat["p"].min()), float(flat["p"].max())],
        "note": "the 3D case has walls front and back, so the slice is not expected to equal the 2D flow"}

    report["runs"] = {name: run_info(out / name) for name in
                      ("serial3d", "par3d", "noobs3d", "slicez3d", "badz3d", "outz3d", "serial2d")}
    (out / "frame-comparison.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: report[k] for k in ("serial_vs_par2", "frame_vs_written_fields", "observer_vs_no_observer")},
                     indent=1))
    print("2D frame identical to 2026-10-27:", report["frame_2d_vs_2026_10_27"]["all_identical"],
          "request body identical:", report["frame_2d_vs_2026_10_27"]["request_body_identical"])
    print("request body equals builder:", report["frame_tools"]["request_body_equals_builder_applied_to_frame"])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
