#!/usr/bin/env python3
"""How large are the POD mode differences of the 2026-10-27 POD-difference job (Slurm 24903065)?

Usage: mode_differences.py RUN_DIR   (the job's run-24903065 folder, in the release archive)
For every POD mode file (upod_*, vpod_*, wpod_*) of every written time of each run, compares the
internal field with run A (one BLAS thread, alone) and reports the largest absolute difference,
the largest mode value, and whether a sign flip of the whole mode explains it. Writes JSON to stdout.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np


def field(path):
    text = path.read_text()
    m = re.search(r"internalField\s+nonuniform\s+List<scalar>\s*\n?(\d+)\s*\(", text)
    n = int(m.group(1))
    body = text[m.end():].split(")", 1)[0]
    values = np.array(body.split(), dtype=float)
    assert len(values) == n, path
    return values


def main(run):
    run = Path(run)
    ref = run / "A-alone-1thread"
    out = {}
    for case in sorted(p for p in run.iterdir() if p.is_dir() and p != ref):
        worst = {"max_abs_difference": 0.0, "where": None, "files": 0, "differ": 0, "sign_flips": 0}
        for f in sorted(case.glob("0.1*/[uvw]pod_*")):
            a, b = field(ref / f.parent.name / f.name), field(f)
            worst["files"] += 1
            d = float(np.abs(a - b).max())
            if d > 0:
                worst["differ"] += 1
            if np.abs(a + b).max() < d:
                worst["sign_flips"] += 1
            if d > worst["max_abs_difference"]:
                worst.update(max_abs_difference=d, where=f"{f.parent.name}/{f.name}",
                             max_abs_value_there=float(np.abs(a).max()))
        out[case.name] = worst
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
