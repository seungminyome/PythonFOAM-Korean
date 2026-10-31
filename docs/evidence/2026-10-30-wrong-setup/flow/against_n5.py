#!/usr/bin/env python3
"""How far each run's frames lie from N5's at the same step, inside the window: the mean absolute
difference of |U| and of p over the cells. All wrong runs start from N5's start state.

Usage: against_n5.py <test set> <output.json>   (numpy; reads frames/<run>/<time>/fields.npz)
"""
import json
from pathlib import Path
import sys

import numpy as np

RUNS = ("N1", "N2", "N3", "N4", "M1-inlet-speed", "M2-viscosity", "M3-slip-walls", "M4-moving-wall", "M5-half-inlet")
STEPS = range(4500, 8001, 500)


def load(root, run, step):
    with np.load(Path(root) / "frames" / run / f"{0.1 + step * 5e-6:.10g}" / "fields.npz", allow_pickle=False) as data:
        centres, velocity, pressure = data["centres"], data["U"], data["p"]
    inside = (centres[:, 0] >= 0) & (centres[:, 0] <= 0.12) & (centres[:, 1] >= 0) & (centres[:, 1] <= 0.04)
    return np.linalg.norm(velocity, axis=1)[inside], pressure[inside]


def main(root, output):
    out = {}
    for run in RUNS:
        rows = {}
        for step in STEPS:
            a, b = load(root, run, step), load(root, "N5", step)
            rows[str(step)] = {"mean_abs_diff_speed_m_per_s": float(np.abs(a[0] - b[0]).mean()),
                               "mean_abs_diff_p_m2_per_s2": float(np.abs(a[1] - b[1]).mean())}
        out[run] = {"by_step": rows,
                    "mean_abs_diff_speed_range": [min(r["mean_abs_diff_speed_m_per_s"] for r in rows.values()),
                                                  max(r["mean_abs_diff_speed_m_per_s"] for r in rows.values())],
                    "mean_abs_diff_p_range": [min(r["mean_abs_diff_p_m2_per_s2"] for r in rows.values()),
                                              max(r["mean_abs_diff_p_m2_per_s2"] for r in rows.values())]}
    Path(output).write_text(json.dumps(out, indent=1) + "\n")
    for run, row in out.items():
        print(run, [round(v, 3) for v in row["mean_abs_diff_speed_range"]], [round(v, 2) for v in row["mean_abs_diff_p_range"]])


if __name__ == "__main__":
    main(*sys.argv[1:3])
